"""``/careers`` lấy nhóm vị trí từ bảng ``job_families``, không từ cột text cũ.

Vì sao cần khoá chặn này: trước đây ``/careers`` lọc và gom danh mục theo cột
text ``positions.job_family``. Hệ quả đo được là một nhóm vừa tạo trong màn hình
quản trị **không** xuất hiện trong danh mục lọc ở trang tuyển dụng, vì bảng
``job_families`` và cột text là hai nguồn song song không ai đồng bộ.

Cột text vẫn còn trong schema (dữ liệu lịch sử, không xoá), nên một lần sửa vô
tình đọc lại nó sẽ không làm hỏng test nào khác. Đó chính là lý do cần file này.
"""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
CAREERS = (BACKEND / "app" / "api" / "careers.py").read_text()

JOBS = CAREERS[CAREERS.index("@router.get('/jobs')"):CAREERS.index("@router.get('/filters')")]
FILTERS = CAREERS[CAREERS.index("@router.get('/filters')"):]


def test_jobs_join_the_family_table():
    """Tên nhóm trong danh sách phải lấy từ bảng, nên phải có join."""
    assert "LEFT JOIN app_private.job_families f ON f.job_family_id = p.job_family_id" in JOBS


def test_jobs_select_the_family_name_not_the_legacy_column():
    """Chọn ``f.name`` chứ không ``p.job_family``.

    Hai chuỗi này khác nhau đúng một ký tự; đọc nhầm chỉ lộ ra khi một vị trí có
    ``job_family_id`` nhưng cột text trống — chính là trạng thái của dữ liệu thật
    hiện nay.
    """
    import re
    assert "f.name AS job_family" in JOBS
    assert not re.search(r"p\.job_family\b(?!_id)", JOBS)


def test_jobs_filter_matches_the_family_table():
    """Bộ lọc phải so với tên trong bảng; so với cột text thì lọc luôn ra rỗng."""
    assert "(:job_family IS NULL OR f.name = :job_family)" in JOBS
    assert "p.job_family = :job_family" not in JOBS


def test_filters_group_by_the_family_table():
    """Danh mục lọc gom theo bảng — đây là chỗ nhóm mới tạo phải xuất hiện."""
    assert "f.name AS job_family" in FILTERS
    assert "GROUP BY p.employment_type, f.name" in FILTERS
    assert "p.job_family" + "\n" not in FILTERS and "p.job_family " not in FILTERS


def test_filters_still_return_the_shape_the_frontend_reads():
    """Giao diện đọc ``job_families: [{value, count}]`` — đổi shape là vỡ im lặng."""
    assert "'job_families': [{'value': k, 'count': v}" in FILTERS


def test_positions_without_a_family_are_not_dropped():
    """Vị trí chưa gán nhóm vẫn phải hiện tin.

    Dùng LEFT JOIN chứ không JOIN: đổi thành JOIN thì mọi tin chưa gán nhóm biến
    mất khỏi trang tuyển dụng, và hiện trạng dữ liệu thật là **tất cả** tin đều
    chưa gán nhóm — trang sẽ trống hoàn toàn.
    """
    assert "LEFT JOIN app_private.job_families" in JOBS
    assert "JOIN app_private.job_families f" not in JOBS.replace("LEFT JOIN app_private.job_families f", "")


def test_a_public_query_never_reads_the_legacy_column():
    """Module này không còn câu SQL nào chạm ``p.job_family``."""
    # ``p.job_family_id`` có hợp lệ (khoá ngoại), nên phải so khớp cả ranh giới
    # từ — chính cái bẫy đã làm hỏng một test ở đây lần đầu viết.
    import re
    legacy = re.compile(r"p\.job_family\b(?!_id)")
    sql_lines = [line.strip() for line in CAREERS.splitlines()
                 if legacy.search(line) and not line.strip().startswith(('"""', '#', '*'))]
    assert sql_lines == []
