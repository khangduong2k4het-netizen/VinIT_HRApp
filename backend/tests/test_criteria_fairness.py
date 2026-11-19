"""Unit tests for the F1.02 protected-attribute screen (no database needed)."""
import pytest

from app.services.criteria_fairness import detect_protected_attributes, fairness_warnings


@pytest.mark.parametrize("criterion, expected", [
    ({"name": "Age under 30", "description": "Young and dynamic"}, ["AGE"]),
    ({"name": "Nam giới", "description": "Ưu tiên ứng viên nam giới"}, ["GENDER"]),
    ({"name": "Độ tuổi 25-35", "description": "Ứng viên trong độ tuổi phù hợp"}, ["AGE"]),
    ({"name": "Ngoại hình ưa nhìn", "description": "Chiều cao từ 1m60"}, ["APPEARANCE"]),
    ({"name": "Chưa kết hôn", "description": "Ưu tiên độc thân"}, ["MARITAL_STATUS"]),
    ({"name": "Culture fit", "description": "Fits our culture"}, ["CULTURE_FIT"]),
    ({"name": "Tính cách hướng ngoại", "description": "Hòa đồng"}, ["PERSONALITY"]),
    ({"name": "Python", "description": "x", "expected_evidence_keywords": ["female"]}, ["GENDER"]),
    ({"name": "Python", "description": "x", "evidence_guidance": "Check the candidate's nationality"}, ["NATIONALITY_ETHNICITY"]),
])
def test_flags_non_job_related_personal_attributes(criterion, expected):
    assert detect_protected_attributes(criterion) == expected


@pytest.mark.parametrize("criterion", [
    {"name": "Python", "description": "3+ years of Python experience in production systems"},
    {"name": "Concurrency", "description": "Debug race conditions and deadlocks"},
    {"name": "SSO", "description": "Experience integrating single sign-on with Azure AD"},
    {"name": "Kinh nghiệm", "description": "Tối thiểu 3 năm kinh nghiệm phát triển phần mềm tại Việt Nam"},
    {"name": "Management", "description": "Managed agile teams; manages page layouts"},
    {"name": "Photoshop", "description": "Image editing with Photoshop"},
    {"name": "English", "description": "IELTS 6.5 or equivalent", "expected_evidence_keywords": ["IELTS", "TOEIC"]},
])
def test_job_related_criteria_are_not_flagged(criterion):
    assert detect_protected_attributes(criterion) == []


def test_fairness_warnings_keep_rubric_order_and_identity():
    criteria = [
        {"criterion_id": "a", "name": "Python", "description": "Python"},
        {"criterion_id": "b", "name": "Giới tính", "description": "Nữ", "expected_evidence_keywords": "not-a-list"},
        {"criterion_id": "c", "name": "Age", "description": "Under 35, married"},
    ]
    assert fairness_warnings(criteria) == [
        {"criterion_id": "b", "name": "Giới tính", "attributes": ["GENDER"]},
        {"criterion_id": "c", "name": "Age", "attributes": ["AGE", "MARITAL_STATUS"]},
    ]
