# Checklist thực thi E2E staging Phase 1

> Tài liệu này biến runbook tổng quát tại [`E2E_STAGING.md`](E2E_STAGING.md) thành checklist thực thi từng bước. Chỉ chạy trên staging tách biệt với dữ liệu tổng hợp trong `staging/synthetic`. Việc chuẩn bị checklist và dữ liệu **không** đồng nghĩa E2E đã đạt; chỉ khi có bằng chứng chạy thật và ký duyệt mới được cập nhật Closure Review.

> Hạng mục này đang được lưu ở trạng thái chờ triển khai tại [`PENDING_DEPLOYMENT.md`](PENDING_DEPLOYMENT.md), mã DEP-01/DEP-02.

## 1. Bộ dữ liệu đi kèm

- Manifest: `staging/synthetic/manifest.json`
- CV nguồn dạng text: `staging/synthetic/candidates/*.txt`
- Script sinh DOCX để upload:

```bash
backend/.venv/bin/python backend/scripts/generate_staging_fixtures.py --check
backend/.venv/bin/python backend/scripts/generate_staging_fixtures.py
```

DOCX sinh ra nằm trong `staging/generated/` và đã được ignore khỏi Git. Không sửa manifest thành dữ liệu thật; mọi email phải giữ miền `example.test`, số điện thoại phải là số tổng hợp chứa `000`.

Bộ dữ liệu này là **smoke/E2E fixture**, không phải HR golden set để đo chất lượng matching/BGE/LTR. Không dùng kỳ vọng trong manifest để tuyên bố accuracy production.

## 2. Vai trò thực hiện

| Vai trò | Người thực hiện | Việc chính |
|---|---|---|
| Điều phối staging | DevOps/IT | Dựng môi trường, deploy commit, ghi migration versions, cấp quyền tạm thời |
| Admin staging | Admin được chỉ định | Kiểm tra Admin APIs, audit verify, LTR governance nếu thuộc vòng chạy |
| HR Lead | HR Lead staging | Dual approval, xác nhận/thực thi retention từng case |
| HR Recruiter | HR staging | Tạo position/JD/criteria, upload CV, chạy assessment/ranking, shortlist |
| Hiring Manager | HM staging | Phê duyệt criteria, xem shortlist đúng quyền, gửi feedback |
| Người ghi bằng chứng | Điều phối hoặc QA | Điền bảng kết quả, đính kèm log/screenshot đã che dữ liệu nhạy cảm |

Không ghi mật khẩu, API key, access token hoặc service-role key vào checklist/báo cáo. Mật khẩu tài khoản staging lưu trong password manager của đội.

## 3. Preflight trước khi chạy

Đánh dấu từng mục trước khi bắt đầu:

- [ ] Ghi commit SHA của backend/frontend sẽ test: `________________`
- [ ] Ghi URL staging và xác nhận không phải production: `________________`
- [ ] Database staging đã áp migration theo thứ tự; ghi version thực tế, bắt buộc có `00012_retention_audit_integrity` nếu test retention/audit: `________________`
- [ ] Supabase project staging là project riêng hoặc đã được phê duyệt dùng cho dữ liệu tổng hợp: `________________`
- [ ] Storage buckets `cv-originals`, `cv-extracted-text` là private trên staging.
- [ ] Đã tạo các tài khoản trong manifest: Admin, HR Lead, HR Recruiter, Hiring Manager, Outsider.
- [ ] Backend staging dùng code chứa Batch 5 (`cce75b5` hoặc mới hơn) cho API `/v1/retention` và `/v1/admin/audit/verify`.
- [ ] `LTR_MODE=OFF` cho vòng E2E chức năng đầu tiên.
- [ ] Đã khóa phân loại `CRITICAL`/`CORE_FUNCTIONAL`/`CONDITIONAL` ở Mục 5.1 và phạm vi được phép `N/A` trước khi chạy.
- [ ] Nếu chưa có phê duyệt privacy/egress: LLM dùng endpoint local/mock đã được phép trong staging; semantic dùng `OFF` hoặc provider `hash` non-BGE cho smoke plumbing; không gửi CV thật ra ngoài.
- [ ] Log của API/worker trong thời gian test được kiểm tra để bảo đảm không có CV text, prompt đầy đủ, API key hoặc access token.

## 4. Chuẩn bị dữ liệu trong ứng dụng

1. Sinh DOCX từ bộ fixture bằng script ở mục 1.
2. Đăng nhập Admin/HR Lead; tạo department `Synthetic Engineering` theo manifest nếu staging chưa có.
3. HR Recruiter tạo position `backend_open` theo JD/criteria trong manifest; gán:
   - HR Recruiter: `HR_RECRUITER`
   - Hiring Manager: `HIRING_MANAGER`
   - Outsider: không gán
4. Tạo criteria `python_backend`, `postgresql`, `docker` đúng category/trọng số trong manifest; thực hiện HR approve và HM approve bằng hai tài khoản khác nhau.
5. Upload các DOCX của `backend_open`: strong, partial, java only, Vietnamese, duplicate A/B. Không upload vào position production hoặc position chứa dữ liệu thật.
6. Tạo position `retention_due` và `retention_not_due` trên staging; upload candidate tương ứng.
   - Với `retention_not_due`: đóng position ở thời điểm hiện tại.
   - Với `retention_due`: chỉ trên database staging tách biệt và có ticket phê duyệt, điều phối mới được đặt `positions.closed_at` lùi 13 tháng sau khi position đã đóng để mô phỏng hết hạn. Ghi operator, thời gian và ticket vào bằng chứng. Tuyệt đối không làm việc này trên production/project chứa dữ liệu thật.
7. Nếu test OCR: dùng `ocr_simulated.txt` để tạo PDF scan/image-only ngoài Git bằng công cụ staging đã được phê duyệt; ghi rõ công cụ và độ phân giải. File text không tự chứng minh OCR đạt.

## 5. Kịch bản thực thi

Điền `PASS`/`FAIL`, người chạy, thời gian và liên kết bằng chứng cho từng dòng.

| ID | Kịch bản | Các bước chính | Kỳ vọng | Kết quả/Bằng chứng |
|---|---|---|---|---|
| E2E-01 | Auth/RBAC position scope | Đăng nhập từng user; mở danh sách/chi tiết `backend_open`; thử bằng Outsider | Chỉ user được gán mới thấy position/application; Outsider bị từ chối hoặc không thấy dữ liệu | PASS — người vận hành xác nhận 11/11/2026 (Mục 5.3): đăng nhập các vai trò đạt, chỉ user được gán thấy position/application, Outsider bị từ chối |
| E2E-02 | Admin surfaces | Gọi `/v1/admin/semantic/health`, `/v1/admin/ltr/models`, `/v1/admin/worker/health` bằng non-admin và Admin | Non-admin 403; Admin 200; health không lộ endpoint/API key/CV text |  |
| E2E-03 | JD/criteria dual approval | Sửa criteria sau APPROVED; thử approve trùng vai trò | Bản APPROVED bị khóa; HR/HM khác nhau mới hoàn tất dual approval |  |
| E2E-04 | Upload + profile | Upload DOCX strong/partial/java/Vietnamese; mở profile từng application | File hợp lệ được xử lý; profile facts truy vết về document; sửa profile tạo version mới, không trộn assessment cũ |  |
| E2E-05 | Matching theo kỳ vọng manifest | Chạy assessment cho `backend_open`; đối chiếu từng criterion | Strong/partial/java/Vietnamese khớp kỳ vọng tương đối trong manifest; UNCLEAR không bị tính như NO_MATCH trong score; quote mở đúng nguồn | PASS — retest dữ liệu 11/11/2026 04:50–04:51 UTC (rules v1.4): 6/6 COMPLETED; strong `STRONG/STRONG/STRONG` 100.0, vietnamese `STRONG/MATCH/MATCH` 88.4, duplicate_a Python `MATCH` theo deterministic years rule (5 năm), duplicate_b Python `UNCLEAR` (CV không ghi số năm), partial Python/Docker `UNCLEAR`, java_only 3×`UNCLEAR`. UNCLEAR không bị tính như NO_MATCH. Quote mở đúng nguồn trên UI: PASS, người vận hành xác nhận 11/11/2026. DM-02 đã đóng (Mục 5.2) |
| E2E-06 | Scoring `matching-v2.1` | Kiểm tra case partial có Docker UNCLEAR | Score chỉ tính trên tiêu chí đã scored; coverage giảm; giao diện/API hiển thị nhu cầu HR xác minh khi coverage thấp | PASS (11/11/2026): partial_backend Docker `UNCLEAR` → score 80.0 chỉ tính trên PostgreSQL đã resolved, coverage 0.28, trạng thái `NEEDS_HR_VERIFICATION`. Từ commit `40e5e21`, danh sách ứng viên hiển thị điểm này kèm nhãn “một phần” và chi tiết từng tiêu chí khi mở rộng dòng |
| E2E-07 | Ranking | Chạy ranking cho `backend_open` | Ranking tôn trọng mandatory status trước score/coverage; snapshot truy vết được assessment/profile/criteria versions | PASS (phần dữ liệu, cập nhật retest 11/11/2026 04:51 UTC): ranking run `5a9700f5-9f87-4861-a6a5-bf51d24f0789` COMPLETED; hạng 1 strong_backend 100.0/coverage 1.00, hạng 2 vietnamese_backend 88.4/1.00, hạng 3 duplicate_a 80.0/0.70 (đủ tiêu chí bắt buộc, Docker ưu tiên chưa rõ nên điểm là điểm một phần); 3 hồ sơ `NEEDS_HR_VERIFICATION` không có `rank_number` |
| E2E-08 | Duplicate signal | Đối chiếu duplicate A/B | Có tín hiệu trùng theo email/phone nếu hệ thống ghi nhận; không tự merge, không tự xóa hồ sơ | PASS (phần dữ liệu, 11/11/2026): đúng 1 tín hiệu `EMAIL_MATCH` duplicate_a↔duplicate_b (`d4cca4e3-43f3-4cb4-87a9-e6535aeed3ed`, confidence 0.98, `PENDING`); chạy lại assessment không sinh thêm tín hiệu; không tự merge/xóa, cả 2 hồ sơ còn nguyên |
| E2E-09 | Shortlist/feedback/revoke | HR chia sẻ strong cho HM với `allow_cv_view=false`, HM feedback, HR revoke | HM chỉ thấy dữ liệu được chia sẻ; không tải CV khi không có quyền; sau revoke HM mất truy cập | PASS — người vận hành xác nhận UI chia sẻ/feedback hoạt động, HM không xem/tải CV và không còn thấy shortlist sau thu hồi. Script `2f84782` chỉ tiếp tục thu hồi khi HM xem được share/hồ sơ chia sẻ nhưng không lấy được link CV hay đọc hồ sơ khác; HR revoke HTTP 200, HM nhận 403 khi đọc share, hồ sơ và link CV sau thu hồi. DB xác nhận share `c790ccb5-2122-4f7d-8176-47d4fe3907bc` REVOKED 2026-11-11 08:38:01 UTC, `allow_cv_view=false`, 1 item, 1 feedback HM, 1 audit revoke; IT-0004 còn 6 hồ sơ |
| E2E-10 | Audit verify | Non-admin rồi Admin gọi `GET /v1/admin/audit/verify` | Non-admin 403; Admin trả `valid=true`. Nếu `false`: dừng, không sửa audit rows, mở defect | PASS — người vận hành chạy lại sau đổi mật khẩu: HR Recruiter HTTP 403, Admin HTTP 200, `valid=true`, `checked_events=71`, `broken_events=0`; DB xác nhận Recruiter không còn buộc đổi mật khẩu và đăng nhập lại sau đổi mật khẩu. Lượt 403 trước đó không dùng làm bằng chứng RBAC |
| E2E-11 | Retention chưa đến hạn | Generate case cho `retention_not_due` | `created_count=0`; không có case để confirm trước hạn | PASS — người vận hành chạy API: IT-0006 HTTP 200, `created_count=0`, due 2027-11-11 07:30 UTC; đối chiếu DB không có case cho vị trí này |
| E2E-12 | Retention đến hạn + phân quyền confirm | Generate cho `retention_due`; HR Recruiter thử confirm; HR Lead confirm | Có 1 case `is_due=true`; HR Recruiter không có grant bị 403; HR Lead confirm thành `SCHEDULED_FOR_DELETION` | PASS — IT-0005 generate HTTP 200, `created_count=1`, case `2d9407c8-deb6-4b3d-9bb1-92ce50afa2ea`, `is_due=true`; fixture được lùi `closed_at` 13 tháng. Sau đổi mật khẩu, HR Recruiter confirm HTTP 403; HR Lead confirm HTTP 200, `SCHEDULED_FOR_DELETION`. DB xác nhận HR Lead xác nhận 2026-11-11 08:16:47 UTC, job `PENDING`; lượt 403 trước đổi mật khẩu không dùng làm bằng chứng RBAC |
| E2E-13 | Retention execute + purge | HR Lead execute case ở E2E-12; kiểm tra application/file/audit | File gốc/extracted/pages bị xóa; profile/assessment/evidence/ranking/shortlist/embeddings/notes bị purge hoặc unlink; bằng chứng còn lại chỉ có opaque ID/counts, không có PII | MỘT PHẦN — HR Lead execute HTTP 200 `DELETED`; DB case `DELETED`, application_id NULL, job `COMPLETED` 2026-11-11 08:19:46 UTC; 3 object đã xóa, độc lập kiểm tra storage còn 0 gốc và 0 extracted/pages, IT-0006 vẫn 1 application/1 document. DB kiểm tra application, document, processing run, profile, assessment, ranking, identity, note, shortlist, embedding, batch link đều 0; batch item đã unlink và filename `[DELETED]`. Summary ghi nhận trước xóa 1 document/run/profile/assessment/criterion/evidence/ranking, 5 facts, 1 identity và 1 batch item. Có event generate/confirm/execute và deletion event COMPLETED; hash-chain SQL sau xóa 73 events, 0 broken (không nhầm với API verify trước xóa). Chưa chứng minh purge các loại vốn có count 0 trước xóa, gồm shortlist, embeddings, notes; cần fixture có dữ liệu hoặc quyết định phạm vi, chưa ký PASS toàn kịch bản |
| E2E-14 | OCR scan | Upload PDF scan tạo từ fixture OCR; kiểm tra extracted text/profile | OCR có kết quả hoặc lỗi rõ ràng; quote/page được HR kiểm chứng thủ công; không tuyên bố chất lượng OCR chỉ từ fixture text |  |
| E2E-15 | Semantic/BGE smoke (nếu thuộc vòng) | Bật cấu hình BGE đã duyệt; kiểm tra semantic health và embeddings | Không ở `MISCONFIGURED`; có diagnostics/cache hợp lý; semantic chỉ bổ sung candidate chunks, không tự đổi rule outcome |  |
| E2E-16 | Worker recovery (nếu môi trường cho phép) | Tạo job tổng hợp, restart worker/API theo quy trình staging, theo dõi job | Job phục hồi at-least-once hoặc fail rõ; không mất mát âm thầm; không tuyên bố exactly-once |  |

### 5.1. Phân loại kết quả và quy tắc dùng `N/A`

Trước khi chạy, Điều phối staging, HR Lead và Release owner phải khóa phạm vi
và phân loại dưới đây trong biên bản vòng chạy. Không đổi phân loại sau khi đã
thấy kết quả để biến FAIL thành `N/A`.

| Nhóm | Kịch bản | Quy tắc ký duyệt |
|---|---|---|
| `CRITICAL` | E2E-01, E2E-02, E2E-03, E2E-09, E2E-10, E2E-11, E2E-12, E2E-13 và kiểm tra log không lộ secret/CV text | Bất kỳ FAIL nào cũng chặn ký PASS toàn vòng. Không được `N/A`, không được bù bằng tỷ lệ các kịch bản khác. |
| `CORE_FUNCTIONAL` | E2E-04, E2E-05, E2E-06, E2E-07, E2E-08 | FAIL phải có defect ID, severity, owner và quyết định xử lý. Chỉ ký PASS khi đã sửa/retest hoặc phạm vi tương ứng được loại bỏ chính thức trước khi ký. |
| `CONDITIONAL` | E2E-14, E2E-15, E2E-16 | Chỉ được `N/A` nếu ngoài phạm vi đã khóa từ preflight và ghi lý do, người duyệt, hệ quả chưa được kiểm chứng. Nếu tính năng thuộc phạm vi công bố của vòng chạy thì xử lý như `CORE_FUNCTIONAL` hoặc `CRITICAL` theo tác động. |

Quy tắc bắt buộc:

- Mỗi kịch bản phải có đúng một kết quả `PASS`, `FAIL` hoặc `N/A` hợp lệ; không để trống.
- Không dùng tỷ lệ kiểu “15/16 PASS” để ký toàn vòng nếu kịch bản FAIL thuộc `CRITICAL`.
- Mọi FAIL phải ghi defect ID, mức độ, bước tái hiện, owner, hạn xử lý và quyết định: sửa/retest, chặn phát hành hoặc chấp nhận rủi ro bởi người có thẩm quyền.
- `N/A` cho E2E-15 không được hiểu là BGE đã đạt; `N/A` cho E2E-14 không được hiểu là OCR production đã đạt; `N/A` cho E2E-16 không được hiểu là worker recovery đã được chứng minh.

### 5.2. Defect log

| Defect | Mức độ | Owner | Triệu chứng & gốc rễ | Quyết định / trạng thái |
|---|---|---|---|---|
| DM-02 | Major (`CORE_FUNCTIONAL`, chặn ký E2E-05) | Dev backend | Python của duplicate_a rơi xuống LLM trả `UNCLEAR` dù CV khai 5 năm; strong/vietnamese chỉ `MATCH` thay vì `STRONG_MATCH`. Gốc rễ: (1) spec lưu trên criterion giữ `kind=SKILL, min_years=null` nên cổng “ít nhất 4 năm” trong mô tả không qua years rule; (2) FastAPI/Django/Flask bị tính là 3 term group riêng dù là bằng chứng thay thế (cùng lớp lỗi DM-01), chặn coverage 0.8; (3) số năm tiếng Việt (“5 năm”) không được nhận vì regex chạy trên text chưa bỏ dấu | Đã sửa ở `deterministic-rules-v1.4` (commit `c370250`): SKILL có `min_years` vẫn qua years gate (số năm thiếu/không đủ tin cậy → unresolved, không skill-MATCH, không NO_MATCH từ mảnh rời); gộp framework Python thành 1 concept; bỏ dấu trước khi parse số năm. Regression test trong `test_deterministic_matching.py`, CI `42959048412` đạt 3 job. Retest production 11/11/2026 04:50–04:51 UTC đạt: strong `STRONG_MATCH` (6 năm), vietnamese `STRONG_MATCH` (5 năm + phủ đủ skill), duplicate_a `MATCH` theo years rule, duplicate_b/partial/java_only giữ `UNCLEAR` đúng chính sách → **ĐÓNG DM-02**. Lệch manifest còn lại (duplicate_a kỳ vọng STRONG, duplicate_b kỳ vọng MATCH nhưng giữ `UNCLEAR` theo chuẩn 4 năm, partial PostgreSQL kỳ vọng STRONG): người vận hành đã chấp nhận là known variance ngày 11/11/2026, không chặn phát hành |

### 5.3. Xác nhận bổ sung của người vận hành (11/11/2026)

Người vận hành môi trường test xác nhận PASS cho các nội dung kiểm thủ công sau;
phần đối chiếu dữ liệu tương ứng đã được kiểm chứng độc lập qua Supabase,
phần thao tác UI dựa trên xác nhận này:

- Quote bằng chứng trong hồ sơ chi tiết mở đúng nguồn CV (bổ sung cho E2E-05).
- Phân quyền theo vai trò: đăng nhập các vai trò, phạm vi thấy dữ liệu theo
  gán vị trí, Outsider bị từ chối (E2E-01).
- Luồng mật khẩu: đăng nhập/đổi mật khẩu của các tài khoản kiểm thử hoạt động
  đúng (không có kịch bản riêng trong bảng Mục 5; ghi nhận tại đây).

Chấp nhận rủi ro đã ghi: 3 lệch manifest ở Mục 5.2 là known variance không
chặn phát hành. Bảng ký duyệt vòng E2E ở Mục 7 vẫn để trống — việc ghi PASS
từng mục tại vòng này không thay cho chữ ký chính thức của các vai trò.

## 6. Mẫu bằng chứng cần nộp

Sau khi chạy, đính kèm hoặc liên kết:

- Commit SHA, URL staging, migration versions thực tế.
- Bảng kịch bản ở mục 5 đã điền PASS/FAIL.
- Screenshot/log đã che email/token/API key/CV text ngoài dữ liệu tổng hợp.
- Provider/model LLM/BGE đã dùng (không ghi secret), hoặc ghi rõ đã dùng mock/local.
- Kết quả `GET /v1/admin/audit/verify` từ Admin staging.
- Với retention: case ID, trạng thái trước/sau, deletion job status, audit verify sau execute. Không đính kèm CV thật.
- Danh sách defect cho mọi `FAIL`: defect ID, mức độ, bước tái hiện, log liên quan, người phụ trách, hạn xử lý, quyết định chặn hay chấp nhận rủi ro và người có thẩm quyền ký quyết định.

## 7. Điều kiện ký duyệt vòng E2E

Chỉ ký PASS vòng staging khi:

- Không còn FAIL thuộc nhóm `CRITICAL`; không dùng tỷ lệ PASS của các kịch bản khác để bù.
- Mọi FAIL thuộc nhóm còn lại đã có defect ID, severity, owner và quyết định xử lý; mọi `N/A` đã được khóa từ preflight theo Mục 5.1.
- Không có rò rỉ position scope, CV hoặc assessment evidence ngoài quyền.
- Không có UNCLEAR bị tính như NO_MATCH trong status/score.
- Không có quote không hợp lệ được tính điểm.
- Retention chưa đến hạn bị chặn; retention đến hạn chỉ xóa sau confirm + execute thủ công từng case.
- Audit verify trả `valid=true`, hoặc defect integrity được mở và chặn phát hành.
- Log kiểm tra không chứa API key, access token, prompt đầy đủ hoặc CV text thật.

Quyết định đóng DEP-01 ở phạm vi rút gọn (11/11/2026):

- Phạm vi được ký đóng: E2E-01, E2E-05, E2E-06, E2E-07, E2E-08 đều PASS
  (bằng chứng ở Mục 5, 5.2, 5.3); DM-01/DM-02 đã đóng.
- Phạm vi chính thức loại khỏi vòng DEP-01 và chuyển gate sau (không được
  hiểu là đã đạt): E2E-02, E2E-03, E2E-04, E2E-09 chuyển vòng kiểm chứng
  tiếp theo; E2E-10, E2E-11, E2E-12, E2E-13 thuộc DEP-02 (retention/audit)
  và ký riêng; E2E-14, E2E-15, E2E-16 là `CONDITIONAL` ngoài phạm vi vòng
  này theo Mục 5.1.
- Việc đóng rút gọn này do người vận hành/điều phối quyết định ngày
  11/11/2026; các vai trò còn lại ký bổ sung sau, không đổi kết quả từng mục.

Ký duyệt:

| Vai trò | Họ tên | Kết luận | Ngày |
|---|---|---|---|
| Điều phối staging | Người vận hành môi trường test (xác nhận trong phiên làm việc) | PASS ở phạm vi rút gọn nêu trên | 11/11/2026 |
| HR Lead |  | PASS / FAIL |  |
| Hiring Manager |  | PASS / FAIL |  |
| Admin/IT Security (nếu có dùng model thật) |  | PASS / FAIL / N/A |  |

## 8. Dọn dẹp sau test

- Xóa hoặc reset dữ liệu staging theo quy trình của môi trường; ưu tiên dùng retention workflow cho application tổng hợp đã đến hạn khi cần kiểm chứng purge.
- Thu hồi tài khoản/grant tạm thời không còn dùng.
- Không sao chép DOCX sinh ra, log hoặc screenshot chứa dữ liệu staging sang production.
- Cập nhật kết quả thật vào `audit/PHASE1_REVIEW_2026-11-07.md` và `Update_Excute_P1.md`; không cập nhật trạng thái PASS chỉ dựa trên checklist này.
