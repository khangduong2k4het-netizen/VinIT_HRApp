"""Fixtures for a disposable, synthetic demonstration only."""
from email.message import EmailMessage
from io import BytesIO
from docx import Document

DEMO_USER_ID = '4e3710f8-7de4-4f9e-8bde-335f44b377a7'
SOURCE_ID = '8fab8c45-b683-469f-8d82-52714390715a'
TARGET_ID = '607b5006-bc44-4820-a9f2-9192eb7e7084'
SOURCE_CODE = 'DEMO-IT-001'
TARGET_CODE = 'DEMO-IT-002'


#: Hồ sơ hư cấu dùng cho kịch bản Careers. Có họ tên đầy đủ ở dòng đầu vì đó
#: là thứ hệ thống đọc để đặt nhãn ứng viên — trước đây tệp này mở bằng
#: "Ứng viên giả — chỉ phục vụ demo", tức là một nhãn chứ không phải tên người.
DEMO_CANDIDATE_NAME = 'Nguyễn Văn An'
DEMO_CANDIDATE_EMAIL = 'nguyen.van.an@example.test'


def synthetic_cv():
    doc = Document()
    doc.add_heading(DEMO_CANDIDATE_NAME, 0)
    doc.add_paragraph('Backend Engineer · Python')
    doc.add_paragraph(f'Email: {DEMO_CANDIDATE_EMAIL} · Điện thoại: 0912 384 617')
    doc.add_paragraph(
        'Backend engineer với 4 năm kinh nghiệm xây dựng dịch vụ Python cho hệ thống '
        'thương mại điện tử và quản lý danh mục sản phẩm. Quen làm việc với API có lưu '
        'lượng cao, thiết kế truy vấn PostgreSQL và xử lý dữ liệu theo lô.')
    doc.add_paragraph('Kinh nghiệm làm việc')
    doc.add_paragraph('Backend Engineer — Công ty CP Thương mại Sông Hồng (03/2022 – 09/2025)')
    doc.add_paragraph('• Xây dựng 12 endpoint FastAPI phục vụ danh mục sản phẩm, khoảng 40.000 request/ngày.')
    doc.add_paragraph('• Thiết kế truy vấn PostgreSQL và xử lý giao dịch, giảm thời gian phản hồi từ 480ms xuống 190ms.')
    doc.add_paragraph('Kỹ năng')
    doc.add_paragraph('Python · FastAPI · REST API · PostgreSQL · SQL · Git · pytest · Docker')
    doc.add_paragraph('Học vấn')
    doc.add_paragraph('Kỹ sư Công nghệ Thông tin — Đại học Bách khoa Hà Nội (2017 – 2021)')
    output = BytesIO(); doc.save(output)
    return output.getvalue()


def synthetic_email():
    message = EmailMessage()
    message['From'] = DEMO_CANDIDATE_EMAIL
    message['To'] = 'demo@example.invalid'
    message['Subject'] = f'Ứng tuyển giả {SOURCE_CODE}'
    message.set_content('Nội dung email tổng hợp. Không phải thư tuyển dụng thật.')
    message.add_attachment(synthetic_cv(), maintype='application',
        subtype='vnd.openxmlformats-officedocument.wordprocessingml.document', filename='cv-demo-nguyen-van-an.docx')
    return message.as_bytes()
