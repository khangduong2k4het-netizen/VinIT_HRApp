"""F3.03 email channel: CVs sent to the connected Gmail mailbox, with a fake Gmail."""
import base64
import os

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="Set TEST_DATABASE_URL to a disposable local migrated *_test database")

if os.environ.get("TEST_DATABASE_URL"):
    from test_phase1_integration import client, headers, seed  # noqa: F401

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
MAILBOX = "hra.test@gmail.com"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def gmail_message(gid, *, to=MAILBOX, subject="Ứng tuyển", body="Chào anh chị", files=(("CV_Nguyen_Van_A.pdf", PDF),),
                  sender="Nguyễn Văn A <candidate.a@example.test>", message_id=None, extra_headers=()):
    parts = [{"mimeType": "text/plain", "filename": "", "body": {"data": _b64(body.encode())}, "headers": []}]
    for i, (name, data) in enumerate(files):
        parts.append({"mimeType": "application/pdf", "filename": name, "headers": [
            {"name": "Content-Disposition", "value": f'attachment; filename="{name}"'}],
            "body": {"attachmentId": f"att-{gid}-{i}", "size": len(data)}})
    headers_ = [{"name": "From", "value": sender}, {"name": "To", "value": to}, {"name": "Subject", "value": subject},
                {"name": "Message-ID", "value": message_id or f"<{gid}@mail.example.test>"},
                {"name": "Date", "value": "Thu, 26 Nov 2026 09:00:00 +0700"}, *[{"name": k, "value": v} for k, v in extra_headers]]
    return {"id": gid, "threadId": "t-" + gid, "payload": {"mimeType": "multipart/mixed", "headers": headers_, "parts": parts},
            "_files": {f"att-{gid}-{i}": data for i, (_, data) in enumerate(files)}}


@pytest.fixture
def box(seed, monkeypatch, tmp_path):
    from cryptography.fernet import Fernet
    from app.services import gmail_client, mail_intake
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE app_private.mailbox_accounts CASCADE"))
        conn.execute(text("UPDATE app_private.criteria_versions SET status = 'APPROVED' WHERE criteria_version_id = :c"), {"c": seed["cv"]})
        conn.execute(text("""UPDATE app_private.positions SET status = 'OPEN', position_code = 'REQ-IT-901', title = 'Data Engineer'
            WHERE position_id = :p"""), {"p": seed["pos"]})
        conn.execute(text("UPDATE app_private.positions SET position_code = 'REQ-IT-902' WHERE position_id = :p"), {"p": seed["pos2"]})
    monkeypatch.setattr(settings, "GMAIL_INTAKE_ENABLED", True)
    monkeypatch.setattr(settings, "GMAIL_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "GMAIL_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(settings, "GMAIL_PUBSUB_TOPIC", None)
    monkeypatch.setattr(settings, "MAILBOX_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "MALWARE_SCAN_MODE", "off")
    with engine.begin() as conn:
        account_id = conn.execute(text("""INSERT INTO app_private.mailbox_accounts(email_address, refresh_token_ciphertext, history_id)
            VALUES (:e, :t, '100') RETURNING account_id"""), {"e": MAILBOX, "t": gmail_client.encrypt_token("refresh")}).scalar_one()
    inbox: dict = {}
    pending: list = []
    labelled: list = []
    monkeypatch.setattr(gmail_client, "access_token", lambda refresh: "access")
    monkeypatch.setattr(gmail_client, "ensure_labels", lambda token, names: {n: "L" + str(i) for i, n in enumerate(names)})
    monkeypatch.setattr(gmail_client, "history_message_ids", lambda token, start: (list(pending), "200"))
    monkeypatch.setattr(gmail_client, "get_message", lambda token, gid: inbox[gid])
    monkeypatch.setattr(gmail_client, "get_attachment", lambda token, gid, att: inbox[gid]["_files"][att])
    monkeypatch.setattr(gmail_client, "add_label", lambda token, gid, label: labelled.append((gid, label)))

    def deliver(*messages):
        pending.clear()
        for m in messages:
            inbox[m["id"]] = m
            pending.append(m["id"])
        return mail_intake.sync_mailbox()
    return {**seed, "account_id": str(account_id), "deliver": deliver, "labelled": labelled, "tmp": tmp_path}


def _apps(pos):
    with engine.connect() as conn:
        return conn.execute(text("""SELECT a.application_id, a.source_code, i.email, i.display_name
            FROM app_private.applications a JOIN app_private.application_identities i USING (application_id)
            WHERE a.position_id = :p AND a.source_code = 'EMAIL'"""), {"p": pos}).mappings().all()


def _message(gid):
    with engine.connect() as conn:
        return conn.execute(text("SELECT * FROM app_private.mailbox_messages WHERE provider_message_id = :g"), {"g": gid}).mappings().one()


def test_plus_address_places_the_cv_and_keeps_the_sender_as_contact(box):
    counts = box["deliver"](gmail_message("m1", to="hra.test+REQ-IT-901@gmail.com"))
    assert counts["MATCHED"] == 1
    apps = _apps(box["pos"])
    assert len(apps) == 1 and apps[0]["email"] == "candidate.a@example.test" and apps[0]["display_name"] == "Nguyễn Văn A"
    assert _message("m1")["match_method"] == "PLUS_ADDRESS"
    with engine.connect() as conn:
        consents = conn.execute(text("SELECT purpose, channel FROM app_private.application_data_consents WHERE application_id = :a"),
                                {"a": apps[0]["application_id"]}).all()
        audit = conn.execute(text("""SELECT metadata FROM app_private.audit_events WHERE action_type = 'RECEIVE_EMAIL_CV'
            ORDER BY created_at DESC LIMIT 1""")).scalar_one()
    # Consent for this position only: email CVs never enter the Talent Pool.
    assert [tuple(c) for c in consents] == [("THIS_POSITION", "EMAIL")]
    assert "candidate.a" not in str(audit) and "CV_Nguyen" not in str(audit)
    assert ("m1", "L0") in box["labelled"]  # HRA/Đã nhận


def test_code_in_subject_body_or_file_name(box):
    box["deliver"](gmail_message("s1", subject="Ứng tuyển REQ-IT-901 - Tran B", files=(("b.pdf", PDF + b"%1"),)),
                   gmail_message("b1", body="Em ứng tuyển vị trí req-it-901 ạ", files=(("c.pdf", PDF + b"%2"),),
                                 sender="c@example.test"),
                   gmail_message("f1", files=(("CV_REQ-IT-901_D.pdf", PDF + b"%3"),), sender="d@example.test"))
    assert [_message(g)["match_method"] for g in ("s1", "b1", "f1")] == ["SUBJECT_CODE", "BODY_CODE", "FILENAME_CODE"]
    assert len(_apps(box["pos"])) == 3


def test_unclear_mail_goes_to_triage_with_suggestions(box):
    box["deliver"](gmail_message("n1", subject="Ứng tuyển Data Engineer"),
                   gmail_message("u1", subject="Ứng tuyển REQ-XX-999", files=(("u.pdf", PDF + b"%u"),)),
                   gmail_message("x1", subject="REQ-IT-901 hoặc REQ-IT-902", files=(("x.pdf", PDF + b"%x"),)))
    n1, u1, x1 = _message("n1"), _message("u1"), _message("x1")
    assert (n1["status"], n1["reason"]) == ("NEEDS_TRIAGE", "NO_CODE")
    assert n1["suggestions"][0]["position_code"] == "REQ-IT-901"  # title found in the subject
    assert (u1["status"], u1["reason"]) == ("NEEDS_TRIAGE", "UNKNOWN_CODE")
    assert (x1["status"], x1["reason"]) == ("NEEDS_TRIAGE", "MULTIPLE_CODES")
    assert _apps(box["pos"]) == []


def test_closed_position_and_non_cv_mail(box):
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.positions SET status = 'CLOSED' WHERE position_id = :p"), {"p": box["pos"]})
    box["deliver"](gmail_message("c1", subject="REQ-IT-901"),
                   gmail_message("e1", files=()),
                   gmail_message("t1", files=(("notes.pdf", b"not a pdf"),), sender="t@example.test"),
                   gmail_message("a1", extra_headers=(("Auto-Submitted", "auto-replied"),), files=(("a.pdf", PDF + b"%a"),)),
                   gmail_message("o1", sender=MAILBOX, files=(("o.pdf", PDF + b"%o"),)))
    assert (_message("c1")["status"], _message("c1")["reason"]) == ("NEEDS_TRIAGE", "POSITION_NOT_OPEN")
    assert [(_message(g)["status"], _message(g)["reason"]) for g in ("e1", "t1", "a1", "o1")] == [
        ("IGNORED", "NO_CV_ATTACHMENT"), ("IGNORED", "NO_CV_ATTACHMENT"), ("IGNORED", "AUTO_REPLY"), ("IGNORED", "OWN_MESSAGE")]


def test_each_message_is_handled_once_and_a_resent_cv_is_a_duplicate(box):
    first = gmail_message("d1", to="hra.test+REQ-IT-901@gmail.com")
    box["deliver"](first)
    box["deliver"](first)  # same Gmail id again
    box["deliver"](gmail_message("d2", to="hra.test+REQ-IT-901@gmail.com", message_id="<other@x>"))  # same file again
    assert len(_apps(box["pos"])) == 1
    assert (_message("d2")["status"], _message("d2")["reason"]) == ("IGNORED", "DUPLICATE_CV")


def test_hr_assigns_or_ignores_triage_mail(client, box):
    box["deliver"](gmail_message("h1", subject="Gửi CV"), gmail_message("h2", subject="Quảng cáo", files=(("ad.pdf", PDF + b"%ad"),)))
    h = headers(box["hr"])
    listed = client.get("/v1/mailbox/messages", headers=h).json()["items"]
    assert {m["subject"] for m in listed} == {"Gửi CV", "Quảng cáo"}
    assert client.get("/v1/mailbox/messages", headers=headers(box["hm"])).status_code == 403
    h1 = next(m for m in listed if m["subject"] == "Gửi CV")
    opened = client.get(f"/v1/mailbox/attachments/{h1['attachments'][0]['attachment_id']}/file", headers=h)
    assert opened.status_code == 200 and opened.content.startswith(b"%PDF")
    # HR of another position cannot place it there.
    assert client.post(f"/v1/mailbox/messages/{h1['message_id']}/assign", headers=headers(box["hr2"]),
                       json={"position_id": box["pos"]}).status_code == 403
    done = client.post(f"/v1/mailbox/messages/{h1['message_id']}/assign", headers=h, json={"position_id": box["pos"]})
    assert done.status_code == 200 and done.json()["status"] == "MATCHED"
    assert _message("h1")["match_method"] == "HR" and len(_apps(box["pos"])) == 1
    assert client.post(f"/v1/mailbox/messages/{h1['message_id']}/assign", headers=h,
                       json={"position_id": box["pos"]}).status_code == 409
    h2 = next(m for m in listed if m["subject"] == "Quảng cáo")
    assert client.post(f"/v1/mailbox/messages/{h2['message_id']}/ignore", headers=h).json()["status"] == "IGNORED"
    assert not any(p.is_file() for p in (box["tmp"]).rglob("*") if "mailbox" in str(p))  # kept files removed


def test_connect_flow_checks_state_and_admin(client, box, monkeypatch):
    from app.api import mailbox
    from app.services import gmail_client
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id, role_code) VALUES (:u, 'ADMIN')"), {"u": box["other"]})
    assert client.post("/v1/mailbox/gmail/connect", headers=headers(box["hr"])).status_code == 403
    url = client.post("/v1/mailbox/gmail/connect", headers=headers(box["other"])).json()["auth_url"]
    assert "gmail.modify" in url and "pubsub" in url and "access_type=offline" in url
    monkeypatch.setattr(gmail_client, "exchange_code", lambda code: {"access_token": "a", "refresh_token": "new-refresh"})
    monkeypatch.setattr(gmail_client, "get_profile", lambda token: {"emailAddress": "New.Box@gmail.com", "historyId": "5"})
    monkeypatch.setattr("app.services.mail_intake.sync_mailbox", lambda: {})
    bad = client.get("/v1/mailbox/gmail/callback", params={"code": "c", "state": "forged"}, follow_redirects=False)
    assert bad.status_code == 302 and "error=STATE_INVALID" in bad.headers["location"]
    hr_state = mailbox.make_state(box["hr"])  # signed, but not for an admin
    assert "error=NOT_ADMIN" in client.get("/v1/mailbox/gmail/callback", params={"code": "c", "state": hr_state},
                                           follow_redirects=False).headers["location"]
    ok = client.get("/v1/mailbox/gmail/callback", params={"code": "c", "state": mailbox.make_state(box["other"])},
                    follow_redirects=False)
    assert "connected=1" in ok.headers["location"]
    status = client.get("/v1/mailbox/status", headers=headers(box["other"])).json()
    assert status["account"]["email_address"] == "new.box@gmail.com"
    assert status["account"]["address_example"] == "new.box+REQ-IT-043@gmail.com"
    with engine.connect() as conn:
        stored = conn.execute(text("SELECT refresh_token_ciphertext FROM app_private.mailbox_accounts WHERE status = 'ACTIVE'")).scalar_one()
    assert "new-refresh" not in stored and gmail_client.decrypt_token(stored) == "new-refresh"
    addr = client.get("/v1/mailbox/intake-address", params={"position_code": "req-it-901"}, headers=headers(box["hr"])).json()
    assert addr["address"] == "new.box+REQ-IT-901@gmail.com"


def test_email_cv_held_while_busy_is_queued_once_the_position_is_free(box):
    from app.services.portal_dispatch import dispatch_held_portal_cvs
    box["deliver"](gmail_message("busy1", to="hra.test+REQ-IT-901@gmail.com", files=(("a.pdf", PDF + b"%a1"),)),
                   gmail_message("busy2", to="hra.test+REQ-IT-901@gmail.com", files=(("b.pdf", PDF + b"%b2"),),
                                 sender="b@example.test"))
    held_sql = """SELECT COUNT(*) FROM app_private.application_documents d JOIN app_private.applications a USING (application_id)
        WHERE a.position_id = :p AND a.source_code = 'EMAIL' AND d.file_processing_status = 'NEEDS_HR_REVIEW'"""
    with engine.connect() as conn:
        assert conn.execute(text(held_sql), {"p": box["pos"]}).scalar_one() == 1  # the second CV waits
    with engine.begin() as conn:
        conn.execute(text("UPDATE app_private.operations SET status = 'COMPLETED' WHERE position_id = :p"), {"p": box["pos"]})
    assert dispatch_held_portal_cvs() == 1
    with engine.connect() as conn:
        assert conn.execute(text(held_sql), {"p": box["pos"]}).scalar_one() == 0
