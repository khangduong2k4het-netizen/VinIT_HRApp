"""Dữ liệu 30 hồ sơ cho bộ demo tuyển dụng.

Mỗi hồ sơ là một người **hư cấu** nhưng được viết như CV thật: có họ tên đầy
đủ, chức danh, tóm tắt nghề nghiệp, kinh nghiệm theo từng công ty với số liệu
cụ thể, học vấn, chứng chỉ và kỹ năng.

Ràng buộc quan trọng: **hồ sơ kỹ năng phải khớp `BANG_PHAN_BO_30_CV.md`**.
Kịch bản demo dựa vào việc CV nào đủ/thiếu bằng chứng cho vị trí nào (ví dụ CV
02 có Flask nhưng thiếu pipeline; CV 06 thiên Java). Đổi kỹ năng là làm hỏng
kịch bản, nên phần `skills` phải giữ nguyên ý nghĩa so với bảng.

Mọi thông tin liên hệ dùng tên miền `example.test` / `example.invalid` — không
bao giờ trỏ tới người thật. Không có ảnh, ngày sinh, giới tính, tình trạng hôn
nhân, quốc tịch, tôn giáo, CCCD hay địa chỉ nhà: đó cũng đúng là những gì hệ
thống được phép xử lý.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Experience:
    role: str
    company: str
    period: str
    location: str
    #: Gạch đầu dòng thành tích, có số liệu. Viết như người thật viết CV.
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class Education:
    degree: str
    school: str
    period: str
    detail: str = ""


@dataclass(frozen=True)
class Candidate:
    number: int
    full_name: str
    headline: str
    email: str
    #: Định dạng hiển thị; số điện thoại cố ý dùng dải 09xx không ấn định.
    phone: str
    summary: str
    skills: tuple[str, ...]
    experience: tuple[Experience, ...]
    education: tuple[Education, ...]
    certifications: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    projects: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    #: Vị trí nộp theo bảng phân bổ (chỉ để đối chiếu, không in lên CV).
    applies_to: str = ""
    #: Tên tệp cũ (tham chiếu cho kịch bản), không in lên CV.
    legacy_filename: str = ""


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        number=1,
        full_name="Nguyễn Văn An",
        headline="Backend Engineer · Python",
        email="nguyen.van.an@example.test",
        phone="0912 384 617",
        summary=(
            "Backend engineer với 4 năm kinh nghiệm xây dựng dịch vụ Python cho "
            "hệ thống thương mại điện tử và quản lý danh mục sản phẩm. Quen làm "
            "việc với API có lưu lượng cao, thiết kế truy vấn và xử lý dữ liệu "
            "theo lô. Thích viết kiểm thử trước khi sửa mã cũ."
        ),
        skills=(
            "Python", "FastAPI", "REST API", "PostgreSQL", "SQL", "Git",
            "pytest", "Docker", "Redis", "làm sạch dữ liệu",
        ),
        experience=(
            Experience(
                role="Backend Engineer",
                company="Công ty CP Thương mại Sông Hồng",
                period="03/2022 – 09/2025",
                location="Hà Nội",
                bullets=(
                    "Xây dựng 12 endpoint FastAPI phục vụ danh mục sản phẩm, phục vụ khoảng 40.000 request/ngày.",
                    "Thiết kế truy vấn PostgreSQL và xử lý giao dịch cho luồng cập nhật tồn kho, giảm thời gian phản hồi trung bình từ 480ms xuống 190ms.",
                    "Bổ sung xác thực dữ liệu đầu vào và tài liệu OpenAPI, cắt 60% lỗi 500 do dữ liệu sai định dạng.",
                    "Viết unit test và integration test cho tầng API, nâng độ phủ từ 41% lên 78%.",
                ),
            ),
            Experience(
                role="Backend Developer",
                company="Công ty TNHH Phần mềm An Phú",
                period="07/2021 – 02/2022",
                location="Hà Nội",
                bullets=(
                    "Phát triển dịch vụ đồng bộ dữ liệu giữa hệ thống bán hàng và kho, chạy theo lô 30 phút một lần.",
                    "Bổ sung cơ chế thử lại và ghi log có mã tương quan, giảm số tác vụ thất bại âm thầm.",
                ),
            ),
        ),
        education=(
            Education(
                degree="Kỹ sư Công nghệ Thông tin",
                school="Đại học Bách khoa Hà Nội",
                period="2017 – 2021",
                detail="Chuyên ngành Hệ thống thông tin. Đồ án tốt nghiệp: hệ thống đặt hàng viết bằng Django.",
            ),
        ),
        certifications=("AWS Certified Cloud Practitioner (2023)",),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (đọc tài liệu kỹ thuật, B2)"),
        projects=(
            (
                "Kho dữ liệu danh mục dùng chung",
                "Tách danh mục sản phẩm khỏi ba hệ thống con thành một dịch vụ đọc duy nhất; "
                "chuẩn hoá 1,2 triệu bản ghi và đặt quy tắc kiểm tra chất lượng dữ liệu.",
            ),
        ),
        applies_to="Backend Python",
        legacy_filename="CV_01_An_Careers_Dong_y.docx",
    ),
    Candidate(
        number=2,
        full_name="Trần Đình Bình",
        headline="Python Developer",
        email="tran.dinh.binh@example.test",
        phone="0963 512 408",
        summary=(
            "Lập trình viên Python 3 năm kinh nghiệm, chủ yếu làm dịch vụ web nhỏ "
            "và công cụ nội bộ bằng Flask. Quen với SQL và viết kiểm thử ở mức "
            "đơn vị. Đang tìm môi trường có quy trình review mã rõ ràng."
        ),
        skills=(
            "Python", "Flask", "REST API", "SQL", "SQLite", "Git", "unittest",
            "viết tài liệu kỹ thuật",
        ),
        experience=(
            Experience(
                role="Python Developer",
                company="Công ty TNHH Giải pháp Dữ liệu Tân Long",
                period="05/2023 – 10/2025",
                location="Đà Nẵng",
                bullets=(
                    "Bảo trì dịch vụ Flask phục vụ 8 khách hàng doanh nghiệp nhỏ, xử lý khoảng 5.000 request/ngày.",
                    "Bổ sung 7 endpoint tra cứu và xuất báo cáo CSV từ SQLite.",
                    "Viết bộ kiểm thử unittest cho tầng xử lý, phát hiện 15 lỗi biên trước khi phát hành.",
                    "Soạn tài liệu vận hành và hướng dẫn bàn giao cho nhóm hỗ trợ.",
                ),
            ),
            Experience(
                role="Thực tập sinh phát triển",
                company="Trung tâm Công nghệ Thông tin Đà Thành",
                period="09/2022 – 04/2023",
                location="Đà Nẵng",
                bullets=(
                    "Viết script Python xử lý file Excel chấm công, tiết kiệm khoảng 6 giờ mỗi tháng.",
                ),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Đà Nẵng",
                period="2018 – 2022",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (A2)"),
        applies_to="Backend Python",
        legacy_filename="CV_02_Binh_Careers_Khong_dong_y.pdf",
    ),
    Candidate(
        number=3,
        full_name="Lê Thị Kim Chi",
        headline="Backend Developer · Python & FastAPI",
        email="le.thi.kim.chi@example.test",
        phone="0977 204 583",
        summary=(
            "Kỹ sư backend 5 năm kinh nghiệm, tập trung vào API Python cho lĩnh "
            "vực tài chính. Có kinh nghiệm phối hợp triển khai với nhóm hạ tầng "
            "và hỗ trợ kỹ thuật sau bán."
        ),
        skills=(
            "Python", "FastAPI", "REST API", "PostgreSQL", "SQL", "Git", "pytest",
            "Docker", "tài liệu API",
        ),
        experience=(
            Experience(
                role="Backend Developer",
                company="Công ty CP Công nghệ Tài chính Minh Khang",
                period="01/2022 – 10/2025",
                location="TP. Hồ Chí Minh",
                bullets=(
                    "Xây dựng API FastAPI cho luồng đăng ký và xác thực hồ sơ vay, phục vụ 25.000 người dùng.",
                    "Thiết kế truy vấn PostgreSQL cho báo cáo đối soát hằng ngày, rút thời gian chạy từ 11 phút xuống 3 phút.",
                    "Phối hợp với nhóm hạ tầng đóng gói dịch vụ bằng Docker và cấu hình kiểm thử sức chịu tải.",
                    "Trực hỗ trợ kỹ thuật cấp hai, xử lý khoảng 20 sự cố mỗi tháng và viết lại tài liệu khắc phục.",
                ),
            ),
            Experience(
                role="Junior Backend Developer",
                company="Công ty TNHH Phần mềm Sao Việt",
                period="06/2020 – 12/2021",
                location="TP. Hồ Chí Minh",
                bullets=(
                    "Phát triển module thông báo qua email và tin nhắn cho hệ thống quản lý đơn hàng.",
                ),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Khoa học Máy tính",
                school="Đại học Khoa học Tự nhiên TP. Hồ Chí Minh",
                period="2016 – 2020",
                detail="GPA 3.2/4.0.",
            ),
        ),
        certifications=("Microsoft Certified: Azure Fundamentals (2022)",),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1, làm việc với tài liệu)"),
        applies_to="Backend Python (Gmail)",
        legacy_filename="CV_03_Chi_Gmail.docx",
    ),
    Candidate(
        number=4,
        full_name="Phạm Tiến Dũng",
        headline="Backend Engineer",
        email="pham.tien.dung@example.test",
        phone="0908 741 236",
        summary=(
            "Backend engineer 4 năm kinh nghiệm với Python và PostgreSQL, chủ yếu "
            "làm hệ thống quản lý đơn hàng. Chú trọng chuẩn hoá dữ liệu đầu vào và "
            "kiểm thử tích hợp."
        ),
        skills=(
            "Python", "FastAPI", "PostgreSQL", "SQL", "pytest", "Git",
            "chuẩn hoá dữ liệu", "kiểm thử tích hợp",
        ),
        experience=(
            Experience(
                role="Backend Engineer",
                company="Công ty CP Bán lẻ Hà Thành",
                period="04/2022 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Xây dựng API quản lý đơn hàng bằng FastAPI, xử lý 6.000 đơn mỗi ngày vào cao điểm.",
                    "Chuẩn hoá dữ liệu đầu vào từ ba kênh bán hàng, loại bỏ 4.000 bản ghi trùng trong quý đầu.",
                    "Viết kiểm thử tích hợp cho luồng thanh toán và hoàn tiền, chặn được 9 lỗi hồi quy.",
                    "Tham gia trực ca và xử lý sự cố liên quan tới hàng đợi xử lý đơn.",
                ),
            ),
            Experience(
                role="Backend Developer",
                company="Công ty TNHH Công nghệ Vĩnh Phát",
                period="08/2021 – 03/2022",
                location="Hà Nội",
                bullets=(
                    "Bảo trì dịch vụ tra cứu tồn kho viết bằng Python và PostgreSQL.",
                ),
            ),
        ),
        education=(
            Education(
                degree="Kỹ sư Công nghệ Thông tin",
                school="Đại học Công nghệ – Đại học Quốc gia Hà Nội",
                period="2017 – 2021",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        projects=(
            (
                "Đồng bộ danh mục đa kênh",
                "Gộp danh mục sản phẩm của website, ứng dụng và sàn liên kết về một nguồn; "
                "viết tác vụ đối soát hằng đêm bằng Python.",
            ),
        ),
        applies_to="Backend Python",
        legacy_filename="CV_04_Dung.docx",
    ),
    Candidate(
        number=5,
        full_name="Vũ Thị Hạnh",
        headline="Backend Engineer · Python & QA",
        email="vu.thi.hanh@example.test",
        phone="0934 618 902",
        summary=(
            "Kỹ sư backend 4 năm kinh nghiệm với Django, có thế mạnh ở phần kiểm "
            "thử: từng làm việc sát nhóm QA để chuẩn hoá test case và tự động hoá "
            "kiểm thử API."
        ),
        skills=(
            "Python", "Django", "REST", "PostgreSQL", "pytest", "Docker",
            "test case", "tự động hoá kiểm thử API",
        ),
        experience=(
            Experience(
                role="Backend Engineer",
                company="Công ty CP Giáo dục Trực tuyến Nam Việt",
                period="02/2022 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Bảo trì dịch vụ Django phục vụ 18.000 học viên, sửa 30 lỗi API trong năm đầu.",
                    "Phối hợp nhóm QA chuẩn hoá 120 test case và tự động hoá 45 ca kiểm thử API bằng pytest.",
                    "Đóng gói dịch vụ bằng Docker cho môi trường kiểm thử, giảm lệch cấu hình giữa các máy.",
                    "Rà soát truy vấn chậm và thêm chỉ mục, cải thiện 35% thời gian tải trang danh sách khoá học.",
                ),
            ),
            Experience(
                role="Developer",
                company="Công ty TNHH Phần mềm Đông Á",
                period="07/2021 – 01/2022",
                location="Hà Nội",
                bullets=("Phát triển module quản lý người dùng cho hệ thống nội bộ.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Thăng Long",
                period="2017 – 2021",
            ),
        ),
        certifications=("ISTQB Certified Tester Foundation Level (2022)",),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="Backend Python",
        legacy_filename="CV_05_Hanh.docx",
    ),
    Candidate(
        number=6,
        full_name="Đỗ Minh Khánh",
        headline="Backend Engineer · Java",
        email="do.minh.khanh@example.test",
        phone="0918 337 064",
        summary=(
            "Kỹ sư backend 5 năm kinh nghiệm phát triển hệ thống Java cho ngân "
            "hàng và bảo hiểm. Có nền tảng API và cơ sở dữ liệu quan hệ vững, đang "
            "muốn mở rộng sang Python."
        ),
        skills=(
            "Java", "Spring Boot", "MySQL", "REST", "JUnit", "Git", "Maven",
            "thiết kế cơ sở dữ liệu quan hệ",
        ),
        experience=(
            Experience(
                role="Backend Engineer",
                company="Công ty CP Công nghệ Ngân hàng Tín Việt",
                period="03/2021 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Phát triển API Java cho danh mục sản phẩm tín dụng, phục vụ 3 hệ thống nội bộ.",
                    "Viết JUnit cho tầng nghiệp vụ, nâng độ phủ kiểm thử của module từ 30% lên 65%.",
                    "Review truy vấn MySQL và tối ưu 14 câu lệnh chậm, giảm tải cơ sở dữ liệu vào giờ cao điểm.",
                    "Tham gia thiết kế luồng xử lý hồ sơ và viết tài liệu kỹ thuật bàn giao.",
                ),
            ),
            Experience(
                role="Java Developer",
                company="Công ty TNHH Phần mềm Bảo hiểm An Gia",
                period="06/2019 – 02/2021",
                location="Hà Nội",
                bullets=("Phát triển module tính phí bảo hiểm và xuất hợp đồng.",),
            ),
        ),
        education=(
            Education(
                degree="Kỹ sư Công nghệ Thông tin",
                school="Đại học Bách khoa Hà Nội",
                period="2015 – 2019",
            ),
        ),
        certifications=("Oracle Certified Associate, Java SE 8 (2020)",),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (đọc tài liệu, B2)"),
        applies_to="Backend Python",
        legacy_filename="CV_06_Khanh.docx",
    ),
    Candidate(
        number=7,
        full_name="Hoàng Thị Linh",
        headline="Data Engineer · Python",
        email="hoang.thi.linh@example.test",
        phone="0946 820 551",
        summary=(
            "Kỹ sư dữ liệu 4 năm kinh nghiệm xây dựng pipeline xử lý dữ liệu bằng "
            "Python và SQL. Làm chủ yếu với dữ liệu bán hàng và marketing, quan "
            "tâm tới chất lượng dữ liệu hơn là số lượng báo cáo."
        ),
        skills=(
            "Python", "SQL", "PostgreSQL", "pandas", "REST", "pytest",
            "làm sạch dữ liệu", "thiết kế pipeline",
        ),
        experience=(
            Experience(
                role="Data Engineer",
                company="Công ty CP Thương mại Điện tử VinaShop",
                period="05/2022 – 10/2025",
                location="TP. Hồ Chí Minh",
                bullets=(
                    "Xây dựng tác vụ làm sạch dữ liệu bằng Python và pandas cho 2,4 triệu bản ghi giao dịch.",
                    "Kiểm tra giá trị thiếu và xử lý lỗi nhập theo lô, giảm 70% số dòng lỗi trong báo cáo cuối ngày.",
                    "Viết truy vấn SQL tổng hợp dữ liệu bán hàng cho nhóm phân tích.",
                    "Đóng gói pipeline bằng Docker và thêm kiểm thử pytest cho từng bước xử lý.",
                ),
            ),
            Experience(
                role="Data Analyst",
                company="Công ty TNHH Nghiên cứu Thị trường Sài Gòn",
                period="03/2021 – 04/2022",
                location="TP. Hồ Chí Minh",
                bullets=("Tổng hợp dữ liệu khảo sát bằng SQL và Excel cho khoảng 40 dự án.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Khoa học Dữ liệu",
                school="Đại học Khoa học Tự nhiên TP. Hồ Chí Minh",
                period="2017 – 2021",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        projects=(
            (
                "Kho dữ liệu bán hàng hợp nhất",
                "Hợp nhất dữ liệu từ ba kênh bán hàng về một mô hình chung, viết tác vụ đối soát hằng ngày.",
            ),
        ),
        applies_to="Tích hợp dữ liệu",
        legacy_filename="CV_07_Linh.docx",
    ),
    Candidate(
        number=8,
        full_name="Ngô Quang Minh",
        headline="Data Integration Specialist",
        email="ngo.quang.minh@example.test",
        phone="0912 905 778",
        summary=(
            "Chuyên viên tích hợp dữ liệu 5 năm kinh nghiệm, làm việc với SQL và "
            "Python để đối soát dữ liệu giữa các hệ thống. Quen với môi trường "
            "nhiều nguồn dữ liệu và yêu cầu số liệu phải khớp."
        ),
        skills=(
            "SQL", "Python", "pandas", "PostgreSQL", "Git", "Excel",
            "đối soát dữ liệu", "kiểm tra chất lượng dữ liệu",
        ),
        experience=(
            Experience(
                role="Chuyên viên tích hợp dữ liệu",
                company="Công ty CP Tài chính Tiêu dùng Phương Đông",
                period="02/2021 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Viết truy vấn SQL và script Python đối soát dữ liệu giữa hệ thống lõi và hệ thống báo cáo, chạy hằng ngày.",
                    "Kiểm tra chất lượng dữ liệu theo bộ 25 quy tắc, phát hiện trung bình 300 dòng lỗi mỗi tháng.",
                    "Phối hợp với nhóm kế toán xử lý chênh lệch số liệu cuối kỳ, rút thời gian đối soát từ 3 ngày xuống 1 ngày.",
                    "Viết tài liệu luồng dữ liệu cho 6 hệ thống nguồn.",
                ),
            ),
            Experience(
                role="Chuyên viên dữ liệu",
                company="Công ty TNHH Dịch vụ Số Hoàng Long",
                period="08/2019 – 01/2021",
                location="Hà Nội",
                bullets=("Tổng hợp và làm sạch dữ liệu khách hàng bằng SQL và Excel.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Hệ thống Thông tin Quản lý",
                school="Đại học Kinh tế Quốc dân",
                period="2015 – 2019",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="Tích hợp dữ liệu",
        legacy_filename="CV_08_Minh.docx",
    ),
    Candidate(
        number=9,
        full_name="Trịnh Thị Nga",
        headline="Pipeline Engineer",
        email="trinh.thi.nga@example.test",
        phone="0975 462 130",
        summary=(
            "Kỹ sư pipeline 4 năm kinh nghiệm vận hành luồng dữ liệu bằng Airflow "
            "và Python. Làm nhiều với theo dõi tác vụ thất bại, viết quy trình phục "
            "hồi và cảnh báo sớm."
        ),
        skills=(
            "Python", "SQL", "Airflow", "PostgreSQL", "Docker", "pytest",
            "theo dõi tác vụ", "viết tài liệu phục hồi",
        ),
        experience=(
            Experience(
                role="Pipeline Engineer",
                company="Công ty CP Dữ liệu Lớn Miền Nam",
                period="06/2022 – 10/2025",
                location="TP. Hồ Chí Minh",
                bullets=(
                    "Điều chỉnh 60 pipeline Airflow chạy theo lô, giảm số lần chạy lại thủ công 45%.",
                    "Theo dõi tác vụ thất bại và viết tài liệu phục hồi cho 12 pipeline quan trọng nhất.",
                    "Thêm kiểm thử pytest cho từng DAG trước khi triển khai, chặn 18 lỗi cấu hình.",
                    "Đóng gói môi trường chạy bằng Docker để đồng nhất giữa kiểm thử và vận hành.",
                ),
            ),
            Experience(
                role="Data Operations Engineer",
                company="Công ty TNHH Công nghệ Số Tân Bình",
                period="09/2021 – 05/2022",
                location="TP. Hồ Chí Minh",
                bullets=("Giám sát luồng dữ liệu hằng ngày và xử lý sự cố tác vụ chậm.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Công nghệ Thông tin – ĐHQG TP. Hồ Chí Minh",
                period="2017 – 2021",
            ),
        ),
        certifications=("Astronomer Certification for Apache Airflow Fundamentals (2023)",),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="Tích hợp dữ liệu",
        legacy_filename="CV_09_Nga.docx",
    ),
    Candidate(
        number=10,
        full_name="Bùi Hồng Phúc",
        headline="API Integration Engineer",
        email="bui.hong.phuc@example.test",
        phone="0938 217 645",
        summary=(
            "Kỹ sư tích hợp 4 năm kinh nghiệm nối hệ thống qua REST API bằng "
            "Python. Quen thiết kế endpoint, xử lý thử lại và giới hạn tải khi "
            "làm việc với đối tác bên ngoài."
        ),
        skills=(
            "Python", "FastAPI", "SQL", "REST", "Git", "unittest",
            "tích hợp hệ thống", "thiết kế endpoint",
        ),
        experience=(
            Experience(
                role="API Integration Engineer",
                company="Công ty CP Công nghệ Bán lẻ Thiên Phú",
                period="04/2022 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Tích hợp API giữa ứng dụng bán hàng và hệ thống danh mục, đồng bộ 90.000 bản ghi mỗi ngày.",
                    "Thêm giới hạn thử lại và backoff khi gọi dịch vụ đối tác, giảm 80% số lần đồng bộ thất bại.",
                    "Thiết kế 15 endpoint nội bộ bằng FastAPI kèm tài liệu OpenAPI.",
                    "Viết kiểm thử unittest cho tầng chuyển đổi dữ liệu giữa hai hệ thống.",
                ),
            ),
            Experience(
                role="Backend Developer",
                company="Công ty TNHH Phần mềm Cầu Vồng",
                period="07/2021 – 03/2022",
                location="Hà Nội",
                bullets=("Phát triển module nhập dữ liệu từ file CSV cho hệ thống quản lý.",),
            ),
        ),
        education=(
            Education(
                degree="Kỹ sư Công nghệ Thông tin",
                school="Học viện Công nghệ Bưu chính Viễn thông",
                period="2017 – 2021",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="Tích hợp dữ liệu",
        legacy_filename="CV_10_Phuc.docx",
    ),
    Candidate(
        number=11,
        full_name="Đặng Kim Quyên",
        headline="Data Analyst",
        email="dang.kim.quyen@example.test",
        phone="0903 574 862",
        summary=(
            "Chuyên viên phân tích dữ liệu 6 năm kinh nghiệm với SQL và Power BI, "
            "làm báo cáo vận hành cho khối bán lẻ. Mạnh ở việc hiểu nghiệp vụ và "
            "trình bày số liệu, chưa có kinh nghiệm phát triển API."
        ),
        skills=(
            "SQL", "Excel", "Power BI", "dữ liệu bảng", "tài liệu nghiệp vụ",
            "phân tích báo cáo", "trực quan hoá dữ liệu",
        ),
        experience=(
            Experience(
                role="Chuyên viên phân tích dữ liệu",
                company="Công ty CP Bán lẻ Miền Trung",
                period="01/2019 – 10/2025",
                location="Đà Nẵng",
                bullets=(
                    "Tổng hợp báo cáo doanh thu và tồn kho cho 32 cửa hàng bằng SQL và Power BI.",
                    "Chuẩn hoá danh mục ngành hàng, giảm số nhóm trùng từ 210 xuống 145.",
                    "Phối hợp với khối vận hành làm rõ yêu cầu số liệu cho 8 báo cáo định kỳ.",
                    "Viết tài liệu nghiệp vụ cho hệ thống báo cáo nội bộ.",
                ),
            ),
            Experience(
                role="Nhân viên phân tích",
                company="Công ty TNHH Thương mại Hòa Bình",
                period="06/2017 – 12/2018",
                location="Đà Nẵng",
                bullets=("Làm báo cáo bán hàng tháng bằng Excel và SQL cơ bản.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Thống kê Kinh tế",
                school="Đại học Kinh tế – Đại học Đà Nẵng",
                period="2013 – 2017",
            ),
        ),
        certifications=("Microsoft Power BI Data Analyst Associate (2022)",),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (A2)"),
        applies_to="Tích hợp dữ liệu",
        legacy_filename="CV_11_Quyen.docx",
    ),
    Candidate(
        number=12,
        full_name="Lý Thanh Sơn",
        headline="Data Synchronisation Specialist",
        email="ly.thanh.son@example.test",
        phone="0968 130 924",
        summary=(
            "Chuyên viên đồng bộ dữ liệu 5 năm kinh nghiệm, viết script Python và "
            "SQL để giữ dữ liệu giữa các hệ thống khớp nhau. Quen xử lý tình huống "
            "API timeout và dữ liệu về muộn."
        ),
        skills=(
            "Python", "SQL", "MySQL", "REST", "Git", "script đồng bộ",
            "xử lý lỗi tích hợp",
        ),
        experience=(
            Experience(
                role="Chuyên viên đồng bộ dữ liệu",
                company="Công ty CP Logistics Hải Đăng",
                period="03/2020 – 10/2025",
                location="Hải Phòng",
                bullets=(
                    "Viết script Python đồng bộ dữ liệu vận đơn giữa hệ thống điều phối và kho, 40.000 bản ghi mỗi ngày.",
                    "Kiểm thử tình huống API timeout và bổ sung cơ chế chạy bù, giảm 65% số đơn thiếu trạng thái.",
                    "Viết truy vấn MySQL kiểm tra chênh lệch dữ liệu giữa hai hệ thống.",
                    "Bàn giao quy trình xử lý sự cố cho nhóm vận hành ca đêm.",
                ),
            ),
            Experience(
                role="Nhân viên kỹ thuật",
                company="Công ty TNHH Cảng Đình Vũ",
                period="07/2018 – 02/2020",
                location="Hải Phòng",
                bullets=("Hỗ trợ nhập liệu và kiểm tra dữ liệu chuyến hàng.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Hàng hải Việt Nam",
                period="2014 – 2018",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (A2)"),
        applies_to="Tích hợp dữ liệu",
        legacy_filename="CV_12_Son.docx",
    ),
    Candidate(
        number=13,
        full_name="Nguyễn Phương Thảo",
        headline="Frontend Developer · React",
        email="nguyen.phuong.thao@example.test",
        phone="0914 628 305",
        summary=(
            "Frontend developer 4 năm kinh nghiệm với React và TypeScript, làm sản "
            "phẩm nội bộ cho khối vận hành. Quen viết kiểm thử thành phần và phối "
            "hợp chặt với nhóm QA."
        ),
        skills=(
            "TypeScript", "React", "HTML", "CSS", "REST", "React Testing Library",
            "quản lý trạng thái tải", "xử lý lỗi API",
        ),
        experience=(
            Experience(
                role="Frontend Developer",
                company="Công ty CP Công nghệ Vận hành Tín Thành",
                period="05/2022 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Xây dựng 24 biểu mẫu React cho hệ thống quản lý đơn nội bộ, dùng chung bộ thành phần.",
                    "Quản lý trạng thái tải và hiển thị lỗi API, giảm 50% phản hồi người dùng về màn hình trắng.",
                    "Viết kiểm thử thành phần bằng React Testing Library cho các luồng nhập liệu quan trọng.",
                    "Làm việc với nhóm QA để chốt tiêu chí kiểm thử giao diện trước mỗi bản phát hành.",
                ),
            ),
            Experience(
                role="Frontend Developer",
                company="Công ty TNHH Phần mềm Sao Mai",
                period="08/2021 – 04/2022",
                location="Hà Nội",
                bullets=("Phát triển giao diện trang quản trị bằng React và Ant Design.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Quốc gia Hà Nội",
                period="2017 – 2021",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="Frontend React",
        legacy_filename="CV_13_Thao.docx",
    ),
    Candidate(
        number=14,
        full_name="Trần Anh Tuấn",
        headline="Frontend Engineer · React & Next.js",
        email="tran.anh.tuan@example.test",
        phone="0987 340 216",
        summary=(
            "Frontend engineer 5 năm kinh nghiệm với React, Next.js và "
            "TypeScript. Có kinh nghiệm viết kiểm thử hành trình người dùng bằng "
            "Playwright và tối ưu hiệu năng tải trang."
        ),
        skills=(
            "React", "TypeScript", "Next.js", "CSS", "Playwright", "Git",
            "tối ưu hiệu năng", "kiểm thử hành trình",
        ),
        experience=(
            Experience(
                role="Frontend Engineer",
                company="Công ty CP Thương mại Số Nam Long",
                period="02/2021 – 10/2025",
                location="TP. Hồ Chí Minh",
                bullets=(
                    "Phát triển 40 thành phần tái sử dụng cho ứng dụng Next.js phục vụ 120.000 người dùng tháng.",
                    "Tích hợp REST API và xử lý phân trang, tìm kiếm phía máy chủ.",
                    "Viết kiểm thử hành trình người dùng bằng Playwright cho 18 luồng chính.",
                    "Tối ưu tải trang đầu, giảm điểm Largest Contentful Paint từ 4,2s xuống 2,1s.",
                ),
            ),
            Experience(
                role="Frontend Developer",
                company="Công ty TNHH Công nghệ Trẻ Sài Gòn",
                period="07/2019 – 01/2021",
                location="TP. Hồ Chí Minh",
                bullets=("Xây dựng giao diện landing page và trang sản phẩm bằng React.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Kỹ thuật Phần mềm",
                school="Đại học Công nghệ Thông tin – ĐHQG TP. Hồ Chí Minh",
                period="2015 – 2019",
            ),
        ),
        certifications=("Meta Front-End Developer Professional Certificate (2022)",),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B2)"),
        projects=(
            (
                "Bảng điều khiển vận hành",
                "Thiết kế lại bảng điều khiển cho nhóm vận hành, dùng Next.js và biểu đồ thời gian thực.",
            ),
        ),
        applies_to="Frontend React",
        legacy_filename="CV_14_Tuan.docx",
    ),
    Candidate(
        number=15,
        full_name="Đinh Thị Vân",
        headline="Frontend Developer · Accessible UI",
        email="dinh.thi.van@example.test",
        phone="0902 715 438",
        summary=(
            "Frontend developer 4 năm kinh nghiệm chú trọng khả năng tiếp cận và "
            "chất lượng giao diện. Làm việc sát với nhóm thiết kế, quen rà soát "
            "nhãn form và điều hướng bàn phím."
        ),
        skills=(
            "JavaScript", "React", "HTML", "CSS", "accessibility", "Figma",
            "kiểm thử giao diện", "rà soát thiết kế",
        ),
        experience=(
            Experience(
                role="Frontend Developer",
                company="Công ty CP Công nghệ Giáo dục Tri Thức",
                period="03/2022 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Triển khai 30 màn hình theo thiết kế Figma cho nền tảng học trực tuyến.",
                    "Rà soát nhãn form và khả năng sử dụng bằng bàn phím trên 18 màn hình, sửa 60 lỗi tiếp cận.",
                    "Chuẩn hoá bộ thành phần giao diện dùng chung cho 4 nhóm sản phẩm.",
                    "Phối hợp nhóm kiểm thử xây dựng checklist kiểm tra giao diện trước phát hành.",
                ),
            ),
            Experience(
                role="Web Developer",
                company="Công ty TNHH Thiết kế Số Hà Nội",
                period="08/2021 – 02/2022",
                location="Hà Nội",
                bullets=("Cắt giao diện từ thiết kế và xử lý tương tác cơ bản bằng JavaScript.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Đa phương tiện",
                school="Đại học Công nghệ – Đại học Quốc gia Hà Nội",
                period="2017 – 2021",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="Frontend React",
        legacy_filename="CV_15_Van.docx",
    ),
    Candidate(
        number=16,
        full_name="Phan Hải Yến",
        headline="Frontend Developer · API Integration",
        email="phan.hai.yen@example.test",
        phone="0936 408 571",
        summary=(
            "Frontend developer 3 năm kinh nghiệm với React và TypeScript, làm các "
            "màn hình quản lý lịch và xử lý lỗi mạng. Có hiểu biết về API nhưng "
            "kinh nghiệm backend còn hạn chế."
        ),
        skills=(
            "TypeScript", "React", "REST", "Node.js", "Git", "Jest",
            "xử lý lỗi mạng", "tích hợp API",
        ),
        experience=(
            Experience(
                role="Frontend Developer",
                company="Công ty CP Đặt lịch Trực tuyến Giờ Vàng",
                period="06/2022 – 10/2025",
                location="Đà Nẵng",
                bullets=(
                    "Xây dựng màn hình quản lý lịch hẹn cho 5.000 người dùng, dùng React và TypeScript.",
                    "Xử lý lỗi mạng và trạng thái thử lại, giảm 40% số lượt đặt lịch bị bỏ dở.",
                    "Thêm Jest cho phần logic giao diện, đạt độ phủ 55% các hàm xử lý.",
                    "Tham gia thiết kế hợp đồng API với nhóm backend trước khi triển khai.",
                ),
            ),
            Experience(
                role="Frontend Intern",
                company="Công ty TNHH Công nghệ Miền Trung",
                period="01/2022 – 05/2022",
                location="Đà Nẵng",
                bullets=("Sửa lỗi giao diện và hỗ trợ kiểm thử trên nhiều kích thước màn hình.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Bách khoa – Đại học Đà Nẵng",
                period="2017 – 2021",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="Frontend React",
        legacy_filename="CV_16_Yen.docx",
    ),
    Candidate(
        number=17,
        full_name="Đoàn Gia Bảo",
        headline="Web Developer",
        email="doan.gia.bao@example.test",
        phone="0917 536 280",
        summary=(
            "Lập trình viên web 3 năm kinh nghiệm làm website giới thiệu và trang "
            "quản trị đơn giản bằng HTML, CSS, JavaScript. Đang học React, chưa có "
            "kinh nghiệm làm dự án React ở môi trường sản phẩm."
        ),
        skills=(
            "HTML", "CSS", "JavaScript", "Git", "Bootstrap", "jQuery",
            "làm website giới thiệu", "sửa lỗi hiển thị",
        ),
        experience=(
            Experience(
                role="Web Developer",
                company="Công ty TNHH Truyền thông Sáng Tạo Việt",
                period="09/2022 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Thực hiện 35 website giới thiệu doanh nghiệp bằng HTML, CSS và Bootstrap.",
                    "Sửa lỗi hiển thị trên trình duyệt cũ và thiết bị di động.",
                    "Hỗ trợ kiểm thử thủ công trước khi bàn giao cho khách hàng.",
                ),
            ),
            Experience(
                role="Thực tập sinh",
                company="Công ty TNHH Thiết kế Web Hà Thành",
                period="03/2022 – 08/2022",
                location="Hà Nội",
                bullets=("Cắt giao diện từ file thiết kế và nhập nội dung.",),
            ),
        ),
        education=(
            Education(
                degree="Cao đẳng Công nghệ Thông tin",
                school="Cao đẳng Công nghệ Hà Nội",
                period="2018 – 2021",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (A2)"),
        applies_to="Frontend React",
        legacy_filename="CV_17_Bao.docx",
    ),
    Candidate(
        number=18,
        full_name="Mai Đức Cường",
        headline="Frontend Developer · React (Junior)",
        email="mai.duc.cuong@example.test",
        phone="0925 174 603",
        summary=(
            "Frontend developer 2 năm kinh nghiệm với React và JavaScript, tham "
            "gia phát triển màn hình quản lý cho hệ thống nội bộ. Quen kết nối API "
            "và rà soát dữ liệu nhập."
        ),
        skills=("React", "JavaScript", "CSS", "REST", "Git", "kết nối API", "rà soát dữ liệu nhập"),
        experience=(
            Experience(
                role="Frontend Developer",
                company="Công ty CP Phần mềm Quản lý Tài sản Tín Minh",
                period="11/2023 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Tham gia phát triển 16 màn hình React cho hệ thống quản lý tài sản nội bộ.",
                    "Kết nối API và xử lý lỗi xác thực, hiển thị thông báo rõ ràng cho người dùng.",
                    "Rà soát dữ liệu nhập trên form và bổ sung kiểm tra định dạng.",
                ),
            ),
            Experience(
                role="Frontend Intern",
                company="Công ty TNHH Công nghệ Trí Tuệ Số",
                period="04/2023 – 10/2023",
                location="Hà Nội",
                bullets=("Học và làm quen React, sửa các lỗi giao diện nhỏ.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Mở Hà Nội",
                period="2019 – 2023",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (A2)"),
        applies_to="Frontend React",
        legacy_filename="CV_18_Cuong.docx",
    ),
    Candidate(
        number=19,
        full_name="Nguyễn Tiến Duy",
        headline="QA Automation Engineer",
        email="nguyen.tien.duy@example.test",
        phone="0913 820 476",
        summary=(
            "Kỹ sư kiểm thử tự động 5 năm kinh nghiệm, chủ yếu kiểm thử API và "
            "dịch vụ backend bằng Python và pytest. Quen đọc log và phối hợp với "
            "nhóm phát triển để tái hiện lỗi."
        ),
        skills=(
            "Python", "pytest", "REST", "SQL", "Playwright", "Git",
            "thiết kế test case", "kiểm thử API",
        ),
        experience=(
            Experience(
                role="QA Automation Engineer",
                company="Công ty CP Thương mại Điện tử Bình Minh",
                period="04/2021 – 10/2025",
                location="TP. Hồ Chí Minh",
                bullets=(
                    "Thiết kế 260 test case và tự động kiểm thử API cho hệ thống đặt hàng.",
                    "Viết bộ pytest kiểm tra mã phản hồi, lược đồ dữ liệu và thời gian xử lý.",
                    "Đưa kiểm thử tự động vào CI, rút thời gian kiểm thử hồi quy từ 2 ngày xuống 3 giờ.",
                    "Theo dõi lỗi trên môi trường thật và phối hợp nhóm phát triển tái hiện 45 sự cố.",
                ),
            ),
            Experience(
                role="QA Engineer",
                company="Công ty TNHH Phần mềm Tín Dụng Việt",
                period="07/2019 – 03/2021",
                location="TP. Hồ Chí Minh",
                bullets=("Kiểm thử chức năng hệ thống tín dụng và ghi nhận lỗi.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Sài Gòn",
                period="2015 – 2019",
            ),
        ),
        certifications=("ISTQB Certified Tester Advanced Level, Test Automation Engineer (2023)",),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="QA Automation",
        legacy_filename="CV_19_Duy.docx",
    ),
    Candidate(
        number=20,
        full_name="Trương Thanh Giang",
        headline="QA Engineer · API & Data",
        email="truong.thanh.giang@example.test",
        phone="0978 402 193",
        summary=(
            "Kỹ sư kiểm thử 4 năm kinh nghiệm kiểm thử API và đối soát dữ liệu. "
            "Viết script Python để tự động hoá việc kiểm tra số liệu và mô tả lỗi "
            "sao cho nhóm phát triển tái hiện được ngay."
        ),
        skills=(
            "Python", "pytest", "SQL", "Postman", "REST", "Git",
            "đối soát dữ liệu", "mô tả lỗi",
        ),
        experience=(
            Experience(
                role="QA Engineer",
                company="Công ty CP Công nghệ Tài chính Sao Đỏ",
                period="03/2022 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Kiểm thử API và đối soát dữ liệu giữa hệ thống giao dịch và sổ cái, chạy hằng ngày.",
                    "Viết script pytest và SQL tự động kiểm tra số dư sau mỗi lô giao dịch.",
                    "Mô tả 120 lỗi kèm bước tái hiện và log, giảm thời gian sửa trung bình từ 3 ngày xuống 1,5 ngày.",
                    "Dùng Postman xây bộ sưu tập kiểm thử cho 40 endpoint.",
                ),
            ),
            Experience(
                role="QA Engineer",
                company="Công ty TNHH Công nghệ Thanh Toán Nhanh",
                period="08/2021 – 02/2022",
                location="Hà Nội",
                bullets=("Kiểm thử chức năng thanh toán và kiểm tra dữ liệu đầu vào.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Hệ thống Thông tin Quản lý",
                school="Đại học Thương mại",
                period="2016 – 2020",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="QA Automation",
        legacy_filename="CV_20_Giang.docx",
    ),
    Candidate(
        number=21,
        full_name="Phạm Minh Hải",
        headline="QA Automation Engineer · UI",
        email="pham.minh.hai@example.test",
        phone="0941 638 207",
        summary=(
            "Kỹ sư kiểm thử tự động 4 năm kinh nghiệm, tập trung vào giao diện web "
            "với Playwright và TypeScript. Quen kiểm thử hồi quy trên nhiều kích "
            "thước màn hình và phối hợp với nhóm frontend."
        ),
        skills=(
            "TypeScript", "Playwright", "React", "HTML", "test case", "Git",
            "kiểm thử hồi quy", "kiểm thử giao diện",
        ),
        experience=(
            Experience(
                role="QA Automation Engineer",
                company="Công ty CP Bán lẻ Số Hà Nội",
                period="05/2022 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Xây dựng bộ kiểm thử hồi quy giao diện bằng Playwright cho 20 màn hình chính.",
                    "Xác nhận hành trình người dùng trên 5 kích thước màn hình và 3 trình duyệt.",
                    "Giảm số lỗi giao diện lọt ra môi trường thật từ 12 xuống 3 mỗi quý.",
                    "Viết test case cho các luồng thanh toán và đổi trả.",
                ),
            ),
            Experience(
                role="Manual QA",
                company="Công ty TNHH Công nghệ Bán lẻ Tân Việt",
                period="09/2021 – 04/2022",
                location="Hà Nội",
                bullets=("Kiểm thử thủ công chức năng giỏ hàng và viết báo cáo lỗi.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Giao thông Vận tải",
                period="2017 – 2021",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="QA Automation",
        legacy_filename="CV_21_Hai.docx",
    ),
    Candidate(
        number=22,
        full_name="Bùi Anh Kiệt",
        headline="QA Engineer · Automation & CI",
        email="bui.anh.kiet@example.test",
        phone="0909 527 348",
        summary=(
            "Kỹ sư kiểm thử 5 năm kinh nghiệm, mạnh ở đưa kiểm thử tự động vào "
            "pipeline CI. Quen đóng gói bộ kiểm thử bằng Docker và phân tích kết "
            "quả chạy trên Linux."
        ),
        skills=(
            "Python", "pytest", "Docker", "CI", "REST", "Linux",
            "cấu hình pipeline", "phân tích kết quả kiểm thử",
        ),
        experience=(
            Experience(
                role="QA Engineer",
                company="Công ty CP Công nghệ Chuỗi Cung ứng Đông Dương",
                period="02/2021 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Tạo bộ kiểm thử hồi quy API bằng pytest cho 70 endpoint, chạy trên pipeline mỗi lần hợp nhất.",
                    "Cấu hình chạy kiểm thử tự động trên CI, giảm thời gian phát hiện lỗi từ 1 tuần xuống dưới 1 ngày.",
                    "Đóng gói bộ kiểm thử trong Docker để chạy giống nhau trên máy phát triển và máy chủ.",
                    "Xuất báo cáo kết quả và phân tích các ca kiểm thử không ổn định.",
                ),
            ),
            Experience(
                role="Test Engineer",
                company="Công ty TNHH Phần mềm Vận tải Thăng Long",
                period="07/2019 – 01/2021",
                location="Hà Nội",
                bullets=("Kiểm thử chức năng và viết script kiểm tra dữ liệu bằng Python.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Bách khoa Hà Nội",
                period="2015 – 2019",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="QA Automation",
        legacy_filename="CV_22_Kiet.docx",
    ),
    Candidate(
        number=23,
        full_name="Nguyễn Thị Lâm",
        headline="QA Engineer · Manual Testing",
        email="nguyen.thi.lam@example.test",
        phone="0961 482 735",
        summary=(
            "Kỹ sư kiểm thử 4 năm kinh nghiệm kiểm thử chức năng web theo test case. "
            "Làm tốt việc ghi lỗi và phối hợp với lập trình viên, đang học tự động "
            "hoá kiểm thử."
        ),
        skills=(
            "test case", "kiểm thử web", "theo dõi lỗi", "SQL cơ bản",
            "kiểm thử chức năng", "viết báo cáo lỗi",
        ),
        experience=(
            Experience(
                role="QA Engineer",
                company="Công ty CP Giải pháp Nghiệp vụ Hà Nội",
                period="06/2021 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Kiểm thử chức năng website quản lý nhân sự cho 14 khách hàng doanh nghiệp.",
                    "Ghi lỗi và làm việc với lập trình viên để tái hiện, xử lý 380 lỗi trong 4 năm.",
                    "Viết test case cho các luồng tính lương, nghỉ phép và chấm công.",
                    "Dùng SQL cơ bản để kiểm tra dữ liệu sau khi thao tác.",
                ),
            ),
            Experience(
                role="Nhân viên kiểm thử",
                company="Công ty TNHH Phần mềm Kế toán An Việt",
                period="09/2020 – 05/2021",
                location="Hà Nội",
                bullets=("Kiểm thử thủ công phần mềm kế toán và nhập kết quả kiểm thử.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Điện lực",
                period="2016 – 2020",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (A2)"),
        applies_to="QA Automation",
        legacy_filename="CV_23_Lam.docx",
    ),
    Candidate(
        number=24,
        full_name="Đinh Quang Nam",
        headline="QA Engineer (Junior)",
        email="dinh.quang.nam@example.test",
        phone="0932 715 860",
        summary=(
            "QA engineer 2 năm kinh nghiệm kiểm thử API bằng Postman và kiểm thử hồi "
            "quy thủ công. Có nền SQL và JavaScript cơ bản, đang tìm cơ hội làm tự "
            "động hoá."
        ),
        skills=(
            "Postman", "REST", "SQL", "JavaScript cơ bản", "kiểm thử hồi quy",
            "ghi kết quả kiểm thử", "kiểm thử API",
        ),
        experience=(
            Experience(
                role="QA Engineer",
                company="Công ty CP Dịch vụ Số Vân Long",
                period="12/2023 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Thực hiện test API bằng Postman cho 30 endpoint và ghi kết quả kiểm thử hồi quy.",
                    "Dùng SQL kiểm tra dữ liệu sau mỗi lần cập nhật trạng thái đơn.",
                    "Viết báo cáo lỗi hằng tuần cho nhóm phát triển.",
                ),
            ),
            Experience(
                role="QA Intern",
                company="Công ty TNHH Công nghệ Đông Nam Á",
                period="05/2023 – 11/2023",
                location="Hà Nội",
                bullets=("Kiểm thử thủ công ứng dụng di động và nhập kết quả.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Hệ thống Thông tin",
                school="Đại học Nội vụ Hà Nội",
                period="2019 – 2023",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (A2)"),
        applies_to="QA Automation",
        legacy_filename="CV_24_Nam.docx",
    ),
    Candidate(
        number=25,
        full_name="Nguyễn Thị Oanh",
        headline="DevOps Engineer · Python",
        email="nguyen.thi.oanh@example.test",
        phone="0912 630 574",
        summary=(
            "DevOps engineer 5 năm kinh nghiệm vận hành dịch vụ Python trên Linux. "
            "Quen build pipeline CI/CD, đọc log và phối hợp sửa lỗi triển khai cùng "
            "nhóm phát triển."
        ),
        skills=(
            "Linux", "Docker", "CI/CD", "Python", "Git", "PostgreSQL",
            "phân tích log", "xử lý lỗi triển khai",
        ),
        experience=(
            Experience(
                role="DevOps Engineer",
                company="Công ty CP Công nghệ Hạ tầng VinaCloud",
                period="03/2021 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Duy trì pipeline build và triển khai cho 9 dịch vụ Python, chạy trung bình 40 lần mỗi tuần.",
                    "Phân tích log và phối hợp nhóm phát triển xử lý 60 lỗi triển khai trong năm đầu.",
                    "Chuẩn hoá Dockerfile cho các dịch vụ, giảm kích thước ảnh trung bình 35%.",
                    "Viết runbook cho các sự cố thường gặp và hướng dẫn trực ca.",
                ),
            ),
            Experience(
                role="System Engineer",
                company="Công ty TNHH Dịch vụ Máy chủ Sao Bắc",
                period="08/2019 – 02/2021",
                location="Hà Nội",
                bullets=("Quản trị máy chủ Linux và hỗ trợ triển khai ứng dụng nội bộ.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Mạng máy tính và Truyền thông",
                school="Đại học Bách khoa Hà Nội",
                period="2015 – 2019",
            ),
        ),
        certifications=("Docker Certified Associate (2022)",),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="DevOps và Cloud",
        legacy_filename="CV_25_Oanh.docx",
    ),
    Candidate(
        number=26,
        full_name="Trần Xuân Phong",
        headline="Cloud Engineer · Infrastructure as Code",
        email="tran.xuan.phong@example.test",
        phone="0974 318 652",
        summary=(
            "Cloud engineer 5 năm kinh nghiệm với AWS và Terraform. Xây dựng hạ "
            "tầng cho dịch vụ container, giám sát tác vụ và tự động hoá triển "
            "khai."
        ),
        skills=(
            "Linux", "Docker", "AWS", "Terraform", "CI/CD", "Python",
            "giám sát hệ thống", "triển khai container",
        ),
        experience=(
            Experience(
                role="Cloud Engineer",
                company="Công ty CP Giải pháp Đám mây Tân Hưng",
                period="02/2021 – 10/2025",
                location="TP. Hồ Chí Minh",
                bullets=(
                    "Viết 40 module Terraform cho hạ tầng AWS của 6 sản phẩm, giảm thời gian dựng môi trường từ 2 ngày xuống 2 giờ.",
                    "Hỗ trợ triển khai container cho 14 dịch vụ và cấu hình cân bằng tải.",
                    "Giám sát tác vụ định kỳ, giảm 50% số sự cố phát hiện muộn.",
                    "Viết script Python cho tác vụ vận hành và dọn dẹp tài nguyên.",
                ),
            ),
            Experience(
                role="Infrastructure Engineer",
                company="Công ty TNHH Công nghệ Mây Việt",
                period="07/2019 – 01/2021",
                location="TP. Hồ Chí Minh",
                bullets=("Quản trị máy chủ và hỗ trợ triển khai ứng dụng lên AWS.",),
            ),
        ),
        education=(
            Education(
                degree="Kỹ sư Công nghệ Thông tin",
                school="Đại học Công nghệ Thông tin – ĐHQG TP. Hồ Chí Minh",
                period="2015 – 2019",
            ),
        ),
        certifications=(
            "AWS Certified Solutions Architect – Associate (2022)",
            "HashiCorp Certified: Terraform Associate (2023)",
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B2)"),
        applies_to="DevOps và Cloud",
        legacy_filename="CV_26_Phong.docx",
    ),
    Candidate(
        number=27,
        full_name="Lê Hải Quang",
        headline="DevOps Engineer · CI & Testing",
        email="le.hai.quang@example.test",
        phone="0948 206 317",
        summary=(
            "DevOps engineer 4 năm kinh nghiệm, tập trung vào pipeline build và "
            "kiểm thử tự động. Viết script Python và cấu hình CI cho các nhóm sản "
            "phẩm."
        ),
        skills=(
            "Linux", "Docker", "Git", "CI", "Python", "pytest",
            "cấu hình pipeline", "theo dõi lỗi build",
        ),
        experience=(
            Experience(
                role="DevOps Engineer",
                company="Công ty CP Phần mềm Doanh nghiệp Tín Phát",
                period="05/2022 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Thiết lập pipeline build và test cho 5 sản phẩm, chạy 30 lần mỗi tuần.",
                    "Viết script Python tự động hoá bước kiểm tra trước khi phát hành.",
                    "Theo dõi lỗi build và phối hợp nhóm phát triển giảm 40% số lần build hỏng.",
                    "Cải thiện thời gian phản hồi của pipeline từ 25 phút xuống 12 phút.",
                ),
            ),
            Experience(
                role="System Administrator",
                company="Công ty TNHH Hạ tầng Số Thăng Long",
                period="09/2021 – 04/2022",
                location="Hà Nội",
                bullets=("Quản trị Linux và hỗ trợ triển khai ứng dụng nội bộ.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Công nghiệp Hà Nội",
                period="2017 – 2021",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="DevOps và Cloud",
        legacy_filename="CV_27_Quang.docx",
    ),
    Candidate(
        number=28,
        full_name="Nguyễn Thu Trang",
        headline="Container Operations Engineer",
        email="nguyen.thu.trang@example.test",
        phone="0916 507 284",
        summary=(
            "Kỹ sư vận hành container 4 năm kinh nghiệm với Kubernetes và Docker. "
            "Quen theo dõi logs, viết quy trình xử lý lỗi và phối hợp trực ca. "
            "Phần lớn tự động hoá hiện tại viết bằng Bash."
        ),
        skills=(
            "Linux", "Kubernetes", "Docker", "Bash", "Git", "monitoring",
            "theo dõi log", "viết quy trình xử lý lỗi",
        ),
        experience=(
            Experience(
                role="Container Operations Engineer",
                company="Công ty CP Công nghệ Tài chính Số Việt",
                period="04/2021 – 10/2025",
                location="TP. Hồ Chí Minh",
                bullets=(
                    "Hỗ trợ vận hành 3 cụm Kubernetes chạy 80 dịch vụ nội bộ.",
                    "Theo dõi logs và ghi lại quy trình xử lý 25 loại sự cố thường gặp.",
                    "Viết script Bash kiểm tra tình trạng pod và dọn dẹp tài nguyên mồ côi.",
                    "Cấu hình cảnh báo cho các chỉ số tài nguyên quan trọng.",
                ),
            ),
            Experience(
                role="Operations Engineer",
                company="Công ty TNHH Dịch vụ Hạ tầng Nam Sài Gòn",
                period="08/2019 – 03/2021",
                location="TP. Hồ Chí Minh",
                bullets=("Giám sát hệ thống máy chủ và xử lý sự cố theo ca trực.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Truyền thông và Mạng máy tính",
                school="Đại học Công nghệ Thông tin – ĐHQG TP. Hồ Chí Minh",
                period="2015 – 2019",
            ),
        ),
        certifications=("Certified Kubernetes Administrator (2022)",),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (B1)"),
        applies_to="DevOps và Cloud",
        legacy_filename="CV_28_Trang.docx",
    ),
    Candidate(
        number=29,
        full_name="Phan Quốc Uy",
        headline="IT Support Engineer",
        email="phan.quoc.uy@example.test",
        phone="0939 164 508",
        summary=(
            "Kỹ sư hỗ trợ hệ thống 4 năm kinh nghiệm xử lý ticket người dùng và "
            "kiểm tra kết nối mạng. Mạnh ở quy trình và tài liệu, chưa có kinh "
            "nghiệm Docker hay CI."
        ),
        skills=(
            "Windows", "Linux cơ bản", "ticket", "mạng cơ bản", "tài liệu",
            "hỗ trợ người dùng", "kiểm tra kết nối",
        ),
        experience=(
            Experience(
                role="IT Support Engineer",
                company="Công ty CP Sản xuất Thực phẩm Hương Việt",
                period="07/2021 – 10/2025",
                location="Bắc Ninh",
                bullets=(
                    "Theo dõi và xử lý trung bình 180 ticket hỗ trợ mỗi tháng cho 400 người dùng.",
                    "Kiểm tra kết nối mạng và phối hợp nhà cung cấp đường truyền khi có sự cố.",
                    "Cập nhật hướng dẫn xử lý cho 30 tình huống thường gặp.",
                    "Quản lý máy trạm Windows và cài đặt phần mềm theo yêu cầu.",
                ),
            ),
            Experience(
                role="Nhân viên hỗ trợ kỹ thuật",
                company="Công ty TNHH Dịch vụ Tin học Kinh Bắc",
                period="09/2020 – 06/2021",
                location="Bắc Ninh",
                bullets=("Hỗ trợ người dùng qua điện thoại và xử lý sự cố máy tính.",),
            ),
        ),
        education=(
            Education(
                degree="Cao đẳng Công nghệ Thông tin",
                school="Cao đẳng Công nghiệp Bắc Ninh",
                period="2017 – 2020",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (A2)"),
        applies_to="DevOps và Cloud",
        legacy_filename="CV_29_Uy.docx",
    ),
    Candidate(
        number=30,
        full_name="Trần Thảo Vy",
        headline="DevOps Engineer (Junior)",
        email="tran.thao.vy@example.test",
        phone="0926 408 153",
        summary=(
            "DevOps engineer 2 năm kinh nghiệm với Linux, Docker và CI cơ bản. Hỗ "
            "trợ đóng gói ứng dụng và cập nhật pipeline theo hướng dẫn của nhóm. "
            "Đang học Kubernetes."
        ),
        skills=(
            "Linux", "Bash", "Git", "Docker", "CI cơ bản",
            "đóng gói ứng dụng", "đọc log",
        ),
        experience=(
            Experience(
                role="DevOps Engineer",
                company="Công ty CP Công nghệ Giáo dục Số An Khang",
                period="11/2023 – 10/2025",
                location="Hà Nội",
                bullets=(
                    "Hỗ trợ đóng gói 12 ứng dụng bằng Docker theo mẫu có sẵn của nhóm.",
                    "Đọc log triển khai và báo cáo lỗi cho kỹ sư chính.",
                    "Cập nhật cấu hình pipeline theo hướng dẫn, chạy được 8 pipeline mới.",
                    "Viết script Bash kiểm tra tiến trình và dung lượng đĩa.",
                ),
            ),
            Experience(
                role="IT Intern",
                company="Công ty TNHH Công nghệ An Khang",
                period="05/2023 – 10/2023",
                location="Hà Nội",
                bullets=("Hỗ trợ vận hành máy chủ nội bộ và cài đặt môi trường.",),
            ),
        ),
        education=(
            Education(
                degree="Cử nhân Công nghệ Thông tin",
                school="Đại học Hà Nội",
                period="2019 – 2023",
            ),
        ),
        languages=("Tiếng Việt (bản ngữ)", "Tiếng Anh (A2)"),
        applies_to="DevOps và Cloud",
        legacy_filename="CV_30_Vy.docx",
    ),
)


def by_number(number: int) -> Candidate:
    for candidate in CANDIDATES:
        if candidate.number == number:
            return candidate
    raise KeyError(f"Không có hồ sơ số {number}")
