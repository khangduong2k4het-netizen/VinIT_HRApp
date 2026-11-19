# Update Execute — Phase 2

> File này ghi lại quá trình rà soát, lập plan và triển khai Phase 2 theo quy ước giống `Update_Excute_P1.md`: trạng thái tổng quan, thay đổi file/code/migration, test đã chạy và kết quả, commit hash sau khi push, blocker và điều kiện mở khóa.
>
> **Cập nhật 12/11/2026 trên nhánh `khangduong`:** F2.01, phần scorecard F2.02 và F2.03 đã có code từ các commit `96b7587` / `1eeeffd`. Theo yêu cầu mới, F2.04 kiểm định chất lượng và F2.05 cảnh báo trùng chéo vị trí đã bổ sung backend, giao diện, migration `00017` và tests. Đã kiểm tra trên PostgreSQL dùng một lần và browser với dữ liệu tổng hợp; chưa deploy hay áp migration lên Supabase/VPS. Chi tiết tại [PHASE2_04_05.md](doc/PHASE2_04_05.md). Các phần rà soát/plan phía dưới là lịch sử, không thay thế hiện trạng code này. Các gate production và Langfuse staging vẫn riêng biệt.
>
> **Cập nhật 12/11/2026 (tiếp):** F2.06 (OCR ảnh JPG/PNG và ảnh nhúng DOCX, tiền xử lý, hàng đợi thủ công cho ảnh DPI thấp/mờ) và F2.07 (nhắc hạn 30/15/7 ngày, tạm hoãn có số văn bản Pháp chế, OTP trước khi xóa vật lý, hủy case khi vị trí mở lại) đã có code, migration `00018` và tests; chu kỳ retention tự động tắt mặc định chờ Pháp chế duyệt. Chi tiết tại [PHASE2_06_07.md](doc/PHASE2_06_07.md). Quyết định "F2.07 loại khỏi vòng này" ở mục 4.1 là của vòng 07/11, nay đã được làm theo yêu cầu mới.
>
> **F2.08 SSO: TẠM TREO** theo quyết định của người dùng; không đưa vào plan ở vòng này.

## 1. Trạng thái tổng quan

| Giai đoạn | Phạm vi | Trạng thái | Bằng chứng |
|---|---|---|---|
| P2-0 | Đọc tài liệu, rà soát code/schema/API/frontend/tests F2.01–F2.07 và F2.09 | HOÀN THÀNH RÀ SOÁT | `audit/PHASE2_REVIEW_2026-11-07.md` |
| P2-0 | F2.08 SSO | TẠM TREO | Không lập plan/không thay đổi auth trong vòng này |
| P2-1 | Chốt phạm vi ưu tiên đầu tiên | ĐÃ CHỐT | Workflow cốt lõi F2.01 + F2.02; F2.07 loại khỏi vòng này; Candidate Rediscovery để cuối Phase 2 |
| P2-2 | Lập plan triển khai chi tiết batch đầu | HOÀN THÀNH — CHỜ DUYỆT PLAN | `doc/PHASE2_IMPLEMENTATION_PLAN.md` |
| P2-2.1 | Chốt quyết định nghiệp vụ D-01…D-10 trong plan batch đầu | CHỜ HR/HR LEAD DUYỆT | Mục 3 của plan chi tiết |
| P2-3 | Triển khai/test/CI batch Workflow Core | ĐÃ CÓ CODE — CHƯA NGHIỆM THU MÔI TRƯỜNG ĐÍCH | `96b7587`, test Phase 2 workflow trên PostgreSQL local |
| F2.03 | Báo cáo vận hành và HR override | ĐÃ CÓ CODE — CHƯA NGHIỆM THU MÔI TRƯỜNG ĐÍCH | `1eeeffd`, `test_hr_analytics.py` |
| F2.04 | QA sampling, HR Lead review và feedback | ĐÃ TRIỂN KHAI, KIỂM THỬ LOCAL | Migration `00017`, `test_quality_duplicates.py`, browser smoke; xem tài liệu batch mới |
| F2.05 | Cảnh báo trùng chéo vị trí, phạm vi quyền và review | ĐÃ TRIỂN KHAI, KIỂM THỬ LOCAL | Migration `00017`, `test_quality_duplicates.py`, browser smoke; không tự gộp/xóa |
| F2.06 | OCR ảnh JPG/PNG, ảnh nhúng và bảng trong DOCX, tiền xử lý, cổng DPI/độ nét | ĐÃ TRIỂN KHAI, KIỂM THỬ LOCAL | Migration `00018`, `test_ocr_images_retention.py`; ngưỡng độ nét là đề xuất, chưa đo > 98% |
| F2.07 | Nhắc hạn retention, tạm hoãn có văn bản Pháp chế, OTP khi xóa, reset khi mở lại | ĐÃ TRIỂN KHAI, KIỂM THỬ LOCAL — CHỜ PHÁP CHẾ | Migration `00018`, `test_ocr_images_retention.py`; scheduler tắt mặc định |
| UX-PLAN | Lập plan nâng cấp UI/UX Recruitment Workspace từ review GPT 2026-11-08 | HOÀN THÀNH | `doc/FRONTEND_UI_UX_UPGRADE_PLAN.md` |
| UX-0…UX-4 | Triển khai Recruitment Workspace: Work Queue, Position Workspace, Applicant/Candidate Review, CV Intake và polish | ĐÃ TRIỂN KHAI Ở CODE — CHỜ CI/STAGING | Backend/frontend/test thay đổi trong batch UI/UX; usability trên staging chưa thực hiện |
| LF-0 | Lập tài liệu, lộ trình và plan triển khai Langfuse AI Observability | HOÀN THÀNH | `doc/LANGFUSE_IMPLEMENTATION_PLAN.md` |
| LF-1 | Observability foundation: cấu hình, wrapper fail-open, tracing LLM/worker/BGE, score assessment, Admin health và smoke script | ĐÃ TRIỂN KHAI Ở CODE — CHỜ STAGING | Chưa dựng/bật Langfuse server; không gửi nội dung CV/JD mặc định |
| LF-2A/LF-3A | Child spans worker, runbook staging và cầu nối evaluation scores sang Langfuse | ĐÃ TRIỂN KHAI Ở CODE — CHỜ STAGING | Chỉ gửi evaluation khi có `--send`; sandbox không có Docker/Podman và DEP-01 chưa mở |

## 2. Nguyên tắc áp dụng cho Phase 2

1. Chỉ làm việc trên branch `arena/ea6e2570-vinit-hrapp`; không tự ý triển khai trước khi plan được duyệt.
2. Phase 1 vẫn chưa đóng; các DEP-01…DEP-08 tạm dừng chờ triển khai Production và không bị đóng bởi công việc Phase 2.
3. Không dùng CV/dữ liệu thật khi chưa có phê duyệt privacy/egress và kiểm chứng vận hành cần thiết.
4. Không tự suy diễn HR override, chất lượng OCR/matching hoặc hiệu quả tuyển dụng từ trạng thái hiện tại khi hệ thống chưa ghi sự kiện/dữ liệu phù hợp.
5. F2.08 SSO giữ trạng thái tạm treo cho tới khi người dùng có quyết định mở lại.
6. Candidate Rediscovery đã được chốt để ở cuối Phase 2, không thuộc batch đầu; trước khi lập plan chi tiết cho hạng mục này vẫn phải có quyết định về consent, retention và quyền tái sử dụng CV.

## 3. P2-0 — Rà soát tài liệu và code hiện tại

### 3.1. Tài liệu đã đọc

- `doc/HRA_NextPhase.md`: yêu cầu F2.01–F2.09.
- `doc/HRA_PRD.md`: mục Phase 2 và bối cảnh roadmap.
- `Update_Excute_P1.md`, `audit/PHASE1_REVIEW_2026-11-07.md`, `audit/UPGRADE_AUDIT_2026-11-07.md`: trạng thái và giới hạn của nền tảng Phase 1.
- `doc/PENDING_DEPLOYMENT.md`: các DEP còn chờ triển khai Production.

### 3.2. Phạm vi code đã đối chiếu

- Schema/migrations `00001`–`00012`.
- Backend API/services/worker: criteria, positions, shortlist, candidate details, dashboard, applications, document processor, matching, evaluation scripts và retention.
- Frontend routes/API client: dashboard, positions, applicants, applicant detail, shortlist và admin hiện có.
- Tests/scripts liên quan tới matching evaluation, document processing, dashboard, duplicate signals và retention.

### 3.3. Kết quả chính

| ID | Kết luận rà soát |
|---|---|
| F2.01 | Có criteria versioning/phê duyệt theo position; chưa có rubric library/template/clone theo job family. |
| F2.02 | Có shortlist share/feedback text và HR private notes; chưa có structured scorecard, task/deadline/reminder. |
| F2.03 | Có dashboard cơ bản; chưa có HR override tracking, funnel thời gian, processing-time và error analytics. |
| F2.04 | Có evidence verification/coverage và evaluation offline; chưa có sampling queue, inspection viewer và feedback flags. |
| F2.05 | Có exact duplicate trong cùng position; chưa có cross-position detection/history/review workflow. |
| F2.06 | Có PDF/DOCX OCR hiện tại; chưa hỗ trợ JPG/PNG độc lập và ảnh nhúng DOCX. |
| F2.07 | Có retention thủ công an toàn từng case; chưa có scheduler/cảnh báo, retention UI, exception hold, OTP/chữ ký. Cần guard case khi position mở lại. |
| F2.08 | Tạm treo. |
| F2.09 | Chưa có side-by-side comparison và custom Excel/PDF export. |

Chi tiết bằng chứng và khoảng thiếu: `audit/PHASE2_REVIEW_2026-11-07.md`.

### 3.4. File đã thay đổi ở P2-0

- Tạo `audit/PHASE2_REVIEW_2026-11-07.md`.
- Tạo `Update_Excute_P2.md`.
- Cập nhật `Update_Excute_P1.md`: ghi quyết định tạm dừng các gate Phase 1 chờ Production.
- Cập nhật `doc/PENDING_DEPLOYMENT.md`: ghi rõ rà soát Phase 2 không đóng DEP nào.

Không thay đổi code tính năng, schema/migration, API hoặc frontend ở giai đoạn rà soát này.

### 3.5. Kiểm chứng đã thực hiện

- Kiểm tra branch/worktree và mốc HEAD trước rà soát.
- Đọc tài liệu Phase 2 và đối chiếu trực tiếp schema/API/service/frontend bằng tìm kiếm mã nguồn.
- Kiểm tra `git diff --check` sau khi hoàn thành tài liệu.
- Không chạy test code vì P2-0 chỉ thay đổi tài liệu; trạng thái test của code vẫn theo bằng chứng Phase 1 đã lưu.

### 3.6. Commit

- Commit rà soát Phase 2: `7189d20` (`docs: rà soát Phase 2 và tạm dừng gate Phase 1`), đã push lên `arena/ea6e2570-vinit-hrapp`.

### 3.7. P2-2 — Plan chi tiết batch đầu Workflow Core

- Đã tạo `doc/PHASE2_IMPLEMENTATION_PLAN.md` cho F2.01 Rubric Library và F2.02 Structured Collaborative Workflow HR–HM.
- Plan đã khóa phạm vi ngoài batch đầu: F2.07 loại khỏi vòng này, Candidate Rediscovery để cuối Phase 2 và F2.08 SSO tiếp tục tạm treo.
- Plan gồm cổng quyết định D-01…D-10, thiết kế dữ liệu/API/UI dự kiến, thứ tự triển khai, kiểm thử bắt buộc, tiêu chí nghiệm thu và rủi ro.
- Chưa thay đổi code tính năng, schema/migration, API hoặc frontend; triển khai chỉ bắt đầu sau khi plan và D-01…D-10 được duyệt.
- Commit plan: `ffc8043` (`docs: lập plan batch đầu Phase 2`), đã push lên `arena/ea6e2570-vinit-hrapp`.

### 3.8. Plan UI/UX bổ sung — Recruitment Workspace

- Đã tạo `doc/FRONTEND_UI_UX_UPGRADE_PLAN.md` để đánh giá và lập lộ trình cho đề xuất UI/UX ngày 2026-11-08.
- Quyết định trong plan: ưu tiên Position Workspace + Workflow Stepper/Next Best Action, My Work Queue, Applicant Review theo hàng đợi và nâng cấp Candidate Review; CV Intake làm panel trong Position Workspace; Global Search, PDF text highlight và overall confidence để backlog/không làm cho tới khi có contract phù hợp.
- Plan khóa UX-0 contract/baseline trước UX-1…UX-4, nêu API work-queue/workspace, queue model, file dự kiến, kiểm thử, usability và gate triển khai.
- Chưa thay đổi code frontend/backend, schema/migration hoặc API. Triển khai UX-1 trở đi chờ duyệt plan và vẫn phụ thuộc DEP-01 đạt hoặc có chấp nhận rủi ro bằng văn bản theo quyết định hiện hành.

### 3.9. Triển khai UI/UX Recruitment Workspace — UX-0…UX-4

- Người dùng đã yêu cầu triển khai code UI/UX theo lộ trình; batch này không triển khai nghiệp vụ Phase 2 F2.01/F2.02, không thay schema/migration và không thay matching/BGE/LTR.
- Backend: tạo `backend/app/services/workspace.py`; bổ sung `GET /v1/dashboard/work-queue` trong `backend/app/api/dashboard.py` và `GET /v1/positions/{position_id}/workspace` trong `backend/app/api/positions.py`. Workflow/next-action/queue dùng cùng helper, scope theo assignment/share như dashboard; HR mới nhận việc rà soát hồ sơ, HM không nhận việc HR và summary không cộng chỉ số HR cho HM.
- Frontend: Dashboard thành Tổng quan công việc + My Work Queue; Position Workspace có summary/stepper/next-action và CV Intake Panel; Applicants có queue chips, sort, URL state, sticky table và bulk share bar; Candidate Review có sticky bar, prev/next theo hàng đợi, EvidenceCard/CVDocumentViewer; Sidebar/Header/AppLayout được phân nhóm và bỏ lần gọi profile trùng.
- UX-5 vẫn chưa làm: Global Search, highlight chữ trong PDF, server-side pagination, retry từng file và overall confidence.
- Kiểm chứng đã chạy: backend unit/integration-selected `5 passed, 50 skipped` cho workspace + integration file ở môi trường không có `TEST_DATABASE_URL`; backend full `103 passed, 64 skipped`; Ruff phạm vi mới đạt. Frontend `test:unit` 3 passed, `test:i18n` 3 passed, `type-check`, `lint` và `build` đạt.
- Chưa chạy synthetic UI E2E vì cần backend testing + DB tổng hợp dùng một lần theo guard của test; chỉ cập nhật kỳ vọng link Sidebar từ `Dashboard` sang `Work overview`. Chưa chạy usability HR/HM trên staging.
- Commit triển khai: `c5c81e0` (`feat: triển khai Recruitment Workspace UI/UX`), đã push lên `arena/ea6e2570-vinit-hrapp`.
- CI run `42549064191` cho commit trên: **success** cả Frontend checks, Backend unit tests và Backend integration (disposable PostgreSQL + pgvector).

### 3.10. Langfuse AI Observability — LF-0/LF-1

- Đã tạo `doc/LANGFUSE_IMPLEMENTATION_PLAN.md` gồm kiến trúc đích, trace/score taxonomy, trường dữ liệu được phép/cấm gửi, lựa chọn Cloud/self-host, cấu hình, lộ trình LF-0…LF-5, kiểm thử, rollback và gate DEP-01/privacy/retention.
- LF-1 triển khai observability foundation ở code, không dựng Langfuse server và không bật ở môi trường thật:
  - Backend: thêm cấu hình `LANGFUSE_*` tắt mặc định vào `backend/app/core/config.py`, env examples và dependency `langfuse>=4,<5` trong `backend/pyproject.toml`.
  - Tạo `backend/app/services/langfuse_observability.py`: lazy client, no-op khi tắt/thiếu cấu hình, sanitize metadata, content summary bằng hash/count, chặn capture content ở production, span/generation/embedding/score fail-open và status an toàn.
  - Instrument `LLMClient._call_llm` cho ba task criteria/profile/criterion matching; ghi model/provider/prompt version, usage nếu provider trả về và output dạng count/hash, không ghi reasoning/quote.
  - Instrument worker operation/assessment và BGE HTTP embedding; assessment gắn observation score `matching_score`, `evidence_coverage`, `needs_verification`, count UNCLEAR/RULE/LLM và evidence verified rate. PostgreSQL vẫn là nguồn sự thật.
  - Thêm `GET /v1/admin/langfuse/health` không trả key/host và script `backend/scripts/langfuse_smoke.py` chỉ gửi trace tổng hợp khi chạy chủ động với `--send`.
- Kiểm chứng local: test Langfuse + LLM client/Phase 1 unit `35 passed`; backend full `111 passed, 64 skipped`; Ruff phạm vi file mới/đổi chính đạt; smoke script ở chế độ chỉ kiểm tra cấu hình chạy đạt và báo `enabled=false`.
- Chưa chạy Langfuse server, chưa gửi trace lên Cloud/self-host và chưa dùng dữ liệu thật. LF-2 chỉ mở sau DEP-01 environment mapping và lựa chọn đích đến được duyệt.
- Commit triển khai: `5e401b1` (`feat: triển khai Langfuse observability LF-1`), đã push lên `arena/ea6e2570-vinit-hrapp`.
- CI run `42564275009` cho commit trên: **success** cả Frontend checks, Backend unit tests và Backend integration (disposable PostgreSQL + pgvector).

### 3.11. Langfuse LF-2A/LF-3A — Child spans, runbook và evaluation bridge

- Người dùng yêu cầu tiếp tục sau LF-1. Đối chiếu cho thấy DEP-01 vẫn bị chặn vì bảng environment mapping trong `doc/PENDING_DEPLOYMENT.md` còn `CHƯA XÁC NHẬN — BLOCKER`; sandbox không có Docker/Podman nên không dựng Langfuse self-host và không bật staging. Phần làm được an toàn ở code là LF-2A/LF-3A.
- Worker `backend/app/workers/processor.py`: bổ sung span metadata-only cho `hra.cv.document_extraction`, `hra.assessment.deterministic_matching`, `hra.assessment.semantic_retrieval`, `hra.assessment.evidence_verification`, `hra.assessment.scoring` và `hra.ranking.generate`. Chỉ ghi ID nội bộ, version, trạng thái, count và tỷ lệ; không thay matching semantics và không gửi CV/JD/quote/reasoning.
- Evaluation bridge: tạo `backend/scripts/push_langfuse_evaluation.py`, tái sử dụng `build_repeatability_report`/`compare_rankings` từ snapshot hiện có. Mặc định dry-run và in report/scores dự kiến; chỉ gửi aggregate scores khi có `--send` và cấu hình hợp lệ. Thêm `backend/tests/test_push_langfuse_evaluation.py`.
- Runbook: tạo `doc/LANGFUSE_STAGING_RUNBOOK.md` gồm gate DEP-01, cấu hình staging, smoke, workflow tổng hợp, evaluation bridge, kiểm tra fail-open, rollback và tiêu chí đóng LF-2/LF-3. Tài liệu này không mở gate môi trường.
- Kiểm chứng local: nhóm test liên quan `38 passed`; backend full `112 passed, 64 skipped`; Ruff `--select F` trên phạm vi thay đổi đạt; `langfuse_smoke.py` chế độ chỉ kiểm tra báo `enabled=false`; evaluation bridge dry-run trên snapshot tổng hợp nhỏ chạy đạt và báo `sent=false`.
- Chưa gửi trace/score lên Langfuse Cloud/self-host, chưa dựng server và chưa dùng dữ liệu thật. LF-2B chỉ mở sau DEP-01 environment mapping đã ký, lựa chọn đích đến, phê duyệt privacy/egress/retention/RBAC và chỉ dùng dữ liệu tổng hợp.
- Commit triển khai: `5d77423` (`feat: bổ sung Langfuse LF-2A và LF-3A`), đã push. CI run `42565258509` **failed** ở bước thu thập test vì `scripts` không phải package khi pytest chạy từ thư mục gốc; commit `2f51585` sửa test nạp module theo đường dẫn file.
- CI run `42565430193` cho commit `2f51585`: **success** cả Frontend checks, Backend unit tests và Backend integration (disposable PostgreSQL + pgvector).

## 4. Quyết định đã chốt và việc còn phải duyệt

### 4.1. Quyết định phạm vi đã chốt ngày 2026-11-07

1. Ưu tiên đầu tiên: Workflow cốt lõi F2.01 + F2.02.
2. Chỉ lập plan chi tiết cho batch đầu; các nhóm Phase 2 còn lại ở mức roadmap.
3. F2.07 loại khỏi vòng triển khai này; giữ nguyên retention thủ công an toàn của Phase 1.
4. Candidate Rediscovery để ở cuối Phase 2, không thuộc batch đầu.
5. F2.08 SSO tiếp tục tạm treo.

### 4.2. Quyết định còn phải chốt trước khi triển khai batch đầu

Các quyết định D-01…D-10 tại Mục 3 của `doc/PHASE2_IMPLEMENTATION_PLAN.md`, đặc biệt:

- Job-family taxonomy, chủ sở hữu/publish template và chuẩn hóa `level_band`.
- Thang scorecard, điều kiện submit, deadline mặc định và phạm vi email reminder.
- Quyền xem scorecard và xác nhận HR private notes luôn tách khỏi HM view.

### 4.3. Quyết định để dành cho các plan sau

- Định nghĩa HR override và metric dictionary cho F2.03.
- QA sampling/reviewer/flag handling cho F2.04.
- Mức hiển thị cross-position duplicate cho F2.05.
- Ngưỡng OCR/manual review cho F2.06.
- Quyền và trường dữ liệu export cho F2.09.
- Consent/retention/quyền tái sử dụng CV cho Candidate Rediscovery cuối Phase 2.

## 5. Blocker và điều kiện mở khóa

| Mã | Hạng mục | Trạng thái | Điều kiện mở khóa |
|---|---|---|---|
| P2-B01 | Phạm vi/ưu tiên batch đầu Phase 2 | ĐÃ CHỐT | Workflow cốt lõi F2.01 + F2.02; chỉ lập plan chi tiết batch đầu |
| P2-B02 | Plan chi tiết batch Workflow Core | CHỜ DUYỆT PLAN | Người dùng duyệt `doc/PHASE2_IMPLEMENTATION_PLAN.md` |
| P2-B03 | Quyết định nghiệp vụ D-01…D-10 | CHỜ HR/HR LEAD + HM/IT | Chốt taxonomy/template ownership, chuẩn hóa level, scorecard, deadline, reminder và quyền xem |
| P2-B04 | Nội dung rubric mẫu và dữ liệu kiểm thử nghiệp vụ | CHỜ HR CUNG CẤP | Có taxonomy đã duyệt và ít nhất một rubric draft thực tế để kiểm thử |
| P2-B05 | Phase 1 Production gates đang tạm dừng | KHÔNG CHẶN LẬP PLAN | Chỉ chặn nghiệm thu Production/dữ liệu thật; không chặn thiết kế hoặc dev bằng dữ liệu tổng hợp |
| P2-B06 | SSO | TẠM TREO | Chỉ mở lại khi người dùng yêu cầu |
| P2-B07 | F2.07 Retention automation | LOẠI KHỎI VÒNG NÀY | Chỉ xét lại khi có quyết định mới; quyết định Legal về hold/OTP/chữ ký vẫn cần nếu mở lại |
| P2-B08 | Candidate Rediscovery | ĐỂ CUỐI PHASE 2 | Chỉ lập plan sau khi chốt consent, retention và quyền tái sử dụng CV |
| P2-B09 | Triển khai UI/UX Recruitment Workspace | ĐÃ TRIỂN KHAI Ở CODE — CHỜ CI/STAGING | Đẩy commit và theo dõi CI; usability HR/HM chỉ thực hiện trên staging với dữ liệu tổng hợp sau khi DEP-01/điều kiện dữ liệu cho phép. UX-5 cần contract/đánh giá riêng |
| P2-B10 | Langfuse staging/pilot | LF-2A/LF-3A ĐÃ Ở CODE; LF-2B CHƯA MỞ | DEP-01 environment mapping, chọn Cloud project riêng hoặc self-host, duyệt privacy/egress/retention/RBAC; chỉ dùng dữ liệu tổng hợp cho tới khi có phê duyệt dữ liệu thật |

## 6. Quy ước cập nhật file này

Sau khi plan được duyệt và mỗi batch triển khai hoàn thành, bổ sung:

1. Trạng thái mới trong bảng tổng quan.
2. File/code/migration đã thay đổi.
3. Lệnh test đã chạy và kết quả.
4. Commit hash sau khi push và CI run tương ứng nếu có.
5. Blocker còn lại và điều kiện mở khóa.
