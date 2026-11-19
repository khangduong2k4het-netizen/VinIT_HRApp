"""Human profile corrections and HR-private notes; never passed to AI as notes."""
import json
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.core.exceptions import NotFoundError
from app.core.permissions import application_access
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.cross_duplicates import refresh_application

router = APIRouter()


class ProfileFactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_type: Literal["EDUCATION", "WORK_EXPERIENCE", "SKILL", "CERTIFICATION", "LANGUAGE", "PROJECT"]
    fact_value: dict[str, Any]
    source_page_number: int | None = Field(default=None, ge=1, le=10000)


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_profile_version_id: UUID | None = None
    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=60)
    facts: list[ProfileFactInput] = Field(default_factory=list, max_length=200)


class PrivateNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=5000)


def _position_id(db, application_id: UUID) -> str:
    position = db.execute(text("SELECT position_id FROM app_private.applications WHERE application_id = :id"),
                          {"id": str(application_id)}).scalar_one_or_none()
    if not position:
        raise NotFoundError("Application")
    return str(position)


def _require_hr_locked(db, user_id: str, position_id: str, *, include_admin: bool = False) -> None:
    """Recheck active roles under row locks so revocation cannot race a write."""
    account = db.execute(text("SELECT account_status FROM app_private.user_profiles WHERE user_id = :id FOR SHARE"),
                         {"id": user_id}).scalar_one_or_none()
    if account != "ACTIVE":
        raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt hoặc đã bị khóa")
    roles = ["HR_LEAD", "ADMIN"] if include_admin else ["HR_LEAD"]
    global_roles = db.execute(text("""
        SELECT role_code FROM app_private.user_role_assignments
        WHERE user_id = :user AND revoked_at IS NULL AND role_code = ANY(:roles) FOR SHARE
    """), {"user": user_id, "roles": roles}).scalars().all()
    assigned = db.execute(text("""
        SELECT position_role FROM app_private.position_assignments
        WHERE position_id = :position AND user_id = :user AND revoked_at IS NULL
          AND position_role IN ('HR_RECRUITER', 'HR_LEAD') FOR SHARE
    """), {"position": position_id, "user": user_id}).scalars().all()
    if not global_roles and not assigned:
        raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới có quyền thực hiện thao tác này")


def _load_profile(db, application_id: str) -> dict:
    profile = db.execute(text("""
        SELECT profile_version_id, version_number, source_document_id, extraction_config, status, created_at, created_by
        FROM app_private.profile_versions WHERE application_id = :id AND status = 'COMPLETED'
        ORDER BY version_number DESC LIMIT 1
    """), {"id": application_id}).mappings().first()
    identity = db.execute(text("""
        SELECT display_name, email, phone FROM app_private.application_identities WHERE application_id = :id
    """), {"id": application_id}).mappings().first()
    result = dict(profile) if profile else {"profile_version_id": None, "version_number": 0}
    result["identity"] = dict(identity) if identity else {}
    result["facts"] = []
    if profile:
        result["facts"] = [dict(row) for row in db.execute(text("""
            SELECT fact_id, fact_type, fact_value, source_page_number, confidence
            FROM app_private.profile_facts WHERE profile_version_id = :id ORDER BY fact_type, fact_id
        """), {"id": profile["profile_version_id"]}).mappings().all()]
    return result


@router.get("/{application_id}/profile")
async def get_profile(application_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        position = _position_id(db, application_id)
        access = application_access(current_user["user_id"], position, str(application_id))
        if not access["can_view_cv"]:
            raise HTTPException(status_code=403, detail="Shortlist này chỉ cho phép xem tóm tắt")
        return _load_profile(db, str(application_id))
    finally:
        db.close()


@router.put("/{application_id}/profile")
async def update_profile(application_id: UUID, request: ProfileUpdate, current_user: dict = Depends(get_current_user)):
    name = request.display_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tên ứng viên không được để trống")
    # Bound nested JSON and reject non-finite values; it is untrusted HR input.
    try:
        facts_json = [json.dumps(fact.fact_value, ensure_ascii=False, allow_nan=False) for fact in request.facts]
    except (ValueError, TypeError, RecursionError):
        raise HTTPException(status_code=400, detail="Thông tin hồ sơ không hợp lệ") from None
    if any(len(item) > 10_000 for item in facts_json) or sum(map(len, facts_json)) > 100_000:
        raise HTTPException(status_code=400, detail="Thông tin hồ sơ vượt giới hạn cho phép")
    db = SessionLocal()
    try:
        app_id = str(application_id)
        position = _position_id(db, application_id)
        # Same ordering as queue, approval and JD edits, so none can race a new profile.
        db.execute(text("SELECT 1 FROM app_private.positions WHERE position_id = :id FOR UPDATE"), {"id": position})
        app = db.execute(text("SELECT application_id FROM app_private.applications WHERE application_id = :id FOR UPDATE"), {"id": app_id}).first()
        if not app:
            raise NotFoundError("Application")
        _require_hr_locked(db, current_user["user_id"], position, include_admin=True)
        if db.execute(text("""
            SELECT 1 FROM app_private.operations WHERE position_id = :id
              AND capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING')
              AND status IN ('PENDING', 'PROCESSING') LIMIT 1
        """), {"id": position}).first():
            raise HTTPException(status_code=409, detail="Vị trí đang xử lý hồ sơ. Vui lòng đợi tác vụ hoàn tất trước khi chỉnh sửa.")
        previous = _load_profile(db, app_id)
        expected = str(request.expected_profile_version_id) if request.expected_profile_version_id else None
        actual = str(previous["profile_version_id"]) if previous["profile_version_id"] else None
        if expected != actual:
            raise HTTPException(status_code=409, detail="Hồ sơ đã thay đổi. Vui lòng tải lại trước khi lưu.")
        source_document = previous.get("source_document_id") or db.execute(text("""
            SELECT document_id FROM app_private.application_documents WHERE application_id = :id AND document_type = 'CV'
            ORDER BY created_at DESC LIMIT 1
        """), {"id": app_id}).scalar_one_or_none()
        if not source_document:
            raise HTTPException(status_code=400, detail="Hồ sơ chưa có CV nguồn để tạo phiên bản profile")
        version = db.execute(text("SELECT COALESCE(MAX(version_number), 0) + 1 FROM app_private.profile_versions WHERE application_id = :id"), {"id": app_id}).scalar_one()
        profile_id = db.execute(text("""
            INSERT INTO app_private.profile_versions
                (application_id, source_document_id, version_number, extraction_config, status, created_by)
            VALUES (:app, :document, :version, CAST(:config AS jsonb), 'COMPLETED', :user)
            RETURNING profile_version_id
        """), {"app": app_id, "document": source_document, "version": version,
                "config": json.dumps({"origin": "HR_MANUAL", "previous_profile_version_id": actual}),
                "user": current_user["user_id"]}).scalar_one()
        for fact, encoded in zip(request.facts, facts_json):
            db.execute(text("""
                INSERT INTO app_private.profile_facts (profile_version_id, fact_type, fact_value, source_page_number, confidence)
                VALUES (:profile, :type, CAST(:value AS jsonb), :page, NULL)
            """), {"profile": profile_id, "type": fact.fact_type, "value": encoded, "page": fact.source_page_number})
        email, phone = (request.email or "").strip() or None, (request.phone or "").strip() or None
        db.execute(text("""
            INSERT INTO app_private.application_identities (application_id, display_name, email, phone)
            VALUES (:id, :name, :email, :phone)
            ON CONFLICT (application_id) DO UPDATE SET display_name = EXCLUDED.display_name,
                email = EXCLUDED.email, phone = EXCLUDED.phone, updated_at = NOW()
        """), {"id": app_id, "name": name, "email": email, "phone": phone})
        if email != previous["identity"].get("email") or phone != previous["identity"].get("phone"):
            # Old automatic duplicate signals no longer reflect the identifiers.
            # New signals are recomputed on the next ranking run.
            db.execute(text("""
                UPDATE app_private.duplicate_signals SET review_status = 'DISMISSED', detector_version = 'identity-changed', reviewed_by = :user, reviewed_at = NOW()
                WHERE review_status = 'PENDING' AND (application_id_1 = :id OR application_id_2 = :id)
            """), {"id": app_id, "user": current_user["user_id"]})
        refresh_application(db, app_id)
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome)
            VALUES (:user, 'UPDATE_PROFILE', 'PROFILE_VERSION', :id, :position, 'SUCCESS')
        """), {"user": current_user["user_id"], "id": profile_id, "position": position})
        db.commit()
        return _load_profile(db, app_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/{application_id}/private-notes")
async def list_private_notes(application_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        position = _position_id(db, application_id)
        _require_hr_locked(db, current_user["user_id"], position)
        return [dict(row) for row in db.execute(text("""
            SELECT n.note_id, n.content, n.created_at, n.created_by, p.display_name AS author_name
            FROM app_private.application_private_notes n
            LEFT JOIN app_private.user_profiles p ON p.user_id = n.created_by
            WHERE n.application_id = :id ORDER BY n.created_at DESC, n.note_id DESC LIMIT 500
        """), {"id": str(application_id)}).mappings().all()]
    finally:
        db.close()


@router.post("/{application_id}/private-notes", status_code=status.HTTP_201_CREATED)
async def add_private_note(application_id: UUID, request: PrivateNoteCreate, current_user: dict = Depends(get_current_user)):
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Vui lòng nhập ghi chú")
    db = SessionLocal()
    try:
        position = _position_id(db, application_id)
        _require_hr_locked(db, current_user["user_id"], position)
        note = db.execute(text("""
            INSERT INTO app_private.application_private_notes (application_id, created_by, content)
            VALUES (:id, :user, :content) RETURNING note_id, created_at
        """), {"id": str(application_id), "user": current_user["user_id"], "content": content}).mappings().one()
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome)
            VALUES (:user, 'ADD_HR_NOTE', 'HR_NOTE', :note, :position, 'SUCCESS')
        """), {"user": current_user["user_id"], "note": note["note_id"], "position": position})
        db.commit()
        return dict(note)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
