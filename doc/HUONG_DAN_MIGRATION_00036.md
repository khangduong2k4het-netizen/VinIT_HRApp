# Migration `00036` — người phụ trách hồ sơ + ghi chú theo tiêu chí

> **✅ ĐÃ ÁP ngày 2026-11-20** trên project `myrymlqdbyqmpynesiwk`:
> version remote `20261120090000` (`application_owner_and_criterion_notes_00036`).
> Hậu kiểm đạt đủ (xem mục 3). **Không chạy lại.**
> Phần dưới giữ làm hồ sơ quy trình và để áp cho production sau này.

---

## 0. Vì sao phải áp trước khi deploy

Đây là migration đi kèm bốn commit UI/UX vòng duyệt hồ sơ. Code đọc **hai cột
chưa tồn tại** ở hai chỗ nằm trong luồng chính:

| Cột | Đọc ở | Nếu thiếu |
| --- | --- | --- |
| `applications.assigned_to` | `applications.py:319` (`GET /v1/applications` — danh sách ứng viên) và `:364` (chi tiết hồ sơ) | **500** ⇒ trang danh sách ứng viên và trang hồ sơ **trắng** |
| `application_private_notes.criterion_id` | `candidate_details.py:190,219` | **500** ⇒ không xem/ghi được ghi chú HR |

Không có guard `information_schema` nào trong code, nên nó **không** tự chịu được
tình huống thiếu cột.

`scripts/deploy.sh` sẽ **tự dừng (exit 2)** khi phát hiện `supabase/migrations`
đổi mà không có `--migrations-verified`. Cờ đó **không** áp migration — nó chỉ
xác nhận "đã áp rồi". Áp cờ mà chưa áp migration = deploy code lên DB thiếu cột.

---

## 1. Kiểm tra trước (đã chạy, kết quả đạt)

```sql
SELECT to_regclass('app_private.applications')            AS applications,
       to_regclass('app_private.application_private_notes') AS notes,
       to_regclass('app_private.criteria_items')          AS criteria_items,
       (SELECT count(*) FROM app_private.operations
        WHERE status IN ('PENDING','PROCESSING'))         AS busy_operations;

SELECT count(*) FROM information_schema.columns
WHERE table_schema='app_private'
  AND ((table_name='applications' AND column_name IN ('assigned_to','assigned_at'))
    OR (table_name='application_private_notes' AND column_name='criterion_id'));
```

Kết quả: 3 bảng cha đều tồn tại · **0** operation đang chạy · **0** cột mới đã có.

---

## 2. Áp

Chạy nguyên văn file trong **một** transaction (`BEGIN … COMMIT`). Migration này
**idempotent** (`ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`) nên chạy
lại không hỏng — khác `00033`/`00034`.

Bằng `psql` trên VPS:

```bash
cd ~/hra
export $(grep -E '^DATABASE_URL=' backend/.env | xargs)
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 --single-transaction \
  -f supabase/migrations/00036_application_owner_and_criterion_notes.sql
```

Sau đó ghi version để lần deploy sau không bị chặn nhầm:

```sql
INSERT INTO supabase_migrations.schema_migrations (version, name)
VALUES ('20261120090000', 'application_owner_and_criterion_notes_00036')
ON CONFLICT (version) DO NOTHING;
```

> Thứ tự `version` phải lớn hơn `20261119100305` (của `00035`) — đúng.

---

## 3. Hậu kiểm (đã chạy, kết quả đạt)

```sql
-- 3 cột, đều nullable
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema='app_private'
  AND ((table_name='applications' AND column_name IN ('assigned_to','assigned_at'))
    OR (table_name='application_private_notes' AND column_name='criterion_id'));

-- 2 index
SELECT indexname FROM pg_indexes WHERE schemaname='app_private'
  AND indexname IN ('applications_assigned_to_idx','application_private_notes_criterion_idx');

-- Khoá ngoại: cả hai phải là ON DELETE SET NULL
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
WHERE conname IN ('applications_assigned_to_fkey','application_private_notes_criterion_id_fkey');
```

**Đạt** khi:

| Kiểm | Kết quả thực tế |
| --- | --- |
| `assigned_to` — uuid, nullable | ✅ |
| `assigned_at` — timestamptz, nullable | ✅ |
| `criterion_id` — uuid, nullable | ✅ |
| `applications_assigned_to_idx` | ✅ |
| `application_private_notes_criterion_idx` | ✅ |
| FK `assigned_to → auth.users` `ON DELETE SET NULL` | ✅ |
| FK `criterion_id → criteria_items` `ON DELETE SET NULL` | ✅ |
| Câu query từng gây 500 (`LEFT JOIN … a.assigned_to`) chạy được | ✅ |
| Dữ liệu không đổi (0 applications, 0 notes, 7 criteria_items, 1 position, 5 users) | ✅ |

### Vì sao `ON DELETE SET NULL` chứ không CASCADE

Xoá một tài khoản HR không được làm mất hồ sơ ứng viên. Xoá một tiêu chí không
được làm mất nội dung HR đã viết — ghi chú chỉ mất *liên kết* tới tiêu chí, nội
dung vẫn còn và trở thành ghi chú chung của hồ sơ.

---

## 4. Quyền và audit

| Kiểm | Kết quả |
| --- | --- |
| ACL hai bảng | `postgres` và `service_role` — **không** có `anon`/`authenticated` (đúng posture của repo) |
| Trigger trên `applications` | Chỉ `trg_applications_updated_at` — không có trigger lạ |

Việc gán người phụ trách **có** ghi audit: `applications.py` chèn
`ASSIGN_APPLICATION` vào `audit_events` cùng transaction. Kiểm quyền cũng chặt:
tự nhận hồ sơ thì cần `update_status`; giao cho người khác thì cần `HR_LEAD`/
`ADMIN` **và** người nhận phải là HR của đúng vị trí đó.

---

## 5. Deploy sau khi áp

```bash
cd /home/ubuntu/hra
bash scripts/deploy.sh --branch arena/ea6e2570-vinit-hrapp --migrations-verified
```

Sau khi lên, kiểm ba trang từng bị ảnh hưởng:

1. **Danh sách ứng viên** của một vị trí — phải tải được, không 500.
2. **Chi tiết một hồ sơ** — có mục ghi chú HR.
3. **Nút nhận/giao hồ sơ** — giao cho một HR khác trong cùng vị trí.
