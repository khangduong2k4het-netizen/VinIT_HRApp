"""Fixtures for a disposable, synthetic demonstration only."""
from email.message import EmailMessage
from io import BytesIO
from docx import Document

DEMO_USER_ID = '4e3710f8-7de4-4f9e-8bde-335f44b377a7'
SOURCE_ID = '8fab8c45-b683-469f-8d82-52714390715a'
TARGET_ID = '607b5006-bc44-4820-a9f2-9192eb7e7084'
SOURCE_CODE = 'DEMO-IT-001'
TARGET_CODE = 'DEMO-IT-002'


def synthetic_cv():
    doc = Document()
    doc.add_heading('Ứng viên giả — chỉ phục vụ demo', 0)
    doc.add_paragraph('Đây là hồ sơ tổng hợp, không đại diện cho một cá nhân thực tế. ' * 3)
    doc.add_paragraph('Dự án giả: xây dựng API Python, kiểm thử tự động và PostgreSQL. ' * 3)
    output = BytesIO(); doc.save(output)
    return output.getvalue()


def synthetic_email():
    message = EmailMessage()
    message['From'] = 'ungviengia@example.invalid'
    message['To'] = 'demo@example.invalid'
    message['Subject'] = f'Ứng tuyển giả {SOURCE_CODE}'
    message.set_content('Nội dung email tổng hợp. Không phải thư tuyển dụng thật.')
    message.add_attachment(synthetic_cv(), maintype='application',
        subtype='vnd.openxmlformats-officedocument.wordprocessingml.document', filename='cv-gia.docx')
    return message.as_bytes()
