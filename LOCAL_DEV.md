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
