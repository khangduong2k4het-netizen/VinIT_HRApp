"""Lịch phỏng vấn — quyền, chuyển trạng thái, và múi giờ.

Bốn quyết định đã chốt (`doc/DE_XUAT_LICH_PHONG_VAN.md` §1) được khoá ở đây bằng
test, vì chúng là những thứ dễ bị "sửa cho tiện" nhất:

* Q1 — HM **không** tạo được lịch. Cho HM đặt lịch là mở đường vòng qua shortlist.
* Q2 — một buổi nhiều người phỏng vấn; người tham gia phải là tài khoản hoạt động.
* Q3 — vòng bắt buộc, và **hai buổi cùng vòng** bị DB chặn.
* Q4 — chưa gửi thư; **không có cột nào** cho việc đó, để không ai tưởng đã gửi.

Và một điều không nằm trong bốn câu nhưng quan trọng nhất: **lịch là dữ liệu bổ
sung**. Không endpoint nào ở đây đổi trạng thái hồ sơ, và không chốt nào bắt buộc
phải có lịch mới chuyển được trạng thái.
"""
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api import interviews as module

BACKEND = Path(__file__).resolve().parents[1]
SOURCE = (BACKEND / "app" / "api" / "interviews.py").read_text()
MIGRATION = (BACKEND.parent / "supabase" / "migrations" / "00039_interviews.sql").read_text()
API_INIT = (BACKEND / "app" / "api" / "__init__.py").read_text()

T0 = datetime(2026, 12, 1, 7, 0, tzinfo=timezone.utc)   # 14:00 giờ Việt Nam


# ---------------------------------------------------------------------------
# DB giả
# ---------------------------------------------------------------------------

class _Result:
    def __init__(self, *, one=None, all_=None, scalar=None, first=None):
        self._one, self._all, self._scalar, self._first = one, all_ or [], scalar, first

    def mappings(self): return self
    # Code thật có chỗ lặp thẳng trên kết quả `.mappings()` mà không gọi `.all()`
    # (danh sách người tham gia). Không cho lặp được thì test giả sẽ khác DB thật.
    def __iter__(self): return iter(self._all)
    def scalars(self): return self
    def one(self): return self._one
    def all(self): return self._all
    def scalar_one(self): return self._scalar
    def scalar_one_or_none(self): return self._scalar
    def first(self): return self._first


class FakeDB:
    def __init__(self, results):
        self._results = list(results); self.issued = []
        self.committed = self.rolled_back = False

    def execute(self, statement, params=None):
        self.issued.append((str(statement), params or {}))
        if not self._results:
            raise AssertionError(f"execute thừa: {str(statement)[:90]}")
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def commit(self): self.committed = True
    def rollback(self): self.rolled_back = True
    def close(self): pass


ACTOR = str(uuid.uuid4())
APP_ID = str(uuid.uuid4())
POS_ID = str(uuid.uuid4())
INTERVIEW_ID = str(uuid.uuid4())
OTHER_USER = str(uuid.uuid4())
USER = {"user_id": ACTOR}

ACTIVE = [_Result(scalar="ACTIVE")]
HR = [_Result(scalar=True)]   # kết quả của truy vấn is_hr trong _actor_position_access


def _app_row(status="SHORTLIST"):
    return _Result(first={"application_id": APP_ID, "position_id": POS_ID,
                          "application_status": status})


@pytest.fixture
def use_fake_db(monkeypatch):
    def install(db):
        monkeypatch.setattr(module, "SessionLocal", lambda: db)
        return db
    return install


def _detail_results(interview_id=INTERVIEW_ID):
    return [
        _Result(first={"interview_id": interview_id, "application_id": APP_ID,
                       "position_id": POS_ID, "status": "SCHEDULED", "round_number": 1,
                       "starts_at": T0, "ends_at": T0 + timedelta(hours=1)}),
        _Result(all_=[{"user_id": OTHER_USER, "participant_role": "INTERVIEWER"}]),
    ]


# ---------------------------------------------------------------------------
# Router được nạp
# ---------------------------------------------------------------------------

def test_router_is_imported_and_included():
    import_line = API_INIT.split("from . import", 1)[1].split("\n", 1)[0]
    assert "interviews" in import_line
    assert 'api_router.include_router(interviews.router, prefix="/interviews"' in API_INIT


def test_no_delete_route():
    """Huỷ buổi là đổi trạng thái, không xoá — lịch sử phải còn."""
    assert "@router.delete" not in SOURCE
    assert "DELETE FROM app_private.interviews" not in SOURCE


# ---------------------------------------------------------------------------
# Q3 — thời gian và vòng
# ---------------------------------------------------------------------------

def test_start_time_must_have_a_timezone():
    """Không có offset thì không biết 14:00 là giờ nào — không đoán theo máy chủ."""
    with pytest.raises(ValidationError) as excinfo:
        module.InterviewCreate(application_id=uuid.uuid4(), starts_at=datetime(2026, 12, 1, 14, 0),
                               ends_at=datetime(2026, 12, 1, 15, 0), location_kind="ONSITE",
                               participants=[{"user_id": uuid.uuid4()}])
    assert "múi giờ" in str(excinfo.value)


def test_end_must_be_after_start():
    with pytest.raises(ValidationError):
        module.InterviewCreate(application_id=uuid.uuid4(), starts_at=T0, ends_at=T0,
                               location_kind="ONSITE", participants=[{"user_id": uuid.uuid4()}])


def test_round_number_is_bounded():
    with pytest.raises(ValidationError):
        module.InterviewCreate(application_id=uuid.uuid4(), starts_at=T0,
                               ends_at=T0 + timedelta(hours=1), location_kind="ONSITE",
                               round_number=11, participants=[{"user_id": uuid.uuid4()}])


def test_online_interview_requires_a_link():
    """Hẹn online mà không có link là hẹn suông."""
    with pytest.raises(ValidationError) as excinfo:
        module.InterviewCreate(application_id=uuid.uuid4(), starts_at=T0,
                               ends_at=T0 + timedelta(hours=1), location_kind="ONLINE",
                               participants=[{"user_id": uuid.uuid4()}])
    assert "link" in str(excinfo.value)


def test_onsite_interview_may_leave_the_room_blank():
    """Phòng họp có thể chốt sau; đây là khác biệt có chủ đích với online."""
    payload = module.InterviewCreate(application_id=uuid.uuid4(), starts_at=T0,
                                     ends_at=T0 + timedelta(hours=1), location_kind="ONSITE",
                                     participants=[{"user_id": uuid.uuid4()}])
    assert payload.location_text is None


def test_participants_are_required():
    """Một buổi không có người phỏng vấn là buổi không ai chấm được."""
    with pytest.raises(ValidationError):
        module.InterviewCreate(application_id=uuid.uuid4(), starts_at=T0,
                               ends_at=T0 + timedelta(hours=1), location_kind="ONSITE",
                               participants=[])


def test_duplicate_round_is_a_conflict_not_a_500(use_fake_db):
    """Hai HR đặt cùng vòng: DB phân xử bằng unique index, API dịch thành 409."""
    db = use_fake_db(FakeDB(ACTIVE + [_app_row()] + [*HR, _Result(scalar=1),
        IntegrityError("INSERT", {}, Exception("uq_interviews_active_round")),
    ]))
    with pytest.raises(HTTPException) as excinfo:
        module.create_interview(module.InterviewCreate(
            application_id=uuid.UUID(APP_ID), starts_at=T0, ends_at=T0 + timedelta(hours=1),
            location_kind="ONSITE", participants=[{"user_id": uuid.UUID(OTHER_USER)}]), USER)
    assert excinfo.value.status_code == 409
    assert "vòng 1" in excinfo.value.detail
    assert db.rolled_back and not db.committed


# ---------------------------------------------------------------------------
# Q1 — quyền
# ---------------------------------------------------------------------------

def test_non_hr_cannot_schedule(use_fake_db):
    db = use_fake_db(FakeDB(ACTIVE + [_app_row()] + [_Result(scalar=False)]))
    with pytest.raises(HTTPException) as excinfo:
        module.create_interview(module.InterviewCreate(
            application_id=uuid.UUID(APP_ID), starts_at=T0, ends_at=T0 + timedelta(hours=1),
            location_kind="ONSITE", participants=[{"user_id": uuid.UUID(OTHER_USER)}]), USER)
    assert excinfo.value.status_code == 403
    assert not any("INSERT INTO app_private.interviews" in sql for sql, _ in db.issued)
    assert not db.committed


def test_suspended_account_cannot_schedule(use_fake_db):
    db = use_fake_db(FakeDB([_Result(scalar="SUSPENDED")]))
    with pytest.raises(HTTPException) as excinfo:
        module.create_interview(module.InterviewCreate(
            application_id=uuid.UUID(APP_ID), starts_at=T0, ends_at=T0 + timedelta(hours=1),
            location_kind="ONSITE", participants=[{"user_id": uuid.UUID(OTHER_USER)}]), USER)
    assert excinfo.value.status_code == 403
    assert not db.committed


def test_unknown_application_is_404(use_fake_db):
    use_fake_db(FakeDB(ACTIVE + [_Result(first=None)]))
    with pytest.raises(HTTPException) as excinfo:
        module.create_interview(module.InterviewCreate(
            application_id=uuid.uuid4(), starts_at=T0, ends_at=T0 + timedelta(hours=1),
            location_kind="ONSITE", participants=[{"user_id": uuid.uuid4()}]), USER)
    assert excinfo.value.status_code == 404


def test_cannot_schedule_before_shortlist(use_fake_db):
    """Đặt lịch trước khi sàng lọc là bỏ qua bước sàng lọc."""
    db = use_fake_db(FakeDB(ACTIVE + [_app_row("NEW")] + [_Result(scalar=True)]))
    with pytest.raises(HTTPException) as excinfo:
        module.create_interview(module.InterviewCreate(
            application_id=uuid.UUID(APP_ID), starts_at=T0, ends_at=T0 + timedelta(hours=1),
            location_kind="ONSITE", participants=[{"user_id": uuid.UUID(OTHER_USER)}]), USER)
    assert excinfo.value.status_code == 409
    assert "sàng lọc" in excinfo.value.detail
    assert not db.committed


@pytest.mark.parametrize("status", ["SHORTLIST", "INTERVIEW", "OFFERED"])
def test_shortlisted_and_later_stages_can_be_scheduled(use_fake_db, status):
    db = use_fake_db(FakeDB(ACTIVE + [_app_row(status)] + [
        *HR, _Result(scalar=1), _Result(scalar=INTERVIEW_ID)] +
        [_Result()] * 2 +                       # participant + audit
        _detail_results()))
    result = module.create_interview(module.InterviewCreate(
        application_id=uuid.UUID(APP_ID), starts_at=T0, ends_at=T0 + timedelta(hours=1),
        location_kind="ONSITE", participants=[{"user_id": uuid.UUID(OTHER_USER)}]), USER)
    assert result["interview_id"] == INTERVIEW_ID
    assert db.committed


def test_inactive_participant_is_rejected(use_fake_db):
    """Thêm người không tồn tại thì scorecard của họ không ai nộp, và buổi treo."""
    db = use_fake_db(FakeDB(ACTIVE + [_app_row()] + [*HR, _Result(scalar=0)]))
    with pytest.raises(HTTPException) as excinfo:
        module.create_interview(module.InterviewCreate(
            application_id=uuid.UUID(APP_ID), starts_at=T0, ends_at=T0 + timedelta(hours=1),
            location_kind="ONSITE", participants=[{"user_id": uuid.UUID(OTHER_USER)}]), USER)
    assert excinfo.value.status_code == 400
    assert "không tồn tại" in excinfo.value.detail or "đã đóng" in excinfo.value.detail
    assert not db.committed


# ---------------------------------------------------------------------------
# Ghi nhật ký
# ---------------------------------------------------------------------------

def test_create_writes_an_audit_entry_without_candidate_data(use_fake_db):
    """Audit ghi id và thời điểm, không ghi tên ứng viên hay nội dung trao đổi."""
    db = use_fake_db(FakeDB(ACTIVE + [_app_row()] + [
        *HR, _Result(scalar=1), _Result(scalar=INTERVIEW_ID), _Result(), _Result()] + _detail_results()))
    module.create_interview(module.InterviewCreate(
        application_id=uuid.UUID(APP_ID), starts_at=T0, ends_at=T0 + timedelta(hours=1),
        location_kind="ONLINE", location_text="https://meet.example.test/abc",
        participants=[{"user_id": uuid.UUID(OTHER_USER)}]), USER)
    audit = [(sql, params) for sql, params in db.issued if "audit_events" in sql]
    assert len(audit) == 1
    assert audit[0][1]["action"] == "CREATE_INTERVIEW"
    assert "candidate" not in str(audit[0][1]["metadata"]).lower()


# ---------------------------------------------------------------------------
# Chuyển trạng thái — một chiều
# ---------------------------------------------------------------------------

def _status_db(current, target):
    return FakeDB(ACTIVE + [
        _Result(first={"interview_id": INTERVIEW_ID, "application_id": APP_ID,
                       "status": current, "position_id": POS_ID}),
        _app_row(), *HR,               # _require_hr_write: hồ sơ + là HR
        _Result(),                     # UPDATE
        _Result(),                     # audit
    ] + _detail_results())


def test_scheduled_can_become_done(use_fake_db):
    db = use_fake_db(_status_db("SCHEDULED", "DONE"))
    result = module.change_status(uuid.UUID(INTERVIEW_ID), module.StatusChange(status="DONE"), USER)
    assert result["status"] == "SCHEDULED"  # dữ liệu giả trả nguyên bản
    assert db.committed


@pytest.mark.parametrize("current,target", [("DONE", "SCHEDULED"), ("CANCELLED", "SCHEDULED"),
                                            ("NO_SHOW", "SCHEDULED")])
def test_closed_interviews_cannot_reopen(use_fake_db, current, target):
    """Mở lại là tạo buổi mới cùng vòng — để lịch sử nói đúng "đã huỷ rồi xếp lại"."""
    use_fake_db(_status_db(current, target))
    with pytest.raises(HTTPException) as excinfo:
        module.change_status(uuid.UUID(INTERVIEW_ID), module.StatusChange(status=target), USER)
    assert excinfo.value.status_code == 409


def test_same_status_is_idempotent_and_writes_no_audit(use_fake_db):
    db = use_fake_db(FakeDB(ACTIVE + [
        _Result(first={"interview_id": INTERVIEW_ID, "application_id": APP_ID,
                       "status": "CANCELLED", "position_id": POS_ID}),
        _app_row(), *HR] + _detail_results()))
    module.change_status(uuid.UUID(INTERVIEW_ID), module.StatusChange(status="CANCELLED"), USER)
    assert not [sql for sql, _ in db.issued if "audit_events" in sql]
    assert not [sql for sql, _ in db.issued if sql.strip().startswith("UPDATE")]


def test_invalid_status_is_rejected():
    with pytest.raises(ValidationError):
        module.StatusChange(status="RESCHEDULED")


# ---------------------------------------------------------------------------
# Sửa lịch
# ---------------------------------------------------------------------------

def test_cancelled_interview_cannot_be_edited(use_fake_db):
    use_fake_db(FakeDB(ACTIVE + [
        _Result(first={"interview_id": INTERVIEW_ID, "application_id": APP_ID,
                       "status": "CANCELLED", "position_id": POS_ID, "starts_at": T0,
                       "ends_at": T0 + timedelta(hours=1), "round_number": 1,
                       "updated_at": T0}),
        _app_row(), *HR]))
    with pytest.raises(HTTPException) as excinfo:
        module.update_interview(uuid.UUID(INTERVIEW_ID),
                                module.InterviewUpdate(round_number=2), USER)
    assert excinfo.value.status_code == 409


def test_stale_updated_at_is_rejected(use_fake_db):
    """Hai HR cùng sửa: người sau không ghi đè lên thay đổi của người trước."""
    use_fake_db(FakeDB(ACTIVE + [
        _Result(first={"interview_id": INTERVIEW_ID, "application_id": APP_ID,
                       "status": "SCHEDULED", "position_id": POS_ID, "starts_at": T0,
                       "ends_at": T0 + timedelta(hours=1), "round_number": 1,
                       "updated_at": T0}),
        _app_row(), *HR]))
    with pytest.raises(HTTPException) as excinfo:
        module.update_interview(uuid.UUID(INTERVIEW_ID),
                                module.InterviewUpdate(round_number=2,
                                                       expected_updated_at=T0 - timedelta(hours=1)),
                                USER)
    assert excinfo.value.status_code == 409
    assert "thay đổi" in excinfo.value.detail


def test_update_cannot_move_the_interview_to_another_application():
    """Dời buổi sang hồ sơ khác là huỷ + tạo mới, không phải sửa."""
    assert "application_id" not in module.InterviewUpdate.model_fields


# ---------------------------------------------------------------------------
# Lịch là dữ liệu bổ sung
# ---------------------------------------------------------------------------

def test_no_endpoint_changes_application_status():
    """Lịch không được đổi trạng thái hồ sơ.

    Nếu biến lịch thành điều kiện chuyển trạng thái, mọi hồ sơ đang INTERVIEW
    sẵn có sẽ thành dữ liệu không hợp lệ.
    """
    assert "UPDATE app_private.applications" not in SOURCE
    assert "application_status =" not in SOURCE


def test_migration_has_no_notification_column():
    """Q4 chưa làm. Thêm cột rỗng rồi không ai ghi là dấu hiệu tính năng nửa vời."""
    # Chỉ xét dòng định nghĩa cột: từ khoá này có xuất hiện trong phần chú thích
    # giải thích vì sao KHÔNG thêm nó, và đó là điều nên giữ.
    column_lines = [line for line in MIGRATION.splitlines()
                    if not line.strip().startswith("--")]
    definition = "\n".join(column_lines)
    for forbidden in ("notified_at", "email_sent_at", "reminder_sent_at"):
        assert forbidden not in definition


def test_migration_has_the_partial_unique_index():
    """Vòng bị chặn bởi DB, không bởi kiểm tra trước trong code."""
    assert "CREATE UNIQUE INDEX uq_interviews_active_round" in MIGRATION
    assert "WHERE status IN ('SCHEDULED', 'DONE')" in MIGRATION


def test_migration_restricts_rls_like_other_private_tables():
    assert "ENABLE ROW LEVEL SECURITY" in MIGRATION
    # Dùng FOREACH như 00023 để hai bảng mới có cùng một luật với các bảng cũ.
    assert "FOREACH t IN ARRAY ARRAY['interviews', 'interview_participants'] LOOP" in MIGRATION
    assert "REVOKE ALL ON TABLE app_private.%I FROM PUBLIC, anon, authenticated" in MIGRATION


def test_migration_cascades_from_application():
    """Xoá hồ sơ thì lịch của nó là dữ liệu chết — cascade là đúng."""
    assert "REFERENCES app_private.applications(application_id) ON DELETE CASCADE" in MIGRATION


# ---------------------------------------------------------------------------
# B2 — scorecard theo buổi, và đường share cũ không được vỡ
# ---------------------------------------------------------------------------

SCORECARDS = (BACKEND / "app" / "api" / "scorecards.py").read_text()
MIG40 = (BACKEND.parent / "supabase" / "migrations" / "00040_interview_scorecards.sql").read_text()


def test_scorecard_select_handles_both_sources():
    """Mọi route scorecard đi qua một câu SELECT chung, nên cả hai nguồn phải
    được chuẩn hoá về cùng bộ cột — nếu không, mỗi route phải tự rẽ nhánh và
    sẽ có route quên."""
    assert "LEFT JOIN app_private.interviews i ON i.interview_id = sc.interview_id" in SCORECARDS
    assert "CASE WHEN sc.interview_id IS NOT NULL THEN 'INTERVIEW' ELSE 'SHARE' END AS source_kind" in SCORECARDS


def test_share_path_conditions_are_kept():
    """Đường share giữ nguyên điều kiện cũ: reviewer + shared_with + ACTIVE + vai trò HM.

    Đây là chốt chống hồi quy quan trọng nhất của B2: 8 route cũ đang chạy, và
    nới rào cho đường mới mà vô tình nới luôn đường cũ là mở quyền cho HM khác
    không được share.
    """
    assert "str(row['shared_with']) == actor" in SCORECARDS
    assert "row['share_status'] == 'ACTIVE' and 'HIRING_MANAGER' in assignments" in SCORECARDS


def test_interview_path_does_not_require_a_share():
    """Đường buổi không đòi `shared_with`/`share_status` — buổi không đi qua share.

    Đòi share ACTIVE sẽ khoá scorecard của chính người được phân công phỏng vấn,
    vì họ chưa từng được share shortlist.
    """
    body = SCORECARDS[SCORECARDS.index("if row['source_kind'] == 'INTERVIEW':"):]
    block = body[:body.index("else:")]
    # Bỏ comment: đoạn giải thích nói về `shared_with` để cảnh báo đúng điều
    # đang kiểm, nên so khớp thô sẽ đỏ vì chính lời giải thích.
    code = "\n".join(line for line in block.splitlines()
                     if not line.strip().startswith("#"))
    assert "interview_participants" in code
    assert "shared_with" not in code
    assert "share_status" not in code


def test_interview_scorecard_requires_an_active_interview():
    """Buổi đã huỷ thì người chấm không mở được scorecard của buổi đó."""
    assert "row['interview_status'] in ('SCHEDULED', 'DONE')" in SCORECARDS


def test_active_source_helper_covers_both_branches():
    assert "def _is_active_source(row)" in SCORECARDS
    helper = SCORECARDS[SCORECARDS.index("def _is_active_source"):SCORECARDS.index("def _audit(")]
    assert "share_status" in helper and "interview_status" in helper


def test_generation_requires_done_interview():
    """Chấm trước khi phỏng vấn là chấm dự đoán."""
    assert 'if row["status"] != "DONE":' in SOURCE
    assert "Chỉ chấm điểm sau khi buổi phỏng vấn đã diễn ra" in SOURCE


def test_generation_pins_the_approved_rubric_for_the_current_jd():
    """Cùng định nghĩa `APPROVED cho đúng JD mới nhất` với /careers và criteria.py."""
    gen = SOURCE[SOURCE.index('@router.post("/{interview_id}/scorecards"'):]
    assert "c.status = 'APPROVED'" in gen
    assert "ORDER BY version_number DESC LIMIT 1" in gen


def test_only_interviewers_get_scorecards():
    """OBSERVER dự buổi để nghe, không cho điểm."""
    gen = SOURCE[SOURCE.index('@router.post("/{interview_id}/scorecards"'):]
    assert "ip.participant_role = 'INTERVIEWER'" in gen


def test_generation_is_idempotent():
    """Gọi lại không tạo bản trùng: lọc người đã có scorecard trước khi chèn.

    DB có unique index chặn, nhưng nếu code không lọc thì lần gọi thứ hai sẽ
    nổ IntegrityError thành 500 thay vì trả "không còn ai cần tạo".
    """
    gen = SOURCE[SOURCE.index('@router.post("/{interview_id}/scorecards"'):]
    assert "NOT EXISTS (SELECT 1 FROM app_private.shortlist_scorecards sc" in gen
    assert 'raise HTTPException(409, "Không còn người phỏng vấn nào cần tạo scorecard")' in gen


def test_migration_keeps_old_rows_valid():
    """DROP NOT NULL chỉ nới; dòng cũ vẫn có share_item_id nên vẫn thoả CHECK."""
    assert "ALTER COLUMN share_item_id DROP NOT NULL" in MIG40
    assert "CHECK ((share_item_id IS NOT NULL)::int + (interview_id IS NOT NULL)::int = 1)" in MIG40


def test_migration_prevents_duplicate_reviewer_cards():
    assert "CREATE UNIQUE INDEX uq_scorecard_interview_reviewer" in MIG40


def test_reviewers_see_only_their_own_cards():
    """HR xem tất cả để biết ai chưa nộp; người phỏng vấn chỉ thấy của mình."""
    listing = SOURCE[SOURCE.index('@router.get("/{interview_id}/scorecards"'):]
    assert "(:see_all OR sc.reviewer_user_id = :actor)" in listing
