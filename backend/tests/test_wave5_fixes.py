"""Wave 5 review fixes: Talent Pool invitations follow consent, letters are never sent twice, mailbox access/retry."""
from __future__ import annotations

import os
import threading
import time

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from sqlalchemy import text

    from app.core.config import settings
    from app.db.database import engine
    from test_candidate_emails import mail  # noqa: F401
    from test_mail_intake import box  # noqa: F401
    from test_phase1_integration import client, headers, seed  # noqa: F401
    from test_talent_pool_scan import _scan_and_run, _set_contact, pool  # noqa: F401


# ---- Talent Pool invitation (ND13) -----------------------------------------------------------------

def _ready_scan(client, seed, pool, *, reveal=True, decide=True):
    """A finished scan of pos2 where HR (hr2) chose CONTACT for the strong candidate and revealed the contact."""
    _set_contact(pool["strong"], email="strong.pool@example.com", phone="0912345678")
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET title = 'Backend Engineer', position_code = 'REQ-IT-902' WHERE position_id = :p"),
                     {"p": seed["pos2"]})
        for template in ("POOL_INVITE",):
            if not conn.execute(text("SELECT 1 FROM app_private.email_templates WHERE template_code = :c"), {"c": template}).first():
                conn.execute(text("""INSERT INTO app_private.email_templates(template_code, name, subject_template, body_template)
                    VALUES ('POOL_INVITE', 'Mời trao đổi', 'Mời trao đổi {vi_tri}', 'Chào {ho_ten}, vị trí {vi_tri} ({ma_vi_tri}).')"""))
    scan_id = _scan_and_run(client, seed)["scan_id"]
    hr2 = headers(seed["hr2"])
    if decide:
        assert client.post(f"/v1/talent-pool/scans/{scan_id}/results/{pool['strong']}/decision", headers=hr2,
                           json={"decision": "CONTACT"}).status_code == 200
    if reveal:
        assert client.post(f"/v1/talent-pool/scans/{scan_id}/results/{pool['strong']}/contact", headers=hr2).status_code == 200
    return scan_id


def _compose_pool(client, seed, app_id, scan_id, user="hr2"):
    body = {"template_code": "POOL_INVITE", **({"scan_id": scan_id} if scan_id else {})}
    return client.post(f"/v1/candidate-emails/applications/{app_id}/compose", headers=headers(seed[user]), json=body)


def _send_pool(client, seed, app_id, scan_id, *, confirmed=True, send=True):
    return client.post(f"/v1/candidate-emails/applications/{app_id}/emails", headers=headers(seed["hr2"]), json={
        "template_code": "POOL_INVITE", "to_address": "strong.pool@example.com", "subject": "Mời trao đổi",
        "body": "Nội dung thư mời", "send": send, "confirmed": confirmed, "scan_id": scan_id})


def test_pool_invite_needs_scan_decision_and_audited_contact_reveal(client, seed, pool, mail):
    strong = pool["strong"]
    # The plain compose route no longer hands the candidate's name and address to anyone for POOL_INVITE.
    assert _compose_pool(client, seed, strong, None, user="hr").status_code == 409
    scan_id = _ready_scan(client, seed, pool, reveal=False, decide=False)
    assert _compose_pool(client, seed, strong, scan_id).status_code == 409  # not marked CONTACT yet
    client.post(f"/v1/talent-pool/scans/{scan_id}/results/{strong}/decision", headers=headers(seed["hr2"]), json={"decision": "CONTACT"})
    revealed_first = _compose_pool(client, seed, strong, scan_id)
    assert revealed_first.status_code == 409 and "xem thông tin liên hệ" in revealed_first.json()["detail"]
    assert client.post(f"/v1/talent-pool/scans/{scan_id}/results/{strong}/contact", headers=headers(seed["hr2"])).status_code == 200

    ok = _compose_pool(client, seed, strong, scan_id)
    assert ok.status_code == 200, ok.text
    letter = ok.json()
    # The letter names the position being filled (target), not the candidate's earlier one.
    assert "Backend Engineer" in letter["subject"] and "REQ-IT-902" in letter["body"] and "REQ-IT-900" not in letter["body"]
    assert letter["to_address"] == "strong.pool@example.com"
    # HR of the candidate's old position has no part in the new one: refused, and nothing is exposed.
    refused = _compose_pool(client, seed, strong, scan_id, user="hr")
    assert refused.status_code == 403 and "strong.pool" not in refused.text
    with engine.connect() as conn:
        audit = conn.execute(text("""SELECT metadata::text FROM app_private.audit_events WHERE action_type = 'COMPOSE_POOL_INVITE'""")).scalar_one()
    assert scan_id in audit and "strong.pool" not in audit


def test_pool_invite_is_sent_only_after_confirmation_and_is_audited(client, seed, pool, mail):
    scan_id = _ready_scan(client, seed, pool)
    assert _send_pool(client, seed, pool["strong"], scan_id, confirmed=False).status_code == 400
    with engine.connect() as conn:  # a refused send leaves no orphan draft behind
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.candidate_emails WHERE template_code = 'POOL_INVITE'")).scalar_one() == 0
    sent = _send_pool(client, seed, pool["strong"], scan_id)
    assert sent.status_code == 201, sent.text
    assert sent.json()["status"] == "RECORDED" and sent.json()["pool_scan_id"] == scan_id
    with engine.connect() as conn:
        audit = conn.execute(text("""SELECT metadata::text FROM app_private.audit_events
            WHERE action_type = 'SEND_CANDIDATE_EMAIL' ORDER BY created_at DESC LIMIT 1""")).scalar_one()
    assert '"pool_invite": true' in audit and scan_id in audit and "strong.pool" not in audit


@pytest.mark.parametrize("how", ["withdrawn", "expired", "deletion_pending", "unmarked"])
def test_pool_invite_is_blocked_when_consent_no_longer_holds(client, seed, pool, mail, how):
    scan_id = _ready_scan(client, seed, pool)
    draft = _send_pool(client, seed, pool["strong"], scan_id, send=False)
    assert draft.status_code == 201, draft.text  # a draft written while consent held
    strong = pool["strong"]
    with engine.begin() as conn:
        if how == "withdrawn":
            conn.execute(text("UPDATE app_private.application_data_consents SET withdrawn_at = NOW() WHERE application_id = :a AND purpose = 'TALENT_POOL'"), {"a": strong})
        elif how == "expired":
            conn.execute(text("UPDATE app_private.applications SET created_at = NOW() - INTERVAL '61 months' WHERE application_id = :a"), {"a": strong})
        elif how == "deletion_pending":
            conn.execute(text("""INSERT INTO app_private.application_retention_cases(application_id, policy_version, position_closed_at, due_date, status)
                SELECT :a, (SELECT policy_version FROM app_private.retention_policy_versions LIMIT 1), NOW(), NOW(), 'SCHEDULED_FOR_DELETION'"""), {"a": strong})
        else:
            conn.execute(text("UPDATE app_private.talent_pool_marks SET removed_at = NOW() WHERE application_id = :a"), {"a": strong})
    blocked = _compose_pool(client, seed, strong, scan_id)
    assert blocked.status_code == 409 and "không còn đủ điều kiện Talent Pool" in blocked.json()["detail"]
    assert "strong.pool" not in blocked.text
    email_id = draft.json()["email_id"]
    sent = client.post(f"/v1/candidate-emails/emails/{email_id}/send", headers=headers(seed["hr2"]), json={"confirmed": True})
    assert sent.status_code == 409
    assert client.post(f"/v1/candidate-emails/applications/{strong}/emails", headers=headers(seed["hr2"]), json={
        "template_code": "POOL_INVITE", "to_address": "strong.pool@example.com", "subject": "s", "body": "b",
        "send": True, "confirmed": True, "scan_id": scan_id}).status_code == 409
    # The old draft can still be thrown away.
    assert client.post(f"/v1/candidate-emails/emails/{email_id}/cancel", headers=headers(seed["hr2"])).status_code == 200
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM app_private.candidate_emails WHERE email_id = :i"), {"i": email_id}).scalar_one() == "CANCELLED"


# ---- no double sending ------------------------------------------------------------------------------

def _draft(client, mail, **extra):
    d = client.post(f"/v1/candidate-emails/applications/{mail['app']}/compose", headers=headers(mail["hr"]),
                    json={"template_code": "ACK_RECEIVED"}).json()
    r = client.post(f"/v1/candidate-emails/applications/{mail['app']}/emails", headers=headers(mail["hr"]), json={
        "template_code": "ACK_RECEIVED", "to_address": "candidate@example.test", "subject": d["subject"], "body": d["body"], "send": False})
    assert r.status_code == 201, r.text
    return r.json()["email_id"]


def test_two_simultaneous_sends_of_one_letter_send_it_once(client, mail, monkeypatch):
    from fastapi import HTTPException
    from app.api import candidate_emails
    monkeypatch.setattr(settings, "CANDIDATE_EMAIL_SEND_MODE", "smtp")
    calls = []

    def slow_send(*args, **kwargs):
        calls.append(args)
        time.sleep(0.8)  # long enough for the second request to arrive while the first one is "in SMTP"

    monkeypatch.setattr(candidate_emails, "send_email", slow_send)
    email_id = _draft(client, mail)
    outcomes = []

    def go():
        try:
            outcomes.append(candidate_emails._deliver_out_of_tx(email_id, mail["hr"], False, allowed_statuses=("DRAFT",))["status"])
        except HTTPException as exc:
            outcomes.append(exc.status_code)

    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1, "the same letter went out twice"
    assert sorted(map(str, outcomes)) == ["409", "SENT"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM app_private.candidate_emails WHERE email_id = :i"), {"i": email_id}).scalar_one() == "SENT"


def test_a_letter_stuck_in_sending_becomes_failed_and_can_be_retried(client, mail, monkeypatch):
    from app.api import candidate_emails
    email_id = _draft(client, mail)
    with engine.begin() as conn:
        conn.execute(text("""UPDATE app_private.candidate_emails SET status = 'SENDING', sending_started_at = NOW() - INTERVAL '11 minutes'
            WHERE email_id = :i"""), {"i": email_id})
    # Fresh SENDING is left alone.
    fresh = _draft(client, mail)
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.candidate_emails SET status = 'SENDING', sending_started_at = NOW() WHERE email_id = :i"), {"i": fresh})
    history = client.get(f"/v1/candidate-emails/applications/{mail['app']}", headers=headers(mail["hr"])).json()["emails"]
    by_id = {e["email_id"]: e for e in history}
    assert (by_id[email_id]["status"], by_id[email_id]["error_code"]) == ("FAILED", "SEND_TIMEOUT")
    assert by_id[fresh]["status"] == "SENDING"
    assert client.post(f"/v1/candidate-emails/emails/{fresh}/send", headers=headers(mail["hr"]), json={}).status_code == 409
    assert client.post(f"/v1/candidate-emails/emails/{email_id}/retry", headers=headers(mail["hr"]), json={}).status_code == 200


def test_send_refused_before_it_starts_leaves_no_orphan_draft(client, mail, monkeypatch):
    from fastapi import HTTPException
    from app.api import candidate_emails

    def refuse(*args, **kwargs):
        raise HTTPException(status_code=429, detail="limit")

    monkeypatch.setattr(candidate_emails, "_deliver_out_of_tx", refuse)
    d = client.post(f"/v1/candidate-emails/applications/{mail['app']}/compose", headers=headers(mail["hr"]), json={"template_code": "ACK_RECEIVED"}).json()
    r = client.post(f"/v1/candidate-emails/applications/{mail['app']}/emails", headers=headers(mail["hr"]), json={
        "template_code": "ACK_RECEIVED", "to_address": "candidate@example.test", "subject": d["subject"], "body": d["body"], "send": True})
    assert r.status_code == 429
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.candidate_emails WHERE application_id = :a"), {"a": mail["app"]}).scalar_one() == 0


def test_failed_attempts_count_toward_the_hourly_limit(client, mail, monkeypatch):
    from app.services.mailer import MailError
    from app.api import candidate_emails
    monkeypatch.setattr(settings, "CANDIDATE_EMAIL_SEND_MODE", "smtp")
    monkeypatch.setattr(settings, "CANDIDATE_EMAIL_MAX_PER_HOUR", 2)

    def broken(*args, **kwargs):
        raise MailError("SMTP_DOWN")

    monkeypatch.setattr(candidate_emails, "send_email", broken)
    email_id = _draft(client, mail)
    route = f"/v1/candidate-emails/emails/{email_id}"
    assert client.post(route + "/send", headers=headers(mail["hr"]), json={}).json()["status"] == "FAILED"
    assert client.post(route + "/retry", headers=headers(mail["hr"]), json={}).json()["status"] == "FAILED"
    assert client.post(route + "/retry", headers=headers(mail["hr"]), json={}).status_code == 429


# ---- mailbox ------------------------------------------------------------------------------------------

def _failed_message(box_ctx, retry_count=0, status="FAILED"):
    with engine.begin() as conn:
        account = conn.execute(text("SELECT account_id FROM app_private.mailbox_accounts LIMIT 1")).scalar_one()
        return str(conn.execute(text("""INSERT INTO app_private.mailbox_messages(account_id, provider_message_id, status, reason, retry_count)
            VALUES (:a, :g, :s, 'SCAN_UNAVAILABLE', :n) RETURNING message_id"""),
                                {"a": account, "g": "failed-" + str(time.time_ns()), "s": status, "n": retry_count}).scalar_one())


def test_mailbox_queue_stays_with_the_hr_system_roles(client, box):
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.user_role_assignments SET revoked_at = NOW() WHERE user_id = :u"), {"u": box["hr2"]})
    assert client.get("/v1/mailbox/messages", headers=headers(box["hr"])).status_code == 200
    # hr2 is only assigned to a position: no longer sees the whole queue or its attachments.
    assert client.get("/v1/mailbox/messages", headers=headers(box["hr2"])).status_code == 403
    assert client.get("/v1/mailbox/intake-address?position_code=REQ-IT-901", headers=headers(box["hr2"])).status_code == 403


def test_message_retry_is_limited_and_cleans_up(client, box, monkeypatch):
    from app.services import mail_intake
    spent = _failed_message(box, retry_count=mail_intake.MAX_MESSAGE_RETRIES)
    r = client.post(f"/v1/mailbox/messages/{spent}/retry", headers=headers(box["hr"]))
    assert r.status_code == 409 and "hết lượt" in r.json()["detail"]
    # Leftovers of a half-done run are cleared before the next attempt; the counter goes up.
    again = _failed_message(box, retry_count=1)
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO app_private.mailbox_attachments(message_id, filename, mime_type, size_bytes, status, reject_reason)
            VALUES (:m, 'old.pdf', 'application/pdf', 1, 'REJECTED', 'X')"""), {"m": again})
    monkeypatch.setattr(mail_intake, "_process", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    failed = client.post(f"/v1/mailbox/messages/{again}/retry", headers=headers(box["hr"]))
    assert failed.status_code == 502
    with engine.connect() as conn:
        row = conn.execute(text("SELECT status, retry_count FROM app_private.mailbox_messages WHERE message_id = :m"), {"m": again}).one()
        assert tuple(row) == ("FAILED", 2)  # not stuck in NEW
        assert conn.execute(text("SELECT COUNT(*) FROM app_private.mailbox_attachments WHERE message_id = :m"), {"m": again}).scalar_one() == 0
    # A retry that crashed in the middle leaves NEW; after the stale period it can be retried.
    stuck = _failed_message(box, retry_count=1, status="NEW")
    assert client.post(f"/v1/mailbox/messages/{stuck}/retry", headers=headers(box["hr"])).status_code == 409
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.mailbox_messages SET retry_started_at = NOW() - INTERVAL '20 minutes' WHERE message_id = :m"), {"m": stuck})
    assert client.post(f"/v1/mailbox/messages/{stuck}/retry", headers=headers(box["hr"])).status_code == 502  # _process still patched to fail


def test_gmail_label_sync_never_breaks_the_hr_decision(box, monkeypatch):
    from app.services import gmail_client, mail_intake
    with engine.connect() as conn:
        account = str(conn.execute(text("SELECT account_id FROM app_private.mailbox_accounts LIMIT 1")).scalar_one())

    def explode(*args, **kwargs):
        raise ValueError("not a Gmail error")

    monkeypatch.setattr(gmail_client, "access_token", explode)
    mail_intake.sync_triage_label(account, "gid-1", "MATCHED")  # must not raise


def test_assign_and_ignore_do_not_wait_for_gmail(client, box, monkeypatch):
    from app.services import mail_intake
    scheduled = []
    monkeypatch.setattr(mail_intake, "schedule_triage_label_sync", lambda *a: scheduled.append(a))
    with engine.begin() as conn:
        account = conn.execute(text("SELECT account_id FROM app_private.mailbox_accounts LIMIT 1")).scalar_one()
        msg = conn.execute(text("""INSERT INTO app_private.mailbox_messages(account_id, provider_message_id, status)
            VALUES (:a, 'ign-1', 'NEEDS_TRIAGE') RETURNING message_id"""), {"a": account}).scalar_one()
    r = client.post(f"/v1/mailbox/messages/{msg}/ignore", headers=headers(box["hr"]))
    assert r.status_code == 200 and scheduled and scheduled[0][2] == "IGNORED"
