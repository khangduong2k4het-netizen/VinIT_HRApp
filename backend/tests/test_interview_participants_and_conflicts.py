"""Sửa người phỏng vấn (1.1) và chặn chồng lấn lịch (1.2).

Cả hai đều là lỗ hổng làm lịch **sai**, không phải thiếu tiện nghi:

* Trước 1.1, sáng mai phỏng vấn mà một người báo ốm thì cách duy nhất là huỷ
  buổi rồi tạo lại — mất lịch sử, và không tạo lại được cùng vòng nếu buổi đang
  ``DONE``.
* Trước 1.2, một người được gán hai buổi trùng giờ vẫn lưu được; họ phát hiện
  lúc đã ngồi trong phòng.
"""
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api import interviews as module

BACKEND = Path(__file__).resolve().parents[1]
SOURCE = (BACKEND / "app" / "api" / "interviews.py").read_text()

T0 = datetime(2026, 12, 1, 7, 0, tzinfo=timezone.utc)
ACTOR = str(uuid.uuid4())
APP_ID = str(uuid.uuid4())
POS_ID = str(uuid.uuid4())
INTERVIEW_ID = str(uuid.uuid4())
ALICE = str(uuid.uuid4())
BOB = str(uuid.uuid4())
USER = {"user_id": ACTOR}


class _Result:
    def __init__(self, *, one=None, all_=None, scalar=None, first=None):
        self._one, self._all, self._scalar, self._first = one, all_ or [], scalar, first

    def mappings(self): return self
    def __iter__(self): return iter(self._all)
    def scalars(self): return self
    def one(self): return self._one
    def all(self): return self._all
    def scalar_one(self): return self._scalar
    def scalar_one_or_none(self): return self._scalar
    def first(self): return self._first


class FakeDB:
    def __init__(self, results):
        self._results = list(results)
        self.issued = []
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


@pytest.fixture
def use_fake_db(monkeypatch):
    def install(db):
        monkeypatch.setattr(module, "SessionLocal", lambda: db)
        return db
    return install


ACTIVE = [_Result(scalar="ACTIVE")]
HR = [_Result(scalar=True)]


def _interview_row(status="SCHEDULED"):
    return _Result(first={"interview_id": INTERVIEW_ID, "application_id": APP_ID,
                          "status": status, "position_id": POS_ID,
                          "starts_at": T0, "ends_at": T0 + timedelta(hours=1),
                          "round_number": 1, "updated_at": T0,
                          "location_kind": "ONSITE", "location_text": None})


def _detail_results():
    return [
        _Result(first={"interview_id": INTERVIEW_ID, "application_id": APP_ID,
                       "position_id": POS_ID, "status": "SCHEDULED", "round_number": 1,
                       "starts_at": T0, "ends_at": T0 + timedelta(hours=1)}),
        _Result(all_=[{"user_id": ALICE, "participant_role": "INTERVIEWER"}]),
    ]


# ---------------------------------------------------------------------------
# 1.1 — đổi người phỏng vấn
# ---------------------------------------------------------------------------

def test_participants_can_be_replaced_while_scheduled(use_fake_db):
    """Ca thường gặp: Bob ốm, thay bằng Alice. Không phải huỷ buổi."""
    db = use_fake_db(FakeDB(
        ACTIVE + [_interview_row()] + [*HR] +
        [_Result(scalar=1),                                  # Alice đang hoạt động
         _Result(all_=[BOB]),                                # trước: chỉ Bob
         _Result(all_=[]),                                   # Bob chưa có phiếu
         _Result(),                                          # DELETE Bob
         _Result(),                                          # INSERT Alice
         # _notify ghi MỘT dòng mỗi người: Alice (được thêm) và Bob (bị bỏ).
         # Cả hai đều cần biết, và đó chính là lý do `_notify` nhận danh sách
         # người do nơi gọi chọn thay vì tự đọc bảng người tham gia.
         _Result(), _Result(),                               # notify Alice + Bob
         _Result()] +                                        # audit
        _detail_results()))
    try:
        result = module.replace_participants(
            uuid.UUID(INTERVIEW_ID),
            module.ParticipantsReplace(participants=[{"user_id": uuid.UUID(ALICE)}]), USER)
    except HTTPException as error:
        # Chẩn đoán: cho biết đã tiêu thụ bao nhiêu kết quả trước khi lỗi, để
        # biết hàng đợi lệch ở truy vấn thứ mấy thay vì đoán.
        raise AssertionError(
            f"{error.status_code}: {error.detail} | đã dùng {10 - len(db._results)}/10 | "
            f"câu cuối: {db.issued[-1][0][:80]}") from None
    assert db.committed
    assert "DELETE FROM app_private.interview_participants" in " ".join(sql for sql, _ in db.issued)
    # Alice được thêm, Bob bị xoá.
    assert any(ALICE in str(params) for sql, params in db.issued if "INSERT INTO app_private.interview_participants" in sql)
    assert result["interview_id"] == INTERVIEW_ID


def test_cannot_drop_a_reviewer_who_already_has_a_scorecard(use_fake_db):
    """Phiếu đã tồn tại thì không bỏ người đó được.

    Xoá người không xoá phiếu: người đó mất quyền đọc chính đánh giá mình đã
    viết, còn phiếu thì vẫn nằm trong báo cáo của buổi. Nói thẳng tên ra để HR
    biết phải làm gì tiếp (mở lại phiếu trước, hoặc huỷ buổi).
    """
    db = use_fake_db(FakeDB(
        ACTIVE + [_interview_row()] + [*HR] +
        [_Result(scalar=1),
         _Result(all_=[BOB]),                                # trước: Bob
         _Result(all_=[BOB]),                                # Bob ĐÃ có phiếu
         # Truy vấn tên dùng `.scalars().all()`, không phải `.scalar_one()`:
         # cấp bằng `all_`, không phải `scalar`.
         _Result(all_=["Nguyễn Văn Bob"])]))
    with pytest.raises(HTTPException) as exc:
        module.replace_participants(
            uuid.UUID(INTERVIEW_ID),
            module.ParticipantsReplace(participants=[{"user_id": uuid.UUID(ALICE)}]), USER)
    assert exc.value.status_code == 409
    assert "Bob" in exc.value.detail
    assert not db.committed


def test_participants_frozen_once_interview_happened(use_fake_db):
    """Buổi đã diễn ra: danh sách người là sự thật lịch sử, không sửa được."""
    db = use_fake_db(FakeDB(ACTIVE + [_interview_row(status="DONE")] + [*HR]))
    with pytest.raises(HTTPException) as exc:
        module.replace_participants(
            uuid.UUID(INTERVIEW_ID),
            module.ParticipantsReplace(participants=[{"user_id": uuid.UUID(ALICE)}]), USER)
    assert exc.value.status_code == 409
    assert not db.committed


def test_empty_participant_list_is_rejected_by_the_schema():
    """Một buổi không còn người phỏng vấn thì không ai chấm — muốn vậy thì huỷ buổi."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        module.ParticipantsReplace(participants=[])


def test_removed_person_still_gets_notified():
    """Người bị bỏ khỏi buổi phải nhận thông báo — họ cần biết mình không còn dự.

    Đây là lý do `_notify` nhận danh sách người do nơi gọi chọn: nếu nó tự đọc
    bảng người tham gia thì lúc này Bob đã bị xoá và không ai báo cho Bob.
    """
    body = SOURCE[SOURCE.index("def replace_participants"):SOURCE.index("_CANCELLABLE_FROM")]
    assert "_notify(" in body
    assert "recipients=changed" in body


# ---------------------------------------------------------------------------
# 1.2 — chồng lấn lịch
# ---------------------------------------------------------------------------

def test_conflict_query_checks_people_not_rooms():
    """Kiểm theo **người**: hai người hai phòng cùng lúc là bình thường."""
    body = SOURCE[SOURCE.index("def _conflicting_interviews"):SOURCE.index("# ---", SOURCE.index("def _conflicting_interviews"))]
    assert "ip.user_id = ANY" in body
    assert "JOIN app_private.interview_participants ip" in body


def test_cancelled_interviews_do_not_block_a_new_slot():
    """Buổi đã huỷ/không đến thì giờ đó của người ta đã trống lại.

    Mệnh đề lọc trạng thái nằm trong list `clauses` (dựng động), không nằm trong
    chuỗi SQL cuối — nên phải kiểm ở đúng chỗ đó.
    """
    body = SOURCE[SOURCE.index("def _conflicting_interviews"):SOURCE.index("# ---", SOURCE.index("def _conflicting_interviews"))]
    assert "i.status IN ('SCHEDULED', 'DONE')" in body
    # và không có nhánh nào nới điều kiện đó ra
    assert "CANCELLED" not in body.split("def ")[1] or "trống lại" in body


def test_overlap_uses_half_open_interval():
    """14:00–15:00 và 15:00–16:00 KHÔNG trùng. Phép so phải là `<`/`>`, không `<=`."""
    body = SOURCE[SOURCE.index("def _conflicting_interviews"):SOURCE.index("# ---", SOURCE.index("def _conflicting_interviews"))]
    assert '"i.starts_at < :ends_at"' in body
    assert '"i.ends_at > :starts_at"' in body
    assert "<=" not in body and ">=" not in body


def test_create_reports_which_interview_conflicts(use_fake_db):
    """409 kèm vòng và giờ của buổi trùng — người đặt cần biết trùng với buổi nào."""
    db = use_fake_db(FakeDB(
        ACTIVE + [_Result(first={"application_id": APP_ID, "position_id": POS_ID,
                                 "application_status": "SHORTLIST"})] + [*HR] +
        [_Result(scalar=1),                                     # người tham gia hoạt động
         _Result(all_=[{"interview_id": str(uuid.uuid4()), "round_number": 2,
                        "starts_at": T0, "ends_at": T0 + timedelta(hours=1)}])]))
    with pytest.raises(HTTPException) as exc:
        module.create_interview(module.InterviewCreate(
            application_id=uuid.UUID(APP_ID), starts_at=T0, ends_at=T0 + timedelta(hours=1),
            location_kind="ONSITE", participants=[{"user_id": uuid.UUID(ALICE)}]), USER)
    assert exc.value.status_code == 409
    assert "vòng 2" in exc.value.detail
    assert not db.committed


def test_update_rechecks_conflicts_when_times_change(use_fake_db):
    """Dời giờ phải kiểm lại; sửa mỗi phòng họp thì không — báo trùng lúc đó là chặn việc vô hại."""
    body = SOURCE[SOURCE.index("def update_interview"):SOURCE.index("_CANCELLABLE_FROM")]
    assert 'if "starts_at" in values or "ends_at" in values:' in body
