# Chạy HRA trên máy (không cần Supabase, không cần AI Core)

Hướng dẫn chạy toàn bộ dự án trên máy cá nhân với:

- **PostgreSQL cục bộ** thay cho database Supabase;
- **Đăng nhập nội bộ** (`AUTH_BACKEND=local`) thay cho Supabase Auth — mật khẩu được băm scrypt và lưu trong PostgreSQL;
- **AI giả lập** (`LLM_PROVIDER=mock`) trong lúc chờ AI Core, hoặc **OpenAI** khi có API key.

> Chế độ Supabase vẫn giữ nguyên: chỉ cần không đặt `AUTH_BACKEND=local`.

## 1. Cài đặt cần có

| Thành phần | Ghi chú |
|---|---|
| PostgreSQL 16 + **pgvector** | Bộ cài PostgreSQL cho Windows (EDB) đã kèm pgvector. Cần mật khẩu user `postgres`. |
| Python 3.11+ | |
| Node.js 20+ | |

## 2. Tạo database và file cấu hình

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"        # macOS/Linux: .venv/bin/pip
.venv/Scripts/python scripts/setup_local_db.py --admin-url "postgresql://postgres:MAT_KHAU_POSTGRES@127.0.0.1:5432/postgres" --write-env
```

Script sẽ:

1. tạo database `hra_local` và các role mà migration cần;
2. tạo schema `auth` tối giản thay cho Supabase Auth;
3. áp lần lượt toàn bộ `supabase/migrations/*.sql` (chạy lại an toàn — chỉ áp file mới);
4. với `--write-env`: tạo `backend/.env` (đã được git bỏ qua) với `AUTH_BACKEND=local`, `LLM_PROVIDER=mock`, secret JWT và mã khởi tạo Admin **ngẫu nhiên**. File `.env` có sẵn sẽ không bị ghi đè.

Script chỉ chấp nhận host cục bộ. Không trỏ vào Supabase hay database dùng chung.

## 3. Chạy

```bash
# Terminal 1 — backend (cổng 8000; worker xử lý CV chạy kèm)
cd backend
.venv/Scripts/uvicorn app.main:app --port 8000

# Terminal 2 — frontend (cổng 3000)
cd frontend
npm ci
npm run dev
```

Mở http://localhost:3000/bootstrap, nhập `ADMIN_BOOTSTRAP_TOKEN` trong `backend/.env` để tạo **Admin đầu tiên**, rồi xóa dòng đó khỏi `.env`. Admin tạo các tài khoản HR Lead / HR Recruiter / Hiring Manager trong **Quản lý tài khoản**; người dùng mới phải đổi mật khẩu tạm ở lần đăng nhập đầu. Đăng nhập sai 5 lần liên tiếp sẽ khóa tài khoản 15 phút.

## 4. Dùng OpenAI thay cho AI giả lập

> **Dữ liệu:** tài liệu dự án quy định ưu tiên xử lý cục bộ, dịch vụ AI bên ngoài **chỉ dùng cho kiểm thử**. Khi bật OpenAI, nội dung JD/CV (đã che bớt thông tin cá nhân) được gửi sang OpenAI. **Chỉ dùng CV tổng hợp/giả lập**, không dùng CV ứng viên thật khi chưa có phê duyệt privacy/egress.

Sửa `backend/.env`:

```env
LLM_PROVIDER=openai
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL_NAME=ten-model-ban-chon        # ví dụ một model chat của OpenAI hỗ trợ JSON mode
LLM_API_KEY=sk-...                        # tự dán key của bạn; không commit
ALLOW_EXTERNAL_API=true                   # bắt buộc với endpoint ngoài mạng nội bộ (chỉ HTTPS)
# LLM_STRICT_JSON_SCHEMA=true             # tùy chọn: bật nếu model hỗ trợ structured outputs
```

Khởi động lại backend. Kiểm tra nhanh: trên trang một vị trí bấm **Đề xuất tiêu chí AI**. Nếu báo lỗi, xem log backend (thông báo lỗi không chứa key).

Muốn quay về AI giả lập: đặt lại `LLM_PROVIDER=mock`. AI giả lập bị **từ chối khi `APP_ENV` khác `development`/`testing`**, và mọi lập luận của nó đều có nhãn `[MOCK AI]`.

## 5. Chạy test

```bash
# Database test riêng, tên phải kết thúc bằng _test (test sẽ TRUNCATE dữ liệu)
.venv/Scripts/python scripts/setup_local_db.py --admin-url "postgresql://postgres:MAT_KHAU@127.0.0.1:5432/postgres" --database hra_local_test

# Windows: dùng --basetemp ngắn để không vượt giới hạn 260 ký tự của đường dẫn
TEST_DATABASE_URL="postgresql://postgres:MAT_KHAU@127.0.0.1:5432/hra_local_test" .venv/Scripts/pytest -q --basetemp=.pt tests
```

Frontend: `npm run type-check && npm run lint && npm run test:i18n && npm run test:unit`.

## 6. Quên mật khẩu (khi không có email/SSO)

Dự án chưa được cấp SMTP hay SSO nên không có thư tự đặt lại mật khẩu và **không có tự đăng ký tài khoản**
(`SELF_REGISTRATION_ENABLED=false`, mặc định). Cách xử lý:

- **HR / Hiring Manager quên mật khẩu:** ở trang đăng nhập bấm **"Quên mật khẩu? Gửi yêu cầu cho Admin"**, nhập email tài khoản
  và **lý do**. Admin vào **Quản lý tài khoản** -> mục **Yêu cầu đặt lại mật khẩu**, kiểm tra rồi bấm **Duyệt và gửi link**
  (hệ thống gửi link đặt lại mật khẩu 30 phút, dùng một lần, vào đúng email của tài khoản đó) hoặc **Từ chối** (có ghi chú).
  Mỗi tài khoản chỉ có 1 yêu cầu đang chờ; yêu cầu quá 7 ngày tự hết hạn; Admin không tự duyệt yêu cầu của chính mình.
  Trang luôn trả cùng một thông báo dù email có tồn tại hay không. **Cần cấu hình email gửi đi (SMTP)**; nếu chưa có,
  nút Duyệt báo "chưa cấu hình email" và Admin dùng nút **Đặt lại mật khẩu** (mật khẩu tạm) ở danh sách tài khoản:
  người dùng phải đổi ngay khi đăng nhập, các phiên cũ bị thu hồi, có ghi audit.
- **Admin quên mật khẩu hoặc cả email (cách chính — ngay trong giao diện, không cần gõ lệnh):**
  1. **Một lần khi triển khai:** người vận hành tạo một chuỗi ngẫu nhiên dài (từ 32 ký tự) và đặt vào `backend/.env`:
     `ADMIN_RECOVERY_KEY=<chuỗi>`. Cất chuỗi này như mật khẩu hệ thống (két, trình quản lý mật khẩu, phong bì niêm phong).
     Để trống = tắt trang khôi phục. Chỉ dùng với `AUTH_BACKEND=local`.
  2. **Khi Admin không đăng nhập được:** ở trang đăng nhập bấm **"Cần trợ giúp đăng nhập?"** -> thẻ **"Tôi là Admin và không đăng nhập được"**
     -> **Dùng mã khôi phục**. Nhập mã, hệ thống liệt kê các Admin (không cần nhớ email), chọn đúng Admin và đặt mật khẩu mới.
  2b. **Chưa có mã / làm mất mã (qua email):** ở trang khôi phục chọn **"Tôi chưa có mã / làm mất mã"** -> **Nhập email Admin**. Hệ thống gửi tới đúng email đó
     một **mã dùng một lần** (dạng `XXXX-XXXX-XXXX`, hết hạn sau 15 phút, sai 5 lần thì bị hủy) đóng vai **mật khẩu cũ**. Trang chuyển sang 3 dòng:
     mật khẩu cũ (mã trong email) / mật khẩu mới / xác nhận mật khẩu mới; xong là đăng nhập luôn. Phản hồi luôn giống nhau dù email có phải Admin hay không;
     mỗi tài khoản tối đa 3 mã/giờ. Cần cấu hình SMTP (chưa có thì trang báo "Chưa cấu hình email"). Cách này vẫn phải gõ đúng email Admin;
     quên cả email thì xem ở Quản lý tài khoản (Admin khác), dùng mã khôi phục của máy chủ (tự liệt kê Admin), hoặc lệnh `--list-admins`.
  3. Hệ thống thu hồi các phiên cũ, mở khóa tài khoản, ghi audit (`ADMIN_RECOVERY_LIST_VIEWED`, `ADMIN_RECOVERY_RESET_PASSWORD`, không chứa mã
     hay mật khẩu). Nhập sai mã 5 lần thì khóa địa chỉ đó 15 phút; tổng 20 lần sai thì tạm khóa cả trang 15 phút.
  4. Nếu mã khôi phục bị lộ: đổi `ADMIN_RECOVERY_KEY` rồi khởi động lại API.
- **Phương án cuối (không dùng được trang trên):** người vận hành chạy lệnh trên máy chủ (cần quyền DB):

  ```powershell
  cd backend
  .\.venv\Scripts\python scriptseset_admin_password.py --list-admins
  .\.venv\Scripts\python scriptseset_admin_password.py --email admin@vinuni.edu.vn
  ```

  Lệnh in mật khẩu tạm ngẫu nhiên **một lần**; Admin đăng nhập và phải đổi ngay. Mặc định chỉ áp dụng cho Admin (tài khoản khác thêm `--force`),
  có ghi audit `EMERGENCY_RESET_PASSWORD` / `ADMIN_LIST_VIEWED` (actor `operator-cli`), không chứa mật khẩu.
- **Khuyến nghị:** luôn có **ít nhất 2 tài khoản Admin** (trang Quản lý tài khoản sẽ hiện cảnh báo vàng khi chỉ còn 1 Admin) để Admin này đặt lại hộ Admin kia, chỉ dùng lệnh khẩn cấp khi không còn ai đăng nhập được.
- Khi sau này có SMTP, đặt `SMTP_HOST`/`SMTP_FROM`: trang đăng nhập sẽ tự hiện "Quên mật khẩu?" gửi link đặt lại qua email.
