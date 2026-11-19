"""F2.01 — Rubric library by job family.

Roles (plan D-02): HR Recruiters draft templates; only HR Lead publishes or
archives; Admin/HR Lead manage the job-family taxonomy. Hiring Managers have no
access to the library. Published versions are immutable (D-03).
"""
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.schemas.rubric import (JobFamilyCreate, JobFamilyUpdate, TemplateCreate, TemplateItemCreate,
                                TemplateItemUpdate, TemplateReviewRequest, TemplateVersionCreate,
                                TemplateVersionUpdate)
from app.services.criteria_fairness import fairness_warnings
from app.services.workflow_rules import template_publish_errors

router = APIRouter()

LIBRARY_READERS = {"ADMIN", "HR_LEAD", "HR_RECRUITER"}
FAMILY_MANAGERS = {"ADMIN", "HR_LEAD"}
TEMPLATE_EDITORS = {"HR_LEAD", "HR_RECRUITER"}
MAX_ITEMS = 100


def library_roles(db, user_id: str) -> set[str]:
    """System roles, plus HR_RECRUITER for anyone acting as HR on a position."""
    roles = set(db.execute(text("""
        SELECT role_code FROM app_private.user_role_assignments WHERE user_id = :id AND revoked_at IS NULL
    """), {"id": user_id}).scalars())
    if db.execute(text("""
        SELECT 1 FROM app_private.position_assignments WHERE user_id = :id AND revoked_at IS NULL
          AND position_role IN ('HR_RECRUITER', 'HR_LEAD') LIMIT 1
    """), {"id": user_id}).first():
        roles.add("HR_RECRUITER")
    return roles


def _require(roles: set[str], allowed: set[str], message: str):
    if not roles & allowed:
        raise HTTPException(status_code=403, detail=message)


def _audit(db, user_id, action: str, object_type: str, object_id, metadata: Optional[dict] = None):
    db.execute(text("""
        INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome, metadata)
        VALUES (:user_id, :action, :object_type, :object_id, 'SUCCESS', CAST(:metadata AS jsonb))
    """), {"user_id": user_id, "action": action, "object_type": object_type, "object_id": str(object_id),
            "metadata": json.dumps(metadata) if metadata is not None else None})


def _clean(value, limit: int, label: str, required: bool = False):
    value = (value or "").strip() if value is not None or required else None
    if required and not value:
        raise HTTPException(status_code=400, detail=f"{label} không được để trống")
    if value and len(value) > limit:
        raise HTTPException(status_code=400, detail=f"{label} không được vượt quá {limit} ký tự")
    return value or None


def _keywords(values) -> str:
    cleaned: list[str] = []
    for value in values or []:
        keyword = str(value).strip()
        if keyword and len(keyword) <= 100 and keyword.lower() not in {k.lower() for k in cleaned}:
            cleaned.append(keyword)
    return json.dumps(cleaned[:20])


# ---------------- Job families ----------------

@router.get("/families")
async def list_families(include_inactive: bool = False, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _require(library_roles(db, current_user["user_id"]), LIBRARY_READERS, "Bạn không có quyền xem thư viện rubric")
        rows = db.execute(text("""
            SELECT f.*, (SELECT COUNT(*) FROM app_private.rubric_templates t WHERE t.job_family_id = f.job_family_id) AS template_count
            FROM app_private.job_families f
            WHERE :include_inactive OR f.status = 'ACTIVE'
            ORDER BY f.display_order, f.name
        """), {"include_inactive": include_inactive}).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.post("/families", status_code=status.HTTP_201_CREATED)
async def create_family(request: JobFamilyCreate, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _require(library_roles(db, current_user["user_id"]), FAMILY_MANAGERS, "Chỉ Admin hoặc HR Lead quản lý nhóm ngành")
        row = db.execute(text("""
            INSERT INTO app_private.job_families (code, name, description, display_order, created_by)
            VALUES (:code, :name, :description, :display_order, :user_id) RETURNING *
        """), {"code": request.code.upper(), "name": _clean(request.name, 200, "Tên nhóm ngành", True),
                "description": _clean(request.description, 2000, "Mô tả"), "display_order": request.display_order,
                "user_id": current_user["user_id"]}).mappings().one()
        _audit(db, current_user["user_id"], "CREATE_JOB_FAMILY", "JOB_FAMILY", row["job_family_id"], {"code": row["code"]})
        db.commit()
        return dict(row)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Mã nhóm ngành đã tồn tại")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.patch("/families/{job_family_id}")
async def update_family(job_family_id: UUID, request: JobFamilyUpdate, current_user: dict = Depends(get_current_user)):
    """Families are never hard-deleted; deactivate them instead. The code is immutable."""
    fields = request.model_dump(exclude_unset=True)
    values = {}
    if fields.get("name") is not None:
        values["name"] = _clean(fields["name"], 200, "Tên nhóm ngành", True)
    if "description" in fields:
        values["description"] = _clean(fields["description"], 2000, "Mô tả")
    for key in ("status", "display_order"):
        if fields.get(key) is not None:
            values[key] = fields[key]
    if not values:
        raise HTTPException(status_code=400, detail="Không có nội dung cần cập nhật")
    db = SessionLocal()
    try:
        _require(library_roles(db, current_user["user_id"]), FAMILY_MANAGERS, "Chỉ Admin hoặc HR Lead quản lý nhóm ngành")
        sets = ", ".join(f"{key} = :{key}" for key in values)
        row = db.execute(text(f"""
            UPDATE app_private.job_families SET {sets}, updated_at = NOW()
            WHERE job_family_id = :id RETURNING *
        """), {**values, "id": str(job_family_id)}).mappings().first()
        if not row:
            raise NotFoundError("Job family")
        _audit(db, current_user["user_id"], "UPDATE_JOB_FAMILY", "JOB_FAMILY", job_family_id, {"fields": sorted(values)})
        db.commit()
        return dict(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------- Templates ----------------

_TEMPLATE_SUMMARY = """
    SELECT t.*, f.name AS job_family_name, f.code AS job_family_code, creator.display_name AS created_by_name,
           pub.template_version_id AS published_version_id, pub.version_number AS published_version_number,
           pub.published_at,
           draft.template_version_id AS draft_version_id, draft.version_number AS draft_version_number,
           (SELECT COUNT(*) FROM app_private.rubric_template_items i WHERE i.template_version_id = pub.template_version_id) AS published_item_count
    FROM app_private.rubric_templates t
    JOIN app_private.job_families f ON f.job_family_id = t.job_family_id
    LEFT JOIN app_private.user_profiles creator ON creator.user_id = t.created_by
    LEFT JOIN app_private.rubric_template_versions pub ON pub.template_id = t.template_id AND pub.status = 'PUBLISHED'
    LEFT JOIN app_private.rubric_template_versions draft ON draft.template_id = t.template_id AND draft.status = 'DRAFT'
"""


@router.get("/templates")
async def list_templates(job_family_id: Optional[UUID] = None, level_band: Optional[str] = Query(None, max_length=100),
                         status_filter: Optional[str] = Query(None, alias="status", pattern="^(PUBLISHED|DRAFT_ONLY|ALL)$"),
                         q: Optional[str] = Query(None, max_length=200), current_user: dict = Depends(get_current_user)):
    search = (q or "").strip()
    pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%" if search else None
    db = SessionLocal()
    try:
        _require(library_roles(db, current_user["user_id"]), LIBRARY_READERS, "Bạn không có quyền xem thư viện rubric")
        rows = db.execute(text(_TEMPLATE_SUMMARY + """
            WHERE t.status = 'ACTIVE'
              AND (CAST(:family AS uuid) IS NULL OR t.job_family_id = CAST(:family AS uuid))
              AND (CAST(:level AS text) IS NULL OR lower(t.level_band) = lower(:level))
              AND (CAST(:pattern AS text) IS NULL OR t.title ILIKE :pattern ESCAPE '\\')
              AND (CAST(:status AS text) IS NULL OR :status = 'ALL'
                   OR (:status = 'PUBLISHED' AND pub.template_version_id IS NOT NULL)
                   OR (:status = 'DRAFT_ONLY' AND pub.template_version_id IS NULL))
            ORDER BY f.display_order, t.title
        """), {"family": str(job_family_id) if job_family_id else None, "level": (level_band or "").strip() or None,
                "pattern": pattern, "status": status_filter}).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(request: TemplateCreate, current_user: dict = Depends(get_current_user)):
    """Create a template with an empty version 1 draft."""
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        _require(library_roles(db, user_id), TEMPLATE_EDITORS, "Chỉ HR mới tạo được template rubric")
        family = db.execute(text("SELECT status FROM app_private.job_families WHERE job_family_id = :id"),
                            {"id": str(request.job_family_id)}).scalar_one_or_none()
        if family != "ACTIVE":
            raise HTTPException(status_code=400, detail="Nhóm ngành không tồn tại hoặc đã ngừng sử dụng")
        template = db.execute(text("""
            INSERT INTO app_private.rubric_templates (job_family_id, title, level_band, created_by)
            VALUES (:family, :title, :level, :user_id) RETURNING *
        """), {"family": str(request.job_family_id), "title": _clean(request.title, 200, "Tên template", True),
                "level": _clean(request.level_band, 100, "Cấp bậc"), "user_id": user_id}).mappings().one()
        version_id = db.execute(text("""
            INSERT INTO app_private.rubric_template_versions (template_id, version_number, change_note, created_by)
            VALUES (:template, 1, :note, :user_id) RETURNING template_version_id
        """), {"template": template["template_id"], "note": _clean(request.change_note, 2000, "Ghi chú thay đổi"),
                "user_id": user_id}).scalar_one()
        _audit(db, user_id, "CREATE_RUBRIC_TEMPLATE", "RUBRIC_TEMPLATE", template["template_id"],
               {"template_version_id": str(version_id)})
        db.commit()
        return {**dict(template), "draft_version_id": version_id}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/templates/{template_id}")
async def get_template(template_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _require(library_roles(db, current_user["user_id"]), LIBRARY_READERS, "Bạn không có quyền xem thư viện rubric")
        template = db.execute(text(_TEMPLATE_SUMMARY + " WHERE t.template_id = :id"), {"id": str(template_id)}).mappings().first()
        if not template:
            raise NotFoundError("Rubric template")
        versions = db.execute(text("""
            SELECT v.template_version_id, v.version_number, v.status, v.mandatory_weight_total, v.nice_to_have_weight_total,
                   v.change_note, v.created_by, v.created_at, v.published_by, v.published_at, v.archived_at,
                   creator.display_name AS created_by_name, publisher.display_name AS published_by_name,
                   (SELECT COUNT(*) FROM app_private.rubric_template_items i WHERE i.template_version_id = v.template_version_id) AS item_count
            FROM app_private.rubric_template_versions v
            LEFT JOIN app_private.user_profiles creator ON creator.user_id = v.created_by
            LEFT JOIN app_private.user_profiles publisher ON publisher.user_id = v.published_by
            WHERE v.template_id = :id ORDER BY v.version_number DESC
        """), {"id": str(template_id)}).mappings().all()
        return {**dict(template), "versions": [dict(row) for row in versions]}
    finally:
        db.close()


def _copy_items(db, source_version_id, target_version_id):
    db.execute(text("""
        INSERT INTO app_private.rubric_template_items (template_version_id, name, description, category, weight_in_group,
            expected_evidence_keywords, evidence_guidance, display_order)
        SELECT :target, name, description, category, weight_in_group, expected_evidence_keywords, evidence_guidance, display_order
        FROM app_private.rubric_template_items WHERE template_version_id = :source
    """), {"target": str(target_version_id), "source": str(source_version_id)})


@router.post("/templates/{template_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_template_version(template_id: UUID, request: TemplateVersionCreate,
                                  current_user: dict = Depends(get_current_user)):
    """New draft copied from a source version (default: the published one, else the latest)."""
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        _require(library_roles(db, user_id), TEMPLATE_EDITORS, "Chỉ HR mới tạo được phiên bản template")
        if not db.execute(text("SELECT 1 FROM app_private.rubric_templates WHERE template_id = :id AND status = 'ACTIVE' FOR UPDATE"),
                          {"id": str(template_id)}).first():
            raise NotFoundError("Rubric template")
        if db.execute(text("SELECT 1 FROM app_private.rubric_template_versions WHERE template_id = :id AND status = 'DRAFT'"),
                      {"id": str(template_id)}).first():
            raise HTTPException(status_code=409, detail="Template đang có một bản nháp. Vui lòng hoàn tất hoặc lưu trữ bản nháp đó trước.")
        source = db.execute(text("""
            SELECT template_version_id, mandatory_weight_total, nice_to_have_weight_total
            FROM app_private.rubric_template_versions
            WHERE template_id = :id AND (CAST(:source AS uuid) IS NULL OR template_version_id = CAST(:source AS uuid))
            ORDER BY (status = 'PUBLISHED') DESC, version_number DESC LIMIT 1
        """), {"id": str(template_id), "source": str(request.source_version_id) if request.source_version_id else None}).mappings().first()
        if request.source_version_id and not source:
            raise HTTPException(status_code=400, detail="Phiên bản nguồn không thuộc template này")
        number = db.execute(text("SELECT COALESCE(MAX(version_number), 0) + 1 FROM app_private.rubric_template_versions WHERE template_id = :id"),
                            {"id": str(template_id)}).scalar_one()
        version_id = db.execute(text("""
            INSERT INTO app_private.rubric_template_versions (template_id, version_number, mandatory_weight_total,
                nice_to_have_weight_total, change_note, created_by)
            VALUES (:template, :number, :mandatory, :nice, :note, :user_id) RETURNING template_version_id
        """), {"template": str(template_id), "number": number,
                "mandatory": source["mandatory_weight_total"] if source else 70, "nice": source["nice_to_have_weight_total"] if source else 30,
                "note": _clean(request.change_note, 2000, "Ghi chú thay đổi"), "user_id": user_id}).scalar_one()
        if source:
            _copy_items(db, source["template_version_id"], version_id)
        _audit(db, user_id, "CREATE_RUBRIC_TEMPLATE_VERSION", "RUBRIC_TEMPLATE_VERSION", version_id,
               {"template_id": str(template_id), "source_version_id": str(source["template_version_id"]) if source else None})
        result = _load_version(db, version_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------- Template versions & items ----------------

def _load_version(db, version_id) -> dict:
    version = db.execute(text("""
        SELECT v.*, t.title, t.level_band, t.job_family_id, f.name AS job_family_name,
               creator.display_name AS created_by_name, publisher.display_name AS published_by_name
        FROM app_private.rubric_template_versions v
        JOIN app_private.rubric_templates t ON t.template_id = v.template_id
        JOIN app_private.job_families f ON f.job_family_id = t.job_family_id
        LEFT JOIN app_private.user_profiles creator ON creator.user_id = v.created_by
        LEFT JOIN app_private.user_profiles publisher ON publisher.user_id = v.published_by
        WHERE v.template_version_id = :id
    """), {"id": str(version_id)}).mappings().first()
    if not version:
        raise NotFoundError("Rubric template version")
    result = dict(version)
    result["items"] = [dict(row) for row in db.execute(text("""
        SELECT * FROM app_private.rubric_template_items WHERE template_version_id = :id ORDER BY display_order, template_item_id
    """), {"id": str(version_id)}).mappings().all()]
    result["review_events"] = [dict(row) for row in db.execute(text("""
        SELECT e.event_id, e.decision, e.comment, e.decided_at, e.reviewed_by, p.display_name AS reviewer_name
        FROM app_private.rubric_template_review_events e
        LEFT JOIN app_private.user_profiles p ON p.user_id = e.reviewed_by
        WHERE e.template_version_id = :id ORDER BY e.decided_at, e.event_id
    """), {"id": str(version_id)}).mappings().all()]
    result["fairness_warnings"] = fairness_warnings(result["items"])
    result["publish_errors"] = template_publish_errors(result["mandatory_weight_total"],
                                                       result["nice_to_have_weight_total"], result["items"])
    return result


def _lock_draft(db, version_id, user_id: str) -> dict:
    """Only the draft's author or an HR Lead may edit a DRAFT version."""
    roles = library_roles(db, user_id)
    _require(roles, TEMPLATE_EDITORS, "Chỉ HR mới chỉnh sửa được template")
    version = db.execute(text("""
        SELECT template_version_id, template_id, status, created_by FROM app_private.rubric_template_versions
        WHERE template_version_id = :id FOR UPDATE
    """), {"id": str(version_id)}).mappings().first()
    if not version:
        raise NotFoundError("Rubric template version")
    if version["status"] != "DRAFT":
        raise HTTPException(status_code=400, detail="Chỉ sửa được phiên bản nháp; phiên bản đã xuất bản hoặc lưu trữ là bất biến")
    if "HR_LEAD" not in roles and str(version["created_by"]) != user_id:
        raise HTTPException(status_code=403, detail="Chỉ người tạo bản nháp hoặc HR Lead mới sửa được")
    return dict(version)


@router.get("/template-versions/{version_id}")
async def get_template_version(version_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _require(library_roles(db, current_user["user_id"]), LIBRARY_READERS, "Bạn không có quyền xem thư viện rubric")
        return _load_version(db, version_id)
    finally:
        db.close()


@router.patch("/template-versions/{version_id}")
async def update_template_version(version_id: UUID, request: TemplateVersionUpdate,
                                  current_user: dict = Depends(get_current_user)):
    fields = request.model_dump(exclude_unset=True)
    values = {}
    if fields.get("mandatory_weight_total") is not None:
        values["mandatory_weight_total"] = fields["mandatory_weight_total"]
        values["nice_to_have_weight_total"] = fields["nice_to_have_weight_total"]
    if "change_note" in fields:
        values["change_note"] = _clean(fields["change_note"], 2000, "Ghi chú thay đổi")
    if not values:
        raise HTTPException(status_code=400, detail="Không có nội dung cần cập nhật")
    db = SessionLocal()
    try:
        _lock_draft(db, version_id, current_user["user_id"])
        sets = ", ".join(f"{key} = :{key}" for key in values)
        db.execute(text(f"UPDATE app_private.rubric_template_versions SET {sets}, updated_at = NOW() WHERE template_version_id = :id"),
                   {**values, "id": str(version_id)})
        result = _load_version(db, version_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/template-versions/{version_id}/items", status_code=status.HTTP_201_CREATED)
async def add_template_item(version_id: UUID, request: TemplateItemCreate, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _lock_draft(db, version_id, current_user["user_id"])
        stats = db.execute(text("""
            SELECT COUNT(*) AS total, COALESCE(MAX(display_order), -1) AS last_order
            FROM app_private.rubric_template_items WHERE template_version_id = :id
        """), {"id": str(version_id)}).mappings().one()
        if stats["total"] >= MAX_ITEMS:
            raise HTTPException(status_code=400, detail=f"Một template có tối đa {MAX_ITEMS} tiêu chí")
        row = db.execute(text("""
            INSERT INTO app_private.rubric_template_items (template_version_id, name, description, category, weight_in_group,
                expected_evidence_keywords, evidence_guidance, display_order)
            VALUES (:id, :name, :description, :category, :weight, CAST(:keywords AS jsonb), :guidance, :display_order)
            RETURNING *
        """), {"id": str(version_id), "name": _clean(request.name, 200, "Tên tiêu chí", True),
                "description": _clean(request.description, 4000, "Mô tả tiêu chí", True), "category": request.category.value,
                "weight": request.weight_in_group, "keywords": _keywords(request.expected_evidence_keywords),
                "guidance": _clean(request.evidence_guidance, 4000, "Hướng dẫn bằng chứng"),
                "display_order": stats["last_order"] + 1}).mappings().one()
        db.commit()
        return dict(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _item_version(db, item_id) -> str:
    version_id = db.execute(text("SELECT template_version_id FROM app_private.rubric_template_items WHERE template_item_id = :id"),
                            {"id": str(item_id)}).scalar_one_or_none()
    if not version_id:
        raise NotFoundError("Template item")
    return str(version_id)


@router.patch("/template-items/{item_id}")
async def update_template_item(item_id: UUID, request: TemplateItemUpdate, current_user: dict = Depends(get_current_user)):
    fields = request.model_dump(exclude_unset=True)
    values: dict = {}
    if fields.get("name") is not None:
        values["name"] = _clean(fields["name"], 200, "Tên tiêu chí", True)
    if fields.get("description") is not None:
        values["description"] = _clean(fields["description"], 4000, "Mô tả tiêu chí", True)
    if fields.get("category") is not None:
        values["category"] = fields["category"].value
    for key in ("weight_in_group", "display_order"):
        if fields.get(key) is not None:
            values[key] = fields[key]
    if "expected_evidence_keywords" in fields:
        values["expected_evidence_keywords"] = _keywords(fields["expected_evidence_keywords"])
    if "evidence_guidance" in fields:
        values["evidence_guidance"] = _clean(fields["evidence_guidance"], 4000, "Hướng dẫn bằng chứng")
    if not values:
        raise HTTPException(status_code=400, detail="Không có nội dung cần cập nhật")
    db = SessionLocal()
    try:
        version_id = _item_version(db, item_id)
        _lock_draft(db, version_id, current_user["user_id"])
        sets = ", ".join(f"{key} = CAST(:{key} AS jsonb)" if key == "expected_evidence_keywords" else f"{key} = :{key}"
                         for key in values)
        row = db.execute(text(f"""
            UPDATE app_private.rubric_template_items SET {sets}, updated_at = NOW()
            WHERE template_item_id = :id RETURNING *
        """), {**values, "id": str(item_id)}).mappings().one()
        db.commit()
        return dict(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.delete("/template-items/{item_id}")
async def delete_template_item(item_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        version_id = _item_version(db, item_id)
        _lock_draft(db, version_id, current_user["user_id"])
        db.execute(text("DELETE FROM app_private.rubric_template_items WHERE template_item_id = :id"), {"id": str(item_id)})
        db.commit()
        return {"status": "deleted"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/template-versions/{version_id}/publish")
async def publish_template_version(version_id: UUID, request: TemplateReviewRequest,
                                   current_user: dict = Depends(get_current_user)):
    """HR Lead publishes a draft; the previously published version is archived atomically."""
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        _require(library_roles(db, user_id), {"HR_LEAD"}, "Chỉ HR Lead mới được xuất bản template")
        template_id = db.execute(text("SELECT template_id FROM app_private.rubric_template_versions WHERE template_version_id = :id"),
                                 {"id": str(version_id)}).scalar_one_or_none()
        if not template_id:
            raise NotFoundError("Rubric template version")
        # Lock the template first so two publishes of the same template serialise.
        db.execute(text("SELECT 1 FROM app_private.rubric_templates WHERE template_id = :id FOR UPDATE"), {"id": str(template_id)})
        version = db.execute(text("""
            SELECT status, mandatory_weight_total, nice_to_have_weight_total FROM app_private.rubric_template_versions
            WHERE template_version_id = :id FOR UPDATE
        """), {"id": str(version_id)}).mappings().one()
        if version["status"] != "DRAFT":
            raise HTTPException(status_code=400, detail="Chỉ xuất bản được phiên bản nháp")
        items = [dict(row) for row in db.execute(text("""
            SELECT name, description, category, weight_in_group, expected_evidence_keywords, evidence_guidance
            FROM app_private.rubric_template_items WHERE template_version_id = :id
        """), {"id": str(version_id)}).mappings().all()]
        errors = template_publish_errors(version["mandatory_weight_total"], version["nice_to_have_weight_total"], items)
        if errors:
            raise HTTPException(status_code=400, detail=" ".join(errors))
        previous = db.execute(text("""
            UPDATE app_private.rubric_template_versions SET status = 'ARCHIVED', archived_at = NOW(), updated_at = NOW()
            WHERE template_id = :template AND status = 'PUBLISHED' RETURNING template_version_id
        """), {"template": str(template_id)}).scalars().all()
        db.execute(text("""
            UPDATE app_private.rubric_template_versions
            SET status = 'PUBLISHED', published_by = :user_id, published_at = NOW(), updated_at = NOW()
            WHERE template_version_id = :id
        """), {"user_id": user_id, "id": str(version_id)})
        comment = _clean(request.comment, 2000, "Ghi chú")
        db.execute(text("""
            INSERT INTO app_private.rubric_template_review_events (template_version_id, reviewed_by, decision, comment)
            VALUES (:id, :user_id, 'PUBLISH', :comment)
        """), {"id": str(version_id), "user_id": user_id, "comment": comment})
        _audit(db, user_id, "PUBLISH_RUBRIC_TEMPLATE", "RUBRIC_TEMPLATE_VERSION", version_id,
               {"template_id": str(template_id), "archived_versions": [str(v) for v in previous]})
        result = _load_version(db, version_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/template-versions/{version_id}/archive")
async def archive_template_version(version_id: UUID, request: TemplateReviewRequest,
                                   current_user: dict = Depends(get_current_user)):
    """HR Lead retires a published version or discards a draft. Criteria cloned earlier are unaffected."""
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        _require(library_roles(db, user_id), {"HR_LEAD"}, "Chỉ HR Lead mới được lưu trữ template")
        version = db.execute(text("""
            SELECT template_id, status FROM app_private.rubric_template_versions WHERE template_version_id = :id FOR UPDATE
        """), {"id": str(version_id)}).mappings().first()
        if not version:
            raise NotFoundError("Rubric template version")
        if version["status"] == "ARCHIVED":
            raise HTTPException(status_code=400, detail="Phiên bản đã được lưu trữ")
        db.execute(text("""
            UPDATE app_private.rubric_template_versions SET status = 'ARCHIVED', archived_at = NOW(), updated_at = NOW()
            WHERE template_version_id = :id
        """), {"id": str(version_id)})
        db.execute(text("""
            INSERT INTO app_private.rubric_template_review_events (template_version_id, reviewed_by, decision, comment)
            VALUES (:id, :user_id, 'ARCHIVE', :comment)
        """), {"id": str(version_id), "user_id": user_id, "comment": _clean(request.comment, 2000, "Ghi chú")})
        _audit(db, user_id, "ARCHIVE_RUBRIC_TEMPLATE", "RUBRIC_TEMPLATE_VERSION", version_id,
               {"template_id": str(version["template_id"]), "previous_status": version["status"]})
        result = _load_version(db, version_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
