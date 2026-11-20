# BẢNG ĐIỀU PHỐI 30 CV DEMO — 5 JD IT (TIẾNG ANH)

Bảng này là **kế hoạch thao tác**, không phải dữ liệu đã nhập hay consent đã tồn tại. Mỗi CV có họ tên/email @example.test riêng; vào form hãy nhập đúng tên/email in trong CV.

Bộ CV do `backend/scripts/demo_pack/generate.py` sinh ra từ `cv_data.py`: mỗi hồ sơ là một người hư cấu nhưng viết như CV thật (chức danh, kinh nghiệm theo công ty kèm số liệu, học vấn, chứng chỉ). **Tên tệp cố ý lộn xộn** — viết hoa, dấu cách, hậu tố `-final`, `_v2`, ` (1)` — vì ngoài đời HR nhận đúng kiểu đó; hệ thống lấy tên ứng viên từ **nội dung CV**, không lấy từ tên tệp, và giữ `original_filename` làm tham chiếu. Muốn sinh lại toàn bộ: chạy script trên, không sửa tay từng tệp.

**Ngôn ngữ: toàn bộ JD và CV là tiếng Anh.** Nền tảng hướng tới người dùng quốc tế,
nên tiếng Anh là chuẩn cho JD/CV; tiếng Việt vẫn chạy được nhưng là tuỳ chọn. Đừng
dùng dữ liệu tiếng Việt cho buổi demo chính — nó không đại diện cho cách hệ thống
được dùng thật.

Hồ sơ kỹ năng của từng người **giữ nguyên** so với bản cũ để kịch bản (ai đủ/thiếu bằng chứng cho vị trí nào) không đổi. Chỉ 03 dùng Gmail ở kịch bản chính, toàn bộ CV còn lại đề xuất nộp Careers. Không suy ra consent từ file CV, Gmail hay bảng này: phải tích ô lựa chọn riêng trên form khi cột ghi Có.

Nguồn là vị trí ứng tuyển; tham khảo là gợi ý để HR tự đọc, **không phải điểm hoặc kết quả phù hợp**. Scan Talent Pool hiện chỉ lọc điều kiện consent, thời hạn, quyền và trạng thái xử lý; không chấm kỹ năng, không xếp hạng, không loại ứng viên trái ngành. JD đích phải OPEN và rubric JD mới nhất APPROVED.

| # | Ứng viên | Tệp | Nộp nguồn | Opt-in đề xuất | Tham khảo cho HR |
|---|---|---|---|---|---|
| 01 | Daniel Whitfield | `CV_01_daniel_whitfield.docx` | Backend Python | Có | Tích hợp dữ liệu: Python, SQL, pipeline |
| 02 | Marcus Bell | `CV_02_marcus_bell.pdf` | Backend Python | Không | Backend Python: Flask, SQL; ít bằng chứng pipeline |
| 03 | Priya Raghavan | `CV-03-priya_raghavan-final.docx` | Backend Python — Gmail | Không tự cấp | Backend Python: FastAPI, PostgreSQL |
| 04 | Thomas Reilly | `CV_04_thomas_reilly_v2.docx` | Backend Python | Có | Tích hợp dữ liệu: Python, SQL, kiểm tra chất lượng |
| 05 | Sofia Almeida | `sofia_almeida_CV_2024.pdf` | Backend Python | Có | QA Automation: API, pytest |
| 06 | Andrei Popescu | `CV 06 andrei_popescu (1).docx` | Backend Python | Có | Backend Python: có nền API nhưng thiếu bằng chứng Python |
| 07 | Hannah Fischer | `CV_07_hannah_fischer.docx` | Tích hợp dữ liệu | Có | Backend Python: API, Python và SQL |
| 08 | Owen Hartley | `CV_08_owen_hartley.pdf` | Tích hợp dữ liệu | Có | QA Automation: kiểm tra dữ liệu, SQL, Python |
| 09 | Ingrid Solberg | `CV-09-ingrid_solberg-final.docx` | Tích hợp dữ liệu | Có | DevOps: Docker, lịch chạy, quan sát tác vụ |
| 10 | Rafael Duarte | `CV_10_rafael_duarte_v2.docx` | Tích hợp dữ liệu | Có | Backend Python: FastAPI và thiết kế REST |
| 11 | Claire Bennett | `claire_bennett_CV_2024.pdf` | Tích hợp dữ liệu | Không | Tích hợp dữ liệu: SQL nhưng thiếu Python/API |
| 12 | Victor Nunes | `CV 12 victor_nunes (1).docx` | Tích hợp dữ liệu | Không | Backend Python: Python và API; kiểm thử framework còn ít |
| 13 | Emily Zhang | `CV_13_emily_zhang.docx` | Frontend React | Có | QA Automation: kiểm thử giao diện và test case |
| 14 | Jack Morrow | `CV_14_jack_morrow.pdf` | Frontend React | Có | QA Automation: Playwright và kiểm thử UI |
| 15 | Nadia Karim | `CV-15-nadia_karim-final.docx` | Frontend React | Có | QA Automation: tư duy kiểm thử UI; chưa có automation API |
| 16 | Liam Foster | `CV_16_liam_foster_v2.docx` | Frontend React | Có | Backend Python: hiểu API nhưng chưa có bằng chứng Python |
| 17 | Grace Okonkwo | `grace_okonkwo_CV_2024.pdf` | Frontend React | Không | Frontend: HTML/CSS nhưng thiếu bằng chứng React |
| 18 | Peter Novak | `CV 18 peter_novak (1).docx` | Frontend React | Không | Frontend: React; tự động hóa kiểm thử còn ít |
| 19 | Ayesha Siddiqui | `CV_19_ayesha_siddiqui.docx` | QA Automation | Có | Backend Python: Python, API và SQL |
| 20 | Grace Whitmore | `CV_20_grace_whitmore.pdf` | QA Automation | Có | Tích hợp dữ liệu: SQL, Python và chất lượng dữ liệu |
| 21 | Omar Haddad | `CV-21-omar_haddad-final.docx` | QA Automation | Có | Frontend React: TypeScript và React |
| 22 | Sven Lindqvist | `CV_22_sven_lindqvist_v2.docx` | QA Automation | Có | DevOps: Linux, Docker và CI |
| 23 | Laura Simmons | `laura_simmons_CV_2024.pdf` | QA Automation | Không | QA Automation: test case nhưng thiếu bằng chứng tự động hóa |
| 24 | Kevin Duong | `CV 24 kevin_duong (1).docx` | QA Automation | Không | QA Automation: API/SQL; kinh nghiệm automation hạn chế |
| 25 | Mei Ling Tan | `CV_25_mei_ling_tan.docx` | DevOps và Cloud | Có | Backend Python: Python và môi trường API |
| 26 | Diego Alvarez | `CV_26_diego_alvarez.pdf` | DevOps và Cloud | Có | Tích hợp dữ liệu: Python, tác vụ và quan sát lỗi |
| 27 | Rory McAllister | `CV-27-rory_mcallister-final.docx` | DevOps và Cloud | Có | QA Automation: pytest và CI |
| 28 | Aisha Rahman | `CV_28_aisha_rahman_v2.docx` | DevOps và Cloud | Có | DevOps: container và vận hành; script chủ yếu Bash |
| 29 | Billy Chen | `billy_chen_CV_2024.pdf` | DevOps và Cloud | Không | DevOps: vận hành cơ bản nhưng thiếu Docker/CI |
| 30 | Nora Lindberg | `CV 30 nora_lindberg (1).docx` | DevOps và Cloud | Không | DevOps: nền tảng Linux/Docker; cloud chưa rõ |

## Kịch bản tải đủ 30 hồ sơ

1. Tạo 5 vị trí theo JD 01–05, lưu mã HRA thực tế; giao diện tạo JD ban đầu gắn ngôn ngữ English, nên với JD tiếng Việt hãy tạo phiên bản mới chọn Tiếng Việt và thêm một câu có nghĩa trước khi duyệt tiêu chí (xem kịch bản); HR duyệt rubric của JD mới nhất và đặt OPEN, hạn tương lai. Ứng tuyển Careers bằng 29 CV, với lựa chọn theo bảng; CV 03 gửi Gmail đúng mẫu và không được tạo consent. Nộp lần lượt, chờ tác vụ vị trí hoàn tất nếu hệ thống báo bận. Có thể chạy theo từng nhóm 6; 30 lượt và xử lý worker sẽ tốn thời gian, không phải demo 20–30 phút.
2. Lưu riêng mã rút cho những lượt opt-in cần thử withdrawal; mã chỉ xuất hiện trong form/đáp ứng ứng tuyển, không có trong gói này. Không dán mã vào bảng, chat hoặc video. Nếu chưa sẵn sàng làm 30 lượt, nộp 01, 02, 04, 05, 06 và 03 Gmail để trình bày trước; 24 CV còn lại nạp sau. Không khẳng định đã nạp đủ.
3. Mở `/talent-pool`, chọn nguồn Backend Python và đích Tích hợp dữ liệu. Nếu đủ 6 hồ sơ nguồn theo bảng, CV hoàn tất và còn đủ điều kiện, kỳ vọng 01, 04, 05, 06 xuất hiện; 02 không opt-in và 03 qua Gmail không có consent sẽ không xuất hiện. **06 có thể xuất hiện dù thiên Java**: đây là minh họa lọc điều kiện chứ không phải AI matching. Có thể có các hồ sơ khác đã tồn tại.
4. Nguồn Tích hợp dữ liệu → đích Backend Python: 07–10 có thể xuất hiện, 11–12 không xuất hiện nếu nhập đúng theo bảng và các điều kiện còn hiệu lực. Tương tự, các nguồn Frontend, QA, DevOps: bốn CV đầu của mỗi nhóm có opt-in, hai CV cuối không. HR tự đọc CV để so sánh bằng chứng với JD; không coi scan là điểm phù hợp.
5. Rút mã của 01 qua `/pool-withdraw`; tìm lại nguồn Backend → đích Data. Kỳ vọng 01 vắng mặt; 04–06 vẫn còn nếu điều kiện không đổi. Phản hồi withdrawal không xác nhận mã tồn tại. Consent thử nghiệm có thời hạn 7 ngày; hết hạn thì cần chuẩn bị lại có kiểm soát, không tự chèn vào DB.

Điều kiện chung: nhập qua đúng luồng thật, scanner sạch, Storage/worker xử lý COMPLETED, quyền HR, retention và consent còn hiệu lực. Nếu có lỗi, ghi FAIL/CHƯA CHẠY; không bypass scanner, không xóa hoặc reset dữ liệu. Không test bằng dữ liệu cá nhân thật.
