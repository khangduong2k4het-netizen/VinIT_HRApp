"""Lịch phỏng vấn — buổi phỏng vấn và người tham gia.

Vì sao module này: hệ thống dừng ở sàng lọc. Trạng thái ``INTERVIEW`` có trong
ma trận chuyển trạng thái từ Phase 1, nhưng không có nơi nào ghi **một buổi**:
ai, khi nào, ở đâu, vòng mấy. "Hồ sơ đang ở vòng phỏng vấn" vì thế chỉ là một
nhãn; HR vẫn giữ lịch ở email/Excel rồi quay lại đổi trạng thái bằng tay.

Bốn quyết định (``doc/DE_XUAT_LICH_PHONG_VAN.md`` §1), đều đã chốt:

* **Ai tạo** (Q1): HR phụ trách vị trí và HR_LEAD. Hiring Manager **không** tạo
  được — HM chỉ thấy hồ sơ đã được share, nên cho HM đặt lịch là mở đường vòng
  qua bước shortlist.
* **Nhiều người một buổi** (Q2): có. Mỗi ``INTERVIEWER`` một scorecard; xem
  ``/interviews/{id}/scorecards``.
* **Vòng** (Q3): bắt buộc, 1..10.
* **Thông báo** (Q4): chưa gửi thư ở vòng này. Không có cột nào cho việc đó, để
  không ai tưởng đã gửi.

**Lịch là dữ liệu bổ sung.** Không có endpoint nào ở đây đổi trạng thái hồ sơ,
và không có chốt nào bắt buộc phải có lịch mới chuyển được trạng thái. Nếu biến
lịch thành điều kiện, mọi hồ sơ đang ``INTERVIEW`` sẽ thành dữ liệu không hợp lệ.

Múi giờ: nhận ISO-8601 **bắt buộc có offset**, lưu UTC, trả nguyên văn UTC kèm
``+00:00``. Giao diện tự hiện theo giờ máy người dùng.
"""
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.security import get_current_user
from app.db.database import SessionLocal

router = APIRouter()

LOCATION_KINDS = ("ONSITE", "ONLINE", "PHONE")
STATUSES = ("SCHEDULED", "DONE", "CANCELLED", "NO_SHOW")


class ParticipantIn(BaseModel):
    user_id: UUID
    participant_role: str = Field(default="INTERVIEWER")

    @model_validator(mode="after")
    def valid_role(self):
        if self.participant_role not in ("INTERVIEWER", "OBSERVER"):
            raise ValueError("Vai trò chỉ có thể là INTERVIEWER hoặc OBSERVER")
        return self


class InterviewCreate(BaseModel):
    application_id: UUID
    round_number: int = Field(default=1, ge=1, le=10)
    starts_at: datetime
    ends_at: datetime
    location_kind: str
    location_text: str | None = Field(default=None, max_length=500)
    participants: list[ParticipantIn] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def check_times_and_location(self):
        # Không có offset thì không biết 14:00 là giờ nào. Chặn ở đây thay vì
        # đoán theo máy chủ — cùng khuôn với `application_deadline_at` ở
        # positions.py, để hai chỗ đặt thời gian có cùng một luật.
        for value, label in ((self.starts_at, "Bắt đầu"), (self.ends_at, "Kết thúc")):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{label} cần múi giờ rõ ràng")
        if self.ends_at <= self.starts_at:
            raise ValueError("Kết thúc phải sau bắt đầu")
        if self.location_kind not in LOCATION_KINDS:
            raise ValueError("Hình thức chỉ có thể là ONSITE, ONLINE hoặc PHONE")
        if self.location_kind != "ONSITE" and not (self.location_text or "").strip():
            raise ValueError("Hẹn online hoặc qua điện thoại cần link hoặc số liên hệ")
        return self


class InterviewUpdate(BaseModel):
    """Sửa lịch. Không cho đổi ``application_id`` — dời buổi sang hồ sơ khác là huỷ + tạo mới."""

    round_number: int | None = Field(default=None, ge=1, le=10)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location_kind: str | None = None
    location_text: str | None = Field(default=None, max_length=500)
    expected_updated_at: datetime | None = None


class StatusChange(BaseModel):
    status: str

    @model_validator(mode="after")
    def valid(self):
        if self.status not in STATUSES:
            raise ValueError("Trạng thái không hợp lệ")
        return self


# ---------------------------------------------------------------------------
# Quyền
# ---------------------------------------------------------------------------

def _actor_position_access(db, actor: str, application_id: str) -> tuple[dict, bool]:
    """Trả (dòng hồ sơ, có phải HR phụ trách/HR_LEAD không).

    Cùng định nghĩa với ``core/permissions._application_access_flags``: ADMIN và
    HR_LEAD toàn cục, hoặc được gán HR_RECRUITER/HR_LEAD cho đúng vị trí đó.
    Không dùng lại hàm kia vì hàm đó 403 khi người xem không có quyền xem hồ sơ;
    ở đây cần biết cả hai trạng thái để xử lý người tham gia (observer/HM chỉ xem).
    """
    row = db.execute(text("""
        SELECT a.application_id, a.position_id, a.status AS application_status
        FROM app_private.applications a WHERE a.application_id = :app
    """), {"app": application_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Không tìm thấy hồ sơ")
    is_hr = bool(db.execute(text("""
        SELECT EXISTS (SELECT 1 FROM app_private.user_role_assignments ur
                        WHERE ur.user_id = :actor AND ur.revoked_at IS NULL
                          AND ur.role_code IN ('ADMIN','HR_LEAD'))
            OR EXISTS (SELECT 1 FROM app_private.position_assignments pa
                        WHERE pa.user_id = :actor AND pa.position_id = :position
                          AND pa.revoked_at IS NULL
                          AND pa.position_role IN ('HR_RECRUITER','HR_LEAD'))
    """), {"actor": actor, "position": str(row["position_id"])}).scalar_one())
    return dict(row), is_hr


def _require_hr_write(db, actor: str, application_id: str) -> dict:
    row, is_hr = _actor_position_access(db, actor, application_id)
    if not is_hr:
        raise HTTPException(403, "Chỉ HR phụ trách vị trí hoặc HR Lead được đặt lịch phỏng vấn")
    return row


def _require_active(db, actor: str) -> None:
    """Tài khoản còn hoạt động. Token còn hạn không có nghĩa là quyền còn."""
    status = db.execute(text(
        "SELECT account_status FROM app_private.user_profiles WHERE user_id = :actor FOR SHARE"
    ), {"actor": actor}).scalar_one_or_none()
    if status != "ACTIVE":
        raise HTTPException(403, "Tài khoản không hoạt động")


def _audit(db, actor, action, interview_id, position_id, metadata=None):
    db.execute(text("""
        INSERT INTO app_private.audit_events
            (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:actor, :action, 'INTERVIEW', :id, :position, 'SUCCESS', CAST(:metadata AS jsonb))
    """), {"actor": actor, "action": action, "id": str(interview_id),
           "position": str(position_id), "metadata": json.dumps(metadata or {})})


# ---------------------------------------------------------------------------
# Đọc
# ---------------------------------------------------------------------------

_INTERVIEW_SELECT = """
    SELECT i.*, a.position_id, a.status AS application_status,
           p.position_code, p.title AS position_title,
           ai.display_name AS candidate_name,
           (SELECT count(*) FROM app_private.interview_participants ip
             WHERE ip.interview_id = i.interview_id) AS participant_count,
           (SELECT count(*) FROM app_private.shortlist_scorecards sc
             WHERE sc.interview_id = i.interview_id AND sc.status = 'SUBMITTED') AS submitted_scorecards,
           (SELECT count(*) FROM app_private.shortlist_scorecards sc
             WHERE sc.interview_id = i.interview_id) AS total_scorecards
    FROM app_private.interviews i
    JOIN app_private.applications a ON a.application_id = i.application_id
    JOIN app_private.positions p ON p.position_id = a.position_id
    LEFT JOIN app_private.application_identities ai ON ai.application_id = a.application_id
"""


def _detail(db, interview_id: str) -> dict:
    row = db.execute(text(_INTERVIEW_SELECT + " WHERE i.interview_id = :id"),
                     {"id": interview_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Không tìm thấy buổi phỏng vấn")
    data = dict(row)
    data["participants"] = [dict(r) for r in db.execute(text("""
        SELECT ip.user_id, ip.participant_role, up.display_name, up.email
        FROM app_private.interview_participants ip
        LEFT JOIN app_private.user_profiles up ON up.user_id = ip.user_id
        WHERE ip.interview_id = :id ORDER BY ip.participant_role, ip.created_at
    """), {"id": interview_id}).mappings()]
    return data


@router.get("")
def list_interviews(position_id: UUID | None = None, from_at: datetime | None = None,
                    to_at: datetime | None = None, mine: bool = Query(False),
                    user: dict = Depends(get_current_user)):
    """Danh sách buổi phỏng vấn trong một khoảng thời gian.

    ``mine=true`` cho màn "Lịch của tôi": chỉ buổi mình là người tham gia.
    Không có ``mine`` thì phải là HR của vị trí (hoặc HR_LEAD/ADMIN) mới xem được
    lịch của vị trí đó — lịch phỏng vấn là thông tin về ứng viên.
    """
    db = SessionLocal()
    try:
        actor = user["user_id"]
        _require_active(db, actor)
        clauses = ["1=1"]
        params: dict = {"actor": actor}
        if position_id:
            allowed = db.execute(text("""
                SELECT EXISTS (SELECT 1 FROM app_private.user_role_assignments ur
                                WHERE ur.user_id = :actor AND ur.revoked_at IS NULL
                                  AND ur.role_code IN ('ADMIN','HR_LEAD'))
                    OR EXISTS (SELECT 1 FROM app_private.position_assignments pa
                                WHERE pa.user_id = :actor AND pa.position_id = :position
                                  AND pa.revoked_at IS NULL
                                  AND pa.position_role IN ('HR_RECRUITER','HR_LEAD'))
            """), {"actor": actor, "position": str(position_id)}).scalar_one()
            if not allowed:
                raise HTTPException(403, "Không có quyền xem lịch của vị trí này")
            clauses.append("a.position_id = :position")
            params["position"] = str(position_id)
        if mine:
            clauses.append("""EXISTS (SELECT 1 FROM app_private.interview_participants ip
                                       WHERE ip.interview_id = i.interview_id
                                         AND ip.user_id = :actor)""")
        if from_at is not None:
            if from_at.tzinfo is None or from_at.utcoffset() is None:
                raise HTTPException(400, "Mốc thời gian cần múi giờ rõ ràng")
            clauses.append("i.starts_at >= :from_at")
            params["from_at"] = from_at
        if to_at is not None:
            if to_at.tzinfo is None or to_at.utcoffset() is None:
                raise HTTPException(400, "Mốc thời gian cần múi giờ rõ ràng")
            clauses.append("i.starts_at < :to_at")
            params["to_at"] = to_at
        rows = db.execute(text(_INTERVIEW_SELECT + " WHERE " + " AND ".join(clauses)
                              + " ORDER BY i.starts_at, i.interview_id LIMIT 200"),
                          params).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.get("/{interview_id}")
def get_interview(interview_id: UUID, user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        actor = user["user_id"]
        _require_active(db, actor)
        row = db.execute(text("""
            SELECT a.application_id, a.position_id FROM app_private.interviews i
            JOIN app_private.applications a ON a.application_id = i.application_id
            WHERE i.interview_id = :id
        """), {"id": str(interview_id)}).mappings().first()
        if not row:
            raise HTTPException(404, "Không tìm thấy buổi phỏng vấn")
        _, is_hr = _actor_position_access(db, actor, str(row["application_id"]))
        is_participant = bool(db.execute(text("""
            SELECT EXISTS (SELECT 1 FROM app_private.interview_participants
                            WHERE interview_id = :id AND user_id = :actor)
        """), {"id": str(interview_id), "actor": actor}).scalar_one())
        if not is_hr and not is_participant:
            raise HTTPException(403, "Không có quyền xem buổi phỏng vấn này")
        return _detail(db, str(interview_id))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Ghi
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_interview(payload: InterviewCreate, user: dict = Depends(get_current_user)):
    """Tạo buổi phỏng vấn + người tham gia trong **một** transaction.

    Hai người tham gia và buổi phải cùng sống hoặc cùng chết: một buổi không có
    người phỏng vấn là buổi không ai chấm được, và sẽ nằm lại trong lịch như một
    lỗi không ai sửa.
    """
    db = SessionLocal()
    try:
        actor = user["user_id"]
        _require_active(db, actor)
        app_row = _require_hr_write(db, actor, str(payload.application_id))
        # Không đặt lịch được cho hồ sơ chưa qua sàng lọc. Nếu chặn ở đây quá
        # tay, HR sẽ thấy lỗi khi muốn mời phỏng vấn thẳng — nhưng cho phép là
        # bỏ qua bước shortlist, và mọi báo cáo "tỉ lệ qua sàng lọc" sai theo.
        if app_row["application_status"] not in ("SHORTLIST", "INTERVIEW", "OFFERED"):
            raise HTTPException(
                409, "Chỉ đặt lịch phỏng vấn cho hồ sơ đã qua sàng lọc (SHORTLIST trở lên)")

        # Người tham gia phải là người dùng đang hoạt động và có vai trò trên hệ
        # thống; thêm một người không tồn tại thì scorecard của họ không ai nộp.
        ids = sorted({str(p.user_id) for p in payload.participants})
        active = db.execute(text("""
            SELECT count(*) FROM app_private.user_profiles
            WHERE user_id = ANY(CAST(:ids AS uuid[])) AND account_status = 'ACTIVE'
        """), {"ids": "{" + ",".join(ids) + "}"}).scalar_one()
        if int(active) != len(ids):
            raise HTTPException(400, "Có người tham gia không tồn tại hoặc tài khoản đã đóng")

        try:
            interview_id = db.execute(text("""
                INSERT INTO app_private.interviews
                    (application_id, round_number, starts_at, ends_at, location_kind, location_text, created_by)
                VALUES (:app, :round, :starts, :ends, :kind, :text, :actor)
                RETURNING interview_id
            """), {
                "app": str(payload.application_id), "round": payload.round_number,
                "starts": payload.starts_at, "ends": payload.ends_at,
                "kind": payload.location_kind,
                "text": (payload.location_text or "").strip() or None, "actor": actor,
            }).scalar_one()
        except IntegrityError:
            db.rollback()
            # Unique index bộ phận, không phải kiểm tra trước: hai HR bấm cùng lúc
            # thì DB mới là chỗ phân xử đúng.
            raise HTTPException(
                409, f"Hồ sơ đã có buổi phỏng vấn vòng {payload.round_number} đang hiệu lực") from None

        for participant in payload.participants:
            db.execute(text("""
                INSERT INTO app_private.interview_participants
                    (interview_id, user_id, participant_role, added_by)
                VALUES (:id, :user, :role, :actor)
                ON CONFLICT (interview_id, user_id) DO NOTHING
            """), {"id": str(interview_id), "user": str(participant.user_id),
                   "role": participant.participant_role, "actor": actor})

        _audit(db, actor, "CREATE_INTERVIEW", interview_id, app_row["position_id"],
               {"round_number": payload.round_number,
                "participants": len(ids),
                "starts_at": payload.starts_at.astimezone(timezone.utc).isoformat()})
        result = _detail(db, str(interview_id))
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.patch("/{interview_id}")
def update_interview(interview_id: UUID, payload: InterviewUpdate,
                     user: dict = Depends(get_current_user)):
    """Sửa giờ/địa điểm/vòng. Không đổi được hồ sơ của buổi."""
    db = SessionLocal()
    try:
        actor = user["user_id"]
        _require_active(db, actor)
        row = db.execute(text("""
            SELECT i.interview_id, i.application_id, i.status, i.starts_at, i.ends_at,
                   i.round_number, i.updated_at, a.position_id
            FROM app_private.interviews i
            JOIN app_private.applications a ON a.application_id = i.application_id
            WHERE i.interview_id = :id FOR UPDATE OF i
        """), {"id": str(interview_id)}).mappings().first()
        if not row:
            raise HTTPException(404, "Không tìm thấy buổi phỏng vấn")
        _require_hr_write(db, actor, str(row["application_id"]))
        if row["status"] in ("DONE", "CANCELLED", "NO_SHOW"):
            raise HTTPException(409, "Buổi đã kết thúc hoặc đã huỷ, không sửa được nữa")
        # Optimistic lock: hai HR cùng mở form sửa thì người sau không ghi đè
        # lên thay đổi của người trước mà không biết.
        if payload.expected_updated_at is not None:
            if payload.expected_updated_at.astimezone(timezone.utc) != row["updated_at"].astimezone(timezone.utc):
                raise HTTPException(409, "Lịch đã được người khác thay đổi, tải lại trước khi sửa")

        values: dict = {}
        for field in ("round_number", "location_kind"):
            value = getattr(payload, field)
            if value is not None:
                values[field] = value
        if payload.location_kind is not None and payload.location_kind not in LOCATION_KINDS:
            raise HTTPException(400, "Hình thức không hợp lệ")
        if payload.location_text is not None:
            values["location_text"] = payload.location_text.strip() or None
        for field in ("starts_at", "ends_at"):
            value = getattr(payload, field)
            if value is not None:
                if value.tzinfo is None or value.utcoffset() is None:
                    raise HTTPException(400, "Mốc thời gian cần múi giờ rõ ràng")
                values[field] = value
        if not values:
            raise HTTPException(400, "Không có nội dung cần cập nhật")

        starts = values.get("starts_at", row["starts_at"])
        ends = values.get("ends_at", row["ends_at"])
        if ends <= starts:
            raise HTTPException(400, "Kết thúc phải sau bắt đầu")
        kind = values.get("location_kind", None)
        if kind is None:
            kind = db.execute(text("SELECT location_kind FROM app_private.interviews WHERE interview_id = :id"),
                              {"id": str(interview_id)}).scalar_one()
        text_value = values.get("location_text", "giữ nguyên")
        if text_value == "giữ nguyên":
            text_value = db.execute(text("SELECT location_text FROM app_private.interviews WHERE interview_id = :id"),
                                    {"id": str(interview_id)}).scalar_one()
        if kind != "ONSITE" and not (text_value or "").strip():
            raise HTTPException(400, "Hẹn online hoặc qua điện thoại cần link hoặc số liên hệ")

        sets = ", ".join(f"{key} = :{key}" for key in values)
        try:
            db.execute(text(f"""
                UPDATE app_private.interviews SET {sets}, updated_at = now()
                WHERE interview_id = :id
            """), {**values, "id": str(interview_id)})
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Vòng này đã có buổi khác đang hiệu lực") from None

        _audit(db, actor, "UPDATE_INTERVIEW", interview_id, row["position_id"],
               {"fields": sorted(values)})
        result = _detail(db, str(interview_id))
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


_CANCELLABLE_FROM = {"SCHEDULED": {"DONE", "CANCELLED", "NO_SHOW"},
                     "DONE": set(), "CANCELLED": set(), "NO_SHOW": set()}


@router.post("/{interview_id}/status")
def change_status(interview_id: UUID, payload: StatusChange,
                  user: dict = Depends(get_current_user)):
    """Chuyển trạng thái buổi: ``SCHEDULED → DONE / CANCELLED / NO_SHOW``.

    Cố ý **một chiều**. Mở lại buổi đã huỷ là tạo buổi mới cùng vòng (unique
    index bộ phận cho phép, vì buổi cũ đã ``CANCELLED``), để lịch sử nói đúng
    "đã huỷ rồi xếp lại" thay vì che mất lần huỷ.
    """
    db = SessionLocal()
    try:
        actor = user["user_id"]
        _require_active(db, actor)
        row = db.execute(text("""
            SELECT i.interview_id, i.application_id, i.status, a.position_id
            FROM app_private.interviews i
            JOIN app_private.applications a ON a.application_id = i.application_id
            WHERE i.interview_id = :id FOR UPDATE OF i
        """), {"id": str(interview_id)}).mappings().first()
        if not row:
            raise HTTPException(404, "Không tìm thấy buổi phỏng vấn")
        _require_hr_write(db, actor, str(row["application_id"]))
        if payload.status == row["status"]:
            # Idempotent: bấm hai lần không phải lỗi, nhưng cũng không ghi audit lần hai.
            return _detail(db, str(interview_id))
        if payload.status not in _CANCELLABLE_FROM[row["status"]]:
            raise HTTPException(
                409, f"Không chuyển được từ {row['status']} sang {payload.status}")
        db.execute(text("""
            UPDATE app_private.interviews SET status = :status, updated_at = now()
            WHERE interview_id = :id
        """), {"status": payload.status, "id": str(interview_id)})
        _audit(db, actor, "CHANGE_INTERVIEW_STATUS", interview_id, row["position_id"],
               {"from": row["status"], "to": payload.status})
        result = _detail(db, str(interview_id))
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
