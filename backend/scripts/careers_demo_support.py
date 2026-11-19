"""Fixtures for a disposable, synthetic demonstration only."""
from email.message import EmailMessage
from io import BytesIO
from docx import Document

DEMO_USER_ID = '4e3710f8-7de4-4f9e-8bde-335f44b377a7'
SOURCE_ID = '8fab8c45-b683-469f-8d82-52714390715a'
TARGET_ID = '607b5006-bc44-4820-a9f2-9192eb7e7084'
SOURCE_CODE = 'DEMO-IT-001'
TARGET_CODE = 'DEMO-IT-002'


#: Fictional profile for the Careers demo scenario. It opens with a full personal
#: name because that is what the system reads to label the candidate — the old
#: file started with "Ứng viên giả — chỉ phục vụ demo", a label rather than a name.
#: English, because English is the standard language for JDs and CVs here.
DEMO_CANDIDATE_NAME = 'Daniel Whitfield'
DEMO_CANDIDATE_EMAIL = 'daniel.whitfield@example.test'


def synthetic_cv():
    doc = Document()
    doc.add_heading(DEMO_CANDIDATE_NAME, 0)
    doc.add_paragraph('Backend Engineer · Python')
    doc.add_paragraph(f'Email: {DEMO_CANDIDATE_EMAIL} · Phone: +44 7700 900112')
    doc.add_paragraph(
        'Backend engineer with 4 years of experience building Python services for '
        'e-commerce and product catalogue systems. Comfortable with high-traffic APIs, '
        'query design and batch data processing.')
    doc.add_paragraph('Work Experience')
    doc.add_paragraph('Backend Engineer — Northbridge Commerce Ltd (03/2022 – 09/2025)')
    doc.add_paragraph('• Built 12 FastAPI endpoints serving the product catalogue at roughly 40,000 requests per day.')
    doc.add_paragraph('• Designed PostgreSQL queries and transactions, cutting median response time from 480 ms to 190 ms.')
    doc.add_paragraph('Skills')
    doc.add_paragraph('Python · FastAPI · REST API · PostgreSQL · SQL · Git · pytest · Docker')
    doc.add_paragraph('Education')
    doc.add_paragraph('BSc Computer Science — University of Leeds (2017 – 2021)')
    output = BytesIO(); doc.save(output)
    return output.getvalue()


def synthetic_email():
    message = EmailMessage()
    message['From'] = DEMO_CANDIDATE_EMAIL
    message['To'] = 'demo@example.invalid'
    message['Subject'] = f'Ứng tuyển giả {SOURCE_CODE}'
    message.set_content('Nội dung email tổng hợp. Không phải thư tuyển dụng thật.')
    message.add_attachment(synthetic_cv(), maintype='application',
        subtype='vnd.openxmlformats-officedocument.wordprocessingml.document', filename='cv-demo-daniel-whitfield.docx')
    return message.as_bytes()
