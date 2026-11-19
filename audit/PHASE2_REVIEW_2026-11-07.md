# Rà soát Phase 2 — Đối chiếu yêu cầu với code hiện tại

> Ngày rà soát: 2026-11-07  
> Branch: `arena/ea6e2570-vinit-hrapp`  
> Mốc code trước tài liệu rà soát: `737e8b7`  
> Trạng thái: **rà soát/gap analysis — chưa triển khai tính năng Phase 2 và chưa chốt plan thực hiện**.  
> F2.08 SSO: **TẠM TREO theo quyết định của người dùng**, không thuộc phạm vi lập plan ở vòng này.

## 1. Nguồn yêu cầu và phạm vi

Nguồn chính:

- `doc/HRA_NextPhase.md`: F2.01–F2.09.
- `doc/HRA_PRD.md`, mục Phase 2: đo lường hiệu quả, thư viện JD/rubric và khả năng tái sàng lọc kho CV.
- Code/schema/API/frontend/tests tại các batch Phase 1 đã có trên branch hiện tại.

Quy ước trạng thái:

| Trạng thái | Ý nghĩa |
|---|---|
| `ĐÃ CÓ` | Hành vi nghiệp vụ chính đã tồn tại và có đường sử dụng thực tế. |
| `MỘT PHẦN` | Có một số primitive/schema/API tái sử dụng được, nhưng workflow yêu cầu chưa hoàn chỉnh. |
| `CHƯA CÓ` | Không tìm thấy tính năng tương ứng trong code/schema/API/frontend hiện tại. |
| `BỊ CHẶN NGOÀI KỸ THUẬT` | Cần quyết định nghiệp vụ, pháp lý, hạ tầng hoặc dữ liệu trước khi nghiệm thu được. |
| `TẠM TREO` | Người dùng đã loại khỏi vòng lập plan hiện tại. |

Không dùng mức phần trăm hoàn thành vì các tiêu chí có trọng số nghiệp vụ và rủi ro khác nhau.

## 2. Kết quả tổng quan

| ID | Tính năng | Trạng thái rà soát | Kết luận ngắn |
|---|---|---|---|
| F2.01 | Rubric Library theo job family | `MỘT PHẦN` | Đã có criteria theo từng position, versioning và phê duyệt HR/HM; chưa có library/template/clone theo job family. |
| F2.02 | Structured Collaborative Workflow HR–HM | `MỘT PHẦN` | Đã có shortlist share, snapshot, feedback text tự do và HR private notes; chưa có scorecard, task/deadline và nhắc việc. |
| F2.03 | Operational Analytics Dashboard | `MỘT PHẦN` | Đã có dashboard vận hành cơ bản; thiếu funnel theo thời gian, thời gian xử lý, error analytics và HR override tracking thật. |
| F2.04 | QA/Sample Inspection | `MỘT PHẦN — MỚI CÓ NỀN TẢNG` | Đã có kiểm chứng evidence/coverage và script đánh giá offline; chưa có hàng đợi sampling, màn hình đối chiếu và feedback flag. |
| F2.05 | Cross-Requisition Duplicate Detection | `MỘT PHẦN HẸP` | Hiện chỉ exact email/phone trong cùng một position; chưa có cross-position, fuzzy matching hoặc candidate history. |
| F2.06 | OCR JPG/PNG và ảnh nhúng DOCX | `CHƯA CÓ PHẦN MỞ RỘNG` | Hiện chỉ PDF text, PDF scan OCR và DOCX text; chưa nhận ảnh độc lập hoặc OCR ảnh trong DOCX. |
| F2.07 | Retention automation & deletion workflow | `MỘT PHẦN + BỊ CHẶN PHÁP LÝ` | Phase 1 đã có retention thủ công từng case và audit; thiếu scheduler, cảnh báo, exception hold, OTP/chữ ký và giao diện vận hành. |
| F2.08 | SSO | `TẠM TREO` | Không lập plan/không triển khai trong vòng này. |
| F2.09 | Side-by-side Comparison & Custom Export | `CHƯA CÓ` | Có dữ liệu ranking/assessment để tái sử dụng; chưa có comparison view hoặc export Excel/PDF tùy biến. |

## 3. Chi tiết theo tính năng

### F2.01 — Rubric Library theo job family

**Đã có trong code hiện tại**

- Bảng `positions` đã có `job_family` và `level` dạng text; `departments` quản lý đơn vị tổ chức nhưng không phải taxonomy job family.
- `criteria_versions` và `criteria_items` đã version hóa theo từng `position_id`.
- Mỗi criteria version gắn với một JD version, có trạng thái `DRAFT → PENDING_HR_REVIEW → PENDING_HM_APPROVAL → APPROVED`, trường `origin` hiện chỉ cho `AI_DRAFT` hoặc `HR_CREATED`.
- Đã có chỉnh trọng số/item ở draft, approval events, kiểm soát JD mới nhất và materialize `requirement_spec` phục vụ matching.
- Frontend position detail đã có luồng tạo/duyệt criteria theo vị trí.

**Khoảng thiếu**

- Chưa có thực thể thư viện dùng chung: job-family taxonomy được quản trị, rubric template, template items, template version, trạng thái phê duyệt template và lịch sử thay đổi template.
- Chưa có API/UI để chọn template theo job family/level, clone thành criteria draft của position, xem diff hoặc cập nhật position từ template mới mà không phá vỡ version đã duyệt.
- Chưa có seed/nội dung chuẩn cho 5 nhóm VinUni nêu trong tài liệu và chưa có chủ sở hữu phê duyệt nội dung.
- `job_family` hiện là text tự do; nếu không chuẩn hóa taxonomy trước, template matching sẽ dễ trùng/nhiễu tên.

**Đánh giá:** `MỘT PHẦN`. Có thể tái sử dụng state machine và item model của criteria hiện tại, nhưng cần thiết kế thư viện độc lập; không nên sao chép criteria của position thành “template” chỉ bằng quy ước.

**Quyết định cần chốt trước plan**

- Ai sở hữu và phê duyệt taxonomy/template: HR Lead, HRBP theo family hay Admin?
- Template version được duyệt một cấp hay hai cấp HR/HM?
- Khi clone, trường nào khóa theo template và trường nào HR được sửa cho position cụ thể?

---

### F2.02 — Structured Collaborative Workflow HR–HM

**Đã có trong code hiện tại**

- `shortlist_shares`, `shortlist_share_items` và `shortlist_feedback` đã hỗ trợ HR chia sẻ snapshot shortlist cho HM được phân công.
- Share có `allow_cv_view`, trạng thái thu hồi và kiểm soát HM chỉ xem ứng viên đã được share.
- HM/HR có thể gửi feedback text tự do, có thể gắn với một application hoặc ở mức share.
- `application_private_notes` là ghi chú riêng của HR; backend khóa theo quyền HR phụ trách position.
- Trạng thái application do HR kiểm soát; HM hiện không tự chuyển trạng thái.

**Khoảng thiếu**

- Chưa có scorecard có cấu trúc gắn với từng criterion: điểm/chọn mức, khuyến nghị tổng thể, điểm mạnh, quan ngại và trạng thái hoàn thành.
- Chưa có mô hình phân công review cho từng HM, deadline, trạng thái task, bằng chứng đã xem/đã hoàn thành.
- Chưa có hạ tầng notification/reminder dùng chung: không tìm thấy email sender, in-app notification inbox, scheduler nhắc việc hoặc rule “quá hạn 3 ngày làm việc”.
- Feedback hiện là nội dung text tối đa 3.000 ký tự; chưa có thread/reply, read state, visibility tier ngoài việc tách HR private notes, hoặc tổng hợp scorecard.
- Chưa có tổng hợp tự động “HM đã đánh giá/chưa đánh giá” trên shortlist.

**Đánh giá:** `MỘT PHẦN`. Share và phân quyền là nền tảng tốt; phần scorecard/workflow/reminder là tính năng mới đáng kể.

**Quyết định cần chốt trước plan**

- Thang scorecard: 1–5, đạt/không đạt, hay Strong No/No/Yes/Strong Yes theo từng criterion?
- HM có bắt buộc hoàn thành scorecard trước khi HR chuyển trạng thái không?
- Kênh nhắc việc MVP: chỉ in-app hay cả email; ai nhận escalation khi quá hạn?

---

### F2.03 — Operational Analytics Dashboard & HR Override Tracking

**Đã có trong code hiện tại**

- `GET /v1/dashboard/summary` và `GET /v1/dashboard/position/{position_id}` trả số position đang mở, tổng application, phân bố trạng thái, số đang xử lý, file cần HR review, duplicate alert, số assessment hoàn thành, matching status, coverage trung bình và số dưới ngưỡng.
- Dashboard đã scope theo position assignment/shortlist share; HM không được xem aggregate ngoài phần được chia sẻ.
- Frontend `/dashboard` hiển thị các chỉ số vận hành cơ bản trên.

**Khoảng thiếu**

- `hr_override_rate` hiện chủ động trả `null` vì chưa có dữ liệu override đáng tin cậy; `average_processing_time_seconds` cũng trả `null`.
- HR hiện có thể đổi trạng thái application, nhưng `application_status_events` chỉ lưu trạng thái trước/sau, người đổi, reason/note. Sự kiện không lưu AI matching status/score/coverage tại thời điểm HR quyết định và không có mã lý do override chuẩn.
- Hệ thống chưa cho HR override kết quả từng criterion; vì vậy phải định nghĩa “override” là HR đổi quyết định application ngược với khuyến nghị AI hay một hành vi khác.
- Chưa có time-to-shortlist, funnel theo cohort/khoảng ngày, vòng đời theo department/job family/level, xu hướng theo thời gian.
- Chưa có thống kê lỗi kỹ thuật theo loại file, bước OCR/parse/LLM/matching, mã lỗi hoặc provider; dữ liệu thô nằm rải rác ở documents/operations/processing runs.
- Chưa có export báo cáo hoặc định nghĩa denominator/loại trừ cho từng metric.

**Đánh giá:** `MỘT PHẦN`. Cần instrumentation và data dictionary trước; không nên tính override bằng cách suy đoán từ trạng thái hiện tại.

**Quyết định cần chốt trước plan**

- Định nghĩa chính thức của HR override và tập reason code bắt buộc.
- Metric tính theo application, assessment mới nhất hay theo sự kiện quyết định?
- Khoảng thời gian/funnel chuẩn và quyền xem theo HR Lead/Admin/HM.

---

### F2.04 — QA/Sample Inspection cho OCR & AI Matching

**Đã có trong code hiện tại**

- Matching đã có deterministic rules/LLM fallback, `decision_source`, `evidence_items.verification_status`, evidence coverage và cảnh báo `NEEDS_HR_VERIFICATION`.
- Có `backend/scripts/evaluate_matching.py` và snapshot export để đo repeatability/ranking stability offline.
- Trang chi tiết ứng viên đã hiển thị hồ sơ, criterion outcomes, evidence quotes và CV PDF.

**Khoảng thiếu**

- Chưa có bảng/API/UI cho inspection case, sampling rule, reviewer assignment, trạng thái QA hoặc lịch sử xử lý.
- Chưa có cơ chế chọn tự động 10% hồ sơ, chọn 100% nhóm rủi ro cao, chống trùng mẫu hoặc khóa mẫu sau khi đã chọn.
- Chưa có màn hình đối chiếu đồng bộ “trang gốc ↔ OCR text ↔ extracted facts/evidence” theo trang; `pages.json` phục vụ trích xuất nhưng chưa có viewer QA tương ứng.
- OCR confidence hiện không được worker lưu bền vững làm dữ liệu QA; vì vậy chưa lọc được mẫu theo low-confidence một cách tin cậy.
- Chưa có flag taxonomy như sai evidence, thiếu nội dung, sai fact, OCR lỗi; chưa có workflow xác nhận/bác flag, yêu cầu reprocess/reassess hoặc xuất feedback dataset có kiểm soát.
- Script repeatability không thay thế precision/false-negative review bằng con người; chưa có HR-labelled QA dataset.

**Đánh giá:** `MỘT PHẦN — MỚI CÓ NỀN TẢNG`. Cần data model và viewer mới; đây là một trong các hạng mục có giá trị chất lượng cao nhưng phụ thuộc định nghĩa sampling và nhân sự QA.

**Quyết định cần chốt trước plan**

- Mẫu 10% tính theo application, document hay assessment; stratify theo position/file type/OCR confidence ra sao?
- Ai là QA reviewer: HR Lead, HR phụ trách hay người độc lập với quyết định ban đầu?
- Flag nào chỉ ghi nhận, flag nào chặn sử dụng kết quả hoặc buộc reassessment?

---

### F2.05 — Cross-Requisition Duplicate Detection

**Đã có trong code hiện tại**

- `MatchingEngine.detect_duplicates()` phát hiện exact email hoặc exact phone.
- Worker chỉ nạp applications của cùng một `position_id`, sau đó ghi `duplicate_signals` với cặp application trong position đó.
- `duplicate_signals` đã có confidence, signal type, detector version và trường review status/reviewed by/at.
- Danh sách ứng viên, candidate detail và dashboard đã hiển thị cảnh báo trùng trong cùng position.
- Khi HR sửa identity, các signal cũ liên quan được dismiss bằng detector marker `identity-changed`.

**Khoảng thiếu**

- Chưa có truy vấn/index/detector trên toàn hệ thống để phát hiện cùng email/phone ở nhiều position.
- Bảng hiện tại bắt buộc gắn một `position_id`; chưa biểu diễn rõ cặp application thuộc hai requisition khác nhau hoặc lịch sử ứng tuyển của cùng một identity.
- Detector chỉ strip khoảng trắng ở phone khi so sánh; chưa chuẩn hóa dấu phân cách, mã quốc gia `+84`/`0`, email alias hoặc lỗi OCR.
- Chưa có fuzzy name + similarity của nội dung CV, ngưỡng/manual review tương ứng.
- Chưa có API/UI để HR confirm duplicate, đánh dấu false positive, xem candidate application history hoặc điều phối recruiter phụ trách.
- Cross-position visibility tự nó là dữ liệu nhạy cảm: HR của position A không mặc nhiên nên thấy toàn bộ thông tin position B.

**Đánh giá:** `MỘT PHẦN HẸP`. Có thể mở rộng từ exact identity trước; fuzzy/content matching nên là bước sau khi đo false-positive bằng dữ liệu đã phê duyệt.

**Quyết định cần chốt trước plan**

- Mức hiển thị cross-position: chỉ báo “đã có hồ sơ khác”, hiển thị position/title/status, hay xem chi tiết?
- Ai được confirm/merge/điều phối; hệ thống có tuyệt đối không tự gộp/xóa hồ sơ như yêu cầu đã nêu không?
- Chuẩn hóa phone/email dùng chung với dữ liệu nhập tay và dữ liệu OCR như thế nào?

---

### F2.06 — Mở rộng OCR cho JPG/PNG và ảnh nhúng DOCX

**Đã có trong code hiện tại**

- `DocumentProcessor` hỗ trợ PDF có text layer, PDF scan qua `pdf2image` + Tesseract và DOCX paragraphs.
- Upload xác thực magic bytes/MIME cho PDF/DOCX, giới hạn kích thước và chuyển file thiếu text sang `NEEDS_HR_REVIEW`.
- Đã có Pillow, `pytesseract`, `pdf2image` trong dependencies worker/backend.

**Khoảng thiếu**

- Upload API/UI hiện chỉ chấp nhận `.pdf` và `.docx`; chưa nhận JPG/JPEG/PNG độc lập.
- `extract_text_from_docx()` mới nối paragraphs; chưa mở package `word/media/*` để OCR ảnh nhúng, chưa giữ quan hệ ảnh ↔ vị trí/ngữ cảnh trong tài liệu.
- Chưa có tiền xử lý ảnh riêng: deskew, contrast, denoise, resize/upscale, kiểm tra DPI/resolution hoặc EXIF orientation.
- OCR PDF scan hiện gọi Tesseract với `lang='eng'`; CV scan tiếng Việt có nguy cơ chất lượng thấp nếu môi trường không có dữ liệu ngôn ngữ và cấu hình phù hợp.
- Chưa lưu OCR diagnostics chất lượng (DPI, confidence theo trang, preprocessing version) để chuyển case chất lượng thấp sang QA/manual review một cách có hệ thống.
- Chưa có giới hạn chống image bomb/file ảnh bất thường cho định dạng mới.

**Đánh giá:** `CHƯA CÓ PHẦN MỞ RỘNG`, nhưng pipeline xử lý và trạng thái manual review có thể tái sử dụng.

**Quyết định cần chốt trước plan**

- Chỉ JPG/PNG hay thêm TIFF/WebP; một ảnh được coi là một CV hay một trang của CV nhiều ảnh?
- Ngưỡng DPI/confidence nào chuyển `NEEDS_HR_REVIEW`?
- OCR tiếng Việt là yêu cầu nghiệm thu bắt buộc hay chỉ best effort ở vòng đầu?

---

### F2.07 — Retention automation & quy trình xóa an toàn

**Đã có trong code hiện tại từ Phase 1**

- Có `retention_policy_versions`, `application_retention_cases`, deletion jobs/events và API list/generate/confirm/cancel/execute.
- Chỉ generate case cho position đã `CLOSED`; due date tính từ `closed_at + retention_months` của policy đã duyệt.
- HR Lead xác nhận và thực thi từng case; chưa đến hạn bị chặn ở cả confirm và execute.
- Xóa storage trước, chỉ purge DB khi storage thành công; giữ bằng chứng opaque ID/counts, không ghi PII vào retention/audit evidence.
- Audit events có hash chain và endpoint Admin verify.
- Khi position mở lại, API đặt `closed_at = NULL`; lần đóng sau sẽ tạo mốc thời gian mới.

**Khoảng thiếu/rủi ro cần xử lý trong plan**

- Chưa có scheduler/job tự động generate case hoặc quét hạn; hiện HR phải gọi generate thủ công.
- Chưa có cảnh báo trước 30/15/7 ngày và không có email/in-app notification infrastructure.
- Chưa có frontend retention console; Phase 1 mới có API/service.
- Nếu case đã generate khi position đóng, sau đó position mở lại, case cũ vẫn giữ `position_closed_at` snapshot. Luồng execute hiện kiểm tra case confirmed/đã đến hạn nhưng chưa thấy bước revalidate rằng position vẫn đang đóng với cùng `closed_at`; plan Phase 2 phải thêm guard hủy/treo case khi position mở lại để tránh xóa hồ sơ của requisition đang hoạt động.
- Chưa có exception hold: entity, lý do pháp lý, người phê duyệt, thời hạn hold, release hold và lịch sử phê duyệt.
- Chưa có OTP, chữ ký điện tử, tải/gắn biên bản Legal hoặc nhà cung cấp e-signature. Phase 1 đã chủ động không tự triển khai các phần này khi chưa có quyết định Legal/IT.
- Chưa có báo cáo retention toàn cục theo position/due window/hold status.

**Đánh giá:** `MỘT PHẦN + BỊ CHẶN PHÁP LÝ`. Nền tảng xóa an toàn đã tốt hơn yêu cầu tối thiểu ở khâu thực thi, nhưng automation và exception workflow chưa thể nghiệm thu nếu Legal chưa chốt hình thức phê duyệt/bằng chứng.

**Quyết định cần chốt trước plan**

- Legal chọn OTP, chữ ký điện tử, phê duyệt trong hệ thống có audit, hay kết hợp theo mức rủi ro?
- Hold áp dụng ở application, position hay candidate identity; ai được đặt/gỡ hold?
- Cảnh báo gửi qua kênh nào và escalation tới ai khi quá hạn chưa xử lý?

---

### F2.08 — Microsoft/Azure SSO

**Trạng thái:** `TẠM TREO` theo quyết định ngày 2026-11-07.

Rà soát này không lập plan, không chọn giao thức, không đánh giá IdP và không thay đổi authentication hiện tại. Khi người dùng mở lại hạng mục, cần rà soát riêng Supabase Auth, Azure tenant, group-to-role mapping, provisioning/deprovisioning và break-glass Admin.

---

### F2.09 — Side-by-side Comparison & Custom Export

**Đã có trong code hiện tại**

- Trang ranking đã có score, matching status, evidence coverage và chọn ứng viên phục vụ shortlist.
- Trang chi tiết ứng viên đã có profile facts, criterion outcomes, evidence, trạng thái và ghi chú HR.
- Shortlist share đã có snapshot assessment/ranking tại thời điểm chia sẻ.

**Khoảng thiếu**

- Chưa có endpoint hoặc UI chọn 2–4 ứng viên trong cùng position để xem ma trận side-by-side theo từng criterion.
- Chưa có so sánh score/coverage/profile facts/điểm mạnh–quan ngại theo cùng một criteria version; cần khóa rõ assessment version để tránh so sánh dữ liệu không đồng nhất.
- Chưa có export Excel/PDF, chọn cột, template báo cáo hoặc thư viện `openpyxl`/report generator tương ứng.
- Chưa có audit event riêng cho export, giới hạn số hồ sơ, watermark, expiry hoặc chính sách tải dữ liệu cá nhân ra file.

**Đánh giá:** `CHƯA CÓ`. Đây là hạng mục chủ yếu ở tầng API trình bày/báo cáo và có thể tái sử dụng dữ liệu assessment hiện tại; rủi ro chính nằm ở kiểm soát PII khi export hơn là thuật toán.

**Quyết định cần chốt trước plan**

- Export mặc định gồm trường nào; có cho phép email/phone/CV link trong file không?
- Ai được export: HR phụ trách, HR Lead hay cả HM đã được share?
- “Best per criterion” hiển thị theo score thô hay kèm evidence strength/coverage để tránh diễn giải quá mức?

## 4. Khác biệt giữa các tài liệu cần lưu ý

1. `doc/HRA_PRD.md` xếp “tái sàng lọc kho CV cũ” vào roadmap Phase 2, trong khi `doc/HRA_NextPhase.md` xếp Candidate Rediscovery là F3.01 của Phase 3. Báo cáo này không tự gộp rediscovery vào F2.01–F2.09. Cần quyết định riêng trước khi lập plan tổng thể vì rediscovery phụ thuộc consent, retention và quyền dùng lại CV.
2. `doc/HRA_NextPhase.md` giả định đã có pilot 3–6 tháng để lấy baseline. Thực tế ngày rà soát, Phase 1 đang tạm dừng chờ triển khai Production; vì vậy chưa có baseline vận hành thật cho F2.03/F2.04. Plan cần bắt đầu bằng instrumentation/dữ liệu tổng hợp hoặc staging, không chờ số liệu pilot mới thiết kế schema.
3. SSO từng được mô tả là có thể làm độc lập bất cứ lúc nào, nhưng quyết định mới nhất của người dùng là tạm treo; quyết định mới nhất được ưu tiên.

## 5. Phụ thuộc dùng chung

| Phụ thuộc | Ảnh hưởng | Ghi chú |
|---|---|---|
| Notification/task infrastructure | F2.02, F2.07 | Repo chưa có email sender, notification inbox hoặc scheduler nhắc việc; cần chọn kiến trúc trước hai workflow này. |
| Scheduler/background jobs | F2.04, F2.05, F2.07 | Worker hiện xử lý operations theo polling; sampling, cross-duplicate scan và retention scan cần job idempotent có audit. |
| Metric/event instrumentation | F2.03, F2.04 | Phải ghi sự kiện tại thời điểm quyết định; không suy ngược override/quality từ trạng thái hiện tại. |
| Identity normalization | F2.05 | Cần chuẩn hóa phone/email nhất quán giữa nhập tay, OCR và dữ liệu cũ. |
| Legal/privacy decisions | F2.04, F2.05, F2.07, F2.09 | Liên quan QA dataset, hiển thị cross-position, hold/xóa và export PII. |
| Phase 1 DEP-01…DEP-08 | Nghiệm thu Production/dữ liệu thật | Các DEP vẫn tạm dừng chờ Production; rà soát/plan Phase 2 không đóng các DEP này. |
| HR/HM nghiệp vụ | F2.01–F2.04 | Cần taxonomy, mẫu rubric, scorecard, metric dictionary và QA sampling policy được người dùng nghiệp vụ duyệt. |

## 6. Đầu vào đề xuất cho plan — chưa phải plan đã duyệt

Thứ tự dưới đây chỉ là khuyến nghị để lập plan ở bước tiếp theo:

1. **Chốt quyết định nghiệp vụ và data dictionary:** job-family taxonomy, scorecard, override definition, QA sampling, duplicate visibility, export fields và retention Legal workflow.
2. **Nền tảng instrumentation:** sự kiện override tại thời điểm quyết định, processing timing/error taxonomy, notification/task primitives nếu được duyệt.
3. **Workflow cốt lõi:** F2.01 Rubric Library và F2.02 Scorecard/collaboration.
4. **Tiện ích dùng dữ liệu hiện có:** F2.05 exact cross-position duplicate và F2.09 comparison/export có kiểm soát PII.
5. **Chất lượng:** F2.04 QA inspection sau khi có sampling/flag model; dùng kết quả để hoàn thiện F2.03 analytics.
6. **Mở rộng đầu vào:** F2.06 image OCR, có bộ mẫu synthetic và ngưỡng manual review riêng.
7. **Retention automation:** F2.07 sau khi Legal chốt hold/OTP/chữ ký; ưu tiên guard case khi position mở lại trước khi bật scheduler.
8. **F2.08 SSO:** giữ ngoài plan cho tới khi có quyết định mở lại.

## 7. Kết luận rà soát

Phase 2 không bắt đầu từ số 0: criteria versioning, shortlist sharing, dashboard cơ bản, evidence verification, duplicate nội bộ, OCR PDF/DOCX và retention an toàn của Phase 1 tạo nền tảng đáng kể. Tuy nhiên, phần lớn yêu cầu Phase 2 là workflow và dữ liệu mới — không phải chỉ thêm màn hình. Ba quyết định có ảnh hưởng lớn nhất trước khi lập plan là:

- Chuẩn hóa taxonomy/rubric và scorecard nghiệp vụ.
- Định nghĩa sự kiện HR override cùng metric dictionary.
- Chốt Legal/privacy cho QA dataset, cross-position visibility, retention exception và export.

Sau khi các điểm trên và phạm vi ưu tiên được người dùng duyệt, mới chuyển báo cáo này thành plan triển khai theo batch trong `Update_Excute_P2.md`.
