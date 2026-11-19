# Hướng dẫn trình diễn ba ưu tiên tuyển dụng

## An toàn và phạm vi

Bản demo này sử dụng **dữ liệu tổng hợp, database PostgreSQL riêng dùng một lần và Storage local**. Link preview cho phép người có link vào workspace HR giả **không cần mật khẩu**, do đó không gửi hoặc tải lên CV, email, số điện thoại, thông tin cá nhân hay JD thật; không dùng để tuyển dụng thực tế. Không kết nối Supabase/Gmail thật, không có quét mã độc hoặc chống spam. Dữ liệu và tiến trình demo có thể mất khi sandbox dừng. Không coi demo là nghiệm thu hay production.

Trang đầu `/demo` cho tải `cv-demo-nguyen-van-an.docx` (hồ sơ hư cấu Nguyễn Văn An, mở đầu bằng đúng họ tên để hệ thống đọc được tên ứng viên) và `email-gia.eml`, rồi mở workspace HR demo. Nếu dịch vụ được chạy với `DEMO_PREVIEW=1`, đường dẫn `/` tự chuyển đến `/demo`. Server demo tạo JWT tạm thời trong bộ nhớ; đây chỉ là cơ chế mô phỏng, không thay thế Supabase Auth. Worker sử dụng profile giả và **bỏ qua toàn bộ đánh giá/xếp hạng AI**; không có quyết định tuyển dụng tự động.

## Kịch bản demo

1. **Cổng ứng viên:** từ trang đầu tải CV giả → chọn **Trang ứng tuyển giả** → chọn `DEMO-IT-001` → điền tên/email giả, chọn CV giả, tùy chọn opt-in → gửi. Lưu lại mã demo nếu muốn thử rút consent; mã chỉ hiện một lần trong phiên. Vị trí đang mở/còn hạn hiển thị; các vị trí này có rubric tổng hợp đã được thiết lập để có thể nộp.
2. **Talent Pool:** từ `/demo` chọn **Mở workspace HR demo** → trang Talent Pool chọn nguồn `DEMO-IT-001`, đích `DEMO-IT-002` → **Kiểm tra pool demo**. Hồ sơ giả An có sẵn; hồ sơ vừa nộp sẽ xuất hiện khi worker xử lý xong (thường vài giây). Trang chỉ liệt kê hồ sơ đủ điều kiện, chưa so khớp/xếp hạng. Có thể trở lại trang ứng tuyển và nhập mã để rút; quét lại sẽ không thấy hồ sơ đó. Rút không xóa CV và không thu hồi kết quả đã hiển thị.
3. **Email offline:** tải email giả từ trang đầu → trong workspace HR chọn **Email offline (demo)** → tải `email-gia.eml` → **Tiếp nhận demo**. Sau đó mở vị trí `DEMO-IT-001` và danh sách ứng viên để xem hồ sơ nguồn email demo. Nếu vị trí còn xử lý CV trước đó, chờ vài giây rồi thử lại. Email được HR tải thủ công, không có Gmail/polling. Địa chỉ người gửi không được xác minh.

## Chuẩn bị lại từ đầu trong môi trường nội bộ

Yêu cầu dependencies frontend/backend như README, PostgreSQL riêng có extension `uuid-ossp`, `pgcrypto`, `vector`, và `psql/createdb`. Chỉ dùng cụm cục bộ disposable không có dữ liệu thật. Nếu database hoặc thư mục Storage demo đã có, **dừng lại và đối soát**, không xóa hay chạy seed lại trên dữ liệu đang có. Ví dụ dưới đây giả định PostgreSQL local `127.0.0.1:55432`; thay theo cụm riêng thực tế:

```bash
# Trên cụm disposable riêng; tạo các role nếu chưa có, theo backend/tests/README.md.
createdb -h 127.0.0.1 -p 55432 -U postgres hra_careers_ready_test
export DATABASE_URL='postgresql://postgres@127.0.0.1:55432/hra_careers_ready_test'
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
CREATE SCHEMA auth;
CREATE TABLE auth.users (id uuid PRIMARY KEY, email text UNIQUE);
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$;
SQL
for file in supabase/migrations/*.sql; do psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$file" || exit 1; done
export APP_ENV=testing CAREERS_DEMO_ENABLED=true STORAGE_BACKEND=local ALLOW_EXTERNAL_API=false LANGFUSE_ENABLED=false
export LOCAL_STORAGE_PATH="$PWD/staging/generated/hra_careers_ready_test-storage"
backend/.venv/bin/python backend/scripts/seed_careers_demo.py
backend/.venv/bin/uvicorn careers_demo_server:app --app-dir backend/scripts --host 127.0.0.1 --port 8012
```

Trong terminal thứ hai, từ gốc repo:

```bash
cd frontend
DEMO_PREVIEW=1 API_INTERNAL_URL=http://127.0.0.1:8012 npx next dev -H 127.0.0.1 -p 3012
```

Mở `http://127.0.0.1:3012/demo` trên chính máy chạy demo. Không forward/bind public trên môi trường có dữ liệu thật. Script seed từ chối database không rỗng và không xóa dữ liệu; wrapper chỉ cho phép hai tên database demo cục bộ `_test`, storage demo chỉ định, không có Supabase, Langfuse hoặc external API. Trên một preview công khai do nền tảng cung cấp, tất cả dữ liệu phải là giả; quyền truy cập link không phải kiểm soát bảo mật production.

## Kết quả kiểm thử và giới hạn

Trên database disposable, đã chạy browser E2E local: form + CV giả + opt-in; worker và danh sách pool HR; rút consent và quét lại; tải email giả vào hệ thống. Sau đó kiểm tra operation cả hai kênh `COMPLETED` với profile giả và bỏ qua AI scoring. Bản preview người dùng được seed lại trên database demo riêng, không dùng chính database đã bị E2E thay đổi. Không có Gmail OAuth, consent thật, malware scanning, AI matching hay test môi trường thật. Xem `PUBLIC_CAREERS_TALENT_POOL_EMAIL_PLAN.md` để biết các gate còn mở.
