# Migration `00037` — trạng thái `SUPERSEDED` cho bộ tiêu chí

> **✅ ĐÃ ÁP ngày 2026-11-20** trên project `myrymlqdbyqmpynesiwk`:
> version remote `20261120093000` (`criteria_superseded_status_00037`).
> Hậu kiểm đạt (xem mục 3). **Không chạy lại.**

---

## 0. Vì sao phải áp trước khi deploy

Code duyệt tiêu chí (`criteria.py`) hạ bộ `APPROVED` cũ về `'SUPERSEDED'`.
Chuỗi đó **chưa có** trong `CHECK` constraint, nên nếu deploy trước khi áp
migration thì mọi lần duyệt một bộ mới sẽ lỗi:

```
new row for relation "criteria_versions" violates check constraint
"criteria_versions_status_check"
```

Nghĩa là **không duyệt được bộ tiêu chí nào** cho bất kỳ vị trí nào. Đây không
phải lỗi hiếm gặp — đây là thao tác bắt buộc phải xong trước khi chấm CV.

## 1. Vì sao cần trạng thái mới

Trước `00037`, duyệt bộ mới **không** hạ bộ cũ. Hệ quả: một vị trí có thể có
hai bộ cùng `APPROVED` cho cùng một JD. Mỗi chỗ đọc tự chọn "bộ APPROVED mới
nhất" theo một kiểu khác nhau, và không ai trả lời được ứng viên cũ đã chấm
bằng bộ nào.

Không dùng lại `ARCHIVED` hay `REJECTED`:

| Trạng thái | Nghĩa | Có phải bộ bị thay thế? |
| --- | --- | --- |
| `REJECTED` | Người duyệt từ chối bộ này | Không — bộ đó có thể sai |
| `SUPERSEDED` | Đã duyệt, đã dùng, sau đó có bộ mới hơn | Đúng |

Gộp hai nghĩa vào một nhãn là mất đúng thứ tự cần truy khi có khiếu nại.

## 2. Áp

Idempotent (`DROP CONSTRAINT IF EXISTS`, `CREATE INDEX IF NOT EXISTS`) — chạy
lại không hỏng.

```bash
cd ~/hra
export $(grep -E '^DATABASE_URL=' backend/.env | xargs)
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 --single-transaction \
  -f supabase/migrations/00037_criteria_superseded_status.sql
```

Rồi ghi version:

```sql
INSERT INTO supabase_migrations.schema_migrations (version, name)
VALUES ('20261120093000', 'criteria_superseded_status_00037')
ON CONFLICT (version) DO NOTHING;
```

## 3. Hậu kiểm (đã chạy, kết quả đạt)

```sql
SELECT pg_get_constraintdef(oid) FROM pg_constraint
WHERE conname = 'criteria_versions_status_check';

SELECT indexname FROM pg_indexes
WHERE schemaname='app_private' AND indexname='criteria_versions_effective_idx';
```

| Kiểm | Kết quả thực tế |
| --- | --- |
| Constraint có `SUPERSEDED` | ✅ |
| Constraint vẫn có `REJECTED`, `APPROVED`, `PENDING_*`, `DRAFT` | ✅ |
| Index `criteria_versions_effective_idx` | ✅ |
| Dữ liệu không đổi (1 bộ `DRAFT`) | ✅ |
| Version trong `schema_migrations` | ✅ `20261120093000` |

## 4. Migration này **không** đụng dữ liệu

Chỉ `DROP CONSTRAINT`, `ADD CONSTRAINT`, `CREATE INDEX`, và một `COMMENT`.
Không `UPDATE`, không `DELETE`, không `INSERT` vào bảng nghiệp vụ. Không có
dòng nào bị đổi trạng thái — bộ `DRAFT` đang có giữ nguyên.
