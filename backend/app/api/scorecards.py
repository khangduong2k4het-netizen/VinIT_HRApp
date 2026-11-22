"""Snapshot-bound HM scorecards. No candidate data is copied into audit metadata."""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text

from app.core.security import get_current_user
from app.db.database import SessionLocal

router = APIRouter()


def three_business_days(start: datetime) -> datetime:
    # Business weekdays follow Vietnam local time, not UTC midnight.
    result = start.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
    for _ in range(3):
        result += timedelta(days=1)
        while result.weekday() >= 5:
            result += timedelta(days=1)
    return result.astimezone(timezone.utc)


class Rating(BaseModel):
    criterion_id: UUID
    rating: int | None = Field(default=None, ge=1, le=5)
    insufficient_evidence: bool = False
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode='after')
    def only_one(self):
        if self.insufficient_evidence and self.rating is not None:
            raise ValueError('Chọn điểm hoặc thiếu bằng chứng, không chọn cả hai')
        return self


class ScorecardEdit(BaseModel):
    expected_revision: int = Field(ge=1)
    overall_recommendation: Literal['STRONGLY_RECOMMEND', 'RECOMMEND', 'CONSIDER', 'NOT_RECOMMEND'] | None = None
    strengths: str | None = Field(default=None, max_length=3000)
    concerns: str | None = Field(default=None, max_length=3000)
    ratings: list[Rating] = Field(max_length=100)


class Revision(BaseModel):
    expected_revision: int = Field(ge=1)


class Reopen(Revision):
    reason: str = Field(min_length=1, max_length=2000)


# Scorecard có hai nguồn, loại trừ nhau (CHECK trong migration 00040):
#   - đường share shortlist cũ  -> share_item_id NOT NULL
#   - đường buổi phỏng vấn (B2) -> interview_id NOT NULL
# Cả hai được chuẩn hoá về cùng một bộ cột để mọi route bên dưới không phải
# biết mình đang đọc đường nào. `source_kind` chỉ để báo lỗi cho đúng ngữ cảnh.
_SCORECARD_SELECT = """
    SELECT sc.*,
        si.share_id, s.status AS share_status, s.shared_with,
        COALESCE(si.application_id, ia.application_id) AS application_id,
        COALESCE(si.position_id, ia.position_id) AS position_id,
        si.assessment_id,
        i.status AS interview_status, i.round_number AS interview_round,
        i.starts_at AS interview_starts_at,
        CASE WHEN sc.interview_id IS NOT NULL THEN 'INTERVIEW' ELSE 'SHARE' END AS source_kind
    FROM app_private.shortlist_scorecards sc
    LEFT JOIN app_private.shortlist_share_items si ON si.share_item_id = sc.share_item_id
    LEFT JOIN app_private.shortlist_shares s ON s.share_id = si.share_id
    LEFT JOIN app_private.interviews i ON i.interview_id = sc.interview_id
    LEFT JOIN app_private.applications ia ON ia.application_id = i.application_id
"""


def _access(db, card_id, actor, lock=False):
    row = db.execute(text(_SCORECARD_SELECT + ' WHERE sc.scorecard_id=:id'), {'id': str(card_id)}).mappings().first()
    if not row: raise HTTPException(404, 'Không tìm thấy scorecard')
    if lock:
        db.execute(text('SELECT 1 FROM app_private.positions WHERE position_id=:id FOR UPDATE'), {'id': row['position_id']})
        # Re-read after the position lock: assignment, share, or purge may have changed.
        row = db.execute(text(_SCORECARD_SELECT + ' WHERE sc.scorecard_id=:id FOR UPDATE OF sc'), {'id': str(card_id)}).mappings().first()
        if not row: raise HTTPException(404, 'Không tìm thấy scorecard')
    profile = db.execute(text('SELECT account_status FROM app_private.user_profiles WHERE user_id=:actor' + (' FOR SHARE' if lock else '')), {'actor': actor}).scalar_one_or_none()
    if profile != 'ACTIVE': raise HTTPException(403, 'Tài khoản không hoạt động')
    roles = set(db.execute(text('SELECT role_code FROM app_private.user_role_assignments WHERE user_id=:actor AND revoked_at IS NULL' + (' FOR SHARE' if lock else '')), {'actor': actor}).scalars())
    assignments = set(db.execute(text('SELECT position_role FROM app_private.position_assignments WHERE position_id=:position AND user_id=:actor AND revoked_at IS NULL' + (' FOR SHARE' if lock else '')), {'position': row['position_id'], 'actor': actor}).scalars())
    hr = bool(roles.intersection({'ADMIN','HR_LEAD'}) or assignments.intersection({'HR_RECRUITER','HR_LEAD'}))
    if row['source_kind'] == 'INTERVIEW':
        # Người chấm của một buổi là người có tên trong buổi đó. Không đòi
        # `shared_with`/`share_status`: buổi phỏng vấn không đi qua share, và đòi
        # một share ACTIVE sẽ khoá scorecard của chính người được phân công.
        # Trạng thái buổi phải còn hiệu lực — buổi đã huỷ thì không chấm.
        hm = (str(row['reviewer_user_id']) == actor
              and row['interview_status'] in ('SCHEDULED', 'DONE')
              and bool(db.execute(text("SELECT EXISTS (SELECT 1 FROM app_private.interview_participants WHERE interview_id=:i AND user_id=:a)"),
                                  {'i': str(row['interview_id']), 'a': actor}).scalar_one()))
    else:
        hm = (str(row['reviewer_user_id']) == actor and str(row['shared_with']) == actor
              and row['share_status'] == 'ACTIVE' and 'HIRING_MANAGER' in assignments)
    if not hr and not hm: raise HTTPException(403, 'Không có quyền xem scorecard')
    if lock:
        from app.services.retention import position_has_inflight_purge
        if position_has_inflight_purge(db, str(row['position_id'])):
            raise HTTPException(409, 'Vị trí có case xóa đang xử lý hoặc cần phục hồi')
    return row, hr, hm


def _detail(db, row, hr, hm):
    data = dict(row)
    # `share_status` là NULL với scorecard của buổi phỏng vấn. Điều kiện "share còn
    # ACTIVE" chỉ có nghĩa ở đường share; ở đường buổi, điều kiện tương đương là
    # buổi chưa bị huỷ.
    active = (row['share_status'] == 'ACTIVE' if row['source_kind'] == 'SHARE'
              else row['interview_status'] in ('SCHEDULED', 'DONE'))
    data.update({'can_edit': bool(hm and row['status'] != 'SUBMITTED'), 'can_reopen': bool(hr and row['status'] == 'SUBMITTED' and active),
                 'can_change_due': bool(hr and row['status'] != 'SUBMITTED' and active),
                 'can_view_history': hr,
                 'waiting_for_assessment': row['criteria_version_id'] is None,
                 'overdue': row['status'] != 'SUBMITTED' and row['due_at'] < datetime.now(timezone.utc)})
    data['criteria'] = [dict(r) for r in db.execute(text('''SELECT ci.criterion_id,ci.name,ci.description,ci.category,ci.display_order,
        r.rating,r.insufficient_evidence,r.comment FROM app_private.shortlist_scorecard_criteria r
        JOIN app_private.criteria_items ci ON ci.criterion_id=r.criterion_id WHERE r.scorecard_id=:id ORDER BY ci.display_order,ci.criterion_id'''), {'id': row['scorecard_id']}).mappings()]
    return data


def _is_active_source(row) -> bool:
    """Scorecard còn hiệu lực để thao tác: share ACTIVE, hoặc buổi chưa huỷ."""
    if row['source_kind'] == 'INTERVIEW':
        return row['interview_status'] in ('SCHEDULED', 'DONE')
    return row['share_status'] == 'ACTIVE'


def _audit(db, actor, row, action, metadata=None):
    import json
    db.execute(text('''INSERT INTO app_private.audit_events (actor_user_id,action_type,object_type,object_id,position_id,outcome,metadata)
        VALUES (:actor,:action,'SCORECARD',:id,:position,'SUCCESS',CAST(:metadata AS jsonb))'''),
        {'actor': actor, 'action': action, 'id': row['scorecard_id'], 'position': row['position_id'], 'metadata': json.dumps(metadata or {})})


@router.get('/interview/{interview_id}')
def for_interview(interview_id: UUID, user: dict = Depends(get_current_user)):
    """Scorecard của một buổi phỏng vấn, đúng dạng ``_detail`` mà màn chấm cần.

    Vì sao cần route riêng thay vì dùng ``GET /interviews/{id}/scorecards``:
    route kia trả **bảng tóm tắt** (ai nộp, ai chưa) để HR nhìn một dòng một
    người. Màn chấm cần **nội dung** từng tiêu chí kèm cờ ``can_edit``. Dùng bảng
    tóm tắt để dựng màn chấm thì phải gọi thêm từng scorecard một — N+1, và cờ
    quyền lại do client tự suy, đúng thứ đã gây lỗi ở chỗ khác.

    Quyền do ``_access`` quyết từng phiếu: HR thấy cả buổi, người phỏng vấn chỉ
    thấy phiếu của mình, người ngoài 403 ngay phiếu đầu tiên.

    Đường dẫn có tiền tố số nhiều ``/interview/`` để không đụng
    ``/{card_id}``: FastAPI khớp theo thứ tự khai báo, và ``interview`` không
    phải UUID nên lọt xuống ``/{card_id}`` sẽ ra 422 thay vì 404 dễ hiểu.
    """
    db = SessionLocal()
    try:
        ids = db.execute(text("""
            SELECT sc.scorecard_id FROM app_private.shortlist_scorecards sc
            WHERE sc.interview_id = :id ORDER BY sc.created_at, sc.scorecard_id
        """), {"id": str(interview_id)}).scalars().all()
        if not ids:
            # Phân biệt "buổi không tồn tại" với "buổi chưa có phiếu nào": cái
            # đầu là 404, cái sau là danh sách rỗng. Gộp làm một thì màn hình
            # không biết nên báo "không có quyền" hay "chưa sinh phiếu".
            exists = db.execute(text(
                "SELECT EXISTS (SELECT 1 FROM app_private.interviews WHERE interview_id = :id)"
            ), {"id": str(interview_id)}).scalar_one()
            if not exists:
                raise HTTPException(404, "Không tìm thấy buổi phỏng vấn")
            # Buổi có thật nhưng chưa sinh phiếu: vẫn phải kiểm quyền, nếu không
            # người ngoài dò được sự tồn tại của buổi qua mã 200 + [].
            row = db.execute(text("""
                SELECT i.application_id FROM app_private.interviews i WHERE i.interview_id = :id
            """), {"id": str(interview_id)}).mappings().first()
            from app.api.interviews import _actor_position_access
            _, is_hr = _actor_position_access(db, user["user_id"], str(row["application_id"]))
            is_participant = bool(db.execute(text("""
                SELECT EXISTS (SELECT 1 FROM app_private.interview_participants
                                WHERE interview_id = :id AND user_id = :actor)
            """), {"id": str(interview_id), "actor": user["user_id"]}).scalar_one())
            if not is_hr and not is_participant:
                raise HTTPException(403, "Không có quyền xem scorecard của buổi này")
            return []
        return [_detail(db, *_access(db, item, user["user_id"])) for item in ids]
    finally:
        db.close()


@router.get('/share/{share_id}')
def for_share(share_id: UUID, user: dict = Depends(get_current_user)):
    db=SessionLocal()
    try:
        from app.api.shortlist import _get_share
        _get_share(db, str(share_id), user['user_id'])
        ids = db.execute(text('''SELECT sc.scorecard_id FROM app_private.shortlist_scorecards sc
            JOIN app_private.shortlist_share_items si ON si.share_item_id=sc.share_item_id
            WHERE si.share_id=:id ORDER BY sc.created_at,sc.scorecard_id'''), {'id': str(share_id)}).scalars().all()
        return [_detail(db, *_access(db, item, user['user_id'])) for item in ids]
    finally: db.close()


@router.get('/reminders')
def reminders(user: dict = Depends(get_current_user)):
    """Nhắc hạn scorecard, gộp **cả hai nguồn**: share và buổi phỏng vấn.

    Trước đây câu này ``JOIN`` vào ``shortlist_share_items`` nên scorecard sinh
    từ buổi phỏng vấn **không bao giờ** xuất hiện, dù đã quá hạn: ``JOIN`` trong
    loại mọi dòng có ``share_item_id IS NULL``. Hậu quả: dashboard (đọc thẳng
    bảng) báo "2 phiếu quá hạn" còn màn này im lặng — hai chỗ nói khác nhau, và
    người phỏng vấn không nhận được nhắc nào đúng lúc.

    Hai nguồn có "vị trí" và "quyền xem" khác nhau, nên phải ``UNION`` hai nhánh
    đã lọc riêng thay vì một ``LEFT JOIN``: gộp bằng ``LEFT JOIN`` rồi lọc quyền
    sẽ phải viết điều kiện kiểu "hoặc share ACTIVE, hoặc buổi chưa huỷ" ở ba chỗ,
    và mỗi chỗ là một cơ hội đặt sai dấu ngoặc.
    """
    db = SessionLocal()
    try:
        actor = user['user_id']
        if db.execute(text('SELECT account_status FROM app_private.user_profiles WHERE user_id=:actor'), {'actor': actor}).scalar_one_or_none() != 'ACTIVE':
            raise HTTPException(403, 'Tài khoản không hoạt động')
        rows = db.execute(text("""
            WITH nhac AS (
                -- Nguồn 1: share shortlist
                SELECT s.share_id, NULL::uuid AS interview_id, s.position_id,
                       p.position_code, p.title AS position_title,
                       COALESCE(sc.due_at, now()) AS due_at
                FROM app_private.shortlist_scorecards sc
                JOIN app_private.shortlist_share_items si ON si.share_item_id=sc.share_item_id
                JOIN app_private.shortlist_shares s ON s.share_id=si.share_id
                JOIN app_private.positions p ON p.position_id=s.position_id
                WHERE s.status='ACTIVE' AND sc.status <> 'SUBMITTED' AND sc.due_at <= now() + interval '24 hours'
                AND (
                    EXISTS (SELECT 1 FROM app_private.user_role_assignments ur WHERE ur.user_id=:actor AND ur.revoked_at IS NULL AND ur.role_code IN ('ADMIN','HR_LEAD'))
                    OR EXISTS (SELECT 1 FROM app_private.position_assignments pa WHERE pa.position_id=s.position_id AND pa.user_id=:actor AND pa.revoked_at IS NULL AND pa.position_role IN ('HR_RECRUITER','HR_LEAD'))
                    OR (s.shared_with=:actor AND sc.reviewer_user_id=:actor AND EXISTS
                        (SELECT 1 FROM app_private.position_assignments pa WHERE pa.position_id=s.position_id AND pa.user_id=:actor AND pa.position_role='HIRING_MANAGER' AND pa.revoked_at IS NULL))
                )
                UNION ALL
                -- Nguồn 2: buổi phỏng vấn. Buổi đã huỷ/không đến thì không nhắc.
                SELECT NULL::uuid AS share_id, i.interview_id, a.position_id,
                       p.position_code, p.title AS position_title,
                       COALESCE(sc.due_at, now()) AS due_at
                FROM app_private.shortlist_scorecards sc
                JOIN app_private.interviews i ON i.interview_id=sc.interview_id
                JOIN app_private.applications a ON a.application_id=i.application_id
                JOIN app_private.positions p ON p.position_id=a.position_id
                WHERE i.status IN ('SCHEDULED','DONE') AND sc.status <> 'SUBMITTED'
                  AND sc.due_at <= now() + interval '24 hours'
                AND (
                    -- HR phụ trách vị trí thấy mọi phiếu của buổi
                    EXISTS (SELECT 1 FROM app_private.user_role_assignments ur WHERE ur.user_id=:actor AND ur.revoked_at IS NULL AND ur.role_code IN ('ADMIN','HR_LEAD'))
                    OR EXISTS (SELECT 1 FROM app_private.position_assignments pa WHERE pa.position_id=a.position_id AND pa.user_id=:actor AND pa.revoked_at IS NULL AND pa.position_role IN ('HR_RECRUITER','HR_LEAD'))
                    -- người chấm thấy phiếu của chính mình
                    OR (sc.reviewer_user_id=:actor AND EXISTS
                        (SELECT 1 FROM app_private.interview_participants ip WHERE ip.interview_id=i.interview_id AND ip.user_id=:actor))
                )
            )
            SELECT share_id, interview_id, position_id, position_code, position_title,
                COUNT(*) FILTER (WHERE due_at < now()) AS overdue_count,
                COUNT(*) FILTER (WHERE due_at >= now()) AS due_soon_count,
                MIN(due_at) AS earliest_due_at
            FROM nhac
            GROUP BY share_id, interview_id, position_id, position_code, position_title
            ORDER BY MIN(due_at), position_id LIMIT 100
        """), {'actor': actor}).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.get('/{card_id}')
def get_scorecard(card_id: UUID, user: dict = Depends(get_current_user)):
    db=SessionLocal()
    try: return _detail(db, *_access(db, card_id, user['user_id']))
    finally: db.close()


@router.get('/{card_id}/reopen-history')
def reopen_history(card_id: UUID, user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _, hr, _ = _access(db, card_id, user['user_id'])
        if not hr:
            raise HTTPException(403, 'Chỉ HR được xem lý do mở lại')
        return [dict(row) for row in db.execute(text("""SELECT actor_user_id,reason,created_at
            FROM app_private.scorecard_reopen_events WHERE scorecard_id=:id ORDER BY created_at,event_id"""),
            {'id': str(card_id)}).mappings().all()]
    finally:
        db.close()


@router.put('/{card_id}')
def edit_scorecard(card_id: UUID, request: ScorecardEdit, user: dict = Depends(get_current_user)):
    db=SessionLocal()
    try:
        row, hr, hm = _access(db, card_id, user['user_id'], lock=True)
        if not hm: raise HTTPException(403, 'Chỉ HM được giao mới được sửa scorecard')
        if row['status'] == 'SUBMITTED' or row['revision'] != request.expected_revision: raise HTTPException(409, 'Scorecard đã nộp hoặc đã thay đổi')
        if row['criteria_version_id'] is None: raise HTTPException(409, 'Chưa có assessment snapshot; HR cần chia sẻ lại')
        expected = {str(x) for x in db.execute(text('SELECT criterion_id FROM app_private.shortlist_scorecard_criteria WHERE scorecard_id=:id'), {'id': str(card_id)}).scalars()}
        provided = [str(r.criterion_id) for r in request.ratings]
        if len(provided) != len(set(provided)) or set(provided) != expected: raise HTTPException(400, 'Danh sách tiêu chí không khớp snapshot')
        for rating in request.ratings:
            db.execute(text('''UPDATE app_private.shortlist_scorecard_criteria SET rating=:rating,insufficient_evidence=:insufficient,comment=:comment
                WHERE scorecard_id=:id AND criterion_id=:criterion'''), {'id': str(card_id), 'criterion': str(rating.criterion_id), 'rating': rating.rating, 'insufficient': rating.insufficient_evidence, 'comment': rating.comment})
        db.execute(text('''UPDATE app_private.shortlist_scorecards SET status='IN_PROGRESS',overall_recommendation=:recommendation,
            strengths=:strengths,concerns=:concerns,revision=revision+1,updated_at=now() WHERE scorecard_id=:id'''),
            {'id': str(card_id), 'recommendation': request.overall_recommendation, 'strengths': request.strengths, 'concerns': request.concerns})
        _audit(db, user['user_id'], row, 'UPDATE_SCORECARD')
        updated, hr, hm = _access(db, card_id, user['user_id']); result = _detail(db, updated, hr, hm); db.commit(); return result
    except Exception: db.rollback(); raise
    finally: db.close()


@router.post('/{card_id}/submit')
def submit(card_id: UUID, request: Revision, user: dict = Depends(get_current_user)):
    db=SessionLocal()
    try:
        row, hr, hm = _access(db, card_id, user['user_id'], lock=True)
        if not hm: raise HTTPException(403, 'Chỉ HM được giao mới được nộp scorecard')
        if row['status'] == 'SUBMITTED' or row['revision'] != request.expected_revision: raise HTTPException(409, 'Scorecard đã nộp hoặc đã thay đổi')
        incomplete = db.execute(text('''SELECT count(*) AS total,count(*) FILTER (WHERE rating IS NULL AND NOT insufficient_evidence) AS missing
            FROM app_private.shortlist_scorecard_criteria WHERE scorecard_id=:id'''), {'id': str(card_id)}).mappings().one()
        if not row['criteria_version_id'] or not incomplete['total'] or incomplete['missing'] or not (row['overall_recommendation'] or '').strip():
            raise HTTPException(400, 'Cần đánh giá mọi tiêu chí và ghi khuyến nghị tổng thể')
        db.execute(text("UPDATE app_private.shortlist_scorecards SET status='SUBMITTED',submitted_at=now(),updated_at=now(),revision=revision+1 WHERE scorecard_id=:id"), {'id': str(card_id)})
        _audit(db,user['user_id'],row,'SUBMIT_SCORECARD')
        updated,hr,hm=_access(db,card_id,user['user_id']); result=_detail(db,updated,hr,hm); db.commit(); return result
    except Exception: db.rollback(); raise
    finally: db.close()


@router.post('/{card_id}/reopen')
def reopen(card_id: UUID, request: Reopen, user: dict = Depends(get_current_user)):
    db=SessionLocal()
    try:
        row, hr, hm = _access(db,card_id,user['user_id'],lock=True)
        if not hr: raise HTTPException(403, 'Chỉ HR được mở lại scorecard')
        if not request.reason.strip(): raise HTTPException(400, 'Cần lý do mở lại')
        if not _is_active_source(row) or row['status'] != 'SUBMITTED' or row['revision'] != request.expected_revision: raise HTTPException(409, 'Share hoặc scorecard đã thay đổi')
        db.execute(text("UPDATE app_private.shortlist_scorecards SET status='IN_PROGRESS',submitted_at=NULL,updated_at=now(),revision=revision+1 WHERE scorecard_id=:id"), {'id': str(card_id)})
        # Reason is stored in a dedicated event table, not the shared audit chain or logs.
        db.execute(text('INSERT INTO app_private.scorecard_reopen_events(scorecard_id,actor_user_id,reason) VALUES (:id,:actor,:reason)'), {'id': str(card_id), 'actor': user['user_id'], 'reason': request.reason.strip()})
        _audit(db,user['user_id'],row,'REOPEN_SCORECARD')
        updated,hr,hm=_access(db,card_id,user['user_id']); result=_detail(db,updated,hr,hm); db.commit(); return result
    except Exception: db.rollback(); raise
    finally: db.close()


class DueDate(Revision):
    due_at: datetime

    @model_validator(mode='after')
    def future_aware(self):
        if self.due_at.tzinfo is None or self.due_at.utcoffset() is None:
            raise ValueError('Hạn phản hồi cần múi giờ')
        if self.due_at <= datetime.now(timezone.utc):
            raise ValueError('Hạn phản hồi phải ở tương lai')
        return self


@router.put('/{card_id}/due-date')
def change_due_date(card_id: UUID, request: DueDate, user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        row, hr, hm = _access(db, card_id, user['user_id'], lock=True)
        if not hr:
            raise HTTPException(403, 'Chỉ HR được đổi hạn phản hồi')
        if not _is_active_source(row) or row['status'] == 'SUBMITTED' or row['revision'] != request.expected_revision:
            raise HTTPException(409, 'Share hoặc scorecard đã thay đổi')
        db.execute(text('''UPDATE app_private.shortlist_scorecards SET due_at=:due, revision=revision+1,
            updated_at=now() WHERE scorecard_id=:id'''), {'id': str(card_id), 'due': request.due_at})
        _audit(db, user['user_id'], row, 'CHANGE_SCORECARD_DUE_DATE',
               {'previous_due_at': row['due_at'].isoformat(), 'due_at': request.due_at.isoformat()})
        updated, hr, hm = _access(db, card_id, user['user_id'])
        result = _detail(db, updated, hr, hm)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
