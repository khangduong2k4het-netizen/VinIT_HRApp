BỘ DEMO HRA — 5 JD VÀ 30 CV IT GIẢ

Bắt đầu: mở KICH_BAN_DEMO.md (demo ngắn) và BANG_PHAN_BO_30_CV.md (kế hoạch nhập đủ, opt-in và đối chiếu Talent Pool).
NGÔN NGỮ: toàn bộ JD và CV là TIẾNG ANH. Nền tảng hướng tới người dùng quốc tế,
tiếng Anh là ngôn ngữ chuẩn cho JD/CV; tiếng Việt vẫn được hỗ trợ nhưng là tuỳ
chọn, không phải mặc định. Đừng tạo JD/CV tiếng Việt cho buổi demo chính.

01_JD: năm JD IT tiếng Anh. 02_CV: 30 CV tiếng Anh (20 DOCX, 10 PDF) của người
hư cấu, viết như CV thật: họ tên đầy đủ, chức danh, kinh nghiệm theo công ty kèm
số liệu, học vấn, chứng chỉ. Bộ này do backend/scripts/demo_pack/generate.py sinh ra — sửa dữ liệu
trong cv_data.py rồi chạy lại, đừng sửa tay từng tệp.

Tên tệp cố ý không theo quy chuẩn (viết hoa, dấu cách, "-final", "_v2", " (1)")
đúng như tệp HR nhận ngoài đời. Hệ thống đọc tên ứng viên từ nội dung CV; tên tệp
chỉ còn là tham chiếu (original_filename) và hiển thị ở trang chi tiết hồ sơ.
03_GMAIL: mẫu email giả; thay mã vị trí do HRA tạo.

Chỉ dùng dữ liệu và tài khoản test. HTTP qua IP công khai không mã hóa; không dùng thông tin thật. Browser có thể không tạo được mã ứng tuyển qua HTTP/IP: xem cách mở localhost qua SSH tunnel ở đầu kịch bản. Talent Pool hiện lọc điều kiện, không tự chấm hay xếp hạng theo JD. Chưa test end-to-end trên VPS.
