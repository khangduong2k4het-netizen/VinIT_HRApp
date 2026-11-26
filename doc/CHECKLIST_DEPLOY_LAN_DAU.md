# Checklist deploy lần đầu — bản `arena/ea6e2570-vinit-hrapp`

> Kiểm ngày 2026-11-30 tại `a53a22f`. Mỗi dòng có **bằng chứng đo được**, không
> phải "đã kiểm rồi". Nếu một dòng không đạt thì **dừng**, đừng deploy.

---

## A. Điều kiện đã đạt (đo từ Supabase + repo)

| # | Điều kiện | Bằng chứng |
|---|---|---|
| A1 | Migration `00039`–`00041` đã áp lên Supabase | `list_migrations`: 34 bản ghi, bản cuối `20261122033943 interview_notifications_00041` |
| A2 | Bảng mới tồn tại thật và RLS bật | `interviews`, `interview_participants`, `interview_notifications`, `shortlist_scorecards` — cả 4 `relrowsecurity = true` |
| A3 | RLS không policy là **đúng thiết kế**, không phải thiếu | `00039`/`00041` chỉ `GRANT … TO service_role`. `anon`/`authenticated` bị chặn hết. Backend dùng service_role. Toàn DB: 55/66 bảng bật RLS, chỉ 38 policy — mẫu chung là vậy |
| A4 | Supabase project khoẻ | `status: ACTIVE_HEALTHY`, PG 17.11, region `ap-southeast-1` |
| A5 | Code đã push hết | local `a53a22f` = remote `a53a22f`, tree sạch |
| A6 | `package-lock.json` khớp `package.json` | `npm ci --dry-run` exit 0 |
| A7 | Frontend build được | `npm run build` xanh, 26 trang |
| A8 | Test backend | 671 passed (174 skip vì sandbox không có Postgres — CI đã chạy đủ, xanh) |
| A9 | Test frontend | 163 + 3 i18n xanh |
| A10 | CI xanh cả 3 job | `47cef64`, `48ac07b` |

## B. Bốn điều kiện CHƯA kiểm được từ đây — phải làm trên VPS

Đây là lý do tôi **không** nói "deploy được rồi". Bốn thứ dưới chỉ kiểm được ở máy
đích.

### B1. Môi trường đích đã có gì

Deploy script giả định:

```
PM2: hra-backend, hra-frontend
Backend  http://127.0.0.1:8005  (/health/ready)
Frontend http://127.0.0.1:3005
Đường dẫn: /home/ubuntu/hra
```

**Kiểm:** `pm2 list`, `curl -s http://127.0.0.1:8005/health` — nếu chưa có hai
process này thì đây là **lần dựng đầu**, không phải deploy. Cần dựng `.env` trước.

### B2. `.env` trên VPS

Repo chỉ có `.env.example`. Trên VPS phải có `.env` thật. **Kiểm bằng cách đối
chiếu danh sách khoá**, không phải đọc giá trị:

```bash
diff <(grep -oE '^[A-Z_]+' .env.example | sort -u) \
     <(grep -oE '^[A-Z_]+' backend/.env  | sort -u)
```

Thiếu khoá nào thì backend khởi động sai mà không báo rõ.

### B3. `CORS_ORIGINS` phải chứa domain thật — MẪU ĐÃ SAI, đã sửa

`backend/app/core/config.py:162` mặc định chỉ có `localhost:3000` và
`127.0.0.1:3000`. Nhưng `scripts/deploy.sh:44` chạy frontend ở cổng **3005**.

`.env.example` (và `backend/.env.example`) cũng đặt 3000 — tức là **ai chép mẫu
ra .env thì trình duyệt bị chặn CORS** dù backend khoẻ. Đã sửa cả hai mẫu sang
3005 kèm ghi chú. Trên VPS: kiểm `.env` thật, và **thêm domain thật** của bạn.

Đây là lỗi im lặng kinh điển: `curl` từ server thấy 200, nhưng người dùng mở
trình duyệt thấy trắng trang.

### B4. `READINESS_REQUIRE_CLAMAV`

`/health/ready` **báo cáo** trạng thái ClamAV nhưng không chặn 503 (trừ khi bật
cờ). Nếu VPS không có ClamAV, đường nhận CV sẽ hỏng (`careers_intake` fail-closed)
nhưng hệ thống vẫn "ready". **Quyết định trước:** chấp nhận không nhận CV, hay
cài ClamAV? Đừng để phát hiện lúc demo.

---

## C. Lệnh deploy

Trên VPS, tại `/home/ubuntu/hra`:

```bash
# 1. Kiểm 4 điều kiện B ở trên. Không đạt thì dừng.

# 2. Deploy. --migrations-verified vì 00039-00041 ĐÃ áp (A1).
bash scripts/deploy.sh \
  --branch arena/ea6e2570-vinit-hrapp \
  --migrations-verified
```

Cờ `--migrations-verified` là **lời khai của người vận hành**, không phải cờ tiện
dụng. Script cố tình không tự áp migration (`deploy.sh:333`), nên nó cần biết ta đã
áp thật. A1 ở trên là bằng chứng cho lời khai đó.

## D. Kiểm sau deploy — 5 phút, không bỏ bước nào

| # | Kiểm | Đạt khi |
|---|---|---|
| D1 | `curl -s http://127.0.0.1:8005/health/ready` | `db: connected`, có trường `clamav` |
| D2 | Mở trang chủ bằng **trình duyệt**, không phải curl | Không trắng trang, không lỗi CORS trong console |
| D3 | Đăng nhập | Vào được, không lặp về trang login |
| D4 | Mở một vị trí, xem danh sách hồ sơ | Có dữ liệu, không 500 |
| D5 | **Duyệt bộ tiêu chí thứ hai cho cùng một vị trí** | **Không 500** — đây là bug vừa sửa ở `5c939df`, chưa từng chạy trên môi trường thật |
| D6 | Mở `/interviews` | Danh sách lịch phỏng vấn hiện (0 dòng cũng được) |
| D7 | Chuông thông báo ở header | Hiện, poll 60s không lỗi console |

D5 là bước quan trọng nhất. Toàn bộ giá trị của lần deploy này là **chứng minh
tính năng "một vị trí một bộ tiêu chí hiệu lực" chạy được thật**. Nếu D5 ra 500,
đừng đi tiếp sang việc khác.

## E. Nếu deploy hỏng

| Hiện tượng | Nguyên nhân hay gặp |
|---|---|
| Script exit 2 ở bước 3 | Thiếu `--migrations-verified` — nhưng **chỉ thêm cờ khi A1 đúng** |
| Backend chết ngay sau restart | `.env` thiếu khoá (B2). `pm2 logs hra-backend --lines 50` |
| Trang trắng, console báo CORS | `CORS_ORIGINS` thiếu domain (B3) |
| Build fail trên VPS | `package-lock` khớp (A6 đã đạt) nên khả năng cao là hết RAM khi build |
| 502 từ frontend | Frontend build xong nhưng `pm2 restart hra-frontend` chưa xong — chờ, đừng deploy lại ngay |

## F. Rollback

Script giữ marker trong `.deploy-state/`. Cách lùi:

```bash
git checkout <commit trước>
bash scripts/deploy.sh --force
```

**Lưu ý:** rollback **không** lùi được migration đã áp. `00039`–`00041` chỉ thêm
bảng/cột, không xoá gì, nên code cũ chạy trên schema mới vẫn được. Đó là lý do các
migration này an toàn để đi trước.
