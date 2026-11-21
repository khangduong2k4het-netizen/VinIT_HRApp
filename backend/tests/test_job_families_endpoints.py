"""Chạy thật các endpoint ``/job-families`` với DB giả.

Vì sao cần lớp test này: test đọc mã nguồn chỉ chứng minh *có* chuỗi ``"409"``
trong file. Nó không chứng minh request trả về 409 — chuỗi đó có thể nằm trong
một nhánh không bao giờ chạy tới. Ở đây endpoint được gọi thật, ``SessionLocal``
bị thay bằng một đối tượng trả kết quả dàn dựng, nên nhánh nào chạy và trả mã
gì đều được kiểm.

Bộ test này **không** thay thế test tích hợp DB thật (đang nằm trong nhóm skip);
nó bắt được lỗi logic nhánh, không bắt được lỗi SQL.
"""
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api import job_families as module


# ---------------------------------------------------------------------------
# DB giả
# ---------------------------------------------------------------------------

class _Result:
    def __init__(self, *, one=None, all_=None, scalar=None, first=None):
        self._one = one
        self._all = all_ if all_ is not None else []
        self._scalar = scalar
        self._first = first

    def mappings(self):
        return self

    def scalars(self):
        return self

    def one(self):
        return self._one

    def all(self):
        return self._all

    def scalar_one(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def first(self):
        return self._first


class FakeDB:
    """Mỗi ``execute`` lấy kết quả kế tiếp trong hàng đợi; lưu lại SQL đã chạy."""

    def __init__(self, results):
        self._results = list(results)
        self.issued = []
        self.committed = False
        self.rolled_back = False

    def execute(self, statement, params=None):
        self.issued.append((str(statement), params or {}))
        if not self._results:
            raise AssertionError(f"execute thừa, không có kết quả dàn dựng cho: {str(statement)[:80]}")
        result = self._results.pop(0)
        # Dàn dựng một exception nghĩa là "câu này nổ" — phải raise, không trả về.
        if isinstance(result, Exception):
            raise result
        return result

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


ADMIN_OK = [_Result(scalar="ACTIVE"), _Result(all_=["ADMIN"])]
NOT_ADMIN = [_Result(scalar="ACTIVE"), _Result(all_=[])]
SUSPENDED = [_Result(scalar="SUSPENDED"), _Result(all_=["ADMIN"])]

USER = {"user_id": str(uuid.uuid4())}


@pytest.fixture
def use_fake_db(monkeypatch):
    def install(db):
        monkeypatch.setattr(module, "SessionLocal", lambda: db)
        return db
    return install


# ---------------------------------------------------------------------------
# Quyền
# ---------------------------------------------------------------------------

def test_non_admin_cannot_create(use_fake_db):
    db = use_fake_db(FakeDB(NOT_ADMIN))
    with pytest.raises(HTTPException) as excinfo:
        module.create_job_family(module.JobFamilyCreate(code="NEW_FAMILY", name="Nhóm mới"), USER)
    assert excinfo.value.status_code == 403
    assert not db.committed
    assert not any("INSERT INTO app_private.job_families" in sql for sql, _ in db.issued)


def test_suspended_admin_cannot_create(use_fake_db):
    """Token còn hạn nhưng tài khoản đã bị đình chỉ thì vẫn là 403."""
    db = use_fake_db(FakeDB(SUSPENDED))
    with pytest.raises(HTTPException) as excinfo:
        module.create_job_family(module.JobFamilyCreate(code="NEW_FAMILY", name="Nhóm mới"), USER)
    assert excinfo.value.status_code == 403
    assert not db.committed


def test_non_admin_cannot_see_inactive_families(use_fake_db):
    """Danh sách đã tắt là thông tin quản trị, không phải thông tin chung."""
    use_fake_db(FakeDB(NOT_ADMIN))
    with pytest.raises(HTTPException) as excinfo:
        module.list_job_families(include_inactive=True, current_user=USER)
    assert excinfo.value.status_code == 403


def test_non_admin_can_list_active_families(use_fake_db):
    """Đọc nhóm đang hoạt động thì ai trong hệ thống cũng cần — form tạo vị trí dùng nó."""
    db = use_fake_db(FakeDB([_Result(all_=[{
        "job_family_id": uuid.uuid4(), "code": "IT_DIGITAL", "name": "IT & Digital",
        "is_active": True, "position_count": 3, "template_count": 1,
    }])]))
    rows = module.list_job_families(include_inactive=False, current_user=USER)
    assert [row["code"] for row in rows] == ["IT_DIGITAL"]
    assert rows[0]["position_count"] == 3
    assert not any("FOR SHARE" in sql for sql, _ in db.issued)


# ---------------------------------------------------------------------------
# Tạo
# ---------------------------------------------------------------------------

def _created_row(code="NEW_FAMILY", name="Nhóm mới"):
    return {"job_family_id": uuid.uuid4(), "code": code, "name": name, "is_active": True}


def test_create_normalizes_the_code_before_inserting(use_fake_db):
    db = use_fake_db(FakeDB(ADMIN_OK + [_Result(one=_created_row()), _Result()]))
    module.create_job_family(module.JobFamilyCreate(code="new family", name="  Nhóm   mới "), USER)
    insert_params = next(params for sql, params in db.issued if "INSERT INTO app_private.job_families" in sql)
    assert insert_params["code"] == "NEW_FAMILY"
    assert insert_params["name"] == "Nhóm mới"  # gộp khoảng trắng
    assert db.committed


def test_create_writes_an_audit_event(use_fake_db):
    db = use_fake_db(FakeDB(ADMIN_OK + [_Result(one=_created_row()), _Result()]))
    module.create_job_family(module.JobFamilyCreate(code="NEW_FAMILY", name="Nhóm mới"), USER)
    audit = [(sql, params) for sql, params in db.issued if "audit_events" in sql]
    assert len(audit) == 1
    assert audit[0][1]["action"] == "CREATE_JOB_FAMILY"


def test_duplicate_code_is_409_and_rolled_back(use_fake_db):
    """Người dùng đã gõ xong form; trả 409 kèm câu rõ ràng thay vì 500 của DB."""
    db = use_fake_db(FakeDB(ADMIN_OK + [IntegrityError("INSERT", {}, Exception("duplicate key"))]))
    with pytest.raises(HTTPException) as excinfo:
        module.create_job_family(module.JobFamilyCreate(code="IT_DIGITAL", name="Trùng"), USER)
    assert excinfo.value.status_code == 409
    assert db.rolled_back
    assert not db.committed


def test_create_returns_zero_counts(use_fake_db):
    """Nhóm vừa tạo chắc chắn chưa có vị trí nào; trả 0 để màn hình không phải đoán."""
    use_fake_db(FakeDB(ADMIN_OK + [_Result(one=_created_row()), _Result()]))
    result = module.create_job_family(module.JobFamilyCreate(code="NEW_FAMILY", name="Nhóm mới"), USER)
    assert result["position_count"] == 0
    assert result["template_count"] == 0


# ---------------------------------------------------------------------------
# Cập nhật
# ---------------------------------------------------------------------------

def test_unknown_family_is_404(use_fake_db):
    db = use_fake_db(FakeDB(ADMIN_OK + [_Result(first=None)]))
    with pytest.raises(HTTPException) as excinfo:
        module.update_job_family(uuid.uuid4(), module.JobFamilyUpdate(name="Khác"), USER)
    assert excinfo.value.status_code == 404
    assert not db.committed


def test_deactivating_family_in_use_is_409_with_the_count(use_fake_db):
    db = use_fake_db(FakeDB(ADMIN_OK + [_Result(first=(1,)), _Result(scalar=4)]))
    with pytest.raises(HTTPException) as excinfo:
        module.update_job_family(uuid.uuid4(), module.JobFamilyUpdate(is_active=False), USER)
    assert excinfo.value.status_code == 409
    assert "4 vị trí" in excinfo.value.detail
    assert not db.committed


def test_deactivating_empty_family_succeeds(use_fake_db):
    family_id = uuid.uuid4()
    db = use_fake_db(FakeDB(ADMIN_OK + [
        _Result(first=(1,)),
        _Result(scalar=0),
        _Result(one={"job_family_id": family_id, "code": "NEW_FAMILY", "name": "Nhóm mới", "is_active": False}),
        _Result(),
        _Result(one={"position_count": 0, "template_count": 0}),
    ]))
    result = module.update_job_family(family_id, module.JobFamilyUpdate(is_active=False), USER)
    assert result["is_active"] is False
    assert db.committed


def test_update_only_changes_what_was_sent(use_fake_db):
    """Gửi tên thì câu SET không được dính ``is_active`` — người dùng chỉ muốn đổi tên."""
    family_id = uuid.uuid4()
    db = use_fake_db(FakeDB(ADMIN_OK + [
        _Result(first=(1,)),
        _Result(one={"job_family_id": family_id, "code": "NEW_FAMILY", "name": "Tên mới", "is_active": True}),
        _Result(),
        _Result(one={"position_count": 0, "template_count": 0}),
    ]))
    module.update_job_family(family_id, module.JobFamilyUpdate(name="Tên mới"), USER)
    update_sql = next(sql for sql, _ in db.issued if sql.strip().startswith("UPDATE app_private.job_families"))
    assert "name = :name" in update_sql
    assert "is_active" not in update_sql


def test_empty_update_is_rejected(use_fake_db):
    use_fake_db(FakeDB([]))
    with pytest.raises(HTTPException) as excinfo:
        module.update_job_family(uuid.uuid4(), module.JobFamilyUpdate(), USER)
    assert excinfo.value.status_code == 400


def test_code_sent_to_patch_is_ignored(use_fake_db):
    """``code`` không có trong schema nên Pydantic bỏ qua; gửi lên không đổi được gì."""
    family_id = uuid.uuid4()
    db = use_fake_db(FakeDB(ADMIN_OK + [
        _Result(first=(1,)),
        _Result(one={"job_family_id": family_id, "code": "NEW_FAMILY", "name": "Nhóm mới", "is_active": True}),
        _Result(),
        _Result(one={"position_count": 0, "template_count": 0}),
    ]))
    payload = module.JobFamilyUpdate.model_validate({"code": "HACKED", "name": "Nhóm mới"})
    module.update_job_family(family_id, payload, USER)
    update_sql = next(sql for sql, _ in db.issued if sql.strip().startswith("UPDATE app_private.job_families"))
    assert "code" not in update_sql
