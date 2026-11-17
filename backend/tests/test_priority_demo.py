"""Synthetic-only pure tests; no mailbox or candidate data."""
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from app.services.email_demo import inspect_synthetic_email
from app.services.talent_pool_demo import SyntheticEligibility, eligible_for_synthetic_scan


def test_offline_email_routing_and_ambiguity():
    message = EmailMessage()
    message['Subject'] = 'Apply REQ-IT-001'
    message.set_content('Synthetic content')
    message.add_attachment(b'%PDF-1.4 synthetic', maintype='application', subtype='pdf', filename='sample.pdf')
    result = inspect_synthetic_email(message.as_bytes(), {'REQ-IT-001', 'REQ-IT-002'})
    assert result == {'status': 'CANDIDATE', 'position_code': 'REQ-IT-001', 'attachment_size': 18}
    assert inspect_synthetic_email(message.as_bytes(), {'REQ-IT-002'})['reason'] == 'POSITION_AMBIGUOUS'
    message.replace_header('Subject', 'REQ-IT-001 REQ-IT-002')
    assert inspect_synthetic_email(message.as_bytes(), {'REQ-IT-001', 'REQ-IT-002'})['reason'] == 'POSITION_AMBIGUOUS'
    message.add_attachment(b'x', maintype='application', subtype='pdf', filename='other.pdf')
    message.replace_header('Subject', 'REQ-IT-001')
    assert inspect_synthetic_email(message.as_bytes(), {'REQ-IT-001'})['reason'] == 'ATTACHMENT_COUNT'


def test_pool_synthetic_gate_requires_consent_retention_and_no_deletion():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    future = now + timedelta(days=1)
    def make(**kwargs):
        return SyntheticEligibility(**({'opted_in': True, 'withdrawn': False, 'consent_expires_at': future, 'retention_expires_at': future, 'deletion_pending': False} | kwargs))
    assert eligible_for_synthetic_scan(make(), now)
    for change in ({'opted_in': False}, {'withdrawn': True}, {'deletion_pending': True}, {'consent_expires_at': now}, {'retention_expires_at': now}, {'retention_expires_at': None}, {'consent_expires_at': datetime(2026, 1, 2)}):
        assert not eligible_for_synthetic_scan(make(**change), now)
