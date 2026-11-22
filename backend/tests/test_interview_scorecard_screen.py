"""Đường nối chấm điểm: mở phiếu của một buổi phỏng vấn ra được.

Trước đợt sửa này, hành vi thật là: HR bấm "Tạo phiếu chấm điểm", nhận thông báo
"Đã tạo 3 phiếu", rồi **không có màn hình nào mở được** các phiếu đó. Nguyên nhân:
panel chấm duy nhất của app chỉ biết nguồn *share*, còn buổi phỏng vấn không có
share. Người phỏng vấn cũng không có lối nào tới phiếu của chính mình.

Ba thứ được khoá ở đây:

1. `GET /scorecards/interview/{id}` trả **cùng dạng** `_detail` với đường share.
2. Người ngoài không dò được sự tồn tại của buổi qua `[]` hay 404 khác nhau.
3. `/scorecards/reminders` không còn `JOIN` trong vào share — nếu còn, phiếu của
   buổi phỏng vấn không bao giờ được nhắc dù đã quá hạn.
"""
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api import scorecards as module

BACKEND = Path(__file__).resolve().parents[1]
SOURCE = (BACKEND / "app" / "api" / "scorecards.py").read_text()

ACTOR = str(uuid.uuid4())
OTHER = str(uuid.uuid4())
INTERVIEW_ID = str(uuid.uuid4())
CARD_ID = str(uuid.uuid4())


class _Result:
    def __init__(self, *, all_=None, scalar=None, first=None):
        self._all, self._scalar, self._first = all_ or [], scalar, first

    def mappings(self): return self
    def __iter__(self): return iter(self._all)
    def scalars(self): return self
    def all(self): return self._all
    def scalar_one(self): return self._scalar
    def scalar_one_or_none(self): return self._scalar
    def first(self): return self._first


class FakeDB:
    def __init__(self, results):
        self._results = list(results)
        self.issued = []

    def execute(self, statement, params=None):
        self.issued.append((str(statement), params or {}))
        if not self._results:
            raise AssertionError(f"execute thừa: {str(statement)[:90]}")
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def close(self): pass


@pytest.fixture
def use_fake_db(monkeypatch):
    def install(db):
        monkeypatch.setattr(module, "SessionLocal", lambda: db)
        return db
    return install


# ---------------------------------------------------------------------------
# Hợp đồng route
# ---------------------------------------------------------------------------

def test_interview_route_exists_and_is_declared_before_card_id():
    """`/interview/{id}` phải đứng trước `/{card_id}`.

    FastAPI khớp theo thứ tự khai báo. Nếu `/{card_id}` đứng trước, request
    `/scorecards/interview/<uuid>` sẽ khớp vào đó với `card_id="interview"` và
    trả 422 "giá trị không phải UUID" — một lỗi khó đọc cho người dùng và khó
    truy cho người sửa.
    """
    paths = [getattr(route, "path", "") for route in module.router.routes]
    assert "/interview/{interview_id}" in paths
    assert paths.index("/interview/{interview_id}") < paths.index("/{card_id}")


def test_route_returns_full_detail_not_summary():
    """Trả `_detail`, không phải bảng tóm tắt của `/interviews/{id}/scorecards`.

    Bảng tóm tắt không có tiêu chí và không có `can_edit`; dựng màn chấm từ đó
    thì phải gọi thêm N lần và client tự suy quyền — đúng kiểu đã gây lỗi trước.
    """
    body = SOURCE.split("def for_interview", 1)[1].split("@router.get", 1)[0]
    # Trả `_detail` (đầy đủ tiêu chí + cờ quyền), không trả bảng tóm tắt; đi qua
    # bản hàng loạt để không phải N lần đọc cho N phiếu.
    assert "_detail_batch(db, rows, actor)" in body
    assert "_SCORECARD_SELECT" in body


def test_reminders_no_longer_inner_joins_share_items():
    """Nhắc hạn phải phủ cả scorecard của buổi phỏng vấn.

    `JOIN app_private.shortlist_share_items` (JOIN trong) loại mọi dòng có
    `share_item_id IS NULL`, tức toàn bộ phiếu sinh từ buổi. Trước đây đúng như
    vậy: dashboard báo "2 phiếu quá hạn" còn màn nhắc im lặng.
    """
    body = SOURCE.split("def reminders", 1)[1].split("@router.get", 1)[0]
    sql_lines = [line for line in body.split("\n") if not line.strip().startswith("#")]
    sql = "\n".join(sql_lines)
    assert "shortlist_share_items si ON si.share_item_id=sc.share_item_id" in sql
    # và nhánh buổi phỏng vấn phải có mặt
    assert "JOIN app_private.interviews i ON i.interview_id=sc.interview_id" in sql
    # hai nhánh gộp bằng UNION ALL, không phải LEFT JOIN rồi lọc quyền
    assert "UNION ALL" in sql


# ---------------------------------------------------------------------------
# Hành vi
# ---------------------------------------------------------------------------

def _detail_row(**kwargs):
    base = {
        "scorecard_id": CARD_ID, "reviewer_user_id": ACTOR, "status": "IN_PROGRESS",
        "due_at": None, "revision": 1, "share_item_id": None, "share_id": None,
        "share_status": None, "shared_with": None, "application_id": str(uuid.uuid4()),
        "position_id": str(uuid.uuid4()), "assessment_id": None,
        "interview_id": INTERVIEW_ID, "interview_status": "DONE", "interview_round": 2,
        "interview_starts_at": None, "source_kind": "INTERVIEW",
        "criteria_version_id": str(uuid.uuid4()),
    }
    return {**base, **kwargs}


def _row(**kwargs):
    base = {
        "scorecard_id": CARD_ID, "reviewer_user_id": ACTOR, "status": "IN_PROGRESS",
        # `due_at` là NOT NULL trên DB thật (đã kiểm information_schema). Fixture
        # trước đây để None — không làm sai kết quả, nhưng không đại diện: nếu
        # sau này ai bỏ NOT NULL thì test vẫn xanh trong khi production vỡ.
        "due_at": datetime.now(timezone.utc), "revision": 1, "share_item_id": None,
        "share_id": None, "share_status": None, "shared_with": None,
        "application_id": str(uuid.uuid4()), "position_id": str(uuid.uuid4()),
        "assessment_id": None, "interview_id": INTERVIEW_ID, "interview_status": "DONE",
        "interview_round": 2, "interview_starts_at": None, "source_kind": "INTERVIEW",
        "criteria_version_id": str(uuid.uuid4()),
    }
    return {**base, **kwargs}


def test_reviewer_gets_their_own_card(use_fake_db):
    """Người phỏng vấn mở được phiếu của mình và nhận đủ dữ liệu để chấm."""
    db = FakeDB([
        _Result(scalar="ACTIVE"),                         # tài khoản còn hoạt động
        _Result(first={"application_id": str(uuid.uuid4()),
                       "position_id": str(uuid.uuid4())}),
        _Result(first={"application_id": str(uuid.uuid4()),
                       "position_id": str(uuid.uuid4()), "application_status": "SHORTLIST"}),
        _Result(scalar=False),                            # không phải HR phụ trách
        _Result(scalar=True),                             # có tên trong buổi
        _Result(all_=[_row()]),                           # phiếu của chính mình
        # _detail_batch: đọc nền một lần
        _Result(scalar="ACTIVE"),                         # trạng thái tài khoản
        _Result(all_=[]),                                 # vai trò toàn cục
        _Result(all_=[]),                                 # phân công theo vị trí
        _Result(all_=[INTERVIEW_ID]),                     # tư cách người tham gia
        _Result(all_=[{"scorecard_id": CARD_ID, "criterion_id": str(uuid.uuid4()),
                       "name": "Kinh nghiệm", "rating": None, "insufficient_evidence": False,
                       "comment": None, "category": "SKILL", "display_order": 1}]),
    ])
    use_fake_db(db)
    result = module.for_interview(uuid.UUID(INTERVIEW_ID), {"user_id": ACTOR})
    assert len(result) == 1
    assert result[0]["scorecard_id"] == CARD_ID
    assert result[0]["can_edit"] is True
    assert result[0]["criteria"][0]["name"] == "Kinh nghiệm"


def test_outsider_is_refused_even_when_no_cards_exist(use_fake_db):
    """Buổi có thật nhưng chưa sinh phiếu: người ngoài vẫn phải 403.

    Nếu trả `200 []` cho tất cả thì bất kỳ ai đăng nhập cũng dò được "buổi này có
    tồn tại hay không" bằng cách so 200 với 404 — rò rỉ sự tồn tại của lịch
    phỏng vấn, vốn là thông tin gắn với một ứng viên cụ thể.
    """
    db = FakeDB([
        _Result(scalar="ACTIVE"),
        _Result(first={"application_id": str(uuid.uuid4()),
                       "position_id": str(uuid.uuid4())}),
        _Result(first={"application_id": str(uuid.uuid4()), "position_id": str(uuid.uuid4()),
                       "application_status": "SHORTLIST"}),
        _Result(scalar=False),                          # không phải HR
        _Result(scalar=False),                          # không có tên trong buổi
    ])
    use_fake_db(db)
    with pytest.raises(HTTPException) as exc:
        module.for_interview(uuid.UUID(INTERVIEW_ID), {"user_id": OTHER})
    assert exc.value.status_code == 403


def test_unknown_interview_is_404_not_empty_list(use_fake_db):
    """Buổi không tồn tại phải là 404, để màn hình phân biệt được hai ca."""
    db = FakeDB([
        _Result(scalar="ACTIVE"),
        _Result(first=None),        # không có dòng interviews nào
    ])
    use_fake_db(db)
    with pytest.raises(HTTPException) as exc:
        module.for_interview(uuid.UUID(INTERVIEW_ID), {"user_id": ACTOR})
    assert exc.value.status_code == 404


def test_participant_with_no_cards_sees_empty_list(use_fake_db):
    """Người có tên trong buổi, buổi chưa sinh phiếu: danh sách rỗng, không lỗi."""
    db = FakeDB([
        _Result(scalar="ACTIVE"),
        _Result(first={"application_id": str(uuid.uuid4()),
                       "position_id": str(uuid.uuid4())}),
        _Result(first={"application_id": str(uuid.uuid4()), "position_id": str(uuid.uuid4()),
                       "application_status": "SHORTLIST"}),
        _Result(scalar=False),                          # không phải HR
        _Result(scalar=True),                           # có tên trong buổi
        _Result(all_=[]),                               # không phiếu nào
    ])
    use_fake_db(db)
    assert module.for_interview(uuid.UUID(INTERVIEW_ID), {"user_id": ACTOR}) == []
