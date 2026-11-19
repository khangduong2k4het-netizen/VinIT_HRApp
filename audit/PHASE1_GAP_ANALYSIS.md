# Phase 1 — trạng thái triển khai và khoảng trống

**Cập nhật:** 05/11/2026. Đối chiếu yêu cầu trong `doc/HRA_PRD.md` và kiến trúc Phase 1. “Có trong mã” không đồng nghĩa đã triển khai, nghiệm thu hoặc an toàn để dùng CV thật.

| ID | Yêu cầu | Trạng thái hiện tại |
|---|---|---|
| F1.01 | Vị trí, JD, Hiring Manager | HR chọn HM có role và tài khoản hoạt động, khác chính mình khi tạo vị trí; hai bước duyệt cũng chặn cùng tài khoản. Có tạo/sửa vị trí, tạo và xem lịch sử JD. Chưa có UI đổi HM sau khi tạo. JD mới cần duyệt tiêu chí mới; chặn sửa khi job đang chạy và xung đột phiên bản. |
| F1.02 | Tiêu chí, dual approval, trọng số | HR và HM được gán duyệt hai bước bằng **hai tài khoản khác nhau**; khóa tài khoản/vai trò trong transaction, khóa bản đã duyệt, audit và tests. Chưa kiểm thử LLM thật. |
| F1.03 | Upload batch | Giới hạn 50 file, 10 MB/file, 250 MB/lô; kiểm tra PDF/DOCX, báo lỗi và theo dõi tiến trình. |
| F1.04 | Trích xuất, OCR, sửa profile | Có PDF text/DOCX và code OCR scan tiếng Anh; UI HR tạo profile version mới với thông tin chuyên môn. Assessment cũ bị ẩn sau sửa; phải chạy lại. Chưa kiểm thử OCR scan thật. |
| F1.05 | Đánh giá và dẫn chứng | Có bốn mức, kiểm tra trích dẫn với văn bản đã che, số trang PDF được kiểm tra; DOCX không có trang đáng tin cậy. Thiếu bằng chứng/độ tin cậy thấp là `UNCLEAR`. Redaction có thể làm mất bằng chứng hợp lệ. |
| F1.06 | Điểm và ranking | Tính tất định từ rubric đã duyệt, cảnh báo độ phủ, ranking chỉ gồm hồ sơ và profile hiện hành. Điểm là tham khảo; policy cần HR/HM xác nhận trước pilot. |
| F1.07 | Cảnh báo trùng | Tín hiệu email/phone trong cùng vị trí; đổi identifier hủy tín hiệu pending cũ và tính lại ở lần ranking sau. Không tự gộp/xóa. |
| F1.08 | Trạng thái và lịch sử | HR cập nhật theo luồng hợp lệ, yêu cầu lý do khi loại; AI không tự đổi trạng thái. |
| F1.09 | Shortlist, feedback, ghi chú HR | Chia sẻ cho HM được gán, chọn quyền xem CV, feedback và thu hồi. Ghi chú riêng append-only qua API, chỉ HR phụ trách/HR Lead, không gửi AI; snapshot shortlist cần chia sẻ lại khi assessment đổi. |
| F1.10 | RBAC, audit, retention | Có UI/API ADMIN tạo và quản lý roles/trạng thái, bootstrap đầu tiên được bảo vệ một lần, bắt đổi mật khẩu tạm; Auth mới chỉ mock trong test. Migration 00003/00004 đã áp vào project kết nối; 00005 chỉ có trong repo, **chưa áp**, mã mới phụ thuộc 00005. Audit chưa bất biến; chưa có workflow xác nhận xóa/retention 12 tháng. |
| F1.11 | Cấu hình AI, privacy | Admin kích hoạt phiên bản model/endpoint/temperature trong allowlist deployment; secret chỉ từ môi trường. Che PII trước AI và guardrails là **best effort**, không bảo đảm ẩn danh, chống bias hay egress; chỉ hỗ trợ OpenAI-compatible/Bearer. |
| F1.12 | Việt–Anh | UI có lựa chọn Việt–Anh, mặc định Việt và lưu preference; không dịch nội dung do người dùng nhập. Có unit test và cần tiếp tục review bản dịch/ngữ cảnh nghiệp vụ. |
| F1.13 | Dashboard, worker | Số liệu theo quyền, không tạo số giả. Worker có session advisory lock/fencing, heartbeat, recovery và tests crash/concurrency; cần session DB ổn định, drain worker cũ, monitoring và staging. AI calls at-least-once. |

## Kiểm thử và công việc còn lại

Automated backend tests dùng PostgreSQL cục bộ dùng một lần, CV/tài khoản tổng hợp và AI HTTP mock; frontend có type-check, lint, build, kiểm thử i18n và smoke trình duyệt dữ liệu giả. Chưa kiểm thử Supabase Auth/Storage, model thật, OCR scan hay Docker end-to-end; không tuyên bố chất lượng AI hoặc ẩn danh hoàn toàn. Xem [backend/tests/README.md](../backend/tests/README.md) và [DEPLOYMENT.md](../DEPLOYMENT.md).

Trước pilot cần rotate service-role key từng xuất hiện trong Git history, kiểm thử staging/restore và migration riêng ở các môi trường khác, kiểm soát egress, đánh giá privacy/bias và hoàn thành retention/session/audit. Không dùng dữ liệu ứng viên thật trong preview hoặc kiểm thử này.
