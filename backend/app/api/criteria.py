from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID
from app.core.security import get_current_user
from app.core.permissions import check_position_access, can_update_application_status
from app.core.logging import get_logger
from app.core.exceptions import CriteriaNotApprovedError, NotFoundError
from app.core.config import settings
from app.schemas.criteria import (
    CriteriaItemWeightsUpdate,
    CriteriaVersion,
    CriteriaVersionCreate,
    CriteriaWeightsUpdate,
    Criterion,
    CriterionCreate,
    CriterionUpdate,
    ApprovalAction,
    CriteriaApprovalRequest
)
from app.schemas.common import OperationResponse
from app.db.supabase import get_supabase_client
from app.db.database import SessionLocal
from sqlalchemy import text
import json
from decimal import Decimal, ROUND_HALF_UP
from app.services.llm_client import llm_client, LLMError
from app.services.criteria_fairness import fairness_warnings
from app.schemas.rubric import ApplyTemplateRequest
from app.services.deterministic_matching import deterministic_matcher

router = APIRouter()
logger = get_logger(__name__)


def _load_criteria(db, version_id):
    row = db.execute(text("SELECT * FROM app_private.criteria_versions WHERE criteria_version_id = :id"), {"id": str(version_id)}).mappings().first()
    if not row:
        raise NotFoundError("Criteria version")
    result = dict(row)
    result["criteria"] = [dict(item) for item in db.execute(text("""
        SELECT * FROM app_private.criteria_items WHERE criteria_version_id = :id ORDER BY display_order, criterion_id
    """), {"id": str(version_id)}).mappings().all()]
    result["fairness_warnings"] = fairness_warnings(result["criteria"])
    return result


def _require_fair_criteria(db, criteria_version_id: str) -> None:
    """F1.02: criteria must not rely on age, gender, appearance, marital status,
    personality or culture fit. Checked at every step that moves a version
    towards APPROVED, including the direct path (Admin, HR Lead or assigned HR)."""
    items = db.execute(text("""
        SELECT criterion_id, name, description, evidence_guidance, expected_evidence_keywords
        FROM app_private.criteria_items WHERE criteria_version_id = :id
    """), {"id": criteria_version_id}).mappings().all()
    flagged = fairness_warnings([dict(item) for item in items])
    if flagged:
        names = ", ".join(str(w["name"]) for w in flagged[:5])
        raise HTTPException(status_code=400, detail=(
            "Tiêu chí có dấu hiệu dựa trên thông tin cá nhân không liên quan đến công việc "
            f"(tuổi, giới tính, ngoại hình, hôn nhân, tính cách, văn hóa...): {names}. "
            "Vui lòng sửa hoặc xóa trước khi duyệt."))


def _stored_requirement_spec(item: dict) -> dict:
    """Materialize the engine's inferred draft in the stored JSONB shape."""
    spec = deterministic_matcher.build_requirement_spec(item)
    return {
        "kind": spec.kind,
        "terms": [term.label for term in spec.terms],
        "min_years": spec.min_years,
        "required_degree_level": spec.required_degree_level,
        "required_languages": list(spec.required_languages),
        "required_ielts": spec.required_ielts,
        "required_toeic": spec.required_toeic,
        "required_cefr": spec.required_cefr,
        "required_language_rank": spec.required_language_rank,
    }


def _normalize_weights_in_group(items: list[dict]) -> list[dict]:
    """Scale AI/manual draft weights so every present category sums to 100.

    LLM output has historically mixed two meanings: share of the whole rubric
    and share inside a category. The database field is explicitly the latter,
    so generation normalizes it before storage. A zero criterion stays zero;
    the rounding remainder is assigned to the largest criterion in its group.
    """
    normalized = [dict(item) for item in items]
    categories = {str(item.get("category")) for item in normalized}
    for category in categories:
        group = [item for item in normalized if str(item.get("category")) == category]
        total = sum(Decimal(str(item.get("weight") if "weight" in item else item.get("weight_in_group") or 0)) for item in group)
        if total <= 0:
            continue
        scaled: list[Decimal] = []
        for item in group:
            raw = Decimal(str(item.get("weight") if "weight" in item else item.get("weight_in_group") or 0))
            value = (raw * Decimal("100") / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            item["weight"] = float(value)
            if "weight_in_group" in item:
                item["weight_in_group"] = float(value)
            scaled.append(value)
        remainder = Decimal("100.00") - sum(scaled)
        if remainder:
            largest = max(group, key=lambda item: Decimal(str(item.get("weight") if "weight" in item else item.get("weight_in_group") or 0)))
            adjusted = (Decimal(str(largest.get("weight") if "weight" in largest else largest.get("weight_in_group") or 0)) + remainder).quantize(Decimal("0.01"))
            largest["weight"] = float(adjusted)
            if "weight_in_group" in largest:
                largest["weight_in_group"] = float(adjusted)
    return normalized


def _item_weight_totals(db, criteria_version_id: str) -> dict[str, Decimal]:
    rows = db.execute(text("""
        SELECT category, COALESCE(SUM(weight_in_group), 0) AS total, COUNT(*) AS item_count
        FROM app_private.criteria_items WHERE criteria_version_id = :id GROUP BY category
    """), {"id": str(criteria_version_id)}).mappings().all()
    return {str(row["category"]): Decimal(str(row["total"])) for row in rows if int(row["item_count"]) > 0}


def _validate_item_weight_totals(db, criteria_version_id: str) -> None:
    totals = _item_weight_totals(db, criteria_version_id)
    if "MUST_HAVE" not in totals:
        raise HTTPException(status_code=400, detail="Cần có ít nhất một tiêu chí bắt buộc trước khi duyệt.")
    invalid = [category for category, total in totals.items() if total != Decimal("100.00")]
    if invalid:
        labels = {"MUST_HAVE": "Bắt buộc", "NICE_TO_HAVE": "Ưu tiên"}
        details = ", ".join(f"{labels.get(category, category)}={totals[category]}%" for category in invalid)
        raise HTTPException(
            status_code=400,
            detail=f"Tổng trọng số trong mỗi nhóm tiêu chí phải bằng 100%. Hiện tại: {details}.",
        )


def _lock_editable_criteria_version(db, criteria_version_id: UUID, user_id: str):
    version = db.execute(text("""
        SELECT position_id, status FROM app_private.criteria_versions
        WHERE criteria_version_id = :id FOR UPDATE
    """), {"id": str(criteria_version_id)}).mappings().first()
    if not version:
        raise NotFoundError("Criteria version")
    if not can_update_application_status(user_id, str(version["position_id"])):
        raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới có thể sửa tiêu chí")
    if version["status"] not in ("DRAFT", "PENDING_HR_REVIEW"):
        raise HTTPException(status_code=400, detail="Chỉ có thể sửa tiêu chí ở trạng thái bản nháp")
    return version


def _materialize_requirement_specs(db, criteria_version_id: str) -> int:
    """Store inferred specs for legacy criteria before HR approval."""
    rows = db.execute(text("""
        SELECT criterion_id, name, description, category, expected_evidence_keywords, requirement_spec
        FROM app_private.criteria_items WHERE criteria_version_id = :id
    """), {"id": criteria_version_id}).mappings().all()
    materialized = 0
    for row in rows:
        item = dict(row)
        if item.get("requirement_spec"):
            continue
        db.execute(text("""
            UPDATE app_private.criteria_items
            SET requirement_spec = CAST(:spec AS jsonb)
            WHERE criterion_id = :criterion_id
        """), {"spec": json.dumps(_stored_requirement_spec(item)),
               "criterion_id": str(item["criterion_id"])})
        materialized += 1
    return materialized


@router.get("/position/{position_id}/versions", response_model=List[CriteriaVersion])
async def list_criteria_versions(position_id: UUID, current_user: dict = Depends(get_current_user)):
    await check_position_access(position_id, current_user)
    db = SessionLocal()
    try:
        ids = db.execute(text("SELECT criteria_version_id FROM app_private.criteria_versions WHERE position_id = :id ORDER BY version_number DESC"), {"id": str(position_id)}).scalars().all()
        return [_load_criteria(db, item) for item in ids]
    finally:
        db.close()


@router.get("/{criteria_version_id}", response_model=CriteriaVersion)
async def get_criteria_version(criteria_version_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        result = _load_criteria(db, criteria_version_id)
        await check_position_access(result["position_id"], current_user)
        return result
    finally:
        db.close()


@router.post("/generate/{position_id}", response_model=CriteriaVersion, status_code=status.HTTP_202_ACCEPTED)
async def generate_criteria_from_jd(position_id: UUID, current_user: dict = Depends(get_current_user)):
    """Generate a draft only; HR and HM still have to approve it."""
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER"])
    db = SessionLocal()
    try:
        position = db.execute(text("SELECT position_code, title FROM app_private.positions WHERE position_id = :id"), {"id": str(position_id)}).mappings().first()
        if not position:
            raise NotFoundError("Position")
        jd = db.execute(text("""
            SELECT jd_version_id, content_text FROM app_private.jd_versions WHERE position_id = :id
            ORDER BY version_number DESC LIMIT 1
        """), {"id": str(position_id)}).mappings().first()
        if not jd:
            raise HTTPException(status_code=400, detail="Vị trí chưa có mô tả công việc")
        position, jd = dict(position), dict(jd)
    finally:
        db.close()
    try:
        draft = await llm_client.extract_criteria_from_jd(
            jd_text=jd["content_text"],
            requisition_id=position["position_code"],
            job_title=position["title"],
            position_id=str(position_id),
        )
    except LLMError as exc:
        logger.error("Criteria generation failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail="Không thể tạo tiêu chí bằng AI. Vui lòng kiểm tra cấu hình và thử lại.")
    try:
        raw = draft["criteria"]
        if not isinstance(raw, list) or not raw or len(raw) > 100:
            raise ValueError("Empty or oversized rubric")
        items = []
        for criterion in raw:
            name, description = criterion["name"].strip(), criterion["description"].strip()
            category, weight = criterion["category"], float(criterion["weight"])
            keywords = criterion.get("expected_evidence_keywords", [])
            if not name or len(name) > 200 or not description or len(description) > 4000 or category not in ("MUST_HAVE", "NICE_TO_HAVE") or not 0 <= weight <= 100 or not isinstance(keywords, list):
                raise ValueError("Invalid criterion")
            draft_item = {"name": name, "description": description, "category": category,
                          "weight": weight, "keywords": keywords}
            for key in ("jd_reference_text", "evidence_guidance"):
                value = criterion.get(key)
                draft_item[key] = (value.strip()[:4000] or None) if isinstance(value, str) else None
            draft_item["requirement_spec"] = _stored_requirement_spec({
                "name": name, "description": description, "category": category,
                "expected_evidence_keywords": keywords,
            })
            items.append(draft_item)
        if not any(c["category"] == "MUST_HAVE" and c["weight"] > 0 for c in items):
            raise ValueError("No weighted mandatory criterion")
        if any(sum(c["weight"] for c in items if c["category"] == category) <= 0
               for category in {c["category"] for c in items}):
            raise ValueError("A criterion group has no weight")
        items = _normalize_weights_in_group(items)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise HTTPException(status_code=502, detail="AI trả về bộ tiêu chí không hợp lệ. Vui lòng thử lại.")
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1 FROM app_private.positions WHERE position_id = :id FOR UPDATE"), {"id": str(position_id)})
        latest_jd = db.execute(text("SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :id ORDER BY version_number DESC LIMIT 1"), {"id": str(position_id)}).scalar_one_or_none()
        if str(latest_jd) != str(jd["jd_version_id"]):
            raise HTTPException(status_code=409, detail="JD đã thay đổi trong lúc tạo tiêu chí. Vui lòng thử lại.")
        version = db.execute(text("SELECT COALESCE(MAX(version_number), 0) + 1 FROM app_private.criteria_versions WHERE position_id = :id"), {"id": str(position_id)}).scalar_one()
        version_id = db.execute(text("""
            INSERT INTO app_private.criteria_versions (position_id, jd_version_id, version_number, origin, status,
                mandatory_weight_total, nice_to_have_weight_total)
            VALUES (:position, :jd, :version, 'AI_DRAFT', 'DRAFT', :mandatory, :nice) RETURNING criteria_version_id
        """), {"position": str(position_id), "jd": jd["jd_version_id"], "version": version,
               **dict(zip(("mandatory", "nice"), draft_group_totals(items)))}).scalar_one()
        for index, item in enumerate(items):
            db.execute(text("""
                INSERT INTO app_private.criteria_items (criteria_version_id, name, description, category, weight_in_group,
                    expected_evidence_keywords, requirement_spec, display_order, jd_reference_text, evidence_guidance)
                VALUES (:id, :name, :description, :category, :weight, CAST(:keywords AS jsonb),
                        CAST(:requirement_spec AS jsonb), :display_order, :jd_reference_text, :evidence_guidance)
            """), {"jd_reference_text": None, "evidence_guidance": None, **item, "id": version_id, "keywords": json.dumps(item["keywords"]),
                    "requirement_spec": json.dumps(item["requirement_spec"]), "display_order": index})
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome)
            VALUES (:user_id, 'GENERATE_CRITERIA_DRAFT', 'CRITERIA_VERSION', :id, :position, 'SUCCESS')
        """), {"user_id": current_user["user_id"], "id": version_id, "position": str(position_id)})
        result = _load_criteria(db, version_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def draft_group_totals(items: list[dict]) -> tuple[float, float]:
    """Group totals for a new AI draft. A draft without preferred criteria gets
    100/0 instead of the 70/30 default, otherwise the empty 30% group blocks
    approval until HR notices and edits the totals by hand."""
    if any(item["category"] == "NICE_TO_HAVE" for item in items):
        mandatory = round(settings.MANDATORY_CRITERIA_WEIGHT_DEFAULT * 100, 2)
        return mandatory, round(100 - mandatory, 2)
    return 100.0, 0.0


def criteria_decision(current_status: str, action: ApprovalAction, position_roles: set[str], system_roles: set[str]) -> tuple[str, str]:
    """Return the next state and reviewer capacity after checking the actor's active roles."""
    is_hr = bool({"HR_RECRUITER", "HR_LEAD"} & position_roles) or bool({"ADMIN", "HR_LEAD"} & system_roles)
    is_hm = "HIRING_MANAGER" in position_roles
    # The approval trail records the capacity used; system roles are preserved
    # separately in audit metadata.
    hr_role = "HR_LEAD" if "HR_LEAD" in (system_roles | position_roles) and "HR_RECRUITER" not in position_roles else "HR_RECRUITER"
    # Admin/HR Lead may always approve directly. The HR Recruiter assigned to the
    # position may too, but only after accepting responsibility (checked by the
    # endpoint), because the Hiring Manager's expert review is skipped.
    can_direct_approve = (bool({"ADMIN", "HR_LEAD"} & system_roles)
                          or bool({"HR_LEAD", "HR_RECRUITER"} & position_roles))
    if "ADMIN" in system_roles:
        direct_role = "ADMIN"
    elif "HR_LEAD" in (system_roles | position_roles):
        direct_role = "HR_LEAD"
    else:
        direct_role = "HR_RECRUITER"

    if action == ApprovalAction.DIRECT_APPROVE:
        if current_status in ("DRAFT", "PENDING_HR_REVIEW", "PENDING_HM_APPROVAL"):
            if not can_direct_approve:
                raise HTTPException(status_code=403, detail="Chỉ Admin, HR Lead hoặc HR phụ trách mới có thể duyệt trực tiếp, không qua Hiring Manager")
            return "APPROVED", direct_role
    elif action == ApprovalAction.APPROVE:
        if current_status in ("DRAFT", "PENDING_HR_REVIEW"):
            if not is_hr:
                raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới có thể duyệt và gửi tiêu chí cho Hiring Manager")
            return "PENDING_HM_APPROVAL", hr_role
        if current_status == "PENDING_HM_APPROVAL":
            if not is_hm:
                raise HTTPException(status_code=403, detail="Chỉ Hiring Manager được phân công mới có thể duyệt chuyên môn")
            return "APPROVED", "HIRING_MANAGER"
    elif action == ApprovalAction.REQUEST_CHANGES and current_status == "PENDING_HM_APPROVAL":
        if not is_hm:
            raise HTTPException(status_code=403, detail="Chỉ Hiring Manager được phân công mới có thể yêu cầu chỉnh sửa")
        return "DRAFT", "HIRING_MANAGER"
    elif action == ApprovalAction.REJECT and current_status in ("DRAFT", "PENDING_HR_REVIEW"):
        if not is_hr:
            raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới có thể từ chối tiêu chí")
        return "REJECTED", hr_role

    raise HTTPException(status_code=400, detail=f"Không thể thực hiện thao tác này khi tiêu chí ở trạng thái {current_status}")


@router.post("/{criteria_version_id}/approve", response_model=CriteriaVersion)
async def approve_criteria(
    criteria_version_id: UUID,
    request: CriteriaApprovalRequest,
    current_user: dict = Depends(get_current_user)
):
    """Record HR/HM decisions atomically, plus the direct path (Admin/HR Lead, or the assigned HR who accepts responsibility)."""
    user_id = current_user["user_id"]
    cv_id_str = str(criteria_version_id)
    comment = (request.comment or "").strip() or None
    if request.action in (ApprovalAction.REJECT, ApprovalAction.REQUEST_CHANGES) and not comment:
        raise HTTPException(status_code=400, detail="Vui lòng nhập lý do từ chối hoặc yêu cầu chỉnh sửa")
    if comment and len(comment) > 2000:
        raise HTTPException(status_code=400, detail="Nội dung phản hồi không được vượt quá 2000 ký tự")
    db = SessionLocal()
    try:
        # Acquire the position lock in the same order as the upload/queue APIs.
        # A new approval cannot become active halfway through an assessment and
        # change the rubric used by its ranking snapshot.
        position = db.execute(text("""
            SELECT position_id FROM app_private.criteria_versions WHERE criteria_version_id = :cv_id
        """), {"cv_id": cv_id_str}).scalar_one_or_none()
        if not position or not db.execute(text("SELECT 1 FROM app_private.positions WHERE position_id = :id FOR UPDATE"), {"id": str(position)}).first():
            raise NotFoundError("Criteria version")
        cv = db.execute(text("""
            SELECT position_id, jd_version_id, status, mandatory_weight_total, nice_to_have_weight_total, approved_by_hr
            FROM app_private.criteria_versions WHERE criteria_version_id = :cv_id FOR UPDATE
        """), {"cv_id": cv_id_str}).mappings().first()
        if not cv:
            raise NotFoundError("Criteria version")
        position_id = str(cv["position_id"])
        account = db.execute(text("SELECT account_status FROM app_private.user_profiles WHERE user_id = :id FOR SHARE"), {"id": user_id}).scalar_one_or_none()
        if account != 'ACTIVE':
            raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt hoặc đã bị khóa")
        position_roles = set(db.execute(text("""
            SELECT position_role FROM app_private.position_assignments
            WHERE position_id = :position_id AND user_id = :user_id AND revoked_at IS NULL FOR SHARE
        """), {"position_id": position_id, "user_id": user_id}).scalars())
        system_roles = set(db.execute(text("""
            SELECT role_code FROM app_private.user_role_assignments
            WHERE user_id = :user_id AND revoked_at IS NULL FOR SHARE
        """), {"user_id": user_id}).scalars())
        new_status, reviewer_role = criteria_decision(cv["status"], request.action, position_roles, system_roles)
        hr_self_approval = request.action == ApprovalAction.DIRECT_APPROVE and reviewer_role == "HR_RECRUITER"
        if hr_self_approval:
            if not request.accept_responsibility:
                raise HTTPException(status_code=400, detail="Vui lòng xác nhận bạn tự chịu trách nhiệm khi duyệt tiêu chí không qua Hiring Manager")
            comment = comment or "HR tự duyệt, không qua Hiring Manager và tự chịu trách nhiệm về bộ tiêu chí."
        if new_status in ("PENDING_HM_APPROVAL", "APPROVED"):
            latest_jd = db.execute(text("SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :id ORDER BY version_number DESC LIMIT 1"), {"id": position_id}).scalar_one_or_none()
            if str(latest_jd) != str(cv["jd_version_id"]):
                raise HTTPException(status_code=409, detail="JD đã thay đổi. Vui lòng tạo và duyệt tiêu chí cho phiên bản JD mới nhất.")
        if new_status == "APPROVED" and request.action != ApprovalAction.DIRECT_APPROVE:
            # One account may hold both roles.  The position and criteria rows
            # are locked above so this check and the decision are indivisible.
            # DIRECT_APPROVE is the explicit bypass (Admin/HR Lead/assigned HR), so it does
            # not require a prior, distinct HR approver.
            if not cv["approved_by_hr"] or str(cv["approved_by_hr"]) == str(user_id):
                raise HTTPException(status_code=409, detail="Hai bước duyệt phải do hai tài khoản khác nhau thực hiện")
        if new_status == "APPROVED" and db.execute(text("""
            SELECT 1 FROM app_private.operations WHERE position_id = :position_id
              AND capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING')
              AND status IN ('PENDING', 'PROCESSING') LIMIT 1
        """), {"position_id": position_id}).first():
            raise HTTPException(status_code=409, detail="Vị trí đang xử lý hồ sơ. Vui lòng đợi tác vụ hoàn tất trước khi duyệt phiên bản mới.")
        if new_status in ("PENDING_HM_APPROVAL", "APPROVED"):
            _require_fair_criteria(db, cv_id_str)
        if new_status in ("PENDING_HM_APPROVAL", "APPROVED"):
            if (cv["mandatory_weight_total"] <= 0 or cv["nice_to_have_weight_total"] < 0
                    or cv["mandatory_weight_total"] + cv["nice_to_have_weight_total"] != 100):
                raise HTTPException(status_code=400, detail="Trọng số hai nhóm không hợp lệ hoặc không bằng 100%")
        if new_status == "PENDING_HM_APPROVAL":
            _materialize_requirement_specs(db, cv_id_str)
            _validate_item_weight_totals(db, cv_id_str)
        if new_status == "APPROVED":
            if request.action == ApprovalAction.DIRECT_APPROVE:
                # A direct approval may start from a draft, before the normal
                # HR step would have materialized inferred requirement specs.
                _materialize_requirement_specs(db, cv_id_str)
            _validate_item_weight_totals(db, cv_id_str)

        db.execute(text("""
            UPDATE app_private.criteria_versions
            SET status = :new_status,
                approved_by_hr = CASE WHEN :new_status = 'PENDING_HM_APPROVAL' THEN :user_id
                                      WHEN :new_status = 'DRAFT' THEN NULL ELSE approved_by_hr END,
                approved_by_hr_at = CASE WHEN :new_status = 'PENDING_HM_APPROVAL' THEN NOW()
                                         WHEN :new_status = 'DRAFT' THEN NULL ELSE approved_by_hr_at END,
                approved_by_hm = CASE WHEN :new_status = 'APPROVED' AND NOT :direct_approve THEN CAST(:user_id AS uuid)
                                      WHEN :new_status = 'APPROVED' THEN approved_by_hm ELSE NULL END,
                approved_by_hm_at = CASE WHEN :new_status = 'APPROVED' AND NOT :direct_approve THEN NOW()
                                         WHEN :new_status = 'APPROVED' THEN approved_by_hm_at ELSE NULL END,
                updated_at = NOW()
            WHERE criteria_version_id = :cv_id
        """), {"new_status": new_status, "user_id": user_id, "cv_id": cv_id_str,
                "direct_approve": request.action == ApprovalAction.DIRECT_APPROVE})
        db.execute(text("""
            INSERT INTO app_private.criteria_approval_events
                (criteria_version_id, reviewed_by, reviewer_role, decision, comment)
            VALUES (:cv_id, :user_id, :reviewer_role, :decision, :comment)
        """), {"cv_id": cv_id_str, "user_id": user_id, "reviewer_role": reviewer_role,
                "decision": request.action.value, "comment": comment})
        db.execute(text("""
            INSERT INTO app_private.audit_events
                (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES (:user_id, 'REVIEW_CRITERIA', 'CRITERIA_VERSION', :cv_id, :position_id,
                    :outcome, CAST(:metadata AS jsonb))
        """), {"user_id": user_id, "cv_id": cv_id_str, "position_id": position_id,
                "outcome": new_status, "metadata": json.dumps({"decision": request.action.value,
                    "reviewer_role": reviewer_role, "system_roles": sorted(system_roles),
                    "position_roles": sorted(position_roles),
                    "direct_approve": request.action == ApprovalAction.DIRECT_APPROVE,
                    "bypassed_hm": request.action == ApprovalAction.DIRECT_APPROVE,
                    "hr_self_approval": hr_self_approval,
                    "accepted_responsibility": bool(hr_self_approval and request.accept_responsibility)})})
        updated = dict(db.execute(text("SELECT * FROM app_private.criteria_versions WHERE criteria_version_id = :id"),
                                  {"id": cv_id_str}).mappings().one())
        updated["criteria"] = [dict(row) for row in db.execute(text("""
            SELECT * FROM app_private.criteria_items WHERE criteria_version_id = :id ORDER BY display_order
        """), {"id": cv_id_str}).mappings().all()]
        db.commit()
        return updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/{criteria_version_id}/approval-events")
async def list_approval_events(criteria_version_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        position_id = db.execute(text("SELECT position_id FROM app_private.criteria_versions WHERE criteria_version_id = :id"),
                                 {"id": str(criteria_version_id)}).scalar_one_or_none()
        if not position_id:
            raise NotFoundError("Criteria version")
        await check_position_access(position_id, current_user)
        rows = db.execute(text("""
            SELECT e.event_id, e.reviewed_by, e.reviewer_role, e.decision, e.comment, e.decided_at,
                   p.display_name AS reviewer_name
            FROM app_private.criteria_approval_events e
            LEFT JOIN app_private.user_profiles p ON p.user_id = e.reviewed_by
            WHERE e.criteria_version_id = :id ORDER BY e.decided_at, e.event_id
        """), {"id": str(criteria_version_id)}).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.patch("/{criteria_version_id}/weights", response_model=CriteriaVersion)
async def update_criteria_weights(criteria_version_id: UUID, update: CriteriaWeightsUpdate,
                                  current_user: dict = Depends(get_current_user)):
    """Edit group weights only on a draft; the approved version remains immutable."""
    db = SessionLocal()
    try:
        version = db.execute(text("""
            SELECT position_id, status FROM app_private.criteria_versions
            WHERE criteria_version_id = :id FOR UPDATE
        """), {"id": str(criteria_version_id)}).mappings().first()
        if not version:
            raise NotFoundError("Criteria version")
        if not can_update_application_status(current_user["user_id"], str(version["position_id"])):
            raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới có thể sửa trọng số")
        if version["status"] not in ("DRAFT", "PENDING_HR_REVIEW"):
            raise HTTPException(status_code=400, detail="Chỉ có thể sửa trọng số của bản nháp")
        db.execute(text("""
            UPDATE app_private.criteria_versions
            SET mandatory_weight_total = :mandatory, nice_to_have_weight_total = :nice, updated_at = NOW()
            WHERE criteria_version_id = :id
        """), {"mandatory": update.mandatory_weight_total, "nice": update.nice_to_have_weight_total,
                "id": str(criteria_version_id)})
        db.execute(text("""
            INSERT INTO app_private.audit_events
                (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES (:user_id, 'UPDATE_CRITERIA_WEIGHTS', 'CRITERIA_VERSION', :id, :position_id, 'SUCCESS', CAST(:metadata AS jsonb))
        """), {"user_id": current_user["user_id"], "id": str(criteria_version_id),
                "position_id": str(version["position_id"]), "metadata": json.dumps({
                    "mandatory_weight_total": str(update.mandatory_weight_total),
                    "nice_to_have_weight_total": str(update.nice_to_have_weight_total)})})
        result = _load_criteria(db, criteria_version_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{criteria_version_id}/items", response_model=Criterion, status_code=status.HTTP_201_CREATED)
async def create_criterion(criteria_version_id: UUID, request: CriterionCreate,
                           current_user: dict = Depends(get_current_user)):
    """Add a criterion to a draft rubric when the AI proposal is incomplete."""
    name, description = request.name.strip(), request.description.strip()
    if not name or len(name) > 200 or not description or len(description) > 4000:
        raise HTTPException(status_code=400, detail="Tên hoặc mô tả tiêu chí không hợp lệ")
    db = SessionLocal()
    try:
        version = _lock_editable_criteria_version(db, criteria_version_id, current_user["user_id"])
        spec = (request.requirement_spec.model_dump() if request.requirement_spec is not None else _stored_requirement_spec({
            "name": name, "description": description, "category": request.category.value,
            "expected_evidence_keywords": request.expected_evidence_keywords,
        }))
        display_order = db.execute(text("""
            SELECT COALESCE(MAX(display_order), -1) + 1 FROM app_private.criteria_items
            WHERE criteria_version_id = :id
        """), {"id": str(criteria_version_id)}).scalar_one()
        criterion_id = db.execute(text("""
            INSERT INTO app_private.criteria_items
                (criteria_version_id, name, description, category, weight_in_group,
                 expected_evidence_keywords, requirement_spec, evidence_guidance, jd_reference_text, display_order)
            VALUES (:version_id, :name, :description, :category, :weight, CAST(:keywords AS jsonb),
                    CAST(:spec AS jsonb), :guidance, :jd_reference, :display_order)
            RETURNING criterion_id
        """), {"version_id": str(criteria_version_id), "name": name, "description": description,
                "category": request.category.value, "weight": request.weight_in_group,
                "keywords": json.dumps(request.expected_evidence_keywords), "spec": json.dumps(spec),
                "guidance": request.evidence_guidance, "jd_reference": request.jd_reference_text,
                "display_order": int(display_order)}).scalar_one()
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome)
            VALUES (:user_id, 'CREATE_CRITERION', 'CRITERION', :criterion_id, :position_id, 'SUCCESS')
        """), {"user_id": current_user["user_id"], "criterion_id": str(criterion_id),
                "position_id": str(version["position_id"])})
        result = db.execute(text("SELECT * FROM app_private.criteria_items WHERE criterion_id = :id"),
                            {"id": str(criterion_id)}).mappings().one()
        db.commit()
        return dict(result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.patch("/{criteria_version_id}/items/weights", response_model=CriteriaVersion)
async def update_criterion_weights(criteria_version_id: UUID, update: CriteriaItemWeightsUpdate,
                                   current_user: dict = Depends(get_current_user)):
    """Replace all draft item weights atomically; each present group totals 100."""
    db = SessionLocal()
    try:
        version = _lock_editable_criteria_version(db, criteria_version_id, current_user["user_id"])
        rows = db.execute(text("""
            SELECT criterion_id, category FROM app_private.criteria_items WHERE criteria_version_id = :id
        """), {"id": str(criteria_version_id)}).mappings().all()
        existing = {str(row["criterion_id"]): str(row["category"]) for row in rows}
        submitted = {str(item.criterion_id): item.weight_in_group for item in update.items}
        if set(submitted) != set(existing):
            raise HTTPException(status_code=400, detail="Cần gửi trọng số cho toàn bộ tiêu chí trong bộ tiêu chí.")
        totals: dict[str, Decimal] = {}
        for criterion_id, weight in submitted.items():
            category = existing[criterion_id]
            totals[category] = totals.get(category, Decimal("0")) + weight
        invalid = [category for category, total in totals.items() if total != Decimal("100.00")]
        if invalid:
            labels = {"MUST_HAVE": "Bắt buộc", "NICE_TO_HAVE": "Ưu tiên"}
            details = ", ".join(f"{labels.get(category, category)}={totals[category]}%" for category in invalid)
            raise HTTPException(status_code=400, detail=f"Tổng trọng số trong mỗi nhóm tiêu chí phải bằng 100%. Hiện tại: {details}.")
        for criterion_id, weight in submitted.items():
            db.execute(text("""
                UPDATE app_private.criteria_items SET weight_in_group = :weight
                WHERE criterion_id = :criterion_id AND criteria_version_id = :version_id
            """), {"weight": weight, "criterion_id": criterion_id, "version_id": str(criteria_version_id)})
        db.execute(text("""
            INSERT INTO app_private.audit_events
                (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES (:user_id, 'UPDATE_CRITERION_WEIGHTS', 'CRITERIA_VERSION', :id, :position_id, 'SUCCESS', CAST(:metadata AS jsonb))
        """), {"user_id": current_user["user_id"], "id": str(criteria_version_id),
                "position_id": str(version["position_id"]),
                "metadata": json.dumps({"item_weight_totals": {category: str(total) for category, total in totals.items()}})})
        result = _load_criteria(db, criteria_version_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.patch("/{criteria_version_id}/items/{criterion_id}")
async def update_criterion(criteria_version_id: UUID, criterion_id: UUID, update: CriterionUpdate,
                           current_user: dict = Depends(get_current_user)):
    """HR may revise a draft; approved and pending versions are immutable."""
    fields = update.model_dump(exclude_unset=True)
    allowed = {key: value for key, value in fields.items()
               if key in ("name", "description", "category", "weight_in_group", "expected_evidence_keywords")
               and value is not None}
    if "category" in allowed:
        allowed["category"] = allowed["category"].value if hasattr(allowed["category"], "value") else str(allowed["category"])
    if "requirement_spec" in fields:
        allowed["requirement_spec"] = (
            json.dumps(fields["requirement_spec"]) if fields["requirement_spec"] is not None else None
        )
    if not allowed:
        raise HTTPException(status_code=400, detail="Không có nội dung cần cập nhật")
    for key in ("name", "description"):
        if key in allowed:
            allowed[key] = allowed[key].strip()
            if not allowed[key] or len(allowed[key]) > (200 if key == "name" else 4000):
                raise HTTPException(status_code=400, detail="Tên hoặc mô tả tiêu chí không hợp lệ")
    db = SessionLocal()
    try:
        version = _lock_editable_criteria_version(db, criteria_version_id, current_user["user_id"])
        set_parts = []
        for name in allowed:
            if name in ("expected_evidence_keywords", "requirement_spec"):
                set_parts.append(f"{name} = CAST(:{name} AS jsonb)")
            else:
                set_parts.append(f"{name} = :{name}")
        if "expected_evidence_keywords" in allowed:
            allowed["expected_evidence_keywords"] = json.dumps(allowed["expected_evidence_keywords"])
        sets = ", ".join(set_parts)
        result = db.execute(text(f"""
            UPDATE app_private.criteria_items SET {sets}
            WHERE criterion_id = :criterion_id AND criteria_version_id = :version_id RETURNING criterion_id
        """), {**allowed, "criterion_id": str(criterion_id), "version_id": str(criteria_version_id)}).first()
        if not result:
            raise NotFoundError("Criterion")
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome)
            VALUES (:user_id, 'UPDATE_CRITERION', 'CRITERION', :criterion_id, :position_id, 'SUCCESS')
        """), {"user_id": current_user["user_id"], "criterion_id": str(criterion_id), "position_id": str(version["position_id"])})
        db.commit()
        return {"status": "updated"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.delete("/{criteria_version_id}/items/{criterion_id}")
async def delete_criterion(criteria_version_id: UUID, criterion_id: UUID,
                           current_user: dict = Depends(get_current_user)):
    """Remove an unwanted AI-proposed criterion from a draft rubric."""
    db = SessionLocal()
    try:
        version = _lock_editable_criteria_version(db, criteria_version_id, current_user["user_id"])
        deleted = db.execute(text("""
            DELETE FROM app_private.criteria_items
            WHERE criterion_id = :criterion_id AND criteria_version_id = :version_id
            RETURNING criterion_id
        """), {"criterion_id": str(criterion_id), "version_id": str(criteria_version_id)}).first()
        if not deleted:
            raise NotFoundError("Criterion")
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome)
            VALUES (:user_id, 'DELETE_CRITERION', 'CRITERION', :criterion_id, :position_id, 'SUCCESS')
        """), {"user_id": current_user["user_id"], "criterion_id": str(criterion_id),
                "position_id": str(version["position_id"])})
        db.commit()
        return {"status": "deleted"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/position/{position_id}/approved", response_model=Optional[CriteriaVersion])
async def get_latest_approved_criteria(position_id: UUID, current_user: dict = Depends(get_current_user)):
    await check_position_access(position_id, current_user)
    db = SessionLocal()
    try:
        version_id = db.execute(text("""
            SELECT criteria_version_id FROM app_private.criteria_versions WHERE position_id = :id AND status = 'APPROVED'
              AND jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :id ORDER BY version_number DESC LIMIT 1)
            ORDER BY version_number DESC LIMIT 1
        """), {"id": str(position_id)}).scalar_one_or_none()
        return _load_criteria(db, version_id) if version_id else None
    finally:
        db.close()


def _audit(db, user_id, action_type: str, object_type: str, object_id, position_id, metadata: Optional[dict] = None):
    db.execute(text("""
        INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:user_id, :action_type, :object_type, :object_id, :position_id, 'SUCCESS', CAST(:metadata AS jsonb))
    """), {"user_id": user_id, "action_type": action_type, "object_type": object_type, "object_id": str(object_id),
            "position_id": str(position_id), "metadata": json.dumps(metadata) if metadata is not None else None})


def _open_criteria_exists(db, position_id) -> bool:
    return bool(db.execute(text("""
        SELECT 1 FROM app_private.criteria_versions
        WHERE position_id = :id AND status IN ('DRAFT', 'PENDING_HR_REVIEW', 'PENDING_HM_APPROVAL') LIMIT 1
    """), {"id": str(position_id)}).first())


@router.post("/{criteria_version_id}/new-version", response_model=CriteriaVersion, status_code=status.HTTP_201_CREATED)
async def create_new_criteria_version(criteria_version_id: UUID, current_user: dict = Depends(get_current_user)):
    """Copy an approved or rejected rubric into a new HR draft for the latest JD.

    Approved versions stay immutable, so later edits produce a new version
    ("Tạo phiên bản mới" on S-06). The copy restarts approval and never
    inherits any approval.
    """
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        position_id = db.execute(text("""
            SELECT position_id FROM app_private.criteria_versions WHERE criteria_version_id = :id
        """), {"id": str(criteria_version_id)}).scalar_one_or_none()
        # Same lock order as approval and upload: position first, then versions.
        if not position_id or not db.execute(text("SELECT 1 FROM app_private.positions WHERE position_id = :id FOR UPDATE"),
                                             {"id": str(position_id)}).first():
            raise NotFoundError("Criteria version")
        if not can_update_application_status(user_id, str(position_id)):
            raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới có thể tạo phiên bản tiêu chí mới")
        source = db.execute(text("""
            SELECT status, mandatory_weight_total, nice_to_have_weight_total
            FROM app_private.criteria_versions WHERE criteria_version_id = :id
        """), {"id": str(criteria_version_id)}).mappings().one()
        if source["status"] not in ("APPROVED", "REJECTED"):
            raise HTTPException(status_code=400, detail="Chỉ tạo phiên bản mới từ bộ tiêu chí đã duyệt hoặc đã từ chối; bản nháp hãy sửa trực tiếp")
        if _open_criteria_exists(db, position_id):
            raise HTTPException(status_code=409, detail="Vị trí đang có bộ tiêu chí chưa hoàn tất duyệt. Vui lòng xử lý bản đó trước.")
        latest_jd = db.execute(text("""
            SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :id ORDER BY version_number DESC LIMIT 1
        """), {"id": str(position_id)}).scalar_one_or_none()
        if not latest_jd:
            raise HTTPException(status_code=400, detail="Vị trí chưa có mô tả công việc")
        version_number = db.execute(text("""
            SELECT COALESCE(MAX(version_number), 0) + 1 FROM app_private.criteria_versions WHERE position_id = :id
        """), {"id": str(position_id)}).scalar_one()
        new_id = db.execute(text("""
            INSERT INTO app_private.criteria_versions (position_id, jd_version_id, version_number, origin, status,
                mandatory_weight_total, nice_to_have_weight_total)
            VALUES (:position, :jd, :version, 'HR_CREATED', 'DRAFT', :mandatory, :nice)
            RETURNING criteria_version_id
        """), {"position": str(position_id), "jd": str(latest_jd), "version": version_number,
                "mandatory": source["mandatory_weight_total"], "nice": source["nice_to_have_weight_total"]}).scalar_one()
        db.execute(text("""
            INSERT INTO app_private.criteria_items (criteria_version_id, name, description, category, weight_in_group,
                expected_evidence_keywords, evidence_guidance, jd_reference_text, requirement_spec, display_order)
            SELECT :new_id, name, description, category, weight_in_group,
                expected_evidence_keywords, evidence_guidance, jd_reference_text, requirement_spec, display_order
            FROM app_private.criteria_items WHERE criteria_version_id = :source_id
        """), {"new_id": str(new_id), "source_id": str(criteria_version_id)})
        _audit(db, user_id, "CREATE_CRITERIA_VERSION", "CRITERIA_VERSION", new_id, position_id,
               {"source_criteria_version_id": str(criteria_version_id), "version_number": version_number})
        result = _load_criteria(db, new_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------- F2.01: apply a published rubric template ----------------

def _require_position_hr(position_id, current_user: dict):
    if not can_update_application_status(current_user["user_id"], str(position_id)):
        raise HTTPException(status_code=403, detail="Chỉ HR phụ trách vị trí mới dùng được thư viện rubric cho vị trí này")


@router.get("/position/{position_id}/template-matches")
async def list_template_matches(position_id: UUID, current_user: dict = Depends(get_current_user)):
    """Published templates, those matching the position's job family/level first."""
    _require_position_hr(position_id, current_user)
    db = SessionLocal()
    try:
        position = db.execute(text("SELECT job_family_id, level FROM app_private.positions WHERE position_id = :id"),
                              {"id": str(position_id)}).mappings().first()
        if not position:
            raise NotFoundError("Position")
        rows = db.execute(text("""
            SELECT v.template_version_id, v.version_number, v.mandatory_weight_total, v.nice_to_have_weight_total,
                   v.published_at, t.template_id, t.title, t.level_band, t.job_family_id, f.name AS job_family_name,
                   COUNT(i.template_item_id) FILTER (WHERE i.category = 'MUST_HAVE') AS must_have_count,
                   COUNT(i.template_item_id) FILTER (WHERE i.category = 'NICE_TO_HAVE') AS nice_to_have_count,
                   (t.job_family_id = CAST(:family AS uuid)) AS family_match,
                   (t.level_band IS NOT NULL AND lower(t.level_band) = lower(CAST(:level AS text))) AS level_match
            FROM app_private.rubric_template_versions v
            JOIN app_private.rubric_templates t ON t.template_id = v.template_id AND t.status = 'ACTIVE'
            JOIN app_private.job_families f ON f.job_family_id = t.job_family_id
            LEFT JOIN app_private.rubric_template_items i ON i.template_version_id = v.template_version_id
            WHERE v.status = 'PUBLISHED'
            GROUP BY v.template_version_id, t.template_id, f.name
            ORDER BY family_match DESC NULLS LAST, level_match DESC NULLS LAST, t.title
        """), {"family": str(position["job_family_id"]) if position["job_family_id"] else None,
                "level": position["level"]}).mappings().all()
        return [{**dict(row), "family_match": bool(row["family_match"]), "level_match": bool(row["level_match"])}
                for row in rows]
    finally:
        db.close()


@router.post("/position/{position_id}/apply-template", response_model=CriteriaVersion, status_code=status.HTTP_201_CREATED)
async def apply_template_to_position(position_id: UUID, request: ApplyTemplateRequest,
                                     current_user: dict = Depends(get_current_user)):
    """Clone a published template into a criteria DRAFT (D-04: never auto-approved)."""
    _require_position_hr(position_id, current_user)
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        if not db.execute(text("SELECT 1 FROM app_private.positions WHERE position_id = :id FOR UPDATE"),
                          {"id": str(position_id)}).first():
            raise NotFoundError("Position")
        template = db.execute(text("""
            SELECT v.template_version_id, v.status, v.mandatory_weight_total, v.nice_to_have_weight_total
            FROM app_private.rubric_template_versions v
            WHERE v.template_version_id = :id FOR SHARE
        """), {"id": str(request.template_version_id)}).mappings().first()
        if not template or template["status"] != "PUBLISHED":
            raise HTTPException(status_code=400, detail="Chỉ áp dụng được template đã xuất bản")
        if _open_criteria_exists(db, position_id):
            raise HTTPException(status_code=409, detail="Vị trí đang có bộ tiêu chí chưa hoàn tất duyệt. Vui lòng xử lý bản đó trước khi áp dụng template.")
        latest_jd = db.execute(text("""
            SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :id ORDER BY version_number DESC LIMIT 1
        """), {"id": str(position_id)}).scalar_one_or_none()
        if not latest_jd:
            raise HTTPException(status_code=400, detail="Vị trí chưa có mô tả công việc")
        version_number = db.execute(text("""
            SELECT COALESCE(MAX(version_number), 0) + 1 FROM app_private.criteria_versions WHERE position_id = :id
        """), {"id": str(position_id)}).scalar_one()
        new_id = db.execute(text("""
            INSERT INTO app_private.criteria_versions (position_id, jd_version_id, version_number, origin, status,
                mandatory_weight_total, nice_to_have_weight_total, source_template_version_id)
            VALUES (:position, :jd, :version, 'TEMPLATE_CLONE', 'DRAFT', :mandatory, :nice, :template)
            RETURNING criteria_version_id
        """), {"position": str(position_id), "jd": str(latest_jd), "version": version_number,
                "mandatory": template["mandatory_weight_total"], "nice": template["nice_to_have_weight_total"],
                "template": str(request.template_version_id)}).scalar_one()
        db.execute(text("""
            INSERT INTO app_private.criteria_items (criteria_version_id, name, description, category, weight_in_group,
                expected_evidence_keywords, evidence_guidance, display_order, source_template_item_id)
            SELECT :new_id, name, description, category, weight_in_group, expected_evidence_keywords,
                evidence_guidance, display_order, template_item_id
            FROM app_private.rubric_template_items WHERE template_version_id = :template
        """), {"new_id": str(new_id), "template": str(request.template_version_id)})
        # Same structured requirement specs as an AI/HR draft, so deterministic
        # matching treats template criteria identically.
        _materialize_requirement_specs(db, str(new_id))
        _audit(db, user_id, "APPLY_RUBRIC_TEMPLATE", "CRITERIA_VERSION", new_id, position_id,
               {"template_version_id": str(request.template_version_id), "version_number": version_number})
        result = _load_criteria(db, new_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
