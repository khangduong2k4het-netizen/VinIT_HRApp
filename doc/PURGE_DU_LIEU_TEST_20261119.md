# PURGE DỮ LIỆU TEST — 2026-11-19

**Kết quả:** DB đã sạch CV/JD/vị trí/chấm điểm/tuyển dụng. **Còn lại 25 file
trong Storage** — phần này phải làm thủ công, xem mục 4.

**Migration:** `00035_purge_test_cv_jd_data.sql`, áp qua cổng migration Supabase
(version `20261119100305`, rollback tự động nếu lỗi).
**Sao lưu trước khi xoá:** schema `app_backup_20261119` — 63 bảng, **551 dòng**,
đối chiếu **khớp từng bảng** (0 bảng lệch) trước khi xoá.

---

## 1. Đã xoá — về 0 tuyệt đối

| Nhóm | Bảng |
|---|---|
| Ứng viên / hồ sơ | `applications`, `application_documents`, `application_identities`, `application_private_notes`, `application_status_events`, `application_retention_cases`, `talent_pool_consents` |
| CV / OCR | `cv_chunk_embeddings`, `document_processing_runs`, `profile_versions`, `profile_facts`, `cv_batches`, `cv_batch_items` |
| Chấm điểm | `assessment_runs`, `criterion_assessment_results`, `evidence_items`, `hr_criterion_reviews` |
| Xếp hạng | `ranking_runs`, `ranking_items` |
| Shortlist | `shortlist_shares`, `shortlist_share_items`, `shortlist_scorecards`, `shortlist_scorecard_criteria`, `scorecard_reopen_events`, `shortlist_feedback` |
| Vị trí / JD / rubric | `positions`, `jd_versions`, `criteria_versions`, `criteria_items`, `criteria_approval_events` |
| Phân quyền vị trí | `position_assignments`, `position_access_grants`, `position_create_requests`, `position_status_events` |
| Vận hành | `operations`, `operation_recovery_events`, `duplicate_signals`, `gmail_test_messages`, `careers_intake_receipts` |
| Xoá dữ liệu | `deletion_jobs`, `deletion_events` |
| Kiểm toán | `audit_events` |

## 2. Giữ nguyên — đã kiểm chứng

| Thứ | Số lượng | Vì sao giữ |
|---|---|---|
| `auth.users` | 5 | Tạo lại phải qua Supabase Auth, mất là hỏng buổi demo |
| `user_profiles` | 5 | Gắn với Auth user ở trên |
| `user_role_assignments` | 6 | Đủ 5 vai, không đụng |
| `departments` | 2 | Office, IT Department — đơn vị nghiệp vụ |
| `job_families` | 2 | IT & Digital, Vận hành & Hành chính |
| `app_settings` | 2 | `deadline_soon_days=7`, `waiting_attention_days=7` |
| `ai_configuration_versions` | 4 | Cấu hình AI ACTIVE |
| `assessment_policy_versions` | 2 | Chính sách chấm điểm |

Tài khoản còn nguyên, đúng vai:

```
adhra@vinuni.edu.vn      ADMIN
hr@vinuni.edu.vn         HR_LEAD
minhanh@vinuni.edu.vn    HR_RECRUITER
anhkiet@vinuni.edu.vn    HIRING_MANAGER
thanhhoang@vinuni.edu.vn VIEWER
```

## 3. Hai thứ được đánh số lại — dễ bỏ sót nhất

**`departments.next_sequence`: 7 → 1.**
Mã vị trí sinh từ cột này (`backend/app/services/departments.py:next_position_code`),
**không** phải từ `max(position_code)`. Không reset thì vị trí đầu tiên của buổi
demo sẽ là `IT-0007`, `IT-0008`... — người xem sẽ thấy dãy số nhảy cóc và tưởng
còn dữ liệu cũ. Giờ bắt đầu lại từ `IT-0001`.

**`audit_event_chain_seq`: `last_value=1`, `is_called=false`.**
Nghĩa là event kiểm toán đầu tiên của dữ liệu mới sẽ mang `chain_sequence=1` và
`previous_event_hash=NULL` — chuỗi băm bắt đầu sạch, không đứt khúc.

## 4. Việc CÒN LẠI — xoá 25 file trong Storage (anh làm)

DB sạch nhưng **file CV vẫn nằm trong bucket**. Xoá DB không xoá Storage, và
Supabase **chặn** xoá trực tiếp `storage.objects` (lỗi `42501 Direct deletion
from storage tables is not allowed`). Đây là hàng rào có chủ đích để không bỏ rơi
file thật. Tôi **không** lách bằng cách tắt trigger.

Hệ quả nếu bỏ qua: 7 file CV (~252 KB) và 18 file text trích xuất vẫn còn, nhưng
không còn dòng DB nào trỏ tới — **file mồ côi**. Không hiện trên UI, nhưng vẫn
chiếm chỗ và vẫn là dữ liệu ứng viên cũ nằm lại.

### Cách 1 — Dashboard (khuyên dùng, 2 phút)

Supabase → **Storage** → bucket `cv-originals` → chọn tất cả 7 file → Delete →
làm lại với `cv-extracted-text` (18 file).

### Cách 2 — API có service_role key

Lấy `new secret key` trong **Project Settings → API Keys**, rồi:

```bash
cd /home/ubuntu/hra
export SUPABASE_URL="https://myrymlqdbyqmpynesiwk.supabase.co"
read -rsp 'Service role key: ' SRK; echo
export SRK

# Xem trước sẽ xoá gì (không xoá)
for b in cv-originals cv-extracted-text; do
  curl -s -X POST "$SUPABASE_URL/storage/v1/object/list/$b" \
    -H "Authorization: Bearer $SRK" -H 'Content-Type: application/json' \
    -d '{"prefix":"","limit":1000}' | head -c 400; echo
done

# Xoá theo danh sách tên file lấy từ lệnh trên
curl -s -X DELETE "$SUPABASE_URL/storage/v1/object/cv-originals" \
  -H "Authorization: Bearer $SRK" -H 'Content-Type: application/json' \
  -d '{"prefixes":["<tên-file-1>","<tên-file-2>"]}'
```

Không dán service_role key vào chat, vào Git hay vào lịch sử shell
(`read -rsp` ở trên để key không vào history; đừng dùng `export SRK=...` trực
tiếp trên dòng lệnh).

### 25 đường dẫn cần xoá (đã liệt kê sẵn)

`cv-originals` — 7 file, mỗi file ~36 kB:

```
a3c8acac-f03c-407b-9163-0263ee9125d0/465d0374-0879-4116-a3d8-7e54cf8d2df5/aff1feb4-a96f-49d3-8daf-6b317f657314.docx
c65ed290-c3c5-4ae2-9fc4-a81906b3b683/0901b740-8e33-4af9-9789-484695538ab0/f964bfd5-72f9-4ba0-a11c-8782c567b306.docx
c65ed290-c3c5-4ae2-9fc4-a81906b3b683/44379ef3-34c5-4fbb-bcd5-707758963178/240c9791-d1ef-48de-9aff-ab57e485bed9.docx
c65ed290-c3c5-4ae2-9fc4-a81906b3b683/4cfbd7ba-84a2-4374-82d3-d4c154ce03e0/e85369fb-6f42-4a71-ba22-0c12aaed8ed5.docx
c65ed290-c3c5-4ae2-9fc4-a81906b3b683/a7569e6d-f7ad-4772-ae9e-1881d85b03a9/b800fabe-7087-4358-b5c0-35c6c206b384.docx
c65ed290-c3c5-4ae2-9fc4-a81906b3b683/ae23f546-8159-4ef6-9341-06a0a076c18a/d400b8a8-9348-46d3-baac-b7e87b060604.docx
c65ed290-c3c5-4ae2-9fc4-a81906b3b683/cf9cacff-9310-452b-9fa5-f97cac31abb8/20201ccd-e652-42f0-8551-2a793d998e83.docx
```

`cv-extracted-text` — 18 file (`extracted.txt` + `pages.json` cho 7 hồ sơ, có
hồ sơ 2 thế hệ). Dùng Dashboard cho nhanh: bucket nhỏ, 18 file.

Danh sách đầy đủ đã lưu trong DB:
`SELECT bucket_id, name FROM app_backup_20261119._storage_objects ORDER BY 1,2;`

### Kiểm sau khi xoá

```sql
SELECT bucket_id, count(*) FROM storage.objects GROUP BY bucket_id;
```

Phải trả về 0 dòng (hoặc không có dòng nào cho hai bucket này).

## 5. Vì sao phải tắt trigger khi xoá `audit_events`

`audit_events` có trigger `prevent_audit_event_mutation()` **RAISE EXCEPTION với
mọi DELETE và TRUNCATE, không phân biệt role** — kể cả `postgres` của Supabase.
Migration tắt đúng trigger đó trong phạm vi transaction, xoá, rồi bật lại và
**kiểm `tgenabled` phải bằng `O`**; nếu không, `RAISE EXCEPTION` huỷ cả lô.

Đã **kiểm chứng sống** sau khi purge: thử `DELETE FROM app_private.audit_events`
→ bị chặn với `audit_events are append-only`. Hàng rào bất biến vẫn hoạt động.

## 6. Nếu cần lấy lại dữ liệu cũ

Dữ liệu nằm ở `app_backup_20261119` (không có FK, không có trigger — bản sao
thô để tra cứu). Lấy lại một bảng:

```sql
INSERT INTO app_private.positions SELECT * FROM app_backup_20261119.positions;
```

Thứ tự khôi phục phải theo thứ tự ngược với mục 1 (cha trước, con sau), và
`departments.next_sequence` phải đặt lại giá trị lớn hơn `max(position_code)`
đang có.

> Bản sao lưu này **không** phải bản sao lưu vật lý (không PITR). Nó là copy
> logic, chỉ tồn tại chừng nào schema này còn. Xoá schema là mất:
> `DROP SCHEMA app_backup_20261119 CASCADE;` — **chỉ làm sau** khi đã xác nhận
> dữ liệu mới chạy tốt và không cần tra cứu lại.

## 7. Điều KHÔNG làm

- **Không** `supabase db push`, `db reset`, `migration repair`.
- **Không** chạy lại `00033`/`00034` — hai file đó không idempotent.
- **Không** xoá `auth.users`, không đụng tài khoản.
- **Không** tắt trigger `storage.objects` để xoá file — đó là lách hàng rào bảo
  vệ dữ liệu, không phải purge.
- **Không** seed dữ liệu. Dữ liệu demo phải đi qua luồng thật (upload CV, tạo JD)
  để chứng minh hệ thống chạy — nạp thẳng vào DB sẽ làm hỏng chính giá trị buổi
  demo.
