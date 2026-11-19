# Update Execute — Phase 2

> File này ghi lại quá trình rà soát, lập plan và triển khai Phase 2 theo quy ước giống `Update_Excute_P1.md`: trạng thái tổng quan, thay đổi file/code/migration, test đã chạy và kết quả, commit hash sau khi push, blocker và điều kiện mở khóa.
>
> **Trạng thái hiện tại:** đã hoàn thành rà soát tài liệu/code và lập plan chi tiết cho batch đầu Workflow Core. **Chưa triển khai tính năng nghiệp vụ Phase 2 F2.01/F2.02; plan đang chờ duyệt và các quyết định nghiệp vụ D-01…D-10 đang chờ chốt. Lộ trình UI/UX Recruitment Workspace UX-0…UX-4 đã được triển khai ở code và kiểm chứng tự động; usability/staging vẫn là gate riêng. Langfuse AI Observability đã có plan riêng; LF-1, LF-2A và LF-3A đã triển khai ở code ở chế độ tắt mặc định, metadata-first, fail-open; chưa bật server/staging và chưa gửi trace thật.**
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
| P2-3 | Triển khai/test/CI batch Workflow Core | CHƯA BẮT ĐẦU | Chỉ thực hiện sau khi plan và D-01…D-10 được duyệt |
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

### 4.2. Quyết định batch đầu đã chốt

D-01…D-10 đã được người dùng chấp thuận theo `doc/PHASE2_IMPLEMENTATION_PLAN.md`; không tự tạo nội dung rubric nghiệp vụ. Hai luồng phê duyệt criteria dual và direct đều được giữ. Các chi tiết UI và validation vẫn cần hoàn thiện và kiểm thử.

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
| P2-B02 | Plan chi tiết batch Workflow Core | ĐÃ DUYỆT, ĐANG TRIỂN KHAI | Hoàn thiện code/UI và kiểm thử theo plan |
| P2-B03 | Quyết định nghiệp vụ D-01…D-10 | ĐÃ CHỐT | Thực hiện theo plan đã điều chỉnh |
| P2-B04 | Nội dung rubric mẫu và dữ liệu kiểm thử nghiệp vụ | CÓ ĐỀ XUẤT — CHỜ HR/HM RÀ SOÁT | Đã có đề xuất Python Backend trong code; chưa có draft thực tế trong database và chưa có nội dung nghiệp vụ được duyệt |
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


## 7. Batch F2.01/F2.02 — code local, chưa nghiệm thu/deploy

- `00023_phase2_workflow_core.sql`: seed đúng hai family (không seed rubric nghiệp vụ); backfill position chỉ với chuỗi khớp chính xác code/name, giữ text cũ nếu không khớp. Rubric có template/version/item, bản published/archived bất biến và có provenance về criteria. HR tạo draft, HR Lead system publish; cần revision đúng khi publish. Áp dụng tạo criteria draft, bảo toàn hai luồng dual/direct approval.
- Shortlist share mới tạo scorecard theo assessment snapshot, score 1–5 hoặc thiếu bằng chứng, 4 mức khuyến nghị; HM lưu/submit, HR xem/mở lại có lý do, đổi hạn. Lý do mở lại chỉ HR có quyền xem. Share legacy không backfill; share không có snapshot chờ HR đánh giá và chia sẻ lại. HR xem được lịch sử share bị thu hồi, HM cũ/HM khác không xem. Scorecard không thay đổi trạng thái hồ sơ.
- UI VI/EN: thư viện rubric, chọn family cho vị trí, áp dụng vào vị trí, scorecard trong shortlist, chọn hạn khi share. Nhắc hạn in-app trên dashboard/shortlist: quá hạn hoặc trong 24 giờ, hiển thị tối đa 100 share gần hạn nhất. Ngày làm việc là thứ Hai–thứ Sáu theo Asia/Ho_Chi_Minh, giữ giờ tạo, không tính lễ; chọn hạn thủ công theo múi giờ trình duyệt. Không có email.
- PostgreSQL disposable local: full backend **348 passed, 10 warnings**; frontend type-check/lint/i18n/unit/build pass (unit 7). Ruff F và `git diff --check` pass. Kiểm thử tổng hợp gồm permission/immutability/revision, dual/direct, snapshot, HM change/revoke, stale scorecard write khi thu hồi, xóa cascade scorecard/reopen events qua retention với Storage mock và exact-only backfill riêng; không chứng minh Storage hay môi trường thật. Các test UI helper không thay thế browser E2E.
- **Schema đã áp trên project test, app chưa deploy**: migration 00023 đã áp local disposable PostgreSQL (digest shim test-only) và Supabase test `myrymlqdbyqmpynesiwk`, version `20261116081146`. Chưa áp môi trường khác. Bản app này phụ thuộc schema 00023; preflight riêng trước khi deploy app hoặc áp schema ở môi trường khác. E2E tổng thể, benchmark và vận hành/production tiếp tục tạm treo; không coi test local là nghiệm thu. F2.07 ngoài vòng, SSO treo, Rediscovery cuối Phase 2.
- Nội dung rubric thật chưa được HR cung cấp; không nhập dữ liệu CV/JD thật vào các kiểm thử. Cần đánh giá usability HR/HM, quy tắc giờ đến hạn, thông báo, quyền/audit và retention trong bối cảnh triển khai thực tế khi các gate được mở lại.
- Commit code `f8d622c` đã push; GitHub Actions CI run `43828487353` pass cả frontend, backend unit và backend integration trên PostgreSQL disposable. CI không phải E2E/kiểm thử triển khai thật.

## 8. Áp migration 00023 lên Supabase test

- Người dùng yêu cầu áp migration. Project `myrymlqdbyqmpynesiwk`; preflight: 6 positions, 9 criteria versions, 40 items, 1 share/1 item, 0 active operations, 0 processing deletion, 0 family match chính xác và không có đối tượng mới trùng tên. Không tạo backup trong lượt áp này.
- `phase2_workflow_core` đã được ghi trong lịch sử migration remote version `20261116081146`; file local SHA-256 `7e10d5ea098c7d5491f145a2def8d597a5fdc492f2e174f57a6aacbc876c73a4`.
- Hậu kiểm chỉ đọc: số position/criteria/share không đổi; đúng 2 job families; 0 position liên kết qua backfill, 0 template nghiệp vụ và 0 scorecard (không backfill share legacy); 7/7 bảng mới bật RLS, anon/authenticated không có SELECT trên các bảng đó, 4/4 trigger bất biến bật, constraint origin gồm `TEMPLATE_CLONE`. Đây không thay thế kiểm thử runtime hoặc đánh giá toàn diện RLS.
- **Chưa deploy backend/frontend mới**, chưa thực hiện E2E tổng thể, pilot hoặc production. Không chuyển gate tạm treo sang PASS.

## 9. Đề xuất rubric Python Backend khởi đầu

- Theo yêu cầu người dùng, tạo đề xuất tại `doc/RUBRIC_PROPOSAL_PYTHON_BACKEND.md` và dữ liệu `frontend/src/data/rubric-proposal-it-backend.json`: 5 tiêu chí, nhóm bắt buộc/ưu tiên 70/30. Ngưỡng Python backend tối thiểu 4 năm được giữ; các trọng số và tiêu chí còn lại cần HR/HM rà soát, không tự động loại ứng viên.
- UI có nút điền đề xuất vào biểu mẫu; **không tự lưu, không xuất bản, không áp vào vị trí và không ghi Supabase**. HR cần dùng tài khoản hợp lệ để rà soát/lưu draft sau khi app được deploy; HR Lead quyết định publish. Chưa có draft thực tế trên database, chưa deploy app.
- PostgreSQL disposable: full backend **352 passed, 10 warnings**, gồm lưu draft bằng tài khoản HR tổng hợp, quyền publish, giữ ngưỡng 4 năm và kiểm tra lựa chọn framework; frontend type-check/lint/i18n/unit/build pass; Ruff F và `git diff --check` pass. Test tổng hợp/local không thay thế browser E2E, kiểm chứng môi trường thật hay nghiệm thu nghiệp vụ. E2E tổng thể, benchmark và vận hành vẫn tạm treo.

## 10. Đổi ưu tiên theo yêu cầu người dùng — tạm treo công việc hiện tại

- Tạm treo công việc đang thực hiện trước đây, bao gồm triển khai/HR chuẩn hóa đề xuất rubric và các bước F2.01/F2.02 còn chờ; không thay đổi kết quả hay đóng các gate Phase 1/2. CI của commit rubric `06c83f3`: run `43830675762` pass; chưa deploy, chưa có draft thật trong database.
- Ưu tiên mới: cổng công khai cho vị trí đang hoạt động, còn hạn và form ứng tuyển/CV đi vào hệ thống; triển khai ưu tiên một phần F3.01 Talent Pool/Rediscovery và F3.03 Gmail thử nghiệm. Quyết định này **thay thứ tự** trước đây “Rediscovery để cuối Phase 2”, nhưng không thay thế yêu cầu consent, retention và quyền dùng lại CV.
- Khảo sát bước đầu và plan/gate tại `doc/PUBLIC_CAREERS_TALENT_POOL_EMAIL_PLAN.md`. Hiện chưa triển khai các chức năng mới, chưa deploy, không thao tác Gmail/Supabase; cần chốt một số lựa chọn nghiệp vụ và điều kiện dùng dữ liệu trước khi mở dữ liệu thật. Không đưa CV, JD nội bộ, token hoặc email thật vào Git.

## 11. Lát cắt ưu tiên mới — demo tổng hợp trong code

- Đã ghi nhận lựa chọn: hiển thị mọi vị trí `OPEN` có hạn còn hiệu lực (HR rà soát JD), thiết kế opt-in Talent Pool riêng, email demo offline trước. Trước dùng dữ liệu thật vẫn cần phê duyệt notice/consent, thời hạn, quyền, rút consent và bảo vệ dữ liệu.
- Đã làm cổng `/careers-demo`, trường hạn do HR sửa, intake demo vào application/batch/worker, actor nguồn demo không mạo danh HR; chỉ hoạt động khi bật và trỏ DB disposable local `_test`, Storage local. Chưa thể nộp nếu rubric JD mới nhất chưa APPROVED; giới hạn 100 job. Mặc định tắt, không dành cho Internet/CV thật; chưa có AV/anti-spam/rate limiting hay notice được duyệt.
- F3.01 hiện chỉ có thiết kế opt-in và hàm eligibility với dữ liệu giả, chưa lưu consent, rút consent, pool, tìm kiếm hay xếp hạng hồ sơ thật. F3.03 chỉ là script MIME offline với dữ liệu giả, chưa có Gmail/OAuth, spam/antivirus, kết nối intake hay tạo hồ sơ từ email.
- Migration `00024_careers_demo.sql` mới áp local disposable, **chưa áp Supabase**; chưa deploy, chưa thực hiện E2E trình duyệt hoặc nghiệm thu. Backend full 356 pass trước test tranh chấp bổ sung; `test_careers_demo.py` 3 pass sau bổ sung; frontend type-check/lint/i18n/unit/build pass. Chi tiết, lệnh demo, giới hạn, gate và công việc tiếp theo: `doc/PUBLIC_CAREERS_TALENT_POOL_EMAIL_PLAN.md`.

## 12. Tiếp tục ưu tiên: opt-in Talent Pool và email offline demo

- Form synthetic có opt-in riêng, thời hạn demo 7 ngày và mã rút ngẫu nhiên chỉ lưu hash; HR có quyền cả nguồn/đích có thể kiểm tra pool demo trên `/talent-pool-demo` với rubric đích duyệt, loại consent hết hạn/đã rút, hồ sơ chờ xóa, nguồn CLOSED và CV chưa xử lý. Không đánh giá/xếp hạng/tự liên hệ, không áp dụng consent hay retention thật. Quyền rút demo không xóa hồ sơ/CV và không thu hồi kết quả đã hiển thị.
- `/email-demo` cho HR tải EML tổng hợp offline, đối chiếu mã và đính kèm, nối vào hàng đợi demo với nguồn `EMAIL_DEMO`; From không được tin, không suy consent. REVIEW hiện chỉ trả tại thời điểm thao tác; chưa có hàng review/dedupe mailbox bền vững, quét malware/spam hay kết nối Gmail. Script `backend/scripts/demo_email_offline.py` tạo fixture EML tổng hợp theo mã yêu cầu.
- Migration `00025`, `00026` chỉ áp PostgreSQL disposable cục bộ, **chưa áp Supabase/chưa deploy**. Chức năng demo vẫn mặc định khóa, không sử dụng dữ liệu thật. Backend synthetic local full suite **359 passed, 10 warnings** trước test tranh chấp mới; test riêng quét chờ lock khi rút consent **1 passed**; frontend type-check/lint/i18n/unit/build pass. CI commit trước `d1a4c96` run `44004533718` pass. Chi tiết và các gate tại `doc/PUBLIC_CAREERS_TALENT_POOL_EMAIL_PLAN.md`; không coi test local/CI là nghiệm thu.

## 13. Chuẩn bị môi trường trình diễn tổng hợp

- Đã tạo wrapper backend độc lập với session HR giả, profile AI giả và không chạy assessment/ranking; không Supabase/Gmail/external API. Trang `/demo` liên kết cổng ứng tuyển, workspace HR, file CV/email giả tải về. Chỉ DB local tên demo `_test` và Storage demo riêng được phép; link preview có thể truy cập bằng link và không phải lớp bảo mật để dùng dữ liệu thật.
- Đã tạo DB `hra_careers_demo_test` để chạy E2E và DB `hra_careers_ready_test` riêng để trình diễn sạch; đều trên PostgreSQL local disposable, migration 00001–00026 (shim digest SHA-256 chỉ trong cụm test). Seed 2 vị trí giả và 1 ứng viên giả opt-in; không chạm Supabase. Chưa deploy.
- Browser E2E Chromium trên local pass: ứng tuyển CV giả/opt-in, worker, quét pool HR, rút và quét lại, upload email EML giả và thấy application. Lượt test đầu phát hiện worker cố chạy assessment không có LLM; wrapper đã tắt assessment/ranking rõ ràng, chạy lại E2E pass, hai operation demo đều COMPLETED. Không chứng minh AI matching hoặc Gmail.
- Runbook/kịch bản: `doc/HUONG_DAN_DEMO_TUYEN_DUNG.md`. Frontend preview `DEMO_PREVIEW=1` chuyển `/` sang `/demo`; runtime sandbox tạm thời, dữ liệu có thể mất. Các gate bảo mật, consent thật, anti-spam/AV và Gmail vẫn mở.
- Bổ sung kiểm tra sau chuẩn bị: frontend type-check/lint/i18n/unit pass; backend `test_careers_demo.py` + `test_priority_demo.py` 8 pass; Ruff F và `git diff --check` pass. CI commit trước `5f5c10f`: run `44006315383` pass.

## 14. Yêu cầu mới: đấu nối thật vào VPS để test

- Người dùng muốn đưa ba hạng mục vào hệ thống VPS hiện tại và test kết nối thực. Môi trường/project đích và phạm vi dữ liệu chưa được xác minh; không mặc định cho phép dùng dữ liệu ứng viên thật hoặc coi gate production đã đóng.
- Đã lập `doc/VPS_REAL_INTEGRATION_PREFLIGHT.md`: phân biệt demo guarded/giả lập với tính năng thực chưa xây đủ; preflight chỉ đọc, quyết định môi trường & dữ liệu, Gmail test OAuth, backup/restore, malware/anti-abuse, consent/retention và thứ tự triển khai. Không deploy, áp migration, khởi động lại, purge, đọc Gmail hoặc thay đổi Supabase trong lượt này. Phiên agent không có đường SSH trực tiếp tới VPS; operator cần chạy bước trên VPS khi đã xác nhận.
- CI commit `cab29b7`: run `44008706147` pass. CI không thay thế smoke VPS, E2E tích hợp thực hay phê duyệt dữ liệu.

## 15. Chốt môi trường test và chuẩn bị Gmail smoke

- Người dùng chọn VPS hiện tại + project Supabase test trước đây; tích hợp thật nhưng **chỉ dùng dữ liệu tổng hợp**, đã có Gmail test và sẽ cấp OAuth. Không suy ra quyền dùng CV thật, backup hay deploy đã xong.
- Supabase read-only: project `myrymlqdbyqmpynesiwk` healthy DB/Auth/Storage/REST, remote 00023 `20261116081146`; aggregate 6 positions/7 applications, 0 active operations/deletions, chưa có cột deadline demo. Không thao tác ghi, không chứng minh VPS trỏ đúng project; số liệu có thể thay đổi.
- Đã chuẩn bị script `backend/scripts/gmail_readonly_smoke.py` và optional dependency `gmail-smoke`: Gmail OAuth Desktop với scope chỉ đọc, callback loopback qua SSH tunnel, query nhãn `HRA_TEST`, chỉ in count, không lưu token hay đưa CV vào HRA; unit mock 2 pass. Chưa chạy trên VPS/Gmail thật, chưa có ingestion. Setup/giới hạn và preflight chỉ đọc: `doc/VPS_REAL_INTEGRATION_PREFLIGHT.md`.

## 16. VPS preflight vòng 1 do operator cung cấp

- Checkout `~/hra` tại `94e38d9`, tracked sạch; `hra-backend`/`hra-frontend` và hai process khác đều online. Backend `:8005` health healthy, readiness ready/database connected, `APP_ENV=production` theo health. Checkout không chứng minh commit code đang chạy; chưa chứng minh DB nào đang kết nối hoặc frontend build/version.
- Chưa deploy, restart, migration, OAuth hay xóa dữ liệu. Đối chiếu `doc/VPS_REAL_INTEGRATION_PREFLIGHT.md` cho các điểm còn thiếu và bảo vệ hai process còn lại; tiếp tục dùng dữ liệu tổng hợp, không tắt guard demo.

## 17. VPS preflight vòng 2 và nền quét mã độc

- Operator xác nhận stack chỉ để test; chưa có backup DB, dữ liệu test không ưu tiên bảo toàn. Frontend `:3005` HTTP 200 và listen `0.0.0.0`; backend `:8005` listen `127.0.0.1`. Chưa xác minh firewall/TLS hay mapping PM2; không suy frontend chắc chắn public. Chưa có quyết định xóa/reset, backup Storage hoặc phương án rollback cho thay đổi cụ thể.
- Chuẩn bị adapter `app/services/malware_scan.py` ClamAV INSTREAM Unix socket với fail-closed timeout/size/protocol/scanner failures, test fake local socket. **Chưa tích hợp intake, chưa cài/kiểm thử ClamAV thật trên VPS, chưa triển khai**; chi tiết và gates trong preflight.

## 18. Triển khai thực — lát cắt danh sách việc làm

- Theo yêu cầu hoàn thiện FE/BE/DB, đã code migration `00027_careers_real_listing.sql` độc lập với migration demo; API thật `GET /v1/careers/jobs` có flag `PUBLIC_CAREERS_ENABLED=false`, danh sách OPEN/còn hạn/JD mới nhất và phân trang; FE `/careers` public chỉ xem danh sách, cảnh báo chưa nhận CV, HR thấy cảnh báo rà soát JD khi sửa hạn.
- DB integration test dùng riêng disposable `hra_careers_real_test` schema tới 00023 + 00027; không áp Supabase. 2 test danh sách pass (105 vị trí, filter, pagination, flag), cộng scan/OAuth mock tổng 12 pass. FE type-check, lint, i18n/unit/build pass. Không nhầm với kiểm thử end-to-end thật.
- 00024–00026 vẫn demo-only: không tự chạy chuỗi migration lên remote. Chưa deploy/bật flag; cần review công khai JD, topology, firewall, kế hoạch migration/rollback. Intake CV thật, pool và Gmail còn chưa hoàn thiện, chi tiết trong `doc/VPS_REAL_INTEGRATION_PREFLIGHT.md`.

## 19. Nền Talent Pool thật FE/BE/DB

- Tạo migration `00028_talent_pool_real.sql` độc lập demo, bảng consent/expiry/retention/withdraw, RLS; helper server-only lưu hash token, không opt-in dữ liệu cũ. API withdrawal idempotent và scan HR kiểm quyền hai vị trí, tình trạng nguồn/đích, consent, retention, CV và audit; 2 flag mặc định tắt tách khả dụng withdrawal và rediscovery. FE `/talent-pool` cho HR và `/pool-withdraw` token trong body.
- Integration test PostgreSQL local disposable kiểm thử quyền, hết hạn, case retention, CV chưa xử lý, rút khi scan tắt, rút đồng thời với scan (quan sát lock thực); FE type-check/lint/i18n/unit/build pass. Không truy cập Supabase/VPS, không browser E2E.
- **Chưa hoàn thiện toàn bộ**: primitive consent chưa nối form intake thật; notice/thời hạn và mất mã chưa được duyệt, chưa có matching/link/contact; Gmail và CV intake với spam/AV/anti-abuse vẫn chưa có. Không bật các flag, không dùng hồ sơ thật; chi tiết `doc/VPS_REAL_INTEGRATION_PREFLIGHT.md`.
- Kiểm tra tương thích toàn bộ backend: database disposable riêng `hra_all_real_test` với schema nền và 00024–00028 áp local; `376 passed, 10 warnings`. Điều này chỉ chứng minh suite local với schema demo và thật cùng tồn tại, không phải hướng dẫn áp migration demo lên Supabase hay nghiệm thu tích hợp VPS.

## 20. Nối intake synthetic qua hạ tầng thật (chưa triển khai)

- Đã nối FE `/careers`, API apply, DB `00029`, worker và opt-in riêng Talent Pool. `PUBLIC_CAREERS_TEST_INTAKE_ENABLED` mặc định false, chỉ nhận email `@example.test`; chống mã độc bằng ClamAV fail-closed trước parse, consent/test notice và thời hạn 7 ngày chỉ synthetic. Idempotency theo request/fingerprint và receipt STAGING trước storage upload để có dấu vết đối soát. Worker giữ identity form.
- 5 bài test intake local gồm fail-closed, idempotency/concurrent retry, retry khi lỗi storage mơ hồ, pool withdrawal, worker với mock model; toàn backend `381 passed, 10 warnings`, FE type-check/lint/i18n/unit/build pass. Scanner/model/Storage thật và browser E2E chưa test; chưa áp migration, chưa deploy, chưa bật.
- **Chưa hoàn thiện hết ba luồng**: Gmail OAuth ingestion/spam/AV/dedupe/review chưa có; intake cần edge mạng test/HTTPS/rate/body limit, ClamAV thật, đối soát/cleanup receipt-object và policy/token recovery trước dùng thật. `@example.test` không bảo đảm nội dung CV là giả. Runbook và giới hạn cập nhật trong `doc/VPS_REAL_INTEGRATION_PREFLIGHT.md`.

## 21. Đối soát Storage và nền spam filter

- Đã bổ sung `00030`/storage destination fence và công cụ manual dry-run mặc định; chỉ xử lý receipt STAGING cũ, row lock skip active, bảo vệ object có document tham chiếu, xác minh object không còn, audit/tombstone ABANDONED, lỗi fail-closed. Script có xác nhận, giới hạn lô/tuổi và kiểm tra target Storage; xác minh DB + tắt/drain backend vẫn phải do operator làm. Chưa chạy trên Supabase/VPS, chưa chứng minh SDK thật; receipt thiếu thông tin đích để manual review.
- Chuẩn bị SpamAssassin spamd CHECK Unix socket, timeout/size/protocol fail-closed, unit fake socket. **Chưa nối Gmail hay chạy spamd thật**, không coi HAM là an toàn tuyệt đối.
- Bộ backend local đầy đủ migrations demo+thật `396 passed, 10 warnings`; Ruff F/diff-check pass. Gmail ingestion/dedupe/review/AV thực tế và deploy vẫn còn mở. Chi tiết trong `doc/VPS_REAL_INTEGRATION_PREFLIGHT.md`.

## 22. Người dùng cho phép áp DB; luồng Gmail test

- Người dùng yêu cầu tự làm các phần có thể, áp migration cần thiết và chưa bật HTTPS. Đã dùng connector Supabase project test `myrymlqdbyqmpynesiwk`: preflight 0 operation/deletion active, 6 positions/7 applications; áp gộp 00027–00030 tên `careers_talent_pool_real_00027_00030` remote `20261117043801`, và 00031 `gmail_test_intake_00031` remote `20261117044409`, có lock/statement timeout. Không áp 00024–00026, không backup trước migration theo phạm vi test đã được user chấp nhận, không seed/purge. Sau áp vẫn 6 positions/7 applications, pool/receipt/gmail 0, 0 active ops; RLS bật và anon/authenticated không có quyền SELECT các bảng được kiểm tra. Schema này đã có trên project; không áp lại.
- Code Gmail test FE/BE/DB: OAuth Desktop scope `gmail.readonly` token file ngoài repo, chỉ label HRA_TEST + subject `[HRA-TEST] `, quét antivirus raw → spamd → MIME → antivirus attachment → validate; `EMAIL_TEST` identity giả, không consent pool tự động, dedupe mailbox/message và hàng review, HR Lead/Admin sync thủ công, 5 mail/trang. Cờ tắt mặc định, không phải production hay tự polling. Parser marker/email giả không chứng minh dữ liệu giả.
- Suite local 406 passed/10 warnings với Gmail, scanner, model và Storage test/mocked; FE type-check/lint/i18n/unit/build pass. Sau thay đổi marker đã chạy lại các test Gmail riêng. Chưa connect mailbox, scanner, Storage thật, deploy hoặc browser E2E VPS. Xem `doc/GMAIL_VPS_TEST_RUNBOOK.md` cho cổng 3005 đang 0.0.0.0, dùng SSH tunnel thay HTTPS, OAuth và các bước còn cần operator; không đưa token/URL vào chat.

## 23. Tiền kiểm scanner VPS và script xác minh

- Operator báo `clamd`, `clamscan`, `spamd`, `spamc` chưa có. PM2 PID backend `902622`/frontend `898038` khớp snapshot các process đang nghe `127.0.0.1:8005` và `0.0.0.0:3005`; chưa xác minh firewall hoặc scanner, PID chỉ là snapshot.
- CI commit `85b9466` run `44019434971` pass. Bổ sung `backend/scripts/check_test_scanners.py` thực hiện EICAR/GTUBE và mẫu sạch trong bộ nhớ qua đúng adapter, chạy bằng user backend, in verdict không ghi file; 18 test scanner/script local pass. Chưa có scanner thực tế, chưa chạy VPS hoặc deploy; runbook đã cập nhật. Các bước cài phụ thuộc OS/phiên bản: Ubuntu 22.04 có thể gói spamd khác Ubuntu 24.04; phải xác minh trước, không tự đổi cấu hình hệ thống hoặc firewall.

## 24. Chọn luồng Gmail thử nghiệm rút gọn

- User đồng ý phương án chỉ cài ClamAV, dùng nhãn spam/trash của Gmail thay cho spamd ở vòng dữ liệu giả. Thêm `GMAIL_TEST_GMAIL_SPAM_ONLY` mặc định false: khi true chỉ route Gmail thử nghiệm bỏ qua spamd; Gmail nhãn SPAM/TRASH vẫn bị loại, ClamAV email/attachment vẫn bắt buộc và fail-closed. UI cảnh báo rõ và audit ghi mode cho mỗi xử lý; không thay đổi pool consent hay API Careers. Gmail filtering không tương đương SpamAssassin, không chứng minh nội dung an toàn. Cờ không biến hệ thống thành phù hợp dữ liệu thật; mailbox/marker không chứng minh synthetic.
- Script kiểm tra scanner hỗ trợ chỉ ClamAV, vẫn kiểm tra spamd khi truyền socket. Backend local 411 passed/10 warnings; FE type-check, lint, i18n, unit và build pass. Một lệnh `npm test` thử nhầm không tồn tại, sau đó chạy đúng `npm run test:unit` và build. Chưa deploy/khởi động/cài trên VPS; chưa chạy scanner/Gmail thật. Chi tiết lệnh tuần tự và gate: `doc/VPS_THU_NGHIEM_RUT_GON.md`.

## 25. Tài nguyên VPS cho ClamAV

Operator báo Ubuntu noble arm64 package candidate ClamAV `1.5.4+dfsg-0ubuntu0.24.04.1`, RAM 3.8 GiB với 2.5 GiB available, swap 4 GiB với 1.5 GiB used, `/` còn 13 GB/45 GB. Có thể thử cài sau khi chú ý tải VPS, nhưng cần theo dõi RAM/swap và tình trạng các app sau khi nạp signature; không đảm bảo đủ. Chưa cài hoặc test scanner. CI commit `02e816b` run `44031133790` success.

## 26. Hoàn thiện vòng dữ liệu giả trong lúc chờ VPS

- Careers: mô tả lỗi, kết quả chưa rõ và retry cùng form/request ID, không tuyên bố chống mọi hồ sơ trùng; backend trả 400 cho tệp rỗng/quá lớn trước scanner/parse. UI phân biệt đã tiếp nhận với xử lý hoàn tất.
- Gmail test: HR Lead/Admin có thể thử lại từng REVIEW theo receipt đúng mailbox, không tự nhập lại trạng thái SPAM/MALWARE/ACCEPTED; audit mode và retry. Có thể xác nhận tên/email giả cho EMAIL_TEST ACCEPTED sau khi tác vụ vị trí hoàn tất; khóa quyền/position/application, chống ghi đè đồng thời qua `updated_at`, không sửa hồ sơ có retention case, invalidate tín hiệu trùng PENDING khi cập nhật và audit không chép nội dung. `@example.test`/xác nhận không chứng minh dữ liệu giả, không tạo consent hay xác minh danh tính thật. Không chỉnh sửa mail; inbox list vẫn giới hạn 100 bản ghi mới nhất.
- Talent Pool: UI nêu kết quả tìm chỉ snapshot, cần tìm lại trước khi dùng; withdrawal phản hồi đồng nhất không tiết lộ token tồn tại; chưa có cơ chế tự khôi phục token.
- Local disposable backend **416 passed, 10 warnings**, bao gồm quyền, sai mailbox, retry/dedupe, mutation race, retention, input sai và fail-closed; FE type-check/lint/i18n/unit/build pass. Không thêm migration, không deploy hoặc thay đổi DB/VPS; chưa chạy Gmail/ClamAV/E2E thật. Runbook cập nhật `doc/VPS_THU_NGHIEM_RUT_GON.md`.

## 27. Tiếp tục kiểm thử trong khi chờ VPS

- Test Playwright mới `test:e2e:intake-mock` chặn và mock mọi `/v1`, chạy trên Next loopback + Chromium: Careers mất phản hồi, retry cùng request/token, withdrawal, Gmail review/retry/xác nhận, pool scan và HTML khi JavaScript tắt đều pass. Từ kiểm thử phát hiện form rút có thể hoạt động trước hydration; đã disable form cho đến khi React sẵn sàng, thông báo cần JavaScript. Kết quả là UI giả, không phải E2E Gmail/DB/Storage thật.
- Thêm test local PostgreSQL cho đồng bộ Gmail cùng lúc và mất phản hồi sau commit, retry chỉ tạo một application/receipt. Full backend chạy lại tuần tự **418 passed, 10 warnings**; FE type-check/lint/i18n/unit/build pass sau `npm ci`. Lần chạy suite song song FE trước đó 417 pass/1 fail ở test cũ `test_superseded_worker_cannot_commit_after_database_connection_loss` (timeout chờ worker phục hồi); chạy riêng pass và full tuần tự pass, nguyên nhân chưa kết luận, cần theo dõi flaky test. CI `57f26b7` run `44231367729` success.
- Không có migration mới, chưa cài/deploy ClamAV, chưa cấp OAuth hay chạy E2E VPS thật. Tiếp tục chỉ dữ liệu giả.

## 28. VPS scanner, deploy và bộ demo dữ liệu giả

- Operator báo `clamav-daemon.socket`, `clamav-daemon`, `clamav-freshclam` active; socket `/run/clamav/clamd.ctl` owner `ubuntu:clamav` mode 0660; `ScanMail`, `ScanArchive`, `AlertEncrypted`, `AlertExceedsMax` true/yes. Smoke adapter trên VPS: CLEAN mẫu sạch, INFECTED EICAR; PDF giả mã hóa bị chặn (INFECTED heuristic). Kiểm tra này không bảo đảm mọi malware, freshness hoặc xử lý mọi giới hạn/timeout; user backend dùng chung OS user ubuntu nên các process khác cùng user cũng có thể truy cập socket.
- Operator báo `.env` VPS trỏ đúng Supabase test, được sửa trước backend start theo UTC; các cờ Careers/Pool/Gmail/demo chưa đặt ở thời điểm trước deploy. Marker deploy HRA `a218217`, không restart chờ; backend ready, frontend và API proxy HTTP 200; log cuối smoke deploy chưa được cung cấp. Hai app khác có restart do operator tự cập nhật, không liên quan kết luận test HRA. HRA có thể truy cập Internet theo operator; chưa chứng minh cô lập cổng/proxy, chưa bật cờ hoặc kết nối OAuth/Gmail, chưa E2E Storage/worker/VPS.
- Tạo bộ `doc/BO_DEMO_TUYEN_DUNG/` gồm kịch bản có gate an toàn, 2 JD, 3 CV giả (2 DOCX, 1 PDF text), mẫu email hợp lệ/thiếu file. Local `document_processor` xác nhận 3 CV đúng loại, trích xuất trên 350 ký tự; parser MIME giả xác nhận 1 mã/1 tệp và REVIEW khi thiếu tệp. Bài test dùng detected MIME như worker. Đây không chứng minh kết quả VPS hoặc AI scoring. Kịch bản nhấn mạnh không gửi token/dữ liệu thật qua HTTP công khai, không giả mạo pass, không suy consent, không tự xóa hay chạy demo migrations.

## 29. Mở rộng demo IT theo yêu cầu operator

- Operator xác nhận truy cập trực tiếp HTTP qua IP công khai cổng 3005 và lựa chọn không giới hạn mạng trong vòng demo. HTTP không mã hóa và intake thiếu bảo vệ abuse; chỉ dữ liệu/tài khoản test, không coi là cấu hình an toàn/production. Không thay firewall hoặc bật tính năng thay operator. Trình duyệt thường không cho `crypto.randomUUID` ở HTTP/IP; có thể truy cập `localhost:13005` qua SSH tunnel mà không đổi firewall, tunnel không tự đóng cổng công khai.
- Mở rộng bộ thành 5 JD IT và 30 CV tổng hợp; bảng `BANG_PHAN_BO_30_CV.md` quy định nguồn, opt-in dự kiến và gợi ý HR đối chiếu. Talent Pool scan chỉ lọc điều kiện, không chấm hay xếp hạng theo JD; CV thiên Java có thể xuất hiện khi scan sang Data nếu đủ consent/điều kiện. Không tự tạo consent hoặc seed dữ liệu, chưa chạy E2E VPS.

## 30. Tiền kiểm cờ trên VPS trước demo

- Operator kiểm tra theo môi trường tiến trình và `.env` hiện tại: `PUBLIC_CAREERS_ENABLED`, `PUBLIC_CAREERS_TEST_INTAKE_ENABLED`, `TALENT_POOL_STORAGE_READY`, `TALENT_POOL_REDISCOVERY_ENABLED`, `GMAIL_TEST_INGEST_ENABLED`, `GMAIL_TEST_GMAIL_SPAM_ONLY` đều false; `CLAMAV_UNIX_SOCKET` và `GMAIL_TEST_TOKEN_FILE` chưa cấu hình. Storage backend supabase; `clamav-daemon`, socket và `freshclam` active; `/health/ready` báo ready/database connected, APP_ENV production. Đây là cấu hình suy ra từ env tiến trình + file hiện tại, không bảo đảm file đã được backend nạp lúc khởi động nếu file mới thay đổi sau đó.
- Read-only Supabase project test `myrymlqdbyqmpynesiwk`: tại thời điểm kiểm tra active operations 0, vị trí OPEN còn hạn 0, consent chưa rút còn hạn 0. Không bảo đảm các số không đổi trước restart. Dự kiến cấu hình Careers/Pool trước, Gmail sau OAuth; không chạy migration hay xóa dữ liệu. Bật public listing sẽ hiển thị mọi vị trí OPEN còn hạn, không chỉ JD demo; HTTP public chỉ thử dữ liệu giả, không phải production.
- Operator đã chỉnh `/home/ubuntu/hra/backend/.env`: 4 cờ Careers/Pool `true`, `CLAMAV_UNIX_SOCKET=/run/clamav/clamd.ctl`; mỗi khóa có một dòng và không có trong môi trường process trước restart. Gmail vẫn chưa cấu hình. Chưa xác nhận restart/nạp cờ. Snapshot Supabase read-only kế tiếp: active operations 0, vị trí OPEN còn hạn 0; không thay thế kiểm tra trước restart.
- Operator xác nhận restart và hậu kiểm backend ready, Careers API HTTP 200 như dự kiến. Chưa kiểm tra ứng tuyển/Storage/worker/Pool/Gmail thật. Lưu ý code tạo JD mặc định ngôn ngữ `en`, trong khi bộ JD demo là tiếng Việt: tạo phiên bản JD `vi` có thay đổi nội dung trước khi duyệt tiêu chí; đã cập nhật bộ kịch bản/ZIP.

## 31. Rà soát workflow và UI/UX HR/HM — lập plan, tạm dừng demo

- Theo phản hồi người dùng, tạm dừng thực nghiệm Careers/Pool/Gmail để rà soát luồng tạo vị trí/JD/duyệt/danh sách ứng viên/xếp hạng/shortlist HM; chưa thay đổi code hay deploy VPS. Plan mới: `doc/PLAN_CAI_TIEN_WORKFLOW_UX_HR_HM.md`.
- Rà code xác nhận tạo vị trí hiện là popup, JD version đầu luôn `en`; UI applicant mặc định `REVIEW_PRIORITY` ưu tiên hồ sơ cần xử lý chứ không theo `rank_number`, nên số hạng hiển thị có thể không theo thứ tự; đã có nút sort rank, work queue, workspace và side-by-side nên cải tiến trên nền sẵn có. Unit test frontend hiện có `8 passed`, trong đó xác nhận review priority đặt lỗi file trước thứ hạng; không phải usability hay VPS E2E.
- Công cụ đọc trang truy xuất được cả 2 link người dùng đưa, thấy heading Job Description + Requirements và form theo sau, có cả hướng dẫn ứng tuyển; chưa thử HTTP adapter HRA/egress VPS. Plan thiết kế preview/extraction theo cấu trúc, fallback, chặn SSRF, giới hạn tài nguyên; `.doc` legacy hiện chưa hỗ trợ, khác DOCX và cần converter riêng. Không dùng source công khai làm dữ liệu demo IT hay tự lưu lên VPS. Plan yêu cầu giữ RBAC, consent, tách review priority khỏi matching rank, không thay engine ngầm.

## 32. Chốt phạm vi nhập JD theo HR

- Anh xác nhận HR phải chọn một trong ba cách nhập (dán, upload, link); phải có nội dung JD mới tạo vị trí. Không thêm nháp vị trí không JD. Vòng đầu upload `.docx`/`.txt`, chưa hỗ trợ `.doc` legacy. Đã cập nhật `doc/PLAN_CAI_TIEN_WORKFLOW_UX_HR_HM.md`; chưa triển khai code hay thay đổi VPS.

### 33. Triển khai bước đầu UX HR/HM trong workspace — chưa deploy

- Tạo trang riêng `/positions/new`, JD bắt buộc, nhập bằng dán / DOCX-TXT / link VinUni Talent, có preview sửa, ngôn ngữ JD v1 và hạn; scanner fail-closed. Không thay đổi engine matching hay bỏ quyền, consent, approval.
- Thứ tự Xếp hạng mặc định theo rank, chế độ ưu tiên rà soát tách biệt; thêm bộ lọc shortlist. JD hiển thị cạnh tiêu chí; card điều hướng có ngữ cảnh và lọc, inbox chia sẻ lọc theo vị trí, scorecard có link hồ sơ. Số liệu tổng hợp có thể bao gồm trạng thái ngoài sàng lọc.
- Backend không DB: 262 pass, 165 skip; test import và tạo position có mock, không xác nhận transaction PostgreSQL. Frontend build/type/lint, unit 10/10, i18n 3/3; browser mock create/account và shortlist desktop/mobile pass; tất cả API bị mock.
- **Chưa nghiệm thu:** integration PostgreSQL riêng và HR/HM end-to-end, actual URL/ClamAV/Storage trên VPS, baseline usability; URL fetch chưa đảm bảo deadline tổng cho DNS/headers, UI chưa có idempotency server-side hoặc bảo vệ mọi điều hướng khỏi mất form; workspace HM/approval trong plan còn phần chưa hoàn thiện. Xem mục 11 plan để biết chi tiết và các bước tiếp.
- Chưa commit, push, deploy, restart hoặc sửa dữ liệu VPS. Các thay đổi chỉ ở workspace; VPS trước deploy vẫn tạo JD v1 ngôn ngữ mặc định `en`, nên hướng dẫn demo tạo version `vi` vẫn áp dụng tại đó.

### 34. Tiếp tục UX: PostgreSQL disposable và workspace shortlist

- Tạo cụm PostgreSQL 16 hoàn toàn riêng cho test, áp 00001–00031 **chỉ cục bộ**. Backend chạy tuần tự **431 passed**, gồm các test mới cho JD v1 vi/en + timezone, rollback cả giao dịch khi lỗi gán HM và tạo đồng thời bốn mã vị trí không trùng. Auth và `uuid-ossp`/`pgcrypto` bundled là stub; shim `digest` test-only dùng SHA-256 tích hợp của PostgreSQL. Không xem kết quả này là kiểm thử Supabase thật.
- Tách workspace `/shortlist/[share_id]` khỏi dialog, giữ link nhắc hạn cũ, lựa ứng viên và giữ nháp scorecard khi chuyển, chỉ rõ quyền CV và khác biệt giữa JD hiện tại/snapshot; đưa link hồ sơ quay lại share. API từ chối 403/404 thì UI bỏ dữ liệu, kiểm tra lại khi tab trở nên hiển thị; không hứa revoke tức thời trong tab đang mở.
- Thêm timeout phản hồi 20 giây cho URL preview; thread còn bị block có thể tiếp tục giữ một trong hai slot tới khi kết thúc. Test timeout có mock; chưa thử nguồn URL từ VPS.
- Frontend type-check/lint/build, unit 10/10, i18n 3/3 và browser mock tạo vị trí/tài khoản/shortlist desktop-mobile pass. Browser tests mock toàn bộ `/v1`. Các giới hạn và bước còn lại trong mục 12 plan. Không commit/push/deploy/restart hoặc sửa DB VPS.

### 35. Đợt 5: idempotency tạo vị trí, bảo toàn nháp, bằng chứng trong workspace

- Thêm migration `00032_position_create_idempotency.sql` và `request_id` tùy chọn cho `POST /v1/positions`: khóa advisory theo (người dùng, mã yêu cầu), lần gửi lại trả 200 + `Idempotent-Replay`, nội dung khác trả 409, vị trí đã xóa/mất quyền trả 410/403. Không lưu JD/form, chỉ hash; RLS + chỉ `service_role`.
- UI tạo vị trí giữ nguyên payload khi kết quả chưa rõ, khóa fieldset và có nút thử lại an toàn; hook `useUnsavedChangesGuard` chặn rời link nội bộ khi còn nháp cho form tạo vị trí, dialog JD và workspace shortlist.
- Workspace `/shortlist/[id]` thêm khối CV/evidence cạnh scorecard qua API share-scoped hiện có; cổng `allow_cv_view`/snapshot vẫn do backend quyết định, trích dẫn nhảy trang PDF, DOCX chỉ tải.
- URL JD có ngân sách tổng 15 giây và test xác nhận slot được trả sau timeout.
- Backend **434 passed** trên cụm PostgreSQL 16 disposable mới (cổng 55492, migration 00001–00032 chỉ cục bộ, auth stub + shim `digest`). Lần chạy cả bộ đầu tiên fail test cũ `test_superseded_worker...` do timeout; chạy riêng pass và chạy lại cả bộ pass. FE type-check/lint/build, unit 10/10, i18n 3/3, browser mock tạo vị trí/tài khoản/workspace shortlist/lọc shortlist desktop-mobile pass với `/v1` mock.
- **Chưa làm:** áp 00032 lên Supabase, E2E browser + backend + Supabase/Storage/ClamAV thật, URL thật từ VPS, usability/a11y, danh sách lớn, chặn Back/Forward, lưu nháp scorecard server-side. Chưa commit/push/deploy/restart VPS.

### 36. Đợt 6: danh sách lớn, stale và áp migration 00032 lên Supabase

- Áp migration `position_create_idempotency_00032` lên Supabase `myrymlqdbyqmpynesiwk` qua cổng migration (không dùng `supabase db push`). Postflight: bảng receipt tồn tại, RLS bật/0 policy, `service_role` INSERT được, `authenticated` không SELECT; 0 receipt, 6 vị trí, 0 OPEN còn hạn, 0 share ACTIVE, 0 scorecard. Không sửa dữ liệu sản phẩm, chưa gọi API thật.
- Danh sách ứng viên tải theo trang có tiến độ và chỉ mount 50 dòng, mở rộng theo bước 50; lọc/sắp xếp/thứ hạng/chọn chia sẻ vẫn tính toàn danh sách. Workspace share chỉ refetch khi tab ẩn ≥30 giây và có banner dữ liệu cũ; đóng dialog JD hỏi xác nhận khi có thay đổi.
- Thêm browser mock `applicants-large-list-mock.e2e.cjs` (123 hồ sơ) và unit test cửa sổ danh sách: unit 11/11, i18n 3/3, type-check/lint/build pass, 5 bộ browser mock pass. Backend unit không DB 264 passed/170 skipped; ruff `--select F` pass.
- **Chưa làm:** E2E thật Supabase/Storage/ClamAV/URL từ VPS, usability và audit accessibility đầy đủ, chặn Back/Forward, lưu nháp server-side. Chưa commit/push/deploy/restart VPS.

### 37. Đợt 7: commit, push và CI xanh

- Đã commit theo nhóm và push lên `arena/ea6e2570-vinit-hrapp`: `de655ed`, `a158e90`, `170b492`, `aff5c86`, `7f7f2d7`, `94fad03`. Không force-push, không đổi nhánh, không sửa lịch sử đã push.
- CI run **44441175204 success**: backend unit, frontend (i18n/type-check/lint/build) và backend integration trên PostgreSQL 17 + pgvector disposable có áp đủ 32 migration gồm 00032. Số test cụ thể trong log CI không tải được do chặn egress; kết quả local tương ứng 434 passed.
- Supabase: 00032 đã áp qua cổng migration; RLS bật, 0 policy, chỉ `service_role` ghi; `authenticated` không có grant trên các bảng nhạy cảm đã kiểm tra. Dữ liệu sản phẩm không đổi.
- **Chưa deploy VPS** (không có SSH trong phiên). Cần operator pull `94fad03`, build/restart và kiểm tra readiness; sau đó mới chạy E2E thật, usability/a11y và các mục còn lại.

### 38. Đợt 8: a11y smoke và sửa tràn ngang trong workspace share

- Phát hiện vùng live region ẩn làm workspace share rộng 1905px/1280px do `position:absolute` thiếu `left/top`; đã sửa và thêm test chống tái phát.
- Thêm `a11y-mock.e2e.cjs`: kiểm tra tên điều khiển, Tab tới ô tên vị trí, `aria-pressed`/Enter khi chọn ứng viên, mở accordion bằng Enter, không tràn ngang trên desktop/mobile. Là smoke test, không thay screen reader/contrast/zoom audit.
- 6 bộ browser mock pass, unit 11/11, i18n 3/3, type-check/lint/build pass; backend unit 264 passed/170 skipped. Commit `8ba1160` đã push; CI xanh cả ba job. Commit tài liệu sau đó chỉ đổi `.md` nên CI bỏ qua theo cấu hình `paths-ignore`.
- Chưa E2E thật, chưa usability, chưa deploy VPS.

### 39. Đợt 9: chặn Back/Forward và nháp scorecard bền trên trình duyệt

- `useUnsavedChangesGuard` giờ chặn cả Back/Forward: entry trang + một entry bảo vệ cùng URL; huỷ thì `forward()` về entry bảo vệ (giữ URL, không sinh entry mới), đồng ý thì đi tiếp đúng một hộp thoại; deep link không có lịch sử thì về `fallbackHref`. Reload/lưu-rồi-sửa không chồng entry.
- Nháp scorecard và phản hồi share được lưu vào `localStorage` (`hra:draft:*`, TTL 7 ngày, envelope có `saved_at`), khôi phục sau reload kèm banner; nháp scorecard chỉ nhận khi revision khớp và còn quyền sửa, lưu/nộp xong thì xoá và huỷ debounce, “Bỏ nháp đã khôi phục” trả về giá trị server, mất quyền thì purge toàn bộ nháp của share đó. Storage bị chặn → cảnh báo, chỉ còn nháp trong bộ nhớ.
- `localStorage` không mã hoá: nháp chỉ chứa nội dung người đánh giá tự gõ, không có CV/liên hệ/token; không thay thế lưu server.
- Test: unit `local-drafts` 5/5 (tổng 16/16), i18n 3/3; E2E mới `draft-back-guard-mock.e2e.cjs` chạy 3 lần pass trên production build, cùng 7 bộ browser mock cũ (a11y, tạo vị trí, tài khoản, intake, danh sách lớn, workspace shortlist, lọc shortlist) đều pass; type-check/lint/build pass.
- Đã push `01f1da4` (code + test) và `1b4e649` (tài liệu); CI run **44445860343 success** cả ba job. Commit tài liệu chỉ đổi `.md` nên CI bỏ qua.
- **Chưa làm:** chưa thử Safari/iOS/chế độ ẩn danh/tiện ích chặn history, chưa E2E với Supabase/Storage/ClamAV thật, chưa usability test luồng tải lại giữa lúc đánh giá; VPS chưa cập nhật (cần pull `1b4e649`).

### 40. Đợt 10: sửa deep link hàng đợi, giữ ngữ cảnh rà soát, tải CV khi cần

- **Bug thật đã sửa:** backend `_applicants_target` phát `?queue=file_review` (snake_case) trong khi trang xếp hạng chỉ nhận `FILE_REVIEW`, nên mọi link "Kiểm tra file"/"Xác minh hồ sơ" từ Dashboard và thẻ Việc tiếp theo mở danh sách **không lọc**. Nay backend phát UPPER_SNAKE, FE đọc khoan dung cả hai dạng để link cũ không chết; thêm 2 test backend (mã phải thuộc enum của trang xếp hạng; link không trỏ sang vị trí khác) và đã kiểm chứng bằng cách revert bản sửa → test fail.
- **Ngữ cảnh rà soát:** mọi link sang hồ sơ (Xem chi tiết, biểu tượng mắt, cảnh báo trùng, mở rộng tiêu chí) mang `queue/sort/q`; trang hồ sơ ưu tiên URL hơn `sessionStorage` nên tab mới/deep link vẫn giữ bộ lọc; Prev/Next giữ bộ lọc; nút quay lại có `restore=scroll` và danh sách khôi phục vị trí cuộn đã lưu.
- **Bộ lọc dễ hiểu:** chip giữ số theo toàn vị trí và nói rõ bằng `aria-label`/tooltip; dòng đếm tách "Hiển thị N/M · lọc theo tên · hàng đợi"; thêm "Xoá bộ lọc và tìm kiếm".
- **CV tải khi cần:** mở hồ sơ không còn gọi `cv-file`; có nút "Xem CV gốc" (nói rõ truy cập được ghi nhận lúc bấm), spinner, lỗi; bấm trang trích dẫn bằng chứng cũng tải; đổi hồ sơ xoá blob cũ, mất quyền bỏ bản đã tải.
- **Danh sách vị trí:** tìm theo tên **hoặc mã**, chip kèm số lượng, dòng đếm N/M, `?status=`/`?q=` đồng bộ URL, empty state phân biệt "chưa có" vs "không khớp".
- **Form tạo vị trí:** lỗi tại trường sau lần blur đầu + tóm tắt "Còn thiếu: …" trên nút tạo. Không thêm "Lưu nháp" (backend chưa có `DRAFT`).
- **Đo:** backend `tests/` 266 passed/170 skipped; unit 20/20, i18n 3/3, type-check/lint/build pass; **8 bộ browser mock** pass trên production build (thêm mới `ranking-context-mock`, chạy 3 lần liên tiếp). Không đổi API/DB ngoài một chuỗi query, không đổi RBAC/consent/approval/matching.
- Đã push `b3d9e88`, `babf2b3`, `613725f`; CI run **44452044131 success** cả ba job.
- **Chưa làm:** 3.7 file lỗi → hồ sơ, 3.8 sửa tiêu chí inline (cần kiểm API), 3.9 phản hồi async nhất quán, drawer P2, nhóm AI; chưa thử Safari/iOS, chưa E2E Supabase/Storage/ClamAV thật, chưa usability test; VPS chưa cập nhật.

### 41. Đợt 11: rà soát UX ba màn HR/HM — UX-R1…R5

- **Bối cảnh:** đo ba màn Dashboard / Applicant Ranking / Candidate Review, lập báo cáo `doc/BAO_CAO_UX_HR_HM.md` với 6 phát hiện có số đo tái lập được, rồi sửa 5 phát hiện P0/P1. Không thêm tính năng/màn hình/module; không đổi schema, quyền, consent, approval, công thức matching, thứ hạng.
- **UX-R1 (P0) — ba nơi đếm "cần xác minh" theo ba định nghĩa.** `summarize_applications` nay chỉ tính hồ sơ **đang sàng lọc** (`NEW/IN_REVIEW/SHORTLIST`, hằng số `SCREENING_APPLICATION_STATUSES`) và **không** cộng hồ sơ `NOT_ASSESSED` vào nhóm cần xác minh. API ranking và `matching.rank` dùng cùng luật cho cờ `needs_verification`; FE `needsVerification()` loại `NOT_ASSESSED`; ngưỡng `0.7` gom về `COVERAGE_THRESHOLD` (trước đó hard-code 8 chỗ). Kết quả đo: 4/6 hàng đợi lệch → **0/6**; ba nguồn 6/4/6 → **4/4/4**. Lưu ý hành vi: con số trên Dashboard **giảm** vì bỏ đếm trùng và bỏ hồ sơ ngoài vòng sàng lọc — hồ sơ vẫn còn trong bảng "Trạng thái hồ sơ".
- **UX-R2 (P0) — Prev/Next mất khi mở link lạnh.** Trang hồ sơ dựng lại đúng hàng đợi **từ `queue/sort/q` trên URL** (gọi ranking + danh sách hồ sơ) thay vì phụ thuộc `sessionStorage`; storage chỉ còn là dự phòng cho `scrollY`. Đo: mở link trực tiếp 0/2 nút bật → **2/2 bật, "Hồ sơ 3/4"**.
- **UX-R3 (P1) — Back làm rời ứng dụng.** Đổi hàng đợi/sắp xếp dùng `pushState`, gõ tìm kiếm vẫn `replaceState`, thêm listener `popstate` đọc lại URL. Đo: `history.length` tăng 1 mỗi lần đổi bộ lọc, Back/Forward trả đúng bộ lọc, gõ tìm kiếm không sinh entry.
- **UX-R4 (P1) — trang hồ sơ lặp tiêu đề, nội dung bị đẩy xuống.** Bỏ tên lặp ở thanh trên (giữ `h1`), ba ô số liệu gộp thành một dải ngay dưới tên, banner "chưa đủ dữ liệu" gộp vào ô độ phủ. Đo ở 1440×900: ô điểm 426px → **352px**, tiêu chí đầu 537px → **472px**, trang 1842px → **1777px**, tên trong 260px đầu 2 lần → **1 lần**.
- **UX-R5 (P1) — không thấy áp lực thời gian.** Hiện "Chờ N ngày"/"Nhận hôm nay" dưới tên ứng viên, tô màu từ 7 ngày (`WAITING_ATTENTION_DAYS`), dùng `created_at` có sẵn — **không chạm API**, không đổi thứ tự hay thứ hạng. Timestamp thiếu/tương lai thì ẩn hẳn thay vì bịa "0 ngày". Mức B (`age_days`/`due_at` trong payload + item hạn ứng tuyển) vẫn để mở, cần duyệt vì đổi payload.
- **UX-R6 (P2) hoãn:** thu gọn 12–16 điều khiển trước dòng dữ liệu đầu (vẫn ở 896px). Chưa đủ giá trị so với rủi ro đổi bố cục danh sách vừa nghiệm thu.
- **Test:** backend `tests/` **269 passed**/170 skipped (thêm 3 test UX-R1, đã kiểm chứng bằng revert → 2 test fail). Unit FE **23/23** (thêm 3, gồm test đọc mã nguồn chặn hard-code `0.7`), i18n 3/3, `tsc`/`lint`/`next build` pass. `ranking-context-mock` thêm 3 phần (Back/Forward, prev/next từ link lạnh, tuổi hồ sơ) và chạy **3 lần liên tiếp** pass; tổng **8/8 bộ browser mock** pass trên production build.
- **Ảnh trước/sau:** `doc/ui-review/before/` và `doc/ui-review/after/`; số đo trong `doc/ui-review/metrics.json`; script đo `frontend/tests/ui-ux-metrics.cjs`, `ui-screenshots.cjs`, `backend/scripts/probe_queue_drift.py`.
- Đã push `b188c2a`; CI run **44457927230 success** cả 3 job (Frontend checks, Backend unit, Backend integration PostgreSQL 17 + pgvector).
- **Chưa làm:** usability test staging (gate nghiệm thu riêng, kịch bản 6 bước + bước 7 mở link hồ sơ ở tab mới), UX-R6, mức B của UX-R5, chưa thử Safari/iOS, VPS chưa cập nhật.

### 42. Đợt 12: hạn ứng tuyển thành việc, tuổi hồ sơ, KPI "đang mở" nói thật

- **Bối cảnh:** làm đúng hai mục B1/B2 đã duyệt trong `doc/DE_XUAT_R5B_R6.md`, cộng quyết định của anh về thẻ KPI. Không đổi schema, không thêm module, không đổi matching/thứ hạng/quyền/consent.
- **B1 — hạn ứng tuyển thành việc cần làm.** Hai loại việc mới: `POSITION_DEADLINE_PASSED` (ưu tiên cao) khi hạn đã qua, `POSITION_DEADLINE_SOON` (trung bình, ≤ `DEADLINE_SOON_DAYS = 7`) khi sắp tới hạn. Chỉ sinh khi vị trí `OPEN` **và** tiêu chí đã duyệt — vị trí còn trong thiết lập đã có `POSITION_SETUP`, thêm dòng nữa là đếm trùng một việc. `deadline_at = None` thì không có việc: không hạn không phải "còn 0 ngày". Item mang `due_at` + `days_left`, bấm vào mở `tab=overview` của vị trí.
- **B2 — tuổi hồ sơ đang chờ.** `_APPLICATIONS_QUERY` nay lấy `a.created_at` (trước đây **thiếu hẳn**, nên Dashboard không thể biết hồ sơ nằm bao lâu). `summarize_waiting()` trả `waiting_over_7d`, `oldest_waiting_days`, `median_waiting_days`; gộp hồ sơ của mọi vị trí HR thấy được — lấy trung vị của các trung vị thì không phải trung vị của cái gì cả. Không có mốc thời gian ⇒ `null`, không bịa 0. Tuổi hồ sơ **chỉ để đọc**, không tham gia thứ hạng.
- **KPI "Vị trí đang mở" (quyết định của anh).** Chỉ đếm vị trí còn nhận hồ sơ: `OPEN` và chưa quá `application_deadline_at`, đúng như cổng nộp trong `careers_intake.py`. Số vị trí bị ẩn trả riêng ở `open_positions_deadline_passed` và **hiện trên thẻ KPI** ("2 vị trí đã quá hạn, không nhận hồ sơ") để chênh lệch có lời giải thích thay vì âm thầm bớt số.
- **Bug do CI bắt được (đã sửa).** `timedelta.days` làm tròn xuống nên hạn trôi qua 2 ngày 1 giây trả về **-3**: HR sẽ đọc "đã quá hạn 3 ngày" cho một hạn mới qua 2 ngày. Nay đếm số ngày đã trôi qua rồi đặt lại dấu; thêm `deadline_is_passed()` cho chỗ cần câu trả lời chính xác theo giờ, nên hạn đã qua trong sáng nay được tính là đã đóng dù `days_left = 0`. Đã kiểm chứng: gỡ bản sửa → 2 unit test đỏ.
- **Frontend:** nhãn riêng cho hai loại việc mới, câu "Còn N ngày tới hạn / Đã quá hạn N ngày / Hạn chót là hôm nay", dòng tóm tắt hạn và tuổi hồ sơ (chỉ hiện khi có số thật), ghi chú trên thẻ KPI. Loại việc lạ (backend deploy trước frontend) rơi về chữ trung tính thay vì hiện `undefined` — đã kiểm chứng bằng cách gỡ fallback: màn hình **crash**, test bắt được.
- **Payload thay đổi (chỉ thêm khoá, client cũ không vỡ):** `work-queue` thêm `items[].due_at`, `items[].days_left`, `summary.positions_deadline_passed`, `summary.positions_deadline_soon`, `summary.applications_waiting_over_threshold`, `summary.oldest_waiting_days`, `summary.median_waiting_days`; `dashboard/summary` thêm `open_positions_deadline_passed`.
- **Đo:** backend `tests/` **281 passed** / 172 skipped (thêm 11 unit + 2 integration Postgres); unit FE **27/27** (thêm 4), i18n 3/3, `tsc`/`lint`/`build` pass; browser mock **9/9 bộ** pass trên production build (thêm `deadline-work-queue-mock`). CI nay chạy thêm `npm run test:unit` (trước đó workflow **bỏ qua** unit test).
- Đã push `407e695` (tính năng) và `b6501b0` (sửa lỗi làm tròn); CI run **44462243880 success** cả 3 job. Run `44461749522` trước đó **đỏ ở job integration** — chính là lỗi làm tròn nêu trên.
- **Chưa làm:** R6 (thu gọn màn Ranking) vẫn chờ anh xác nhận; usability test staging; chưa thử Safari/iOS; VPS chưa cập nhật.

### 43. Đợt 13: R6 thu gọn màn Ranking + ngưỡng thời gian thành cài đặt

- **Bối cảnh:** anh xác nhận làm R6 theo hướng đề xuất GPT nếu hợp lý, chụp ảnh để GPT review trước khi sang UX-02, và yêu cầu đưa ngưỡng 7 ngày vào cài đặt được.
- **R6-a (một hành động chính):** "Chạy đánh giá & xếp hạng" ở lại, "Làm mới" và "Chia sẻ Shortlist" vào menu `⋮` (`aria-label="Hành động khác"`, mở bằng bàn phím được). Header từ 3 đích nhấn ngang hàng còn 2.
- **R6-b ("Cách đọc danh sách" thu gọn):** nội dung giữ **nguyên từng chữ**, mặc định đóng, nút có `aria-expanded`. e2e khẳng định cả ba câu nghiệp vụ vẫn còn khi mở; đã kiểm chứng bằng cách cố tình xoá nội dung → test đỏ.
- **R6-c (bản cân bằng, khác đề xuất GPT):** đề xuất gộp cả 4 thẻ KPI thành chip, gồm "Tổng hồ sơ" và "Có trong xếp hạng". **Không làm vậy** vì hai số đo hai thứ khác nhau (12 hồ sơ ≠ 10 đã xếp hạng; chênh lệch chính là việc cần làm) — gộp thành chip là mất phép so sánh. Thay vào đó: giữ hai số thành **một dòng** `10/12 hồ sơ đã có trong xếp hạng` (89px → 20px); **bỏ** hai thẻ "Cần HR xác minh" và "Cảnh báo trùng lặp" vì chip `Cần xác minh (4)` / `Cảnh báo trùng (2)` ngay dưới đếm đúng hai thứ đó kèm số; dòng đếm gộp vào hàng tìm kiếm; nút "Cách đọc" sang phải hàng đó. Bốn hành vi lọc vẫn đủ và có e2e bấm từng chip kiểm `?queue=`.
- **Đo trên app thật** (production build, cùng fixture, 1440×900; "before" = build lại từ commit `22888b4` rồi chụp): dòng dữ liệu đầu **896 → 669px**, đầu bảng **815 → 588**, `pageHeight` **1500 → 1274**, `scrollPages` 1.67 → 1.42, chip lọc kèm số **8 → 8** (không mất nhóm nào). Ở viewport 900px thấy 2 dòng dữ liệu (trước: 0).
- **Sửa một phép đo sai:** `filterControlsAboveTable` trong báo cáo cũ báo 12 nhưng phép đo `thead ~ * button` không khớp phần tử nào trong DOM thật, còn `[role="group"] button` bắt cả nút VI/EN ở header toàn cục. Số thật là **9 → 6**; mức cải thiện nhỏ hơn con số 12→8 mà đề xuất dự kiến. Đã sửa phép đo trong `frontend/tests/ui-ux-metrics.cjs`.
- **Ngưỡng thành cài đặt (yêu cầu của anh):** migration `00033` thêm `app_private.app_settings` với `deadline_soon_days` (1–60) và `waiting_attention_days` (1–90), mặc định 7 như code cũ nên deploy không đổi gì. `GET /v1/admin/settings` + `PATCH /v1/admin/settings/{key}`, chỉ **ADMIN**, ngoài khoảng hoặc khoá lạ ⇒ **400** kèm câu nêu khoảng, mọi thay đổi ghi `audit_events` kèm giá trị cũ/mới. Work queue trả `summary.deadline_soon_days` và `summary.waiting_attention_days` để Dashboard nói đúng số đang áp dụng thay vì hard-code "7 ngày". Màn: tab "Cài đặt HR" trong `/admin` và route riêng `/admin/settings`.
- **Test:** backend **289 passed**/173 skipped (+8 unit settings, +1 integration Postgres kiểm bảng thật, RBAC, 400 và ảnh hưởng lên work queue); unit FE 27/27, i18n 3/3, `tsc`/`lint`/`build` sạch; **11/11 bộ e2e mock** (thêm `ranking-compact`, `settings-mock`; `applicants-mock` cập nhật theo menu mới — kiểm cả bàn phím và `menuitem`).
- **Ảnh review:** `doc/ui-review/r6/before/` (app thật ở `22888b4`), `after/` (5 ảnh, gồm màn Cài đặt desktop + mobile 390px), `before-metrics.json`, `after-metrics.json`, và `README.md` nêu rõ chiều ảnh, cảnh báo về con số 12 cũ, cùng 3 câu hỏi cho GPT.
- Đã push `2a56838`; CI run **44471839211** đỏ ở integration vì test gọi settings khi user chưa có role ADMIN → sửa thứ tự trong `67f05f2`, CI run **44472203915 success** cả 3 job.
- **Chưa làm:** chưa sang UX-02 (chờ GPT review ảnh); usability test staging; chưa thử Safari/iOS; VPS chưa cập nhật (cần chạy migration `00033`).

### 44. Chốt R6 + ba chỉnh nhỏ theo review + lập đề xuất UX-02

- **R6 được chốt.** Anh xác nhận "R6 đạt mục tiêu cải thiện trải nghiệm ở mức tốt" và chốt **giữ nguyên R6 làm baseline**, không mở vòng chỉnh sửa giao diện mới. Ba quyết định kèm theo: (Q1) giữ 669px, **không ép xuống 640** — 640 chỉ là mục tiêu tham khảo; không bỏ hai nút chế độ xem; không gộp dòng `10/12 hồ sơ` vào tiêu đề vì đó là chỉ số tiến độ riêng. (Q2) **không** đổi giải thích chế độ xem thành tooltip — nội dung nghiệp vụ phải nhìn thấy được; giữ một câu ngắn dưới hai tab, phần dài vẫn trong "Cách đọc danh sách"; tooltip chỉ cho thuật ngữ/phụ. (Q3) **không** khôi phục hai thẻ KPI trùng chip.
- **Ba chỉnh nhỏ đã làm sau quyết định** (đều là chỗ HR thật sẽ vấp, không phải trang trí):
  - **Alert chế độ xem → dòng chú thích** (`data-testid="sort-explanation"`), bỏ nền xanh + icon, chữ nhỏ. Nội dung giữ nguyên, đổi theo chế độ đang chọn. Nhờ vậy dòng dữ liệu đầu **669 → 633px** — vào dưới mốc 640 **mà không bỏ thông tin nào**.
  - **Menu `⋮`**: `aria-label` thành "Hành động khác: Làm mới, Chia sẻ Shortlist" + tooltip nêu đúng hai thao tác. Trước đây chỉ có icon và nhãn "Hành động khác", HR phải bấm mới biết bên trong có gì.
  - **Settings save**: xác nhận ngay **tại dòng vừa lưu** ("Đã lưu lúc HH:MM") trong vùng `aria-live="polite"`, tự xoá khi sửa lại; lỗi từ server hiện thành alert và **không** để lại dấu đã lưu. Trước đây chỉ có một alert ở đầu trang — lưu thẻ thứ hai thì không thấy gì.
- **Test:** e2e `ranking-compact` thêm phần bàn phím cho "Cách đọc" (Enter mở, Enter đóng, `aria-expanded`, focus ở lại nút), kiểm tooltip + accessible name của `⋮`, kiểm caption đổi theo chế độ và **không** còn `role=alert`. `settings-mock` thêm xác nhận tại dòng, xoá dấu khi sửa lại, và ca lỗi 400 **không** để lại dấu thành công. **11/11 bộ e2e PASS**, unit 27/27, i18n 3/3, tsc/lint sạch.
- **Đo lại:** dòng đầu **896 → 633px**, đầu bảng **815 → 552**, `pageHeight` **1500 → 1238**, chip lọc **8 → 8**. Ảnh mới `06-header-menu-closed` … `09-how-to-read-open` trong `doc/ui-review/r6/after/`.
- **Đã push `a1642d9`.**
- **UX-02 — đã lập đề xuất, chưa sửa code:** `doc/DE_XUAT_UX02_CANDIDATE_REVIEW.md`. Trước khi viết, đã đo màn hồ sơ bằng `frontend/tests/review-metrics.cjs` (mới) ở 1440×900, 820×1180 và 390×844. Ba phát hiện làm thay đổi khung đề xuất:
  - **Không có chỗ nào ghi nhận HR đã xác minh.** Không endpoint, không bảng, không nút — đã kiểm cả ba tầng. `evidence_items.verification_status` chỉ do worker ghi. Và `SHORTLIST` vẫn nằm trong `SCREENING_APPLICATION_STATUSES`, nên **đường duy nhất để hồ sơ rời hàng đợi "Cần xác minh" là loại hồ sơ hoặc đẩy sang phỏng vấn** — tức HR buộc phải ra quyết định tuyển dụng để dọn một hàng đợi kỹ thuật.
  - **Trích dẫn "Đã xác minh" bấm không được** cho tới khi HR bấm "Xem CV gốc", mà UI không nói vậy. Đo được: bấm trích dẫn lúc CV chưa tải → **0** request, không có `role=button`; sau khi tải CV thì cùng trích dẫn đó mới thành nút.
  - **Màn Review không hiển thị yêu cầu gốc của tiêu chí**: trang không gọi endpoint criteria nào, và `GET /v1/assessments/{id}` không trả `description`/`evidence_guidance`/`jd_reference_text` dù dữ liệu có sẵn. HR muốn "đối chiếu tiêu chí" phải rời màn hình.
  - Bố cục 2 cột và CV tải lười (0 request khi mở, 1 khi bấm) đã đúng, **không** đề xuất làm lại. Đề xuất gồm U2 (yêu cầu gốc) → U3 (bấm trích dẫn tải CV + nhảy trang) → U4 (ba nhãn trích dẫn, nhãn điểm, skip-link bỏ 11 tab trang trí) → U1 (ghi nhận xác minh, **việc duy nhất đổi backend**) → U5 (câu "việc tiếp theo" trên thẻ); hoãn U6 (danh sách tiêu chí thu gọn).
  - **Chờ anh duyệt 3 câu hỏi** (Q1 có duyệt U1 không; Q2 chọn (a)/(b)/(c) cho cách rời hàng đợi — em nghiêng (c); Q3 thứ tự).

### 45. UX-02 Candidate Review — U2/U3/U4 thuần FE + U1 đồng bộ backend/FE

- **Bối cảnh:** anh duyệt đề xuất `doc/DE_XUAT_UX02_CANDIDATE_REVIEW.md` với Q1 = duyệt U1 (đồng bộ cả backend lẫn FE), Q2 = phương án **(c)** (hồ sơ rời hàng đợi khi **mọi** tiêu chí `requires_hr_verification` đã được kiểm), Q3 = giữ thứ tự đề xuất.
- **U2 — yêu cầu gốc của tiêu chí ngay trên thẻ.** Gọi `GET /v1/criteria/position/{id}/approved` **một lần** cho cả trang (không một lần mỗi thẻ), map theo `criterion_id`; thẻ hiện `description`, `requirement_spec` (số năm/bậc/ngoại ngữ/từ khoá), `evidence_guidance`, `jd_reference_text`, gập mặc định. Toggle nằm **trên dòng tên tiêu chí** nên không tốn dòng riêng; tiêu chí không có nội dung thì **không hiện toggle** (không có nút rỗng). Chiều cao trang 1777 → **1815px (+38)**, trong ngưỡng ≤40 đã đặt ra trong kế hoạch.
- **U3 — bấm trích dẫn là tải CV và mở đúng trang.** Trước đây thẻ ghi "Trang 2 · Đã xác minh" nhưng bấm không có phản ứng cho tới khi HR bấm "Xem CV gốc": đo được **0 request**, không có `role=button`; sau khi tải CV thì cùng trích dẫn mới thành nút. Nay trích dẫn luôn là nút, nhãn nói rõ "Bấm để mở trang N trong CV", và `jumpToPage` giữ trang đang xin trong `pendingPage` để mở **đúng trang** sau khi file xong (trước đây sẽ rơi về trang mà viewer mount). Đo lại: **0** request khi mở hồ sơ → **1** request khi bấm → viewer `#page=2`.
- **U4 — ba chỉnh nhỏ cùng chủ đề "nói đúng mức tin cậy".** (a) Tách `FAILED` ("Không tìm thấy trong CV", đỏ) khỏi `PENDING` ("Chưa đối chiếu", xám) — trước đây gộp cả hai thành "Trích dẫn chưa xác minh", làm mất tín hiệu mạnh hơn. (b) Nhãn "Điểm trên tiêu chí đã có bằng chứng" → **"Điểm tổng hợp"** kèm dòng "Trên 4 tiêu chí; 1 tiêu chí có trích dẫn đã xác minh", vì nhãn cũ đọc ngược nghĩa con số. (c) Thêm **skip-link "Tới nội dung chính"** + `main` có `tabIndex={-1}`: trước đây phải **11 lần Tab** qua sidebar/ngôn ngữ mới tới nội dung, nay **1 lần** rồi Enter là vào thẳng; Tab tiếp theo đi ngay vào "Quay lại danh sách xếp hạng" và "Tải CV gốc".
- **U1 — HR ghi nhận đã xác minh (đồng bộ backend + FE).**
  - **Migration `00034_hr_criterion_reviews.sql`:** bảng riêng, **append-only** (xem lại là dòng mới, không ghi đè), có người + giờ + lý do; `CHECK` buộc lý do khi `REJECTED`. **Không** ghi vào `evidence_items.verification_status` — đó là kết quả của máy; nếu HR ghi đè thì sau này không ai phân biệt được máy xác minh hay người xác nhận, và audit mất giá trị.
  - **API `POST /v1/assessments/results/{result_id}/review`** (201), quyền qua `application_access().hr_notes_access` → người không phải HR phụ trách bị **403**; ghi `audit_events` `HR_EVIDENCE_REVIEW`. `GET /v1/assessments/{id}` trả thêm `hr_reviews[]` và `result_id` cho từng tiêu chí (một truy vấn, không phải một request mỗi thẻ).
  - **Phương án (c) trong `workspace.py`:** `summarize_applications` đọc thêm `pending_reviews`/`reviewed_criteria` tính từ các tiêu chí `requires_hr_verification`; khi mọi tiêu chí bị gắn cờ đã được kiểm → hồ sơ **rời** `needs_verification` và vào `verification_complete` (key mới), **trạng thái hồ sơ không đổi**. Dashboard thêm `summary.applications_verification_complete`, nhờ vậy con số "cần bạn" không âm thầm nhỏ đi. Truy vấn `_APPLICATIONS_QUERY` thêm `LEFT JOIN LATERAL` đếm theo `result_id`.
  - **FE:** mỗi thẻ bị gắn cờ có khối "Máy đánh dấu tiêu chí này cần HR xác minh" + 2 nút (xác nhận / đánh dấu sai). Đánh dấu sai mở dialog **bắt buộc lý do**, nút Ghi lại bị disable tới khi có chữ. Dải đầu có chip "Đã xác minh 1/2 tiêu chí cần kiểm" → "Đã xác minh đủ 2/2" + câu nói rõ hồ sơ sẽ rời hàng đợi và **trạng thái không thay đổi**.
- **Sửa một kết luận sai trong đề xuất (do chính em viết):** bản đầu nói "shortlist làm hồ sơ rời hàng đợi". Sai — `SHORTLIST` nằm trong `SCREENING_APPLICATION_STATUSES`, nên shortlist **không** làm rời. Đường duy nhất trước đây là **loại hồ sơ hoặc chuyển sang phỏng vấn**, tức HR bị ép ra quyết định tuyển dụng để dọn một hàng đợi kỹ thuật. Tài liệu đề xuất đã được sửa lại theo đúng sự thật này.
- **Test:** backend **292 passed** / 174 skipped (+3 unit cho phương án (c): rời hàng đợi khi đủ, không rời khi chưa kiểm cái nào, và **không** coi "không có tiêu chí bị gắn cờ" là "đã kiểm xong"); +1 integration Postgres (append-only, 403 cho HM, 422 khi thiếu lý do, audit, hàng đợi giảm, `application_status` **không đổi**, `result_id` + thứ tự `hr_reviews` mới nhất trước). FE: unit 27/27, i18n 3/3, `tsc`/`lint`/`build` sạch; e2e **12/12** với bộ mới `ux02-review` (bộ này kiểm cả việc quyết định **sống qua reload**, để không thể pass nhờ optimistic UI).
- **Ảnh:** `doc/ui-review/ux02/after/01..07` (mặc định, panel yêu cầu mở, trích dẫn mở đúng trang CV, dialog lý do, tiến độ sau khi kiểm). Chỉ số đo bằng `npm run -s test:review-metrics`.
- **Chưa làm:** U5 (câu "việc tiếp theo" trên thẻ) — theo Q3 để đợt sau. VPS chưa cập nhật; khi deploy cần chạy **cả `00033` và `00034`**.
- **Ba lỗi thật do CI Postgres bắt được** (unit test và e2e mock đều xanh trước đó — đáng ghi lại vì đúng loại lỗi mà chỉ chạy DB thật mới thấy):
  1. `LATERAL` mới tham chiếu `latest.assessment_id` nhưng subquery `latest` chỉ select `matching_status, evidence_coverage` ⇒ `column does not exist`, đỏ **cả 5** test dùng work queue chứ không riêng test mới. Sửa: select thêm `ar.assessment_id`.
  2. Endpoint review đọc `access["hr_notes_access"]` — key này **không tồn tại**; `application_access` trả `can_view_cv / can_update_status / can_manage_hr_notes`. `.get()` trả `None` ⇒ **mọi** người dùng bị 403, kể cả HR phụ trách. Đã rà cả 6 chỗ khác gọi `application_access`, tất cả dùng đúng key.
  3. `GET /v1/applications/{id}` **tự dựng** `latest_assessment` riêng nên chưa có `hr_reviews`. Nếu deploy: HR thấy nút, bấm, request thành công, nhưng màn hình không hiện được quyết định vừa lưu.
- **CI:** run **44480273858** đỏ (lỗi 1) → **44480708971** đỏ (lỗi 2) → **44481093157** đỏ (lỗi 3) → **44481450082 success** cả 3 job (Backend integration PostgreSQL 17 + pgvector, Backend unit, Frontend checks).

### 46. UX-02 U5 (câu "việc tiếp theo") + UX-03 Dashboard

- **U5 — mỗi tiêu chí nói rõ nó đòi gì.** Thêm `frontend/src/lib/criterionAction.ts`: một hàm thuần suy câu hành động từ **dữ liệu có thật** (outcome, `verification_status`, có trích dẫn hay không, quyết định đã ghi), theo bảng cố định — **không gọi thêm LLM**, không đoán. Bảy nhánh: đã xác nhận / đã đánh dấu sai / cần đối chiếu (kèm số trang) / CV không nêu (câu hỏi phỏng vấn) / máy tìm không thấy / đã đủ bằng chứng / xem CV để kết luận. **10 unit test** phủ từng nhánh + một test chống nhánh chết (`every code reachable`).
- **Hai vòng tự sửa khi làm U5:**
  - Bản đầu để câu hành động **lặp** với khối U1 ("Máy đánh dấu… cần HR xác minh" + "Đối chiếu trích dẫn với CV rồi ghi lại kết quả") ⇒ bỏ tiêu đề và câu giải thích trùng khỏi khối U1, chỉ còn hai nút; câu trấn an về trạng thái chuyển lên dải tiến độ (nơi nó áp cho cả hồ sơ, không phải một tiêu chí).
  - Câu "Đã đủ bằng chứng — không cần làm gì" từng chiếm một dòng trên **mọi** thẻ. Đổi: chỉ hiện khi **có** việc; thẻ không có gì thì im lặng. Chiều cao trang 2191 → **2049px**.
- **Đo U5:** trang hồ sơ 1815 → **2049px** (+234, tức khoảng **+58px mỗi thẻ**). Đây là mức đắt nhất trong cả UX-02 và là **quyết định có ý thức**: một câu nói rõ "cần làm gì" thay vì để HR tự ghép từ ba chip. Thẻ đầu vẫn nằm ở 511px (không đổi).
- **UX-03 — kiểm trước khi sửa, và chỉ sửa cái sai thật.** Đo Dashboard rồi đối chiếu code: **mọi deep link đã đúng** (`queue=FILE_REVIEW / NEEDS_VERIFICATION / DUPLICATE / POSSIBLE_MISMATCH / NOT_ASSESSED`), không có "deep link giả". Vì vậy UX-03 **không** làm lại phần đã tốt; chỉ sửa ba chỗ đo được:
  1. **Lỗi thật — chip lọc không cho thấy trạng thái.** `/positions?status=CLOSED` hiện **"0/1 vị trí"** nhưng **cả bốn chip trông y hệt nhau**: `aria-pressed` đúng nhưng MUI `Chip` không đổi màu theo `color` khi không có `variant`. Người dùng sáng mắt không biết đang lọc gì; screen reader thì biết. Sửa: chip đang chọn **filled**, còn lại **outlined**.
  2. **Khối "Nhắc hạn scorecard" khi không có gì** chiếm một tiêu đề + dòng "Hiển thị tối đa 100…" + câu rỗng — khoảng 90px trước hàng đợi việc, trong khi Dashboard đang có 7 việc thật. Sửa: trạng thái rỗng thu thành **một dòng caption**, tiêu đề và caveat chỉ hiện khi có scorecard thật.
  3. **Việc đã kiểm xong không nhìn thấy.** `applications_verification_complete` đã có từ U1 nhưng Dashboard chưa dùng ⇒ "cần xác minh" nhỏ đi mà không ai biết là đã làm hay mất dữ liệu. Thêm dòng "Đã xác minh xong N hồ sơ — số trên chỉ tính việc còn lại".
- **Đo UX-03:** "Việc cần làm" 428 → **360px** (−68), `pageHeight` 1877 → **1832**, vẫn 4 KPI + 5 nút hàng đợi trong màn đầu.
- **Việc kiểm ngược (làm thật, không chỉ nói):** cố tình đổi `data-testid` của dòng "đã xác minh xong" → e2e **đỏ** (timeout), hoàn nguyên → xanh. Với test chip cũng vậy: chỉ kiểm `aria-pressed` là **không đủ** vì đó chính là lỗi đã ship; e2e giờ kiểm cả `filled`/`outlined`.
- **Test:** unit **37** (thêm 10 test U5), i18n 3/3, tsc/lint/build sạch; e2e **13/13** (thêm `ux03-dashboard`). Thêm `tests/dashboard-metrics.cjs` để đo Dashboard trước/sau.
- **Ảnh:** `doc/ui-review/ux03/before/01..02` và `after/01..03`.

### 47. Hợp đồng queue code giữa backend và frontend (đóng khe hở của UX-03)

`doc/DE_XUAT_UI_UX_TU_GPT.md` §3.3 mô tả đúng một lỗi thật: backend từng phát `?queue=file_review` (thường) trong khi trang xếp hạng chỉ nhận `FILE_REVIEW`, nên mọi nút từ Dashboard mở danh sách **không lọc**. Khi rà lại thì **lỗi đã được sửa** (`_applicants_target` gọi `queue.upper()`, FE `normalizeApplicantQueue` chấp nhận cả hai kiểu). Nhưng cách **kiểm** thì vẫn hở:

- `backend/tests/test_workspace.py` so mã queue với `RANKING_QUEUE_CODES` — một danh sách **chép tay** ngay trong file test. Đổi tên mã ở `applicantReview.ts` thì test backend **vẫn xanh**, đúng kiểu lỗi cũ quay lại mà không ai biết.
- Đã sửa: test backend đọc thẳng `APPLICANT_QUEUES` trong file TS của frontend (`_ranking_queue_codes_from_frontend`).
- Thêm `frontend/tests/queue-contract.test.cjs`: đọc các mã backend **thực sự phát** từ `workspace.py`, áp đúng phép biến đổi backend dùng (`queue.upper()` — test assert luôn tên phép biến đổi để không đoán), rồi đưa qua `isApplicantQueue` thật của trang. Có case cho link cũ dạng thường (bookmark không chết) và case mã lạ phải bị từ chối.
- **Kiểm ngược cả hai phía, làm thật:** đổi `'NEEDS_VERIFICATION'` trong mảng queue của FE → backend pytest **đỏ** (`'queue=NEEDS_VERIFICATION' would not filter the ranking page`), hoàn nguyên → 25 passed. Lần phá đầu tiên rơi vào dòng type union nên không đỏ — đúng, vì đó không phải mảng; đã phá lại đúng dòng 46.
- **Test:** backend 292 passed / 174 skipped, `ruff --select F` sạch trên file đã sửa; FE unit **40** (thêm 3 test hợp đồng).
