"""Bộ CV demo phải khớp tài liệu và khớp chính nó.

Ba thứ dễ trôi khỏi nhau: dữ liệu trong `cv_data.py`, tệp đã sinh trong
`doc/BO_DEMO_TUYEN_DUNG/02_CV/`, và bảng điều phối mà HR dùng khi demo.
Test ở đây ghim cả ba lại với nhau — nếu ai đó sửa một nơi mà quên nơi khác,
bộ demo sẽ gãy ngay trong buổi trình bày chứ không phải trong CI.
"""
from pathlib import Path

import pytest

from scripts.demo_pack.cv_data import CANDIDATES
from scripts.demo_pack.generate import target_filename

REPO_ROOT = Path(__file__).resolve().parents[2]
CV_DIR = REPO_ROOT / "doc" / "BO_DEMO_TUYEN_DUNG" / "02_CV"
ALLOCATION = REPO_ROOT / "doc" / "BO_DEMO_TUYEN_DUNG" / "BANG_PHAN_BO_30_CV.md"

#: Kịch bản demo phụ thuộc vào việc ai đủ/thiếu bằng chứng cho vị trí nào, nên
#: kỹ năng cốt lõi của một số hồ sơ phải được ghim. Đổi mấy dòng này là đổi
#: kết quả mong đợi trong `KICH_BAN_DEMO.md` — đừng sửa test, sửa kịch bản.
PINNED_SKILLS = {
    2: ("Flask",),            # has Flask but no pipeline evidence
    6: ("Java",),             # Java-leaning, not Python
    11: ("Power BI",),        # data analysis, no Python/API
    17: ("Bootstrap",),       # basic web, no React
    23: ("test case design",),  # manual testing, not automated
    29: ("ticketing",),       # IT support, no Docker/CI
}


def test_pack_has_thirty_candidates():
    assert len(CANDIDATES) == 30


def test_identity_fields_are_unique():
    """Trùng tên hoặc trùng email sẽ làm hỏng kịch bản chống trùng lặp."""
    for field in ("full_name", "email", "phone"):
        values = [getattr(c, field) for c in CANDIDATES]
        assert len(values) == len(set(values)), field


def test_contact_details_never_point_at_real_people():
    for candidate in CANDIDATES:
        assert candidate.email.endswith((".test", ".invalid")), candidate.email


def test_no_sensitive_attributes_in_the_pack():
    """Bộ demo không được chứa ngày sinh, giới tính, địa chỉ, CCCD.

    Hệ thống cũng không được phép xử lý mấy trường đó, nên dữ liệu mẫu không
    nên mang chúng vào.
    """
    forbidden = ("ngày sinh", "giới tính", "hôn nhân", "quốc tịch",
                 "tôn giáo", "cccd", "cmnd", "địa chỉ:")
    for candidate in CANDIDATES:
        text = " ".join([
            candidate.summary, candidate.headline,
            *(candidate.skills), *(candidate.certifications),
        ]).lower()
        for word in forbidden:
            assert word not in text, f"{candidate.number}: {word}"


def test_pinned_skills_are_preserved():
    by_number = {c.number: c for c in CANDIDATES}
    for number, skills in PINNED_SKILLS.items():
        for skill in skills:
            assert skill in by_number[number].skills, (number, skill)


def test_every_candidate_has_a_realistic_shape():
    """Một CV thật có tóm tắt, kinh nghiệm, học vấn và vài kỹ năng."""
    for candidate in CANDIDATES:
        assert len(candidate.summary) >= 80, candidate.number
        assert candidate.experience, candidate.number
        assert candidate.education, candidate.number
        assert len(candidate.skills) >= 5, candidate.number
        for job in candidate.experience:
            assert job.bullets, candidate.number
            assert job.period and job.company, candidate.number


def test_filenames_are_deliberately_messy():
    """Tên tệp phải đa dạng — đó chính là điều kiện của bài toán.

    Nếu mọi tệp đều theo một khuôn `CV_xx_ten.docx` thì bộ demo không còn
    chứng minh được hệ thống không phụ thuộc vào tên tệp.
    """
    names = [target_filename(c) for c in CANDIDATES]
    assert len(names) == len(set(names))
    shapes = {name.replace(str(i), "N") for i, name in
              zip([c.number for c in CANDIDATES], names)}
    assert len({name.split(".")[0].count("_") for name in names}) > 1
    assert any(" " in name for name in names)
    assert any(name.endswith(".pdf") for name in names)
    assert any(name.endswith(".docx") for name in names)


@pytest.mark.skipif(not CV_DIR.exists(), reason="Chưa sinh bộ CV demo")
def test_generated_files_match_the_data():
    """Tệp trên đĩa phải là đúng 30 tệp mà dữ liệu mô tả."""
    expected = {target_filename(c) for c in CANDIDATES}
    actual = {p.name for p in CV_DIR.iterdir()
              if p.is_file() and p.suffix in {".docx", ".pdf"}}
    assert actual == expected


@pytest.mark.skipif(not ALLOCATION.exists(), reason="Thiếu bảng điều phối")
def test_allocation_table_matches_the_pack():
    """Bảng HR cầm khi demo phải trỏ đúng tệp và đúng họ tên."""
    text = ALLOCATION.read_text(encoding="utf-8")
    for candidate in CANDIDATES:
        assert target_filename(candidate) in text, candidate.full_name
        assert candidate.full_name in text, candidate.full_name


@pytest.mark.skipif(not CV_DIR.exists(), reason="Chưa sinh bộ CV demo")
def test_mixed_formats_are_present():
    """Bộ demo phải có cả DOCX và PDF, đúng như hồ sơ thật gửi lên."""
    suffixes = [p.suffix for p in CV_DIR.iterdir() if p.is_file()]
    assert suffixes.count(".docx") == 20
    assert suffixes.count(".pdf") == 10


def test_readme_states_the_real_format_counts():
    """README từng ghi sai số định dạng; con số phải khớp thư mục thật."""
    readme = REPO_ROOT / "doc" / "BO_DEMO_TUYEN_DUNG" / "README.txt"
    if not CV_DIR.exists() or not readme.exists():
        pytest.skip("Chưa sinh bộ CV demo")
    suffixes = [p.suffix for p in CV_DIR.iterdir() if p.is_file()]
    text = readme.read_text(encoding="utf-8")
    assert f"({suffixes.count('.docx')} DOCX, {suffixes.count('.pdf')} PDF)" in text


# ---------------------------------------------------------------------------
# Ngôn ngữ: tiếng Anh là chuẩn cho JD/CV.
# ---------------------------------------------------------------------------

def test_demo_pack_is_in_english():
    """Tiếng Việt được hỗ trợ nhưng là tuỳ chọn, không phải dữ liệu demo.

    Nền tảng hướng tới người dùng quốc tế. Nếu bộ demo dùng tiếng Việt, người
    xem sẽ hiểu sai rằng tiếng Việt là mặc định, và các lỗi đặc thù tiếng Việt
    sẽ lẫn vào kịch bản trình bày.
    """
    import unicodedata

    def has_vietnamese_marks(text: str) -> bool:
        # Dấu đặc trưng tiếng Việt không xuất hiện trong tên tiếng Anh thông thường.
        decomposed = unicodedata.normalize("NFD", text)
        marks = {ch for ch in decomposed if unicodedata.combining(ch)}
        # ơ/ư dùng dấu móc riêng, không tách được bằng NFD.
        return bool(marks) or "ơ" in text or "ư" in text or "đ" in text

    for candidate in CANDIDATES:
        text = " ".join([candidate.full_name, candidate.headline, candidate.summary,
                         *candidate.skills, *candidate.certifications, *candidate.languages])
        assert not has_vietnamese_marks(text), candidate.full_name


def test_jd_files_are_in_english():
    jd_dir = REPO_ROOT / "doc" / "BO_DEMO_TUYEN_DUNG" / "01_JD"
    if not jd_dir.exists():
        pytest.skip("Bộ JD demo chưa có")
    files = sorted(jd_dir.glob("*.txt"))
    assert len(files) == 5
    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        assert "job description" in text or "jd" in text, path.name
        # Không còn tiêu đề/nhãn tiếng Việt trong JD mẫu.
        for word in ("mục tiêu", "công việc chính", "yêu cầu bắt buộc", "thử nghiệm"):
            assert word not in text, f"{path.name}: {word}"
