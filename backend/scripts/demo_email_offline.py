"""Generate and inspect synthetic MIME; optionally write a fixture, never connects to Gmail."""
import argparse
from email.message import EmailMessage
import io
import json
from pathlib import Path

from docx import Document
from app.services.email_demo import inspect_synthetic_email


def main():
    parser = argparse.ArgumentParser(description='Synthetic offline email demo')
    parser.add_argument('--write', type=Path, help='write generated synthetic .eml (will not overwrite)')
    parser.add_argument('--code', default='REQ-IT-001', help='synthetic position code')
    args = parser.parse_args()
    cv = Document()
    cv.add_paragraph('Synthetic candidate. This document is not a real CV. ' * 4)
    data = io.BytesIO(); cv.save(data)
    message = EmailMessage()
    message['From'] = 'synthetic@example.invalid'
    message['To'] = 'recruitment@example.invalid'
    message['Subject'] = 'Application ' + args.code
    message.set_content('Synthetic demo only.')
    message.add_attachment(data.getvalue(), maintype='application',
                           subtype='vnd.openxmlformats-officedocument.wordprocessingml.document', filename='synthetic.docx')
    raw = message.as_bytes()
    if args.write:
        with args.write.open('xb') as file:
            file.write(raw)
        print('Synthetic fixture written:', args.write)
    print(json.dumps(inspect_synthetic_email(raw, {args.code}), ensure_ascii=False))
    print('Offline inspection only; no malware scan, mailbox, upload, or application created.')


if __name__ == '__main__':
    main()
