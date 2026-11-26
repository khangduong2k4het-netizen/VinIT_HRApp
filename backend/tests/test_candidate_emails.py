"""F3.05 phase 1: HR reviews every candidate email; nothing is sent on its own."""
import os
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from test_phase1_integration import client, headers, seed  # noqa: F401


MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "00026_candidate_emails.sql"


@pytest.fixture
def mail(seed, monkeypatch):
    monkeypatch.setattr(settings, "CANDIDATE_EMAIL_SEND_MODE", "record")
    # Other tests truncate app tables; put back the default templates the migration seeds.
    seed_sql = MIGRATION.read_text(encoding="utf-8").split("INSERT INTO app_private.email_templates", 1)[1]
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO app_private.email_templates" + seed_sql.replace("%", "%%"))
        # auth.users.email is unique and users stay between tests: one address per seed.
        seed["hr_email"] = f"hr-{seed['hr'][:8]}@example.org"
        conn.execute(text("UPDATE auth.users SET email = :e WHERE id = :id"), {"e": seed["hr_email"], "id": seed["hr"]})
        conn.execute(text("UPDATE app_private.application_identities SET email = 'candidate@example.test' WHERE application_id = :id"),
                     {"id": seed["app"]})
        conn.execute(text("UPDATE app_private.positions SET title = 'Data Engineer', position_code = 'REQ-IT-900' WHERE position_id = :id"),
                     {"id": seed["pos"]})
    return seed


def _compose(client, s, code, user="hr"):
    return client.post(f"/v1/candidate-emails/applications/{s['app']}/compose", headers=headers(s[user]),
                       json={"template_code": code})


def test_compose_prefills_sender_recipient_subject_and_body(client, mail, monkeypatch):
    monkeypatch.setattr(settings, "CANDIDATE_EMAIL_FROM", "tuyendung@example.org")
    r = _compose(client, mail, "INTERVIEW_INVITE")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["from_address"] == "tuyendung@example.org" and d["reply_to_address"] == mail["hr_email"]
    assert d["to_address"] == "candidate@example.test" and d["to_source"] == "PROFILE"
    assert "Data Engineer" in d["subject"] and "Candidate app" in d["body"] and "REQ-IT-900" in d["body"]
    assert d["send_mode"] == "record"
    # Interview time and place are left for HR to fill in.
    assert d["unresolved"] == ["dia_diem_pv", "thoi_gian_pv"]
    # Without a shared mailbox the HR user's own address is the sender.
    monkeypatch.setattr(settings, "CANDIDATE_EMAIL_FROM", None)
    monkeypatch.setattr(settings, "SMTP_FROM", None)
    assert _compose(client, mail, "ACK_RECEIVED").json()["from_address"] == mail["hr_email"]


def test_only_hr_of_the_position_can_write(client, mail):
    assert _compose(client, mail, "ACK_RECEIVED", user="hm").status_code == 403
    assert _compose(client, mail, "ACK_RECEIVED", user="hr2").status_code == 403
    assert client.get(f"/v1/candidate-emails/applications/{mail['app']}", headers=headers(mail["hm"])).status_code == 403


def test_send_records_without_emailing_and_keeps_hr_edits(client, mail, monkeypatch):
    sent = []
    monkeypatch.setattr("app.api.candidate_emails.send_email", lambda *a, **k: sent.append(a))
    d = _compose(client, mail, "INTERVIEW_INVITE").json()
    route = f"/v1/candidate-emails/applications/{mail['app']}/emails"
    base = {"template_code": "INTERVIEW_INVITE", "to_address": "other@example.test", "subject": d["subject"], "send": True}
    # Placeholders still in the letter: refused.
    assert client.post(route, headers=headers(mail["hr"]), json={**base, "body": d["body"]}).status_code == 400
    body = d["body"].replace("{thoi_gian_pv}", "9:00 25/11/2026").replace("{dia_diem_pv}", "Phòng I-201")
    assert client.post(route, headers=headers(mail["hr"]), json={**base, "to_address": "not-an-email", "body": body}).status_code == 400
    r = client.post(route, headers=headers(mail["hr"]), json={**base, "body": body + "\nHR edit"})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "RECORDED" and sent == []  # record mode never emails anyone
    history = client.get(f"/v1/candidate-emails/applications/{mail['app']}", headers=headers(mail["hr"])).json()["emails"]
    assert history[0]["to_address"] == "other@example.test" and history[0]["body"].endswith("HR edit")
    assert _compose(client, mail, "INTERVIEW_INVITE").json()["warnings"] == ["ALREADY_SENT"]
    with engine.connect() as conn:
        meta = conn.execute(text("""SELECT metadata FROM app_private.audit_events WHERE action_type = 'SEND_CANDIDATE_EMAIL'
            ORDER BY created_at DESC LIMIT 1""")).scalar_one()
    assert meta["status"] == "RECORDED" and "other@example.test" not in str(meta) and "Phòng" not in str(meta)


def test_rejection_needs_confirmation_and_drafts_can_be_edited_sent_or_cancelled(client, mail):
    d = _compose(client, mail, "REJECTION").json()
    route = f"/v1/candidate-emails/applications/{mail['app']}/emails"
    draft = client.post(route, headers=headers(mail["hr"]), json={
        "template_code": "REJECTION", "trigger_source": "STATUS_CHANGE",
        "to_address": d["to_address"], "subject": d["subject"], "body": d["body"]})
    assert draft.status_code == 201 and draft.json()["status"] == "DRAFT"
    eid = draft.json()["email_id"]
    upd = client.put(f"/v1/candidate-emails/emails/{eid}", headers=headers(mail["hr"]),
                     json={"to_address": d["to_address"], "subject": d["subject"] + " (sửa)", "body": d["body"]})
    assert upd.status_code == 200 and upd.json()["subject"].endswith("(sửa)")
    assert client.post(f"/v1/candidate-emails/emails/{eid}/send", headers=headers(mail["hr"]), json={}).status_code == 400
    assert client.post(f"/v1/candidate-emails/emails/{eid}/send", headers=headers(mail["hm"]),
                       json={"confirmed": True}).status_code == 403
    sent = client.post(f"/v1/candidate-emails/emails/{eid}/send", headers=headers(mail["hr"]), json={"confirmed": True})
    assert sent.status_code == 200 and sent.json()["status"] == "RECORDED"
    assert client.post(f"/v1/candidate-emails/emails/{eid}/cancel", headers=headers(mail["hr"])).status_code == 409
    other = client.post(route, headers=headers(mail["hr"]), json={
        "template_code": "REQUEST_INFO", "to_address": d["to_address"], "subject": "x", "body": "y"}).json()
    cancelled = client.post(f"/v1/candidate-emails/emails/{other['email_id']}/cancel", headers=headers(mail["hr"]))
    assert cancelled.json()["status"] == "CANCELLED"


def test_smtp_mode_sends_through_the_mailer(client, mail, monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "CANDIDATE_EMAIL_SEND_MODE", "smtp")
    monkeypatch.setattr("app.api.candidate_emails.send_email", lambda to, subject, body, **k: sent.append((to, k)))
    d = _compose(client, mail, "ACK_RECEIVED").json()
    r = client.post(f"/v1/candidate-emails/applications/{mail['app']}/emails", headers=headers(mail["hr"]),
                    json={"template_code": "ACK_RECEIVED", "to_address": d["to_address"], "subject": d["subject"],
                          "body": d["body"], "send": True})
    assert r.json()["status"] == "SENT"
    assert sent == [("candidate@example.test", {"from_address": d["from_address"], "reply_to": mail["hr_email"]})]


def test_templates_are_listed_for_hr_and_edited_by_hr_lead_only(client, mail):
    listed = client.get("/v1/candidate-emails/templates", headers=headers(mail["hr"])).json()
    assert {t["template_code"] for t in listed["templates"]} >= {"INTERVIEW_INVITE", "REJECTION"}
    assert listed["can_edit"] is False
    body = {"subject_template": "Mời phỏng vấn {vi_tri}", "body_template": "Chào {ho_ten}"}
    assert client.put("/v1/candidate-emails/templates/INTERVIEW_INVITE", headers=headers(mail["hr"]), json=body).status_code == 403
    assert client.get("/v1/candidate-emails/templates", headers=headers(mail["hm"])).status_code == 403


def test_header_injection_rejected_and_failed_smtp_can_be_retried(client, mail, monkeypatch):
    from app.services.mailer import MailError, send_email
    d = _compose(client, mail, "ACK_RECEIVED").json()
    route = f"/v1/candidate-emails/applications/{mail['app']}/emails"
    bad = client.post(route, headers=headers(mail["hr"]), json={
        "template_code": "ACK_RECEIVED", "to_address": d["to_address"],
        "subject": "Line 1\r\nBcc: evil@example.test", "body": d["body"], "send": True,
    })
    assert bad.status_code == 400
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_FROM", "hr@example.org")
    with pytest.raises(MailError, match="INVALID_HEADER"):
        send_email("candidate@example.test", "Bad\nSubject", "Body")

    # Simulate transient SMTP failure followed by successful retry.
    calls = []
    monkeypatch.setattr(settings, "CANDIDATE_EMAIL_SEND_MODE", "smtp")

    def flaky_send(to, subject, body, **kw):
        calls.append(to)
        if len(calls) == 1:
            raise MailError("SMTPConnectError")

    monkeypatch.setattr("app.api.candidate_emails.send_email", flaky_send)
    first = client.post(route, headers=headers(mail["hr"]), json={
        "template_code": "ACK_RECEIVED", "to_address": d["to_address"],
        "subject": d["subject"], "body": d["body"], "send": True,
    })
    assert first.status_code == 201 and first.json()["status"] == "FAILED"
    eid = first.json()["email_id"]
    retried = client.post(f"/v1/candidate-emails/emails/{eid}/retry", headers=headers(mail["hr"]), json={})
    assert retried.status_code == 200 and retried.json()["status"] == "SENT"
    assert len(calls) == 2
