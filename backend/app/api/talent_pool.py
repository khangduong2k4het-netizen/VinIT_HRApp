"""P3-1 Talent Pool, phase 1: marking and eligibility. Scanning comes later."""
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app.core.permissions import check_position_access
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.talent_pool import MARK_REASONS, application_pool_state

router = APIRouter()

REASON_TEXT = {
    "NO_CONSENT": "Ứng viên chưa đồng ý cho dùng hồ sơ ở vị trí khác",
    "CONSENT_WITHDRAWN": "Ứng viên đã rút đồng ý",
    "RETENTION_EXPIRED": "Hồ sơ đã quá thời hạn lưu",
    "DELETION_PENDING": "Hồ sơ đang chờ xóa hoặc bị tạm hoãn",
    "STATUS_NOT_ELIGIBLE": "Trạng thái hồ sơ chưa đủ điều kiện",
}


class MarkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason_code: str


class WithdrawInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: Optional[str] = None  # tham chiếu văn bản yêu cầu, không chứa dữ liệu cá nhân


def _audit(db, user_id, action, application_id, position_id, metadata):
    db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:u, :a, 'APPLICATION', :o, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
               {"u": user_id, "a": action, "o": application_id, "p": position_id, "m": json.dumps(metadata)})


async def _state_with_access(db, application_id, current_user):
    state = application_pool_state(db, str(application_id))
    if state is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    await check_position_access(UUID(state["position_id"]), current_user, required_roles=["HR_RECRUITER"])
    return state


@router.get("/applications/{application_id}")
async def pool_state(application_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        state = await _state_with_access(db, application_id, current_user)
        marked = db.execute(text("SELECT 1 FROM app_private.talent_pool_marks WHERE application_id = :a AND removed_at IS NULL"),
                            {"a": str(application_id)}).first() is not None
        return {"marked": marked, "can_mark": state["eligible"], "reason": state["reason"],
                "reason_text": REASON_TEXT.get(state["reason"]), "expires_on": state["expires_on"]}
    finally:
        db.close()


@router.post("/applications/{application_id}/mark", status_code=201)
async def mark(application_id: UUID, body: MarkInput, current_user: dict = Depends(get_current_user)):
    if body.reason_code not in MARK_REASONS:
        raise HTTPException(status_code=400, detail="Lý do không hợp lệ")
    db = SessionLocal()
    try:
        state = await _state_with_access(db, application_id, current_user)
        if not state["eligible"]:
            raise HTTPException(status_code=409, detail=REASON_TEXT[state["reason"]])
        existing = db.execute(text("SELECT 1 FROM app_private.talent_pool_marks WHERE application_id = :a AND removed_at IS NULL"),
                              {"a": str(application_id)}).first()
        if existing:
            raise HTTPException(status_code=409, detail="Hồ sơ đã nằm trong Talent Pool")
        db.execute(text("INSERT INTO app_private.talent_pool_marks(application_id, marked_by, reason_code) VALUES (:a, :u, :r)"),
                   {"a": str(application_id), "u": current_user["user_id"], "r": body.reason_code})
        _audit(db, current_user["user_id"], "MARK_TALENT_POOL", str(application_id), state["position_id"], {"reason_code": body.reason_code})
        db.commit()
        return {"marked": True}
    finally:
        db.close()


@router.delete("/applications/{application_id}/mark")
async def unmark(application_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        state = await _state_with_access(db, application_id, current_user)
        done = db.execute(text("UPDATE app_private.talent_pool_marks SET removed_at = NOW() WHERE application_id = :a AND removed_at IS NULL"),
                          {"a": str(application_id)}).rowcount
        if not done:
            raise HTTPException(status_code=404, detail="Hồ sơ không nằm trong Talent Pool")
        _audit(db, current_user["user_id"], "UNMARK_TALENT_POOL", str(application_id), state["position_id"], {})
        db.commit()
        return {"marked": False}
    finally:
        db.close()


@router.post("/applications/{application_id}/withdraw-consent")
async def withdraw_consent(application_id: UUID, body: WithdrawInput, current_user: dict = Depends(get_current_user)):
    """HR records a candidate's written request. Scanning stops at once; deletion follows the retention queue."""
    db = SessionLocal()
    try:
        state = await _state_with_access(db, application_id, current_user)
        done = db.execute(text("""UPDATE app_private.application_data_consents SET withdrawn_at = NOW(), withdrawn_by = :u
            WHERE application_id = :a AND purpose = 'TALENT_POOL' AND withdrawn_at IS NULL"""),
                          {"a": str(application_id), "u": current_user["user_id"]}).rowcount
        if not done:
            raise HTTPException(status_code=404, detail="Không có đồng ý đang hiệu lực để rút")
        db.execute(text("UPDATE app_private.talent_pool_marks SET removed_at = NOW() WHERE application_id = :a AND removed_at IS NULL"),
                   {"a": str(application_id)})
        _audit(db, current_user["user_id"], "WITHDRAW_TALENT_POOL_CONSENT", str(application_id), state["position_id"],
               {"has_reference": bool(body.reference)})
        db.commit()
        return {"withdrawn": True}
    finally:
        db.close()
