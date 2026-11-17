"""Generate and inspect one synthetic MIME message; never connects to Gmail."""
from email.message import EmailMessage
import json
from app.services.email_demo import inspect_synthetic_email


def main():
    message = EmailMessage()
    message['From'] = 'synthetic@example.invalid'
    message['To'] = 'recruitment@example.invalid'
    message['Subject'] = 'Application REQ-IT-001'
    message.set_content('Synthetic demo only.')
    message.add_attachment(b'%PDF-1.4 synthetic demo only', maintype='application', subtype='pdf', filename='synthetic.pdf')
    print(json.dumps(inspect_synthetic_email(message.as_bytes(), {'REQ-IT-001'}), ensure_ascii=False))
    print('Offline inspection only; no malware scan, mailbox, upload, or application created.')


if __name__ == '__main__':
    main()
