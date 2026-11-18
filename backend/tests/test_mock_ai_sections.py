"""Mock AI reads JD section headings, and an AI draft without preferred
criteria starts at 100/0 so approval is not blocked by an empty 30% group."""
from app.api.criteria import draft_group_totals
from app.services.mock_ai import _criteria_from_jd, _joined_lines

JD = """ABOUT US
We are a strong, solid university with the ability to grow fast and a long history.
Qualifications
:
Required:
3+ years of experience in
Data Engineering, Backend Engineering, or related roles
.
Strong programming skills in
Python, Java, or similar backend technologies
.
Nice to have
Experience with orchestration tools such as
Apache Airflow, Argo Workflows
, or similar technologies.
Experience with Kafka, RabbitMQ, or other message queue platforms.
Benefits
13th month salary and premium health insurance for the whole family.
"""


def _by_category(jd):
    criteria = _criteria_from_jd({"untrusted_job_description": jd})["criteria"]
    return ([c["description"] for c in criteria if c["category"] == "MUST_HAVE"],
            [c["description"] for c in criteria if c["category"] == "NICE_TO_HAVE"])


def test_items_under_nice_to_have_heading_become_preferred():
    must, nice = _by_category(JD)
    assert any("Airflow" in s for s in nice)
    assert any("Kafka" in s for s in nice)
    assert not any("Kafka" in s or "Airflow" in s for s in must)


def test_about_and_benefit_sections_are_not_requirements():
    must, nice = _by_category(JD)
    assert not any("university" in s for s in must + nice)
    assert not any("salary" in s for s in must + nice)
    assert any("3+ years of experience in Data Engineering" in s for s in must)


def test_crawler_broken_lines_are_joined():
    lines = _joined_lines(JD)
    assert "3+ years of experience in Data Engineering, Backend Engineering, or related roles." in lines
    assert "Nice to have" in lines


def test_repeated_requirement_block_is_not_duplicated():
    must, _ = _by_category(JD + "\n" + JD)
    assert len(must) == len(set(must))


def test_draft_without_preferred_criteria_gets_100_0():
    assert draft_group_totals([{"category": "MUST_HAVE"}]) == (100.0, 0.0)
    assert draft_group_totals([{"category": "MUST_HAVE"}, {"category": "NICE_TO_HAVE"}]) == (70.0, 30.0)
