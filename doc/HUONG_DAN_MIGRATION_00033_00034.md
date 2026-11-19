# Chạy migration `00033` + `00034` — hướng dẫn từng bước

> **✅ ĐÃ ÁP XONG ngày 2026-11-19** trên project `myrymlqdbyqmpynesiwk`:
> version remote `20261119093801` (`hr_criterion_reviews_00034`) và
> `20261119093753` (`app_settings_00033`). Postflight đạt đủ: 2 bảng tồn tại,
> `app_settings` có đúng 2 dòng = 7, RLS bật, **0 grant** cho `anon/authenticated`,
> đủ 6 constraint gồm `hr_criterion_reviews_rejected_needs_reason`, và dữ liệu
> nền không đổi (6 positions / 7 applications / 74 assessment results).
> **Không chạy lại.** Phần dưới giữ làm hồ sơ quy trình và để áp cho môi trường
> khác (production sau này).

Áp cho project Supabase `myrymlqdbyqmpynesiwk` (môi trường test code).
Người viết đã **đọc migration và đọc cách 00031/00032 đã được áp trước đó**; những
chỗ dưới đây không phải suy đoán.

---

## 0. Vì sao phải chạy trước khi deploy

Code ở nhánh này đọc/ghi hai bảng **chưa tồn tại** trên Supabase:

| Bảng | Dùng ở đâu | Nếu thiếu |
| --- | --- | --- |
| `app_private.app_settings` | `GET/PATCH /v1/admin/settings`, `summary.deadline_soon_days`, `summary.waiting_attention_days` | Tab **"Cài đặt HR"** trong `/admin` và work queue **lỗi 500** |
| `app_private.hr_criterion_reviews` | `POST /v1/assessments/results/{id}/review`, `GET` assessment, `GET /v1/applications/{id}` | Nút **"Trích dẫn đúng, đã kiểm"** lỗi 500 ⇒ hàng đợi "Cần xác minh" **không bao giờ đóng được** |
| `app_private.app_settings` | `/dashboard` (work queue summary) | Dashboard mất dòng "chờ quá N ngày" |

Đây **không** phải migration thêm-dần-tuỳ-ý: cả hai đều là bảng mới, không sửa
bảng cũ, không đụng dữ liệu sản phẩm.

---

## 1. Kiểm tra trước (5 phút, không thay đổi gì)

Chạy trong **Supabase Dashboard → SQL Editor** (hoặc `psql` với connection string
của project). Chỉ đọc:

```sql
-- 1. Hai bảng đã tồn tại chưa? Kết quả mong đợi: cả hai đều false.
SELECT to_regclass('app_private.app_settings')          AS app_settings,
       to_regclass('app_private.hr_criterion_reviews')  AS hr_criterion_reviews;

-- 2. Bảng cha của khoá ngoại phải có (00034 tham chiếu tới hai bảng này).
SELECT to_regclass('app_private.criterion_assessment_results') AS results_base,
       to_regclass('app_private.positions')                    AS positions;

-- 3. Không có operation nào đang chạy — tránh vừa migrate vừa có worker ghi.
SELECT status, count(*) FROM app_private.operations
WHERE status IN ('PENDING','PROCESSING') GROUP BY status;

-- 4. Đếm nhanh để so sánh sau khi áp (dữ liệu sản phẩm không được đổi).
SELECT count(*) AS positions FROM app_private.positions;
SELECT count(*) AS applications FROM app_private.applications;
```

> Nếu câu 1 trả về **không** NULL: bảng đã có, **dừng lại** — xem mục 6.
> Nếu câu 2 có ô NULL: dừng, migration `00001`/`00008` chưa áp đủ.
> Nếu câu 3 có dòng: dừng, chờ worker xử lý xong.

---

## 2. Chạy hai migration

Repo **không** dùng `supabase db push` — đó là quyết định đã có từ trước
(00020, 00027–00032 đều áp qua cổng riêng, mỗi lần một version remote). Với hai
bảng độc lập, cách gọn nhất là chạy **nguyên văn file** trong một transaction.

Mở **SQL Editor**, dán **toàn bộ nội dung** của
`supabase/migrations/00033_app_settings.sql`, bọc trong transaction:

```sql
BEGIN;
-- ... dán nguyên văn nội dung 00033_app_settings.sql ở đây ...
COMMIT;
```

Làm y hệt với `00034_hr_criterion_reviews.sql`. **Chạy tuần tự, không chạy song
song.** Nếu `COMMIT` báo lỗi, `ROLLBACK;` và **dừng** — không sửa file migration
tại chỗ để "chạy cho được".

### Vì sao bọc transaction

Hai file đều **không idempotent** (`CREATE TABLE` trần, không `IF NOT EXISTS`).
Nếu nửa đường lỗi mà không có transaction, anh sẽ có bảng dở dang khó dọn. Có
transaction thì hoặc cả file vào, hoặc không gì cả.

### Nếu muốn chạy bằng `psql` trên VPS (thay vì SQL Editor)

```bash
# Chạy từ thư mục repo trên VPS, sau khi đã `git pull`.
# .env có DATABASE_URL; không in connection string ra màn hình/log.
cd ~/hra
export $(grep -E '^DATABASE_URL=' backend/.env | xargs)

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 --single-transaction \
  -f supabase/migrations/00033_app_settings.sql

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 --single-transaction \
  -f supabase/migrations/00034_hr_criterion_reviews.sql
```

`ON_ERROR_STOP=1` + `--single-transaction` cho đúng ngữ nghĩa "hoặc cả hai,
hoặc không gì". Migration không `DROP`, không `UPDATE` dữ liệu, nên không cần
backup riêng — nhưng nếu anh muốn chắc chắn, dùng **Supabase → Database →
Backups** tạo một bản trước (mục "Backup" chỉ mất ~1 phút).

---

## 3. Kiểm tra sau khi áp (postflight)

```sql
-- Bảng đã có
SELECT to_regclass('app_private.app_settings'),
       to_regclass('app_private.hr_criterion_reviews');

-- 2 dòng mặc định, đều = 7 (giá trị code cũ đang hard-code ⇒ deploy không đổi gì)
SELECT setting_key, value_int FROM app_private.app_settings ORDER BY setting_key;

-- RLS bật, và browser role không đọc được (phải là 0)
SELECT relname, relrowsecurity FROM pg_class
WHERE relname IN ('app_settings','hr_criterion_reviews');
SELECT count(*) FROM information_schema.role_table_grants
WHERE table_name IN ('app_settings','hr_criterion_reviews')
  AND grantee IN ('anon','authenticated');

-- Ràng buộc "từ chối phải có lý do" đã vào
SELECT conname FROM pg_constraint
WHERE conrelid = 'app_private.hr_criterion_reviews'::regclass;

-- Dữ liệu sản phẩm KHÔNG đổi (so với mục 1)
SELECT count(*) AS positions FROM app_private.positions;
SELECT count(*) AS applications FROM app_private.applications;
```

**Đạt** khi: hai bảng tồn tại · `app_settings` có đúng 2 dòng giá trị 7 ·
`relrowsecurity = true` · grant cho `anon/authenticated` = **0** · có constraint
`hr_criterion_reviews_rejected_needs_reason` · số positions/applications y như
trước.

### Một chi tiết dễ hiểu nhầm về quyền

Cả hai migration `REVOKE ALL` khỏi `PUBLIC, anon, authenticated, service_role`
rồi chỉ `GRANT` lại phần tối thiểu cho `service_role`. Nghĩa là **role kết nối
của backend phải có quyền tương ứng**, nếu không backend sẽ `permission denied`.

Trong repo, `.env` mẫu dùng role `postgres`
(`postgresql://postgres:...`) — superuser, nên **không** bị ảnh hưởng. Chỉ cần
để ý nếu ai đó đổi `DATABASE_URL` sang một role giới hạn:

| Việc backend làm | Quyền cần có trên bảng |
| --- | --- |
| Đọc cài đặt (`/admin/settings`, dashboard) | `SELECT app_settings` |
| Ghi cài đặt (`PATCH /admin/settings/{key}`) | `UPDATE (value_int, updated_at, updated_by)` — đúng 3 cột, không phải UPDATE cả bảng |
| Ghi nhận xét duyệt | `SELECT, INSERT hr_criterion_reviews` (**không** `UPDATE`/`DELETE`: bảng cố ý append-only) |
| Đọc nhận xét duyệt | `SELECT hr_criterion_reviews` |

Nói cách khác: nếu ai đó "sửa cho nhanh" bằng `GRANT ALL ON ... TO service_role`
thì bảng review mất tính append-only ở tầng quyền. Đừng làm vậy.

---

## 4. Deploy code — lưu ý script sẽ **dừng**

`scripts/deploy.sh` phát hiện `supabase/migrations` thay đổi và **exit 2**:

```
supabase/migrations changed — this script does not apply Supabase migrations
apply/verify migrations through the approved Supabase process, then rerun with --migrations-verified
```

Đó là hành vi **đúng** (script không bao giờ tự áp migration). Sau khi mục 3 đạt:

```bash
cd ~/hra
bash scripts/deploy.sh --branch arena/ea6e2570-vinit-hrapp --migrations-verified
```

Cờ này **chỉ** nói "tôi đã áp migration rồi, đừng dừng nữa" — nó **không** áp
migration. Đừng dùng nó trước khi mục 3 đạt.

---

## 5. Smoke sau deploy (3 phút)

```bash
curl --fail http://127.0.0.1:8005/health/ready     # database: connected
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3005   # 200
```

Trên trình duyệt, đăng nhập **ADMIN**:

1. `/admin` → tab **"Cài đặt HR"** → thấy `deadline_soon_days = 7`,
   `waiting_attention_days = 7`. Đổi một giá trị rồi lưu → thấy xác nhận.
   (Đổi lại về 7 nếu không muốn giữ.)
2. `/dashboard` → dòng "… chờ quá 7 ngày …" hiện đúng số.
3. Mở một hồ sơ có tiêu chí "cần xác minh" → bấm **"Trích dẫn đúng, đã kiểm"**
   → dòng trạng thái đổi thành "đã kiểm 1/N", **trạng thái hồ sơ không đổi**.
   Tải lại trang → quyết định vẫn còn (đây là điểm khác biệt so với trước).

Bước 3 là **thứ chứng minh U1 chạy thật**: trước migration, nút này 500.

---

## 6. Nếu bảng đã tồn tại (ai đó áp trước rồi)

**Không chạy lại** — `CREATE TABLE` sẽ báo `relation already exists` và cả
transaction rollback, vô hại nhưng gây hoang mang. Kiểm nội dung thay vì chạy lại:

```sql
\d app_private.app_settings
\d app_private.hr_criterion_reviews
```

So với hai file trong `supabase/migrations/`. Nếu khớp (cột, constraint, RLS,
grant), coi như đã áp và bỏ qua. Nếu **khác**, dừng và báo lại — đừng `DROP`
bảng để chạy lại khi đã có dữ liệu review.

---

## 7. Rollback (nếu buộc phải)

Hai bảng đều **mới**, không bảng nào bị sửa ⇒ rollback = bỏ hai bảng và quay lại
code cũ:

```sql
BEGIN;
DROP TABLE IF EXISTS app_private.hr_criterion_reviews;
DROP TABLE IF EXISTS app_private.app_settings;
COMMIT;
```

**Chỉ làm sau khi đã deploy lại code cũ** (code mới sẽ lỗi 500 khi thiếu bảng).
`hr_criterion_reviews` chứa quyết định của HR — rollback **xoá mất** chúng; nếu
đã có người dùng thật, xuất ra trước bằng
`COPY (SELECT * FROM app_private.hr_criterion_reviews) TO STDOUT WITH CSV HEADER`.

---

## 8. Những gì hướng dẫn này **không** làm

- **Không** chạy `supabase db push`, `supabase db reset`, `migration repair`. Lý do:
  sẽ đẩy cả 34 file và reset trạng thái version — đúng thứ tài liệu deploy cấm.
- **Không** sửa file migration để "cho chạy được". Nếu lỗi, sửa nguyên nhân.
- **Không** áp `00024`–`00026` (đã có quyết định **không** áp trước đó).
- **Không** seed dữ liệu, không purge, không đụng `auth.users`.
- **Không** coi việc áp migration là nghiệm thu xong: vẫn còn **usability test với
  HR thật** và **thử Safari/iOS** (xem `TONG_HOP_DONG_PHASE_UIUX.md` mục 1).

---

## 9. Nếu anh muốn tôi làm thay

Tôi có connector Supabase cho project này và đã từng áp `00027`–`00032` bằng
đường đó. Nếu anh đồng ý, tôi sẽ: chạy mục 1 → áp hai file → chạy mục 3 → gửi
lại **nguyên văn output** cả ba bước. Anh chỉ cần nói "làm đi".

Lưu ý: tôi **không** truy cập được VPS, nên bước deploy (mục 4) và smoke trên
trình duyệt (mục 5) vẫn phải anh chạy.
