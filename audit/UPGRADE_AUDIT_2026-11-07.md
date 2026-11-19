# Audit toàn bộ nâng cấp Phase 1 — 2026-11-07

> Phạm vi: các nâng cấp sau review lần 2, từ commit nền `1326acd` tới mốc được audit `dc9d020` trên branch `arena/ea6e2570-vinit-hrapp`. Báo cáo này audit code/test/migration/tài liệu của các batch nâng cấp; không thay thế Phase 1 Closure Review tại `audit/PHASE1_REVIEW_2026-11-07.md` và không tự đóng các gate môi trường/dữ liệu thật.

## 1. Kết luận điều hành

- **Code và CI:** `PASS` trong phạm vi đã nâng cấp. Không phát hiện P0 làm sai lệch scoring, lộ API key qua diagnostics/retention summary hoặc cho phép xóa retention không qua confirm trong code đã audit.
- **Migration project đã kết nối:** `PASS` cho schema. Project `myrymlqdbyqmpynesiwk` đang `ACTIVE_HEALTHY`, đã có migration tới `20261107142027 retention_audit_integrity`; audit chain remote có 21 events, 0 broken, 0 missing hash tại thời điểm audit.
- **Triển khai/vận hành:** `PARTIAL/BLOCKED`. Backend/frontend đích chưa có bằng chứng deploy và E2E staging thật; legacy Supabase keys chưa đóng; privacy/egress và dữ liệu HR cho BGE/LTR chưa có.
- **Phase 1:** chưa đóng. Các hạng mục chờ được quản lý tại `doc/PENDING_DEPLOYMENT.md`.

## 2. Phương pháp và bằng chứng audit

| Kiểm tra | Cách thực hiện | Kết quả |
|---|---|---|
| Phạm vi diff | `git diff --stat 1326acd..HEAD`: 43 files, +4386/-36 tại mốc audit | Đã đối chiếu các file lõi theo batch |
| Code review | Đọc matching/config, semantic worker/diagnostics, LTR worker/Admin/register script, retention/audit service/API, migration `00011`/`00012`, CI và staging fixture | Xem mục 3–4 |
| Full backend local | PostgreSQL dùng một lần tại local, `pytest backend/tests -q` | **160 passed** |
| Ruff phạm vi CI | Các service/API/worker/scripts/tests thuộc bề mặt nâng cấp, `--select F` | Đạt |
| Staging fixture | `generate_staging_fixtures.py --check` | Đạt; manifest là `SYNTHETIC_ONLY` |
| GitHub CI | Run `42380974685` cho Batch 5, `42382329761` cho Batch 5.1, `42382451554` cho commit ghi nhật ký `dc9d020` | Cả 3 job đạt ở các run đã ghi |
| Supabase remote | Connector: list projects/migrations/health + SQL postflight chỉ đọc | Project `ACTIVE_HEALTHY`; migration tới `00012`; audit 21/21 có hash, 0 broken; 0 operation đang chạy; 0 approved LTR model |

## 3. Kết quả theo batch

| Batch | Nội dung audit | Kết luận | Nhận xét chính |
|---|---|---|---|
| 1 | `matching-v2.1`: UNCLEAR khỏi tử/mẫu score, coverage tách riêng; khóa LTR file artifact khi production ACTIVE | `PASS` ở code/test | Score không còn phạt UNCLEAR như NO_MATCH; low coverage vẫn bị gate. Artifact LTR train bằng score cũ không được coi là tương thích cho tới khi train/đánh giá lại. |
| 2 | Pgvector embedding cache theo document/chunk/text hash/model/index version; semantic diagnostics Admin | `PASS` ở code/test, `NOT TESTED` với BGE thật | Cache tránh embed lại chunk không đổi; diagnostics không trả endpoint/API key/CV text. Provider `hash` chỉ kiểm tra plumbing, không chứng minh chất lượng semantic. |
| 3 | LTR governance: canonical artifact SHA-256, register chống ghi đè, review events, Admin approve/reject, worker kiểm tra hash | `PASS` ở code/CI/remote schema, `PARTIAL` cho vận hành model | Remote chưa có approved LTR model (`approved_ltr_models=0`). Còn finding F-01 về legacy artifact thiếu hash trước khi xét ACTIVE. |
| 4 | RBAC matrix, GitHub CI 3 job, JUnit/annotation diagnostics, runbook E2E | `PASS` ở code/CI tự động, `PARTIAL` cho staging | Root cause integration do test harness làm mất `assessment-v2.0` đã được sửa và CI xanh. Branch protection và E2E staging thật vẫn là gate vận hành. |
| 5 | Retention workflow từng hồ sơ, storage-first purge, audit hash chain/append-only, Admin audit verify, migration `00012` | `PASS` ở code/test/CI/remote schema, `PARTIAL` cho staging | Đã test purge, RBAC confirm/execute, chưa đến hạn, lỗi storage không purge DB, tamper detection, case hủy được tạo lại. Chưa có bằng chứng qua backend staging + Supabase Storage thật. |
| 5.1 | Bộ dữ liệu tổng hợp và checklist E2E staging | `PASS` cho phần chuẩn bị, `NOT TESTED` cho thực thi | Fixture dùng `@example.test`, có validator chống dữ liệu ngoài miền tổng hợp. Expected outcomes là smoke expectation, không phải HR golden set; fixture OCR là text để tạo scan, không chứng minh OCR. |

## 4. Finding còn mở

### F-01 — Trung bình: Worker có thể nạp registry LTR ở ACTIVE nếu `artifact_sha256` bị trống

- **Bằng chứng code:** trong `_load_ltr_model`, worker chỉ từ chối khi stored hash tồn tại và không khớp (`if stored_hash and ...`). Một registry row legacy ở trạng thái `APPROVED` nhưng chưa có hash có thể qua bước này nếu các gate khác đạt.
- **Tác động hiện tại:** thấp trên project đã kết nối vì chưa có approved LTR model và `LTR_MODE` phải giữ `OFF`/`SHADOW`. Tác động tăng lên trước khi bật ACTIVE ở môi trường có registry cũ.
- **Khuyến nghị trước ACTIVE:** sửa worker để `ACTIVE` fail-closed khi thiếu `artifact_sha256`; hoặc re-register/re-approve artifact qua governance để luôn có hash. Ghi nhận tại DEP-07 trong `doc/PENDING_DEPLOYMENT.md`.
- **Cập nhật sau audit:** worker đã được sửa trên branch để `ACTIVE` từ chối registry artifact thiếu/rỗng `artifact_sha256` và vẫn từ chối hash không khớp; test bao phủ hash hợp lệ, hash không khớp và hash thiếu. Thay đổi này chưa tự đóng gate vận hành cho tới khi qua CI, được deploy và kiểm chứng ở môi trường đích.
- **Trạng thái:** `CODE FIXED — CHỜ CI/DEPLOY; VẪN CHẶN LTR ACTIVE TỚI KHI BẢN SỬA ĐƯỢC TRIỂN KHAI`.

### F-02 — Thấp/vận hành: Audit hash chain là tamper-evidence, không chống DB superuser

- Trigger chặn UPDATE/DELETE ở mức row và hash chain phát hiện sửa dữ liệu khi trigger bị bypass trong test. Tuy nhiên không có BEFORE TRUNCATE; DBA/superuser vẫn có thể disable trigger, truncate hoặc restore backup cũ.
- Tài liệu đã ghi giới hạn này trong migration, `DEPLOYMENT.md` và Closure Review.
- **Khuyến nghị:** tối thiểu hóa quyền DBA, kiểm tra `audit/verify` định kỳ, cân nhắc WORM/external log nếu pháp chế yêu cầu.
- **Trạng thái:** `ACCEPTED_LIMITATION` với kiểm soát vận hành.

### F-03 — Thấp/thiết kế: Retention API nhận `reason` nhưng không lưu free-text reason

- API confirm/cancel chấp nhận trường `reason` cho tương thích workflow nhưng service cố ý không lưu vào DB/audit để tránh vô tình ghi PII/định danh ứng viên. Audit vẫn có actor, thời gian, policy, opaque ID, trạng thái và counts.
- Nếu governance sau này yêu cầu lý do bắt buộc, nên dùng mã lý do có cấu trúc đã duyệt, không lưu free text.
- **Cập nhật sau audit:** schema API đã đánh dấu `reason` là trường tương thích deprecated, được chấp nhận nhưng cố ý bỏ qua và không bao giờ lưu; test schema khóa rõ hợp đồng này. Chưa áp dụng taxonomy `reason_code` khi Legal/HR chưa duyệt và không cho phép reason thay đổi điều kiện đến hạn/quyền thực thi.
- **Trạng thái:** `CONTRACT CLARIFIED IN CODE — TAXONOMY CHƯA ÁP DỤNG`, không chặn E2E dữ liệu tổng hợp.

### F-04 — Ngoài code: Schema remote đã đi trước bằng chứng deploy backend

- Migration `00011`/`00012` đã áp lên project đã kết nối, nhưng chưa có bằng chứng backend/frontend phục vụ project đó đang chạy commit đã audit. Schema cộng thêm giúp code cũ thường vẫn chạy, nhưng các workflow LTR governance/retention/audit verify chỉ tồn tại khi backend mới được deploy.
- **Khuyến nghị:** thực hiện DEP-01/DEP-03 trong tài liệu chờ triển khai, không tuyên bố workflow đã vận hành chỉ dựa trên migration.
- **Trạng thái:** `WAITING_DEPLOYMENT`.

### F-05 — Ngoài code: Chất lượng model và dữ liệu thật chưa được chứng minh

- BGE chưa có endpoint/golden set thật; LTR chưa có HR gold dataset, artifact approved hoặc SHADOW report. Không có bằng chứng để bật semantic production hoặc `LTR_MODE=ACTIVE`.
- **Trạng thái:** `BLOCKED` bởi DEP-05/DEP-06/DEP-07.

## 5. Kiểm tra bảo mật và toàn vẹn dữ liệu đã đạt

- Semantic diagnostics không trả API key, endpoint đầy đủ hoặc CV text; chỉ trả trạng thái/cấu hình tổng hợp và counters.
- Retention summary/audit metadata dùng opaque ID + counts; test xác nhận summary không chứa tên candidate hoặc quote tổng hợp nhạy cảm trong fixture.
- Local storage deletion có kiểm tra đường dẫn nằm trong bucket root; path traversal trong test làm job `FAILED` và không purge DB.
- Supabase Storage deletion đếm theo số object provider xác nhận đã xóa, lỗi provider được làm sạch trước khi lưu/trả.
- Purge DB đã đối chiếu các bảng có `application_id`: documents/processing, identities, notes, retention case theo `SET NULL`, status events, assessments/results/evidence qua cascade và thứ tự xóa, batch items được unlink/ẩn danh, embeddings, duplicate signals, ranking và shortlist artifacts.
- Audit insert dùng advisory transaction lock + sequence để hạn chế fork hash chain; verify recompute cả linkage và hash.
- LTR approve/reject chỉ từ `DRAFT`, kiểm tra gates/hash, ghi review event và audit event; register script từ chối ghi đè cùng version bằng artifact khác.

## 6. Ý kiến audit

Các nâng cấp Batch 1–5 đạt mức **sẵn sàng để triển khai staging và nghiệm thu vận hành**, không đạt mức tuyên bố production/Phase 1 closure. Batch 5.1 đã sẵn sàng làm đầu vào chạy staging. Việc còn lại được chuyển thành danh sách chờ có chủ sở hữu và bằng chứng đóng tại `doc/PENDING_DEPLOYMENT.md`; chỉ cập nhật trạng thái Phase 1 sau khi có bằng chứng thật từ các DEP tương ứng.
