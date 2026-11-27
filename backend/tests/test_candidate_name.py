import pytest

from app.services.candidate_name import guess_candidate_name


@pytest.mark.parametrize("text,expected", [
    ("Lam Quoc Viet\nSenior Data Engineer Hanoi, Vietnam | +84 90 000 2084 | viet.lam@example.com\nSUMMARY", "Lam Quoc Viet"),
    ("--- Page 1 ---\nNGUYỄN VĂN AN\nBackend Developer\nan@x.vn", "Nguyễn Văn An"),
    ("--- Page 1 ---\nTrần Thị Bích Ngọc\nHà Nội", "Trần Thị Bích Ngọc"),
    ("CURRICULUM VITAE\nPhạm Đức Anh\n+84 912 345 678", "Phạm Đức Anh"),
    ("Senior Data Engineer\nHanoi, Vietnam\nTang Gia Han\nEmail: han@example.com", "Tang Gia Han"),
    ("Le Hoang Phuc | DevSecOps Engineer", None),
])
def test_name_from_the_top_of_a_cv(text, expected):
    assert guess_candidate_name(text) == expected


@pytest.mark.parametrize("text", [
    "Senior Data Engineer", "viet.lam@example.com", "SUMMARY OF QUALIFICATIONS", "Ho Chi Minh City", "", None,
    "Curriculum Vitae", "1 2 3 4", "a b",
])
def test_unsure_means_no_name(text):
    assert guess_candidate_name(text) is None
