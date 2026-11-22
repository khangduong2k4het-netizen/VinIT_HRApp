"""Thông báo trong ứng dụng — phạm vi "trong app trước, email sau".

Điều quan trọng nhất được khoá ở đây không phải là API đọc được gì, mà là **cái
gì KHÔNG có**: không cột email, không `sent_at`, không trạng thái "đã gửi". Một
cột như vậy sẽ bị đọc như bằng chứng hệ thống đã gửi thư, trong khi nó chưa gửi
gì. Cùng lý do Q4 của đề xuất gốc không thêm cột thông báo ứng viên.
"""
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api import notifications as module

BACKEND = Path(__file__).resolve().parents[1]
SOURCE = (BACKEND / "app" / "api" / "notifications.py").read_text()
MIGRATION = (BACKEND.parent / "supabase" / "migrations" / "00041_interview_notifications.sql").read_text()
API_INIT = (BACKEND / "app" / "api" / "__init__.py").read_text()

ACTOR = str(uuid.uuid4())
INTERVIEW_ID = str(uuid.uuid4())
NOTIF_ID = str(uuid.uuid4())
USER = {"user_id": ACTOR}


class _Result:
    def __init__(self, *, all_=None, scalar=None, rowcount=0):
        self._all, self._scalar, self.rowcount = all_ or [], scalar, rowcount

    def mappings(self): return self
    def __iter__(self): return iter(self._all)
    def all(self): return self._all
    def scalar_one(self): return self._scalar
    def scalar_one_or_none(self): return self._scalar


class FakeDB:
    def __init__(self, results):
        self._results = list(results)
        self.issued = []
        self.committed = self.rolled_back = False

    def execute(self, statement, params=None):
        self.issued.append((str(statement), params or {}))
        if not self._results:
            raise AssertionError(f"execute thừa: {str(statement)[:80]}")
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
        monkeypatch.setattr(module, "SessionLocal", lambda db=db: db)
        return db
    install.db = None
    def _install(db):
        monkeypatch.setattr(module, "SessionLocal", lambda: db)
        return db
    return _install


# ---------------------------------------------------------------------------
# Phạm vi: trong app, chưa email
# ---------------------------------------------------------------------------

def _declared_columns(sql: str) -> set[str]:
    """Tên cột khai báo trong CREATE TABLE, bỏ comment.

    Bài học: bản đầu của test này tìm chữ "email" trong cả file và đỏ ngay vì
    **lời giải thích** "trong app trước, email sau" — đúng thứ đang được ghi lại
    để người sau không đoán. Test phải kiểm thứ nó định kiểm.
    """
    body = sql[sql.index("CREATE TABLE"):sql.index(");", sql.index("CREATE TABLE"))]
    code = "\n".join(line for line in body.split("\n") if not line.strip().startswith("--"))
    columns = set()
    for line in code.split("\n")[1:]:
        token = line.strip().split(" ")[0].strip(",")
        if token and not token.startswith(("CONSTRAINT", "PRIMARY", "CHECK", ")")):
            columns.add(token)
    return columns


def test_migration_has_no_email_columns():
    """Không cột email/đã gửi. Đây là ràng buộc phạm vi, không phải sở thích."""
    columns = _declared_columns(MIGRATION)
    assert {"notification_id", "user_id", "interview_id", "kind", "read_at"} <= columns
    for forbidden in ("email", "sent_at", "delivered", "notified_at", "sent_to"):
        assert forbidden not in columns, (
            f"cột '{forbidden}' trong migration thông báo: người đọc sau sẽ tưởng "
            "hệ thống đã gửi thư trong khi phạm vi hiện tại chưa gửi")


def test_migration_documents_the_deferral():
    """Ghi rõ 'email là việc sau' ngay trong DB, để quyết định không bị thất lạc."""
    assert "email" in MIGRATION.lower()
    assert "sau" in MIGRATION.lower()


def test_notification_kinds_are_constrained():
    """Chỉ 5 loại đã biết. Loại lạ lọt vào là dấu hiệu ghi sai chỗ."""
    for kind in ("INTERVIEW_CREATED", "INTERVIEW_UPDATED", "INTERVIEW_CANCELLED",
                 "PARTICIPANTS_CHANGED", "SCORECARD_DUE_SOON"):
        assert kind in MIGRATION


def test_router_is_wired():
    assert "notifications" in API_INIT.split("from . import", 1)[1].split("\n", 1)[0]
    assert 'api_router.include_router(notifications.router, prefix="/notifications"' in API_INIT


# ---------------------------------------------------------------------------
# Quyền: mọi câu đều giới hạn ở chính người dùng
# ---------------------------------------------------------------------------

def test_every_notification_query_is_scoped_to_the_actor():
    """`user_id = :actor` phải có trong **mọi** câu, kể cả câu đánh dấu đã đọc.

    Thiếu ở đúng một câu là người dùng đọc được thông báo của người khác — mà
    thông báo chứa vòng phỏng vấn và mã vị trí, tức là thông tin về ứng viên.
    """
    for block in SOURCE.split("@router.")[1:]:
        if "interview_notifications" not in block:
            continue
        assert "user_id = :actor" in block or "user_id=:actor" in block, block[:200]


def test_marking_read_cannot_touch_someone_elses_rows():
    """Truyền id của người khác thì chỉ dòng của mình đổi — điều kiện actor chặn."""
    db = FakeDB([_Result(scalar="ACTIVE"), _Result(rowcount=0)])
    import app.api.notifications as n
    original = module.SessionLocal
    module.SessionLocal = lambda: db
    try:
        result = n.mark_read(n.MarkRead(notification_ids=[uuid.UUID(NOTIF_ID)]), USER)
    finally:
        module.SessionLocal = original
    sql = db.issued[1][0]
    assert "user_id = :actor" in sql
    assert db.committed
    assert result == {"marked": 0}


def test_mark_all_requires_no_ids():
    """"Đọc hết" là một câu UPDATE; bắt client gửi 200 id thì request lớn và trượt."""
    db = FakeDB([_Result(scalar="ACTIVE"), _Result(rowcount=7)])
    import app.api.notifications as n
    original = module.SessionLocal
    module.SessionLocal = lambda: db
    try:
        result = n.mark_read(n.MarkRead(), USER)
    finally:
        module.SessionLocal = original
    assert result == {"marked": 7}
    assert "read_at IS NULL" in db.issued[1][0]


def test_inactive_account_is_refused():
    db = FakeDB([_Result(scalar="DISABLED")])
    import app.api.notifications as n
    original = module.SessionLocal
    module.SessionLocal = lambda: db
    try:
        with pytest.raises(HTTPException) as exc:
            n.list_notifications(user=USER)
    finally:
        module.SessionLocal = original
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Phía tạo: không tự báo cho người vừa thao tác
# ---------------------------------------------------------------------------

def test_actor_is_not_notified_about_their_own_action():
    """Người vừa bấm nút đã biết chuyện gì xảy ra; báo lại chỉ làm badge tăng."""
    src = (BACKEND / "app" / "api" / "interviews.py").read_text()
    notify = src[src.index("def _notify"):src.index("def _participant_ids")]
    assert 'if str(user) != str(actor)' in notify.replace("user)", "user)") or "!= str(actor)" in notify
