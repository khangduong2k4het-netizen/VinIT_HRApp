"""API quản trị nhóm vị trí (``/job-families``).

Nhóm vị trí là khoá nối ba thứ: vị trí (``positions.job_family_id``), rubric
mẫu (``rubric_templates.job_family_id``) và chốt chặn "áp rubric khác nhóm".
Trước module này, nhóm vị trí chỉ sinh ra từ migration — muốn mở một ngành
tuyển dụng mới phải nhờ người chạy SQL trên DB thật.

Hai kiểu test, cố ý tách:

* Phần **chạy được** (chuẩn hoá mã, schema đầu vào) gọi thẳng hàm — nó là logic
  thuần, không cần DB.
* Phần **đọc mã nguồn** kiểm những chốt chặn nằm trong SQL (quyền ADMIN, 409
  khi tắt nhóm còn vị trí, không có DELETE). Bộ test này không dựng DB; các
  test cần DB thật vốn đã nằm trong nhóm skip.
"""
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.job_families import (
    JobFamilyCreate,
    JobFamilyUpdate,
    normalize_code,
    router,
)

BACKEND = Path(__file__).resolve().parents[1]
SOURCE = (BACKEND / "app" / "api" / "job_families.py").read_text()
API_INIT = (BACKEND / "app" / "api" / "__init__.py").read_text()

CREATE = SOURCE[SOURCE.index('@router.post'):SOURCE.index('@router.patch')]
UPDATE = SOURCE[SOURCE.index('@router.patch'):]


# ---------------------------------------------------------------------------
# Router thật sự được nạp
# ---------------------------------------------------------------------------

def test_router_is_imported_not_only_included():
    """``include_router`` gọi một cái tên; quên import là app chết lúc khởi động.

    Lỗi này không test nào khác bắt được: ``NameError`` nổ khi import module,
    tức là trước cả khi có request nào để chạy. Đã xảy ra một lần trong chính
    lượt làm việc này.
    """
    import_line = API_INIT.split("from . import", 1)[1].split("\n", 1)[0]
    assert "job_families" in import_line
    assert 'api_router.include_router(job_families.router, prefix="/job-families"' in API_INIT


def test_router_has_no_own_prefix():
    """Prefix do ``api_router`` gắn; đặt thêm ở đây sẽ thành ``/job-families/job-families``."""
    assert 'prefix=' not in SOURCE.split("\n", 30)[14]


def test_routes_cover_list_create_update_only():
    """Ba đường, không hơn: đọc, tạo, sửa. Không DELETE là quyết định, không phải thiếu sót."""
    paths = sorted({(tuple(sorted(route.methods)), route.path) for route in router.routes})
    assert paths == [
        (("GET",), ""),
        (("PATCH",), "/{job_family_id}"),
        (("POST",), ""),
    ]


# ---------------------------------------------------------------------------
# Chuẩn hoá mã — test chạy thật
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["IT Digital", "it-digital", " IT_DIGITAL ", "Digital   Marketing"])
def test_code_is_normalized_to_upper_snake(raw):
    """Người dùng gõ gì cũng ra ``CHỮ_HOA_CÓ_GẠCH``.

    Không chuẩn hoá thì cùng một nhóm sinh ra nhiều mã khác nhau và cột ``code``
    UNIQUE không còn chặn được gì — hai nhóm gần giống nhau lọt vào cùng lúc.
    """
    result = normalize_code(raw)
    assert result == result.upper()
    assert " " not in result and "-" not in result
    assert result.replace("_", "").isalnum()


def test_code_normalization_examples():
    """Ghép cặp cụ thể để test không thể "đúng" một cách vô nghĩa."""
    assert normalize_code("IT Digital") == "IT_DIGITAL"
    assert normalize_code("it-digital") == "IT_DIGITAL"
    assert normalize_code(" IT_DIGITAL ") == "IT_DIGITAL"


def test_code_must_start_with_a_letter():
    """Cột DB cho phép chữ cái đầu; mã bắt đầu bằng số làm hỏng quy ước tra cứu."""
    with pytest.raises(HTTPException) as excinfo:
        normalize_code("1abc")
    assert excinfo.value.status_code == 400


def test_code_length_is_capped_at_the_column_size():
    """Cột ``code`` giới hạn 50 ký tự — cắt ở API để lỗi là 400, không phải 500 từ DB."""
    with pytest.raises(HTTPException) as excinfo:
        normalize_code("A" * 60)
    assert excinfo.value.status_code == 400
    assert normalize_code("A" * 50) == "A" * 50


def test_empty_code_is_rejected():
    with pytest.raises(HTTPException):
        normalize_code("   ")


# ---------------------------------------------------------------------------
# Schema đầu vào
# ---------------------------------------------------------------------------

def test_code_is_immutable_after_create():
    """``code`` cố ý không có trong schema cập nhật.

    Rubric mẫu, báo cáo và cấu hình tích hợp có thể tham chiếu mã; đổi mã của
    nhóm đang dùng là đổi nghĩa dữ liệu cũ. Pydantic bỏ qua field lạ nên ai gửi
    ``code`` lên PATCH cũng không đổi được gì — đây là chốt chặn thật.
    """
    assert set(JobFamilyUpdate.model_fields) == {"name", "is_active"}
    assert "code" not in JobFamilyUpdate.model_fields
    assert set(JobFamilyCreate.model_fields) == {"code", "name"}


def test_update_accepts_is_active_false():
    """Tắt nhóm chính là ``is_active=False`` — nếu bị coi là "không có gì để đổi" thì không tắt được."""
    payload = JobFamilyUpdate(is_active=False)
    values = payload.model_dump(exclude_unset=True)
    assert values == {"is_active": False}
    assert values.get("is_active") is False


def test_create_requires_a_code_and_a_name():
    with pytest.raises(Exception):
        JobFamilyCreate(code="", name="Nhóm")
    with pytest.raises(Exception):
        JobFamilyCreate(code="IT_DIGITAL", name="")


# ---------------------------------------------------------------------------
# Chốt chặn trong SQL — đọc mã nguồn
# ---------------------------------------------------------------------------

def test_writes_require_admin():
    """Đọc cho mọi người dùng nội bộ, ghi chỉ ADMIN — giống phòng ban."""
    assert CREATE.count("_require_admin_write") == 1
    assert UPDATE.count("_require_admin_write") == 1


def test_require_admin_write_locks_the_user_row():
    """``FOR SHARE`` để vai trò không bị thu hồi chen giữa bước kiểm và bước ghi."""
    assert "FOR SHARE" in SOURCE
    assert "403" in SOURCE


def test_include_inactive_is_admin_only():
    """Danh sách nhóm đã tắt không được lộ cho người dùng thường."""
    assert "include_inactive" in SOURCE
    list_body = SOURCE[SOURCE.index('@router.get'):SOURCE.index('@router.post')]
    assert "_require_admin_write" in list_body


def test_duplicate_code_is_a_conflict_not_a_500():
    """Mã trùng phải là 409. Để ``UNIQUE`` nổ ra ngoài thì người dùng nhận 500 và mất dữ liệu form."""
    assert "409" in CREATE
    assert "IntegrityError" in CREATE
    assert "rollback" in CREATE


def test_deactivating_a_family_in_use_is_blocked_with_a_count():
    """Tắt nhóm còn vị trí sẽ khiến vị trí trỏ tới một nhóm không chọn được nữa.

    Trả 409 kèm số vị trí để người dùng biết phải chuyển bao nhiêu vị trí.
    """
    assert "409" in UPDATE
    assert "[0-9] vị trí" not in UPDATE  # câu phải nội suy số, không hard-code
    assert '{in_use} vị trí' in UPDATE


def test_deactivating_an_empty_family_is_allowed():
    """Nhóm lỡ tạo, chưa dùng, phải tắt được — nếu không thì tạo nhầm là kẹt vĩnh viễn."""
    assert "if in_use:" in UPDATE


def test_update_locks_the_family_row():
    """``FOR UPDATE`` để hai người tắt/bật cùng lúc không đè lên nhau."""
    assert "FOR UPDATE" in UPDATE


def test_unknown_family_returns_404():
    assert "404" in UPDATE


def test_there_is_no_delete_route():
    """Không xoá nhóm: dữ liệu cũ phải còn chỗ trỏ tới. Không có nút thì không bấm nhầm."""
    assert "@router.delete" not in SOURCE
    assert "DELETE FROM" not in SOURCE


def test_audit_columns_match_the_real_table():
    """``audit_events`` (00001) có ``metadata`` kiểu JSONB, nên ghi metadata là hợp lệ.

    Ghi một cột không tồn tại sẽ làm hỏng request ở bước cuối — sau khi dữ liệu
    đã đổi. Đây là lý do kiểm tên cột thay vì tin vào khuôn copy từ module khác.
    """
    schema = (BACKEND.parent / "supabase" / "migrations" / "00001_initial_schema.sql").read_text()
    table = schema[schema.index("CREATE TABLE app_private.audit_events"):]
    table = table[:table.index(");")]
    for column in ("actor_user_id", "action_type", "object_type", "object_id", "outcome", "metadata"):
        assert column in table, f"audit_events không có cột {column}"


def test_audit_records_are_written():
    """Tạo/đổi nhóm vị trí là thay đổi cấu hình ảnh hưởng rubric — phải có vết."""
    assert "CREATE_JOB_FAMILY" in CREATE
    assert "UPDATE_JOB_FAMILY" in UPDATE


def test_family_list_reports_usage_counts():
    """Màn hình quản trị cần biết nhóm nào đang bị dùng trước khi cho tắt."""
    list_body = SOURCE[SOURCE.index('@router.get'):SOURCE.index('@router.post')]
    assert "position_count" in list_body
    assert "template_count" in list_body


def test_migration_seeds_codes_the_api_accepts():
    """Hai nhóm mồi là dữ liệu thật — mã của chúng phải qua được ``normalize_code``."""
    migration = (BACKEND.parent / "supabase" / "migrations" / "00023_phase2_workflow_core.sql").read_text()
    assert "IT_DIGITAL" in migration
    assert normalize_code("IT_DIGITAL") == "IT_DIGITAL"
