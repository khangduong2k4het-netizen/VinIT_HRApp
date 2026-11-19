"""Regression tests for the opaque-500 criteria generation failure.

Symptom reported in production: after "Tạo vị trí và tiếp tục" the UI showed
"Đã tạo vị trí nhưng chưa tạo được tiêu chí", even though the position had been
created. The endpoint returned a bare HTTP 500 with **no** ``detail`` field, so
the UI had nothing to display beyond its fallback sentence.

Root cause: ``build_requirement_spec`` classified any criterion whose text
mentioned "communication"/"proficiency" as ``kind=LANGUAGE`` while attaching no
language and no threshold. ``RequirementSpec`` requires one, so pydantic rejected
the stored spec while FastAPI serialized the response — the request died after
the insert had already happened.
"""

import pytest

from app.api.criteria import _sanitize_criteria_response, _stored_requirement_spec
from app.schemas.criteria import Criterion, RequirementSpec


def _criterion(name: str, description: str, keywords: list[str], category: str = "MUST_HAVE") -> dict:
    item = {
        "name": name,
        "description": description,
        "category": category,
        "weight": 10.0,
        "expected_evidence_keywords": keywords,
    }
    return {
        **item,
        "weight_in_group": 10.0,
        "requirement_spec": _stored_requirement_spec(item),
        "criterion_id": "00000000-0000-0000-0000-000000000001",
        "criteria_version_id": "00000000-0000-0000-0000-000000000002",
        "display_order": 0,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": None,
    }


@pytest.mark.parametrize(
    "name,description,keywords",
    [
        ("Communication", "Excellent verbal and written communication skills", ["communication"]),
        ("Teamwork", "Strong communication and teamwork", ["teamwork"]),
        ("Presentation", "Proficiency in presenting to stakeholders", ["presentation"]),
        ("Stakeholder management", "Communication with senior stakeholders", ["stakeholders"]),
        # Vietnamese soft skills must be safe too: a Vietnamese JD is allowed.
        ("Giao tiếp", "Kỹ năng giao tiếp tốt với các phòng ban", ["giao tiếp"]),
    ],
)
def test_soft_skill_mentioning_communication_is_not_a_language_requirement(name, description, keywords):
    """A mention of communication must never yield LANGUAGE without a threshold."""
    spec = _stored_requirement_spec({"name": name, "description": description,
                                    "category": "MUST_HAVE", "expected_evidence_keywords": keywords})
    assert spec["kind"] != "LANGUAGE"
    # The whole point: the response schema must accept it.
    Criterion.model_validate(_criterion(name, description, keywords))


@pytest.mark.parametrize(
    "name,description,keywords,expected_kind",
    [
        ("English", "Good English communication, IELTS 6.5", ["English", "IELTS"], "LANGUAGE"),
        ("Fluent English", "Fluent in English", ["English"], "LANGUAGE"),
        ("TOEIC", "TOEIC 700 or above", ["TOEIC"], "LANGUAGE"),
        # A concrete language is a language requirement even without a numeric threshold.
        ("Japanese", "JLPT N2 is required", ["Japanese"], "LANGUAGE"),
        ("Degree", "Bachelor degree in Computer Science", ["Bachelor"], "DEGREE"),
        ("Years", "At least 3 years of backend experience", ["3 years"], "YEARS"),
        ("Python", "Strong Python and FastAPI experience", ["Python", "FastAPI"], "SKILL"),
    ],
)
def test_real_requirements_keep_their_kind(name, description, keywords, expected_kind):
    """The fix must not flatten genuine language/degree/year requirements."""
    spec = _stored_requirement_spec({"name": name, "description": description,
                                    "category": "MUST_HAVE", "expected_evidence_keywords": keywords})
    assert spec["kind"] == expected_kind
    Criterion.model_validate(_criterion(name, description, keywords))


def test_any_generated_spec_accepted_by_build_is_accepted_by_the_response_schema():
    """Guards the invariant that broke production: build -> store -> serialize."""
    samples = [
        ("Communication", "Excellent communication skills", ["communication"]),
        ("Teamwork", "Works well in teams", ["team"]),
        ("English", "Fluent English", ["English"]),
        ("Degree", "Master degree preferred", ["Master"]),
        ("Nothing useful", "", []),
        ("Many terms", "x", [f"skill{i}" for i in range(20)]),
    ]
    for name, description, keywords in samples:
        Criterion.model_validate(_criterion(name, description, keywords))


def test_stored_row_with_rejected_spec_is_still_serializable():
    """Rows already written with a bad spec must not break reads."""
    bad_version = {
        "criteria": [
            {"requirement_spec": {"kind": "LANGUAGE"}},      # the value that 500'd a whole response
            {"requirement_spec": {"kind": "SKILL", "terms": ["python"]}},
            {"requirement_spec": None},
        ]
    }
    cleaned = _sanitize_criteria_response(bad_version)
    assert cleaned["criteria"][0]["requirement_spec"] is None
    assert cleaned["criteria"][1]["requirement_spec"] == {"kind": "SKILL", "terms": ["python"]}
    assert cleaned["criteria"][2]["requirement_spec"] is None


def test_sanitizer_leaves_valid_specs_untouched():
    valid = {"kind": "LANGUAGE", "required_languages": ["english"], "terms": ["English"]}
    RequirementSpec.model_validate(valid)
    cleaned = _sanitize_criteria_response({"criteria": [{"requirement_spec": valid}]})
    assert cleaned["criteria"][0]["requirement_spec"] == valid


def test_sanitizer_is_safe_on_unexpected_shapes():
    """Reads must never raise because of a malformed row."""
    assert _sanitize_criteria_response({"criteria": None}) == {"criteria": None}
    assert _sanitize_criteria_response({"criteria": ["not-a-dict"]}) == {"criteria": ["not-a-dict"]}
    assert _sanitize_criteria_response({"criteria": [{"requirement_spec": "not-a-dict"}]})["criteria"][0][
        "requirement_spec"
    ] is None
    assert _sanitize_criteria_response({}) == {}
