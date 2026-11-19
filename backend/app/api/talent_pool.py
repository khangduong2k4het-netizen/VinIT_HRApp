"""P3-1 Talent Pool: marking and eligibility (phase 1), scanning and HR decisions (phase 2)."""
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.permissions import check_position_access
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.talent_pool import MARK_REASONS, application_pool_state, eligible_pool, pool_expiry
from app.services.talent_pool_scan import ScanError, enqueue_scan, record_decision, scan_header, scan_results

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
    reference: Optional[str] = Field(default=None, max_length=100)  # tham chiếu văn bản yêu cầu, không chứa dữ liệu cá nhân


def _audit(db, user_id, action, application_id, position_id, metadata):
    db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:u, :a, 'APPLICATION', :o, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
               {"u": user_id, "a": action, "o": application_id, "p": position_id, "m": json.dumps(metadata)})


def _fetch_state_sync(application_id: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        return application_pool_state(db, application_id)
    finally:
        db.close()


async def _require_application_access(application_id: UUID, current_user: dict) -> dict:
    state = await run_in_threadpool(_fetch_state_sync, str(application_id))
    if state is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    await check_position_access(UUID(state["position_id"]), current_user, required_roles=["HR_RECRUITER"])
    return state


def _pool_state_sync(application_id: str, state: dict) -> dict:
    db = SessionLocal()
    try:
        marked = db.execute(text("SELECT 1 FROM app_private.talent_pool_marks WHERE application_id = :a AND removed_at IS NULL"),
                            {"a": application_id}).first() is not None
        return {"marked": marked, "can_mark": state["eligible"], "reason": state["reason"],
                "reason_text": REASON_TEXT.get(state["reason"]), "expires_on": state["expires_on"]}
    finally:
        db.close()


@router.get("/applications/{application_id}")
async def pool_state(application_id: UUID, current_user: dict = Depends(get_current_user)):
    state = await _require_application_access(application_id, current_user)
    return await run_in_threadpool(_pool_state_sync, str(application_id), state)


def _mark_sync(application_id: str, user_id: str, reason_code: str) -> dict:
    db = SessionLocal()
    try:
        state = application_pool_state(db, application_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
        if not state["eligible"]:
            raise HTTPException(status_code=409, detail=REASON_TEXT[state["reason"]])
        existing = db.execute(text("SELECT 1 FROM app_private.talent_pool_marks WHERE application_id = :a AND removed_at IS NULL"),
                              {"a": application_id}).first()
        if existing:
            raise HTTPException(status_code=409, detail="Hồ sơ đã nằm trong Talent Pool")
        try:
            with db.begin_nested():
                db.execute(text("INSERT INTO app_private.talent_pool_marks(application_id, marked_by, reason_code) VALUES (:a, :u, :r)"),
                           {"a": application_id, "u": user_id, "r": reason_code})
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Hồ sơ đã nằm trong Talent Pool") from None
        _audit(db, user_id, "MARK_TALENT_POOL", application_id, state["position_id"], {"reason_code": reason_code})
        db.commit()
        return {"marked": True}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/applications/{application_id}/mark", status_code=201)
async def mark(application_id: UUID, body: MarkInput, current_user: dict = Depends(get_current_user)):
    if body.reason_code not in MARK_REASONS:
        raise HTTPException(status_code=400, detail="Lý do không hợp lệ")
    await _require_application_access(application_id, current_user)
    return await run_in_threadpool(_mark_sync, str(application_id), current_user["user_id"], body.reason_code)


def _unmark_sync(application_id: str, user_id: str, position_id: str) -> dict:
    db = SessionLocal()
    try:
        done = db.execute(text("UPDATE app_private.talent_pool_marks SET removed_at = NOW() WHERE application_id = :a AND removed_at IS NULL"),
                          {"a": application_id}).rowcount
        if not done:
            raise HTTPException(status_code=404, detail="Hồ sơ không nằm trong Talent Pool")
        _audit(db, user_id, "UNMARK_TALENT_POOL", application_id, position_id, {})
        db.commit()
        return {"marked": False}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.delete("/applications/{application_id}/mark")
async def unmark(application_id: UUID, current_user: dict = Depends(get_current_user)):
    state = await _require_application_access(application_id, current_user)
    return await run_in_threadpool(_unmark_sync, str(application_id), current_user["user_id"], state["position_id"])


def _withdraw_sync(application_id: str, user_id: str, position_id: str, reference: Optional[str]) -> dict:
    clean_ref = (reference or "").strip() or None
    evidence_patch = json.dumps({"withdrawal_reference": clean_ref}, ensure_ascii=False) if clean_ref else "{}"
    db = SessionLocal()
    try:
        done = db.execute(text("""UPDATE app_private.application_data_consents
            SET withdrawn_at = NOW(), withdrawn_by = :u,
                evidence = COALESCE(evidence, '{}'::jsonb) || CAST(:ev AS jsonb)
            WHERE application_id = :a AND purpose = 'TALENT_POOL' AND withdrawn_at IS NULL"""),
                          {"a": application_id, "u": user_id, "ev": evidence_patch}).rowcount
        if not done:
            raise HTTPException(status_code=404, detail="Không có đồng ý đang hiệu lực để rút")
        db.execute(text("UPDATE app_private.talent_pool_marks SET removed_at = NOW() WHERE application_id = :a AND removed_at IS NULL"),
                   {"a": application_id})
        _audit(db, user_id, "WITHDRAW_TALENT_POOL_CONSENT", application_id, position_id,
               {"has_reference": bool(clean_ref)})
        db.commit()
        return {"withdrawn": True}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/applications/{application_id}/withdraw-consent")
async def withdraw_consent(application_id: UUID, body: WithdrawInput, current_user: dict = Depends(get_current_user)):
    """HR records a candidate's written request. Scanning stops at once; deletion follows the retention queue."""
    state = await _require_application_access(application_id, current_user)
    return await run_in_threadpool(_withdraw_sync, str(application_id), current_user["user_id"], state["position_id"], body.reference)


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str


_HR_SCOPE_SQL = """
    (EXISTS (SELECT 1 FROM app_private.user_role_assignments ur
             WHERE ur.user_id = :u AND ur.revoked_at IS NULL AND ur.role_code IN ('ADMIN', 'HR_LEAD'))
     OR EXISTS (SELECT 1 FROM app_private.position_assignments pa
                WHERE pa.position_id = a.position_id AND pa.user_id = :u AND pa.revoked_at IS NULL
                  AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD')))
"""


def _list_marks_sync(user_id: str, limit: int, offset: int) -> dict:
    db = SessionLocal()
    try:
        eligible = {str(r["application_id"]): r for r in eligible_pool(db)}
        rows = db.execute(text(f"""
            SELECT m.application_id, m.reason_code, m.marked_at, a.position_id, p.title AS position_title,
                   p.position_code, a.application_status
            FROM app_private.talent_pool_marks m
            JOIN app_private.applications a ON a.application_id = m.application_id
            JOIN app_private.positions p ON p.position_id = a.position_id
            WHERE m.removed_at IS NULL AND {_HR_SCOPE_SQL}
            ORDER BY m.marked_at DESC
            LIMIT :limit OFFSET :offset
        """), {"u": user_id, "limit": limit, "offset": offset}).mappings().all()
        items = []
        for r in rows:
            e = eligible.get(str(r["application_id"]))
            items.append({"application_id": str(r["application_id"]), "reason_code": r["reason_code"],
                          "marked_at": r["marked_at"], "position_id": str(r["position_id"]),
                          "position_title": r["position_title"], "position_code": r["position_code"],
                          "application_status": r["application_status"], "eligible": e is not None,
                          "expires_on": pool_expiry(e["consented_at"]).date().isoformat() if e else None})
        return {"items": items}
    finally:
        db.close()


@router.get("/marks")
async def list_marks(limit: int = Query(default=200, ge=1, le=500), offset: int = Query(default=0, ge=0),
                     current_user: dict = Depends(get_current_user)):
    """Pool applications whose source position the caller handles as HR (all for HR Lead/Admin). No CV content."""
    return await run_in_threadpool(_list_marks_sync, current_user["user_id"], limit, offset)


def _enqueue_sync(position_id: str, user_id: str) -> dict:
    db = SessionLocal()
    try:
        result = enqueue_scan(db, position_id=position_id, user_id=user_id)
        db.commit()
        return result
    except ScanError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/positions/{position_id}/scan", status_code=202)
async def scan_position(position_id: UUID, current_user: dict = Depends(get_current_user)):
    """Queue a rules-only scan of the eligible pool; the worker scores it in the background."""
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER"])
    return await run_in_threadpool(_enqueue_sync, str(position_id), current_user["user_id"])


def _list_scans_sync(position_id: str) -> dict:
    db = SessionLocal()
    try:
        rows = db.execute(text("""SELECT scan_id, created_at, eligible_count, scored_count, skipped_counts, method,
                   status, failed_count, error_message, completed_at
            FROM app_private.talent_pool_scans WHERE position_id = :p ORDER BY created_at DESC LIMIT 20"""),
                          {"p": position_id}).mappings().all()
        return {"items": [{**dict(r), "scan_id": str(r["scan_id"])} for r in rows]}
    finally:
        db.close()


@router.get("/positions/{position_id}/scans")
async def list_scans(position_id: UUID, current_user: dict = Depends(get_current_user)):
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER"])
    return await run_in_threadpool(_list_scans_sync, str(position_id))


def _scan_header_sync(scan_id: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        return scan_header(db, scan_id)
    finally:
        db.close()


async def _require_scan_access(scan_id: UUID, current_user: dict) -> dict:
    header = await run_in_threadpool(_scan_header_sync, str(scan_id))
    if header is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt quét")
    await check_position_access(header["position_id"], current_user, required_roles=["HR_RECRUITER"])
    return header


def _get_scan_sync(scan_id: str, user_id: str) -> dict:
    db = SessionLocal()
    try:
        header = scan_header(db, scan_id)
        if header is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy lượt quét")
        results = scan_results(db, scan_id)
        # Only audit when COMPLETED results are actually viewed; polling PENDING/PROCESSING
        # scans must not flood the append-only audit log with empty view events.
        if header["status"] == "COMPLETED":
            db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
                VALUES (:u, 'VIEW_TALENT_POOL_SCAN', 'TALENT_POOL_SCAN', :s, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
                       {"u": user_id, "s": scan_id, "p": str(header["position_id"]),
                        "m": json.dumps({"result_count": len(results)})})
            db.commit()
        return {**{k: (str(v) if k in ("scan_id", "position_id", "criteria_version_id", "requested_by") else v)
                   for k, v in header.items()},
                "results": results}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: UUID, current_user: dict = Depends(get_current_user)):
    """Ranked results that are still eligible now; results that left the pool are removed first."""
    await _require_scan_access(scan_id, current_user)
    return await run_in_threadpool(_get_scan_sync, str(scan_id), current_user["user_id"])


def _decide_sync(scan_id: str, application_id: str, decision: str, user_id: str, position_id: str) -> dict:
    db = SessionLocal()
    try:
        try:
            done = record_decision(db, scan_id=scan_id, application_id=application_id,
                                   decision=decision, user_id=user_id)
        except ScanError as exc:
            db.commit()  # keep the removal of a result that left the pool
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None
        if not done:
            raise HTTPException(status_code=404, detail="Không có kết quả này trong lượt quét")
        db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES (:u, 'DECIDE_TALENT_POOL_RESULT', 'APPLICATION', :a, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
                   {"u": user_id, "a": application_id, "p": position_id,
                    "m": json.dumps({"scan_id": scan_id, "decision": decision})})
        db.commit()
        return {"decision": decision}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/scans/{scan_id}/results/{application_id}/decision")
async def decide(scan_id: UUID, application_id: UUID, body: DecisionInput, current_user: dict = Depends(get_current_user)):
    """HR records CONTACT / SKIP / LATER. The system never contacts the candidate or creates an application."""
    header = await _require_scan_access(scan_id, current_user)
    return await run_in_threadpool(_decide_sync, str(scan_id), str(application_id), body.decision,
                                   current_user["user_id"], str(header["position_id"]))
