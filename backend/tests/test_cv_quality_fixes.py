"""Regressions found by uploading 10 synthetic CVs through the UI (13/11/2026)."""
from datetime import date

import pytest

from app.services.deterministic_matching import deterministic_matcher as matcher
from app.services.identity_matching import extract_phone


# ------------------------------------------------------- years of experience
def _years(text: str) -> float:
    return matcher._merged_interval_years(matcher._date_intervals_in(text, date.today().year))


def test_month_names_are_read_in_date_ranges():
    assert _years("Jun 2019 - Dec 2020") == pytest.approx(1.58, abs=0.01)   # used to be ignored
    assert _years("May 2023 to June 2024") == pytest.approx(1.17, abs=0.01)
    assert _years("Sept. 2021 – Aug 2022") == pytest.approx(1.0, abs=0.01)
    assert _years("06/2021 - 12/2023") == pytest.approx(2.58, abs=0.01)
    assert _years("2018 - 2020") == pytest.approx(3.0)                      # year-only ranges unchanged
    assert _years("Mayor 2020 - 2021") == pytest.approx(2.0)                # "Mayor" is not a month


def test_present_runs_to_this_month_not_december():
    today = date.today()
    start = date(today.year - 1, today.month, 1)
    months = 12 + 1  # start month through this month
    assert _years(f"{start.strftime('%b')} {start.year} - Present") == pytest.approx(months / 12, abs=0.01)


def test_study_periods_are_not_years_of_work():
    profile = {
        "work_history": [{"job_title": "Junior Backend Developer", "start_date": "Jun 2024", "end_date": "Jun 2025"}],
        "education": [{"degree": "B.Sc. Information Technology", "years": "2020 - 2024"}],
        "certifications": [{"name": "Course 2019 - 2023"}],
    }
    years = matcher._years_assessment(profile, [], None)["years"]
    assert years == pytest.approx(1.08, abs=0.01)  # used to be 4+ from the degree


def test_separate_start_and_end_fields_are_joined():
    profile = {"work_history": [{"job_title": "Engineer", "start_date": "Jan 2020", "end_date": "Dec 2022"},
                                {"job_title": "Developer", "start_date": "Jun 2018", "end_date": "Dec 2019"}]}
    assert matcher._years_assessment(profile, [], None)["years"] == pytest.approx(4.58, abs=0.01)


# --------------------------------------------------------------- phone number
@pytest.mark.parametrize("text,expected", [
    ("Phone: 0912 345 678", "0912345678"),
    ("Call +84 90 123 4567 anytime", "84901234567"),
    ("B.Sc. Computer Science (2016 - 2020)\nPhone 0912345678", "0912345678"),
])
def test_phone_is_extracted(text, expected):
    assert extract_phone(text) == expected


@pytest.mark.parametrize("text", [
    "B.Eng. Software Engineering (2016 - 2020)",     # was read as phone 20162020
    "Jan 2019 - Dec 2021, Hanoi",
    "GPA 3.6/4.0 (2016 - 2020)",
    "Version 2.1.0.12345",
    "Hotline 1900 1234",
    "",
])
def test_years_and_short_numbers_are_not_phones(text):
    assert extract_phone(text) is None


# ------------------------------------------------------- repair of old data
import os  # noqa: E402

from sqlalchemy import text  # noqa: E402

integration = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                 reason="Requires disposable local *_test PostgreSQL")
if os.environ.get("TEST_DATABASE_URL"):
    from app.db.database import engine
    from test_phase1_integration import client, seed  # noqa: F401 (pytest fixtures)


@integration
def test_repair_clears_year_range_phones_and_their_pending_warnings(seed):
    import importlib.util
    from pathlib import Path
    from sqlalchemy.orm import Session
    spec = importlib.util.spec_from_file_location("repair", Path(__file__).resolve().parents[1] / "scripts" / "repair_short_phones.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.applications(application_id,position_id,created_by) VALUES (gen_random_uuid(),:p,:u)"),
                     {"p": seed["pos"], "u": seed["hr"]})
        third = conn.execute(text("SELECT application_id FROM app_private.applications WHERE position_id=:p AND application_id<>:a"),
                             {"p": seed["pos"], "a": seed["app"]}).scalar_one()
        conn.execute(text("INSERT INTO app_private.application_identities(application_id,display_name,phone) VALUES (:a,'X','20162020')"), {"a": third})
        conn.execute(text("UPDATE app_private.application_identities SET phone='20162020' WHERE application_id=:a"), {"a": seed["app"]})
        conn.execute(text("UPDATE app_private.application_identities SET phone='0912345678' WHERE application_id=:a"), {"a": seed["app2"]})
        first, second = sorted([seed["app"], str(third)])
        conn.execute(text("""INSERT INTO app_private.duplicate_signals(position_id,application_id_1,application_id_2,signal_type,confidence)
            VALUES (:p,:a,:b,'PHONE_MATCH',0.95)"""), {"p": seed["pos"], "a": first, "b": second})
    with Session(engine) as db:
        result = module.repair(db)
        db.commit()
    assert result["phones_cleared"] == 2 and result["warnings_dismissed"] == 1
    with engine.connect() as conn:
        phones = dict(conn.execute(text("SELECT application_id::text, phone FROM app_private.application_identities")).all())
        assert phones[seed["app"]] is None and phones[seed["app2"]] == "0912345678"  # real numbers untouched
        assert conn.execute(text("SELECT review_status FROM app_private.duplicate_signals")).scalar_one() == "DISMISSED"
