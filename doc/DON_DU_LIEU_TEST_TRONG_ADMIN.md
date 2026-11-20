# DỌN DỮ LIỆU TEST TRONG /admin

**Vào:** `/admin` → tab **"Dọn dữ liệu test"** (chỉ ADMIN thấy và gọi được).

Thay cho việc chạy SQL tay mỗi lần cần reset. Tính năng này **không** thay thế
migration `00035` đã chạy — nó là công cụ để lặp lại việc đó bất cứ lúc nào.

---

## 1. Ba bước, không tắt được bước nào

| Bước | Làm gì | Vì sao bắt buộc |
|---|---|---|
| 1 | Chọn nhóm dữ liệu | Nhóm nào kéo theo nhóm nào được ghi ngay trên checkbox |
| 2 | **Đếm trước** | Nút xoá không bật trước khi ADMIN xem bảng số dòng sẽ mất |
| 3 | **Gõ chuỗi xác nhận** | Checkbox bị bấm theo quán tính; gõ `OK` thì phải đọc |

Bốn nhóm:

| Mã | Nhãn | Kéo theo |
|---|---|---|
| `CV` | Hồ sơ ứng viên và CV | không |
| `JD` | JD và rubric | **`POSITIONS` + `OPERATIONS` + `CV`** |
| `POSITIONS` | Vị trí tuyển dụng | **`JD` + `OPERATIONS` + `CV`** |
| `OPERATIONS` | Vận hành và kiểm toán | không |

**JD và vị trí không tách rời.** Cả hai chiều đều có khoá ngoại
(`criteria_versions → jd_versions` và `jd_versions → positions`), nên xoá một
bên luôn phải xoá bên kia.

**Xoá vị trí kéo theo cả CV.** Có 11 bảng tham chiếu `positions` với khoá ngoại
**không** CASCADE: `applications`, `assessment_runs`, `audit_events`,
`cv_batches`, `duplicate_signals`, `ranking_runs`, `ranking_items`,
`shortlist_shares`, `shortlist_share_items`, `careers_intake_receipts`,
`position_create_requests`. Còn một dòng trong số đó là PostgreSQL chặn
`DELETE FROM positions`. Vì vậy chọn `JD` hoặc `POSITIONS` tự mở rộng sang cả
bốn nhóm, và màn xác nhận hiện câu giải thích thay vì để FK báo lỗi sau khi bấm.
Có test đọc thẳng `supabase/migrations` để phát hiện bảng mới thêm sau này.

## 2. Cái gì KHÔNG bao giờ bị xoá

Hiện ngay trên màn hình trước khi bấm, kèm số dòng:

`user_profiles` · `user_role_assignments` · `departments` · `job_families` ·
`app_settings` · `ai_configuration_versions` · `ai_policy_versions` ·
`assessment_policy_versions` · `retention_policy_versions` · `auth.users`

Có **test ghim** ràng buộc này (`test_protected_tables_never_appear_in_delete_order`):
thêm bảng vào danh sách xoá mà quên bỏ khỏi danh sách bảo vệ thì test đỏ.

## 3. Hai chỗ được đánh số lại

Giống migration `00035`, và **cố ý**:

- `departments.next_sequence = 1` → vị trí mới bắt đầu từ `IT-0001`, không nhảy
  cóc theo dữ liệu đã xoá.
- `audit_event_chain_seq` restart về 1 → event kiểm toán đầu tiên của chuỗi mới
  có `chain_sequence=1`, `previous_event_hash=NULL`.

### 3.1. Bẫy: `RESTART WITH 1` một mình KHÔNG đủ

Cột `chain_sequence` có **DEFAULT `nextval(...)`** và trigger
`set_audit_event_hash()` **cũng gọi `nextval(...)`**. Một lần INSERT tiêu **hai**
số của sequence:

| Bước | `last_value` | `is_called` |
|---|---|---|
| trước restart | 2 | true |
| sau `RESTART WITH 1` | 1 | false |
| sau INSERT | 2 | true |
| `chain_sequence` của dòng mới | **2** | — |

Vậy dòng đầu tiên của chuỗi mới mang `chain_sequence = 2` dù đáng lẽ là 1 — chuỗi
đứt ngay từ dòng đầu. Đã gặp đúng lỗi này khi chạy thật ngày 2026-11-19.

Cách sửa: **`DROP DEFAULT` trên cột rồi mới `RESTART`**, để trigger là nguồn duy
nhất cấp số. Kiểm chứng: `RESTART` một mình → 2; `DROP DEFAULT` + `RESTART` → 1.
Có test ghim (`test_audit_sequence_drop_default_before_restart`).

Số nhảy cóc **không** làm hỏng kiểm tra toàn vẹn (`verify_audit_chain` bỏ qua
khoảng trống, chỉ so `previous_event_hash` với hash của dòng trước), nhưng nó làm
báo cáo sai và gây khó hiểu khi truy vết.

## 4. Nhật ký kiểm toán — điểm khó nhất

`audit_events` có trigger `prevent_audit_event_mutation()` chặn **mọi** DELETE và
UPDATE, **kể cả với role `postgres`** (không phải superuser trên Supabase).

Nghĩa là **không thể** vừa "xoá sạch audit" vừa "giữ log việc xoá" trong cùng
một lúc — xoá hết audit thì không còn dòng nào để ghi lại.

Cách xử lý: **xoá audit trước, rồi ghi một sự kiện `TEST_DATA_PURGE` sau khi
xoá**, và bắt buộc phải nằm trong transaction tường minh. Nếu bước xoá thất bại
ở bất kỳ bảng nào, transaction rollback — audit cũ còn nguyên, không có trạng
thái nửa vời.

Trigger được tắt trong transaction rồi **bật lại và kiểm `tgenabled = 'O'`**;
nếu không bật lại được thì `RAISE EXCEPTION` huỷ cả lô. Có test ghim thứ tự
`DISABLE` → xoá → `ENABLE` → `RESTART SEQUENCE` → `INSERT audit`.

## 5. Storage — phần dễ hỏng nhất

### 5.1. Dọn tự động, kể cả file mồ côi **cũ**

Vấn đề gốc: xoá dòng trong `application_documents` **không** xoá file trên
Storage. Nếu chỉ xoá theo đường dẫn đã biết thì mọi file mà DB "quên" sẽ nằm lại
vĩnh viễn — đúng 25 file mồ côi còn sót sau migration `00035`.

Giải pháp: **đối soát**, không chỉ xoá theo danh sách. Mỗi lần chạy:

1. Liệt kê **đệ quy** toàn bộ file trong `cv-originals` và `cv-extracted-text`.
2. So với tập đường dẫn mà DB **còn** trỏ tới.
3. Xoá phần dư.

Nhờ vậy lần purge **kế tiếp** sẽ tự dọn nốt 25 file mồ côi hiện tại — không cần
xoá tay trong dashboard Supabase nữa.

Ba chốt an toàn của bước đối soát:

| Chốt | Vì sao |
|---|---|
| Không chạy khi còn operation `PENDING`/`PROCESSING` | tránh xoá file vừa upload xong nhưng chưa kịp ghi dòng DB |
| Bỏ qua file tạo trong **15 phút** gần nhất | lá chắn cho upload đang chạy dở (có test ghim) |
| Không liệt kê được bucket → **không xoá gì** | thà còn rác hơn xoá nhầm; có test ghim |

Bước xem trước hiện luôn số file mồ côi, tách theo từng bucket.

### 5.2. Thứ tự thực thi

**thu thập đường dẫn → xoá DB → commit → xoá theo đường dẫn → đối soát toàn bucket**

Ba quyết định, mỗi cái vì một cách hỏng cụ thể:

1. **Thu thập đường dẫn TRƯỚC vòng DELETE.** `application_documents` bị xoá
   trong vòng lặp, nên đọc sau sẽ không còn dòng nào — file thành mồ côi vĩnh
   viễn, không ai biết đường dẫn để xoá.
2. **Xoá Storage SAU commit.** Nếu xoá file trước rồi commit thất bại, file đã
   mất mà dòng DB vẫn còn — tệ hơn là còn file mồ côi.
3. **Lỗi Storage không làm thao tác thất bại.** DB đã commit; API trả
   `storage_error` riêng và giao diện hiện cảnh báo vàng kèm hướng dẫn xoá tay.
   Im lặng thì ADMIN tưởng đã sạch.

Cột lưu path text trích xuất là `extracted_text_storage_path` — **không phải**
`storage_path` hay `extracted_text_path`. Đã đối chiếu `information_schema`; đừng
đổi lại theo trí nhớ.

## 6. Đo lường an toàn

| Kiểm | Cách | Kết quả |
|---|---|---|
| 42 bảng trong danh sách xoá có thật | đối chiếu `information_schema` trên Supabase | **42/42**, 0 thiếu |
| Không bảng con nào bị bỏ sót gây FK chặn | truy vấn `pg_constraint` cho mọi FK `NO ACTION`/`RESTRICT` trỏ tới 8 bảng cha | **0 dòng** |
| Route được bảo vệ | `GET /v1/admin/test-data/scopes` không token | **401** |
| Không có đường vòng qua POST | `POST /v1/admin/test-data/execute` token giả | **401** |
| Thứ tự FK đúng | 23 unit test, có test ghim 3 cặp từng gây lỗi | **23/23** |
| Test có giá trị thật | đảo thứ tự `positions`/`audit_events` → test phải đỏ | **đỏ đúng test đó**, hoàn nguyên → xanh |
| Lá chắn 15 phút có tác dụng | đặt `MIN_AGE_SECONDS = 0` → test phải đỏ | **đỏ đúng test đó**, hoàn nguyên → xanh |
| Đối soát phân biệt file / thư mục | 10 test với Storage giả (list một cấp, tự đi xuống) | **10/10** |

**Lần chạy thật đầu tiên (2026-11-19 13:35 UTC, ADMIN trên VPS):**

| Kiểm | Kết quả |
|---|---|
| DB trước khi xoá | 0 dòng trên toàn bộ phạm vi (đã purge bằng migration) |
| File mồ côi phát hiện | **25** (`cv-originals` 7/7, `cv-extracted-text` 18/18) |
| Kết quả | *"Đã dọn 25 file mồ côi trên Storage."* |
| Storage sau khi chạy | **0 object** trong cả 2 bucket (bucket còn nguyên) |
| DB sau khi chạy | 0 ở mọi bảng nghiệp vụ; 5 tài khoản / 6 role / 2 phòng ban / 2 app_settings / 4 AI config còn nguyên |
| Nhật ký kiểm toán | 1 dòng `TEST_DATA_PURGE`, metadata đủ 42 bảng |
| Sai lệch phát hiện | `chain_sequence = 2` thay vì 1 → tìm ra bẫy DEFAULT ở mục 3.1, đã sửa code và sửa lại dòng audit về 1 |

**Chưa chạy được:** e2e trình duyệt (`tests/test-data-purge-mock.e2e.cjs`). Sandbox
không tải được Chromium (`Failed to download Chrome for Testing`), và **toàn bộ**
e2e có sẵn cũng không chạy được vì lý do đó. Test đã viết xong và sẵn sàng; cần
chạy trên máy có Chromium:

```bash
cd frontend
HRA_E2E_BASE_URL=http://127.0.0.1:3005 \
HRA_E2E_CHROMIUM_EXECUTABLE=/path/to/chrome \
  node tests/test-data-purge-mock.e2e.cjs
```

## 7. Điều không làm

- **Không** thay thế retention workflow. Retention là nghiệp vụ (xoá một ứng viên
  theo chính sách, có case, có người xác nhận, có hạn). Công cụ này là **vận
  hành phát triển** — xoá hàng loạt dữ liệu test.
- **Không** chạy được trên môi trường không có bảng `audit_events`; bảng thiếu
  được báo trong `skipped_tables` chứ không im lặng.
- **Không** cho phép xoá khi worker đang chạy: trả **409** kèm số operation
  đang xử lý. Xoá giữa chừng làm worker ghi vào bảng vừa mất dòng.
- **Không** có "hoàn tác". Bản sao lưu logic chỉ có ở migration `00035`
  (schema `app_backup_20261119`); công cụ này không tạo bản sao lưu — nếu cần,
  `CREATE TABLE app_backup_<ngày>.<bảng> AS SELECT * FROM ...` trước khi bấm.
