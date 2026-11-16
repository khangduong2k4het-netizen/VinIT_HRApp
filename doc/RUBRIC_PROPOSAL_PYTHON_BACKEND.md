# Đề xuất rubric khởi đầu — Python Backend

**Trạng thái: đề xuất để HR/HM rà soát, chưa phải chuẩn tuyển dụng, chưa xuất bản và chưa áp vào vị trí.** Người dùng cho phép đề xuất một rubric làm tiền đề phát triển; các mục ngoài ngưỡng Python 4 năm là đề xuất, không phải chính sách được phê duyệt. Không dùng tự động để loại ứng viên. Nội dung dựa trên stack FastAPI/Python/PostgreSQL và quy trình kiểm thử của dự án, không lấy CV/JD thật.

## Phạm vi và trọng số

- Family: **IT & Digital**. Vai trò mẫu: **Kỹ sư Backend Python**; level để trống để HR/HM quyết định.
- Hai nhóm: bắt buộc **70%**, ưu tiên **30%**; đây là cấu hình đề xuất, HR có thể sửa. Trọng số bên dưới là *trong từng nhóm*, không phải tổng toàn rubric.

| Nhóm | Tiêu chí | Trọng số trong nhóm | Bằng chứng gợi ý |
|---|---|---:|---|
| Bắt buộc | Phát triển backend bằng Python, tối thiểu **4 năm** | 45% | Vai trò, phạm vi và khoảng thời gian gắn với công việc Python backend |
| Bắt buộc | Dịch vụ/API với **ít nhất một** FastAPI, Django hoặc Flask | 30% | Dự án, endpoint và trách nhiệm; không đòi cả ba framework |
| Bắt buộc | Sử dụng PostgreSQL cho backend | 25% | Ngữ cảnh sử dụng, truy vấn, thiết kế dữ liệu hoặc giao dịch |
| Ưu tiên | Kiểm thử tự động backend/API | 60% | Ví dụ unit/integration test và trách nhiệm; không buộc một công cụ |
| Ưu tiên | Đóng gói/triển khai Docker hoặc container | 40% | Dự án, trách nhiệm triển khai; không bắt buộc Kubernetes |

Tổng trong mỗi nhóm = 100%. Trọng số thực toàn rubric tương ứng là 31,5%, 21%, 17,5%, 18% và 12%. File dữ liệu có mô tả và hướng dẫn bằng chứng chi tiết: `frontend/src/data/rubric-proposal-it-backend.json`.

## Thang HM đề xuất để HR/HM chuẩn hóa

1. Bằng chứng rõ về khoảng cách lớn với yêu cầu.
2. Có bằng chứng liên quan một phần nhưng còn khoảng cách đáng kể.
3. Có đủ bằng chứng đáp ứng mức tối thiểu của tiêu chí.
4. Có bằng chứng tốt, trách nhiệm rõ và vượt mức tối thiểu.
5. Có bằng chứng rất mạnh về chiều sâu, phạm vi và kết quả.

Không đủ thông tin để chấm thì chọn **Thiếu bằng chứng**, không quy đổi thành 1. Điểm HM là nhận định chuyên môn, không tự chuyển trạng thái ứng viên. Các mốc 1–5 trên là gợi ý chung, chưa phải thang chi tiết đã duyệt; UI hiện không có trường riêng cho anchor từng mức. Nếu HR muốn HM nhìn thấy các hướng dẫn này ngay trong scorecard, cần bổ sung nội dung phù hợp vào **mô tả từng tiêu chí** khi rà soát.

## Quy tắc Python và các giới hạn quan trọng

- Criterion Python có `requirement_spec` loại `SKILL`, `terms=["Python"]`, `min_years=4`. **Không sửa manifest hay policy hiện hành.** Trường hợp fixture `partial_backend` chỉ nêu 2 năm vẫn **UNCLEAR** chờ HR xác minh, không tự `MATCH`/`NO_MATCH`.
- Ba framework ở tiêu chí thứ hai là phương án thay thế; không hiểu là bắt buộc cả ba. Engine hiện gom chúng thành một nhóm khái niệm; vẫn cần kiểm chứng bằng chứng và bối cảnh thực tế.
- Tên kỹ năng/keyword và việc có mặt trong CV không chứng minh mức độ thành thạo. Missing evidence cần xác minh; quyền quyết định và status vẫn thuộc HR. Các đề xuất về PostgreSQL, framework và trọng số cần HM xác nhận trước publish vì có thể không phù hợp mọi vị trí IT.
- `requirement_spec` là dữ liệu sẽ ảnh hưởng đánh giá deterministic sau khi criteria được duyệt; HR/HM phải kiểm tra mô tả **và** spec cùng nhau. Hướng dẫn bằng chứng hiện không tự hiển thị trên panel scorecard như mô tả criterion.

## Tạo draft bằng đúng tài khoản HR

1. Sau khi backend/frontend phiên bản phù hợp được deploy vào môi trường đã duyệt, HR đăng nhập bằng tài khoản của mình.
2. Vào **Thư viện rubric → Dùng đề xuất Backend Python**, kiểm tra tất cả trường, sửa nội dung và trọng số nếu cần, rồi **Lưu bản nháp**. Nút đề xuất chỉ điền biểu mẫu, không tự lưu/publish.
3. HR Lead rà soát và chủ động xuất bản sau khi thống nhất với HM. Áp dụng template tạo criteria draft; vẫn giữ cả dual approval và direct approval theo quyền hiện hành.

Không có dữ liệu nào được tự chèn vào Supabase qua file đề xuất. Chưa deploy ứng dụng và chưa có HR tạo bản nháp thực tế trên database; không gán người tạo hoặc phát hành thay một tài khoản HR.
