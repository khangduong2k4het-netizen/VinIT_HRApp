# Plan triển khai Langfuse — AI Observability cho VinIT HRApp

> Ngày lập plan: 2026-11-05  
> Branch: `arena/ea6e2570-vinit-hrapp`  
> Trạng thái: **LF-0 ĐÃ LƯU PLAN; LF-1, LF-2A và LF-3A ĐÃ TRIỂN KHAI Ở CODE — LF-2B/LF-3 ĐẦY ĐỦ CHỜ STAGING VÀ GOLDEN SET**
> Phạm vi: bổ sung khả năng quan sát pipeline AI/LLM, embedding và assessment. Không thay đổi matching engine, điểm số, workflow HR/HM, RBAC, audit nghiệp vụ hoặc quyết định tuyển dụng.

## 1. Kết luận

Langfuse phù hợp với hệ thống vì backend hiện tại có nhiều bước AI khó quan sát bằng log thường:

1. Trích xuất tiêu chí từ JD bằng LLM.
2. Trích xuất profile từ CV bằng LLM.
3. Deterministic matching bằng rule engine.
4. Semantic retrieval bằng BGE/pgvector khi được bật.
5. LLM fallback để đối chiếu tiêu chí chưa được rule quyết định.
6. Kiểm chứng quote/trang, tính `matching_score`, `evidence_coverage`, trạng thái matching.
7. Ranking và LTR ở chế độ OFF/SHADOW/ACTIVE theo gate hiện tại.

Langfuse được dùng để trả lời các câu hỏi vận hành và chất lượng AI:

- Một operation/assessment chậm hoặc lỗi ở bước nào?
- Provider/model/prompt version nào đang tạo nhiều lỗi JSON/schema, `UNCLEAR` hoặc evidence không kiểm chứng được?
- Bao nhiêu tiêu chí do RULE quyết định, bao nhiêu phải qua LLM fallback?
- BGE/pgvector có thực sự hoạt động hay đang fallback về lexical?
- Khi thay prompt/model/policy, score drift, criterion flip và ranking thay đổi ra sao?
- Chi phí/token/latency thay đổi thế nào theo provider/model?

Langfuse **không** thay thế:

- PostgreSQL và các bảng `operations`, `assessment_runs`, `criterion_assessment_results`, `evidence_items`, `ranking_runs`.
- `audit_events` append-only/hash-chain.
- Dashboard/Work Queue của HR/HM.
- Hệ thống monitoring hạ tầng như uptime, CPU/RAM/disk hoặc alert process.
- Quyết định HR/HM. AI vẫn chỉ hỗ trợ; con người giữ quyền quyết định.

## 2. Hiện trạng đã đối chiếu trong code

| Khu vực | File hiện tại | Điểm cần quan sát |
|---|---|---|
| LLM client dùng chung | `backend/app/services/llm_client.py` | 3 task: criteria, profile, criterion matching; provider/model/prompt version; lỗi JSON/schema/HTTP |
| Worker xử lý CV/assessment | `backend/app/workers/processor.py` | operation, batch, OCR/trích text, profile, assessment, ranking, recovery |
| Semantic/BGE | `backend/app/services/embedding.py`, `semantic_retrieval.py`, `semantic_diagnostics.py` | provider/model/dimension/index, cache, pgvector, fallback lexical |
| Matching/evaluation | `backend/app/services/matching.py`, `evaluation.py`, `backend/scripts/evaluate_matching.py` | score drift, criterion flip, ranking stability, fingerprint reuse |
| Cấu hình AI | `backend/app/services/ai_config.py`, `backend/app/api/admin.py` | runtime snapshot công khai, model/provider, config version; tuyệt đối không lộ API key |
| Bảo vệ dữ liệu trước model | `backend/app/services/redaction.py` | redaction best-effort; không được coi là ẩn danh tuyệt đối |
| Nhật ký hiện tại | `backend/app/core/logging.py` | structured log nhưng chưa có trace xuyên pipeline, token/cost, prompt/model analytics hoặc evaluation dashboard |

Hệ thống đã có các khóa liên kết tốt cho observability:

- `operation_id`
- `position_id`
- `application_id`
- `document_id`
- `assessment_id`
- `assessment_fingerprint`
- `criteria_version_id`
- `jd_version_id`
- `profile_version_id`
- `ai_config_id`
- `prompt_version`, `matching_policy_version`, `deterministic_rules_version`
- provider/model snapshot công khai

Các khóa trên là metadata vận hành. Chúng không kéo theo quyền đưa nội dung CV/JD vào Langfuse.

## 3. Kiến trúc đích

```text
HR/HM UI
   |
FastAPI API -------------------- PostgreSQL / Supabase
   |                                  ^
   |                                  | nguồn sự thật nghiệp vụ/audit
Worker polling operations            |
   |                                  |
   +--> OCR / document processing ---+
   +--> deterministic rules ---------+
   +--> BGE / pgvector --------------+
   +--> LLM provider ----------------+
   +--> evidence verification -------+
   +--> scoring / ranking / LTR -----+
   |
   +--> Langfuse observability (metadata-first, fail-open)
          - trace: operation / assessment
          - span: OCR, rules, semantic, verification, scoring, ranking
          - generation: LLM call
          - embedding: BGE call
          - scores: coverage, drift, flip, agreement, operational quality
```

Nguyên tắc bắt buộc:

1. **Metadata-first:** mặc định không gửi prompt, CV text, JD text, quote bằng chứng, reasoning đầy đủ, email, số điện thoại hoặc dữ liệu định danh vào Langfuse.
2. **Fail-open:** Langfuse lỗi, timeout hoặc chưa cài SDK không được làm lỗi upload CV, assessment, ranking hoặc API.
3. **Tắt mặc định:** `LANGFUSE_ENABLED=false`. Chỉ bật có chủ đích theo môi trường.
4. **Không dùng dữ liệu thật khi chưa qua gate:** chưa có phê duyệt privacy/egress, environment mapping và retention thì chỉ dùng dữ liệu tổng hợp/đã được phép.
5. **Không tạo “overall confidence”:** Langfuse score phải giữ đúng ngữ nghĩa. `evidence_coverage` không phải confidence; `matching_score` không phải xác suất trúng tuyển.
6. **Không thay fingerprint/version hiện tại:** thay prompt/model/policy vẫn phải tăng version theo `doc/MATCHING_STABILITY.md` và chạy evaluation liên quan.
7. **Không lộ secret:** không gửi API key của model provider, Langfuse secret key, database URL, endpoint có credential hoặc header Authorization vào trace/metadata/log.

## 4. Mô hình trace và score

### 4.1. Trace taxonomy

| Observation | Loại | Khi tạo | Metadata chính |
|---|---|---|---|
| `hra.worker.operation` | span | Worker claim một operation | `operation_id`, `capability`, `recovered`, `ai_config_id`, provider/model công khai |
| `hra.assessment` | span | Đánh giá một application | `operation_id`, `position_id`, `application_id`, `document_id`, `assessment_id`, fingerprint, criteria/JD/profile version |
| `hra.llm.criteria_extraction` | generation | LLM trích tiêu chí từ JD | prompt version, model/provider, số tiêu chí, category counts, latency, usage |
| `hra.llm.profile_extraction` | generation | LLM trích profile CV | prompt version, model/provider, số section/facts dạng count, latency, usage |
| `hra.llm.criterion_matching` | generation | LLM fallback cho tiêu chí chưa quyết định | prompt version, số tiêu chí, số chunk, outcome counts sau validate, latency, usage |
| `hra.embedding.bge` | embedding | Gọi BGE `/embeddings` | model, dimension, kind, số text, tổng ký tự dạng count/hash, vector count |
| `hra.langfuse.smoke` | span | Script smoke test tổng hợp | `synthetic=true`, môi trường, release |

LF-2A đã bổ sung các span chọn lọc `hra.cv.document_extraction`, `hra.assessment.deterministic_matching`, `hra.assessment.semantic_retrieval`, `hra.assessment.evidence_verification`, `hra.assessment.scoring` và `hra.ranking.generate`. Các span này chỉ ghi ID nội bộ, version, trạng thái và count/tỷ lệ; không ghi CV/JD, quote hoặc reasoning. Không instrument toàn bộ hàm nhỏ để tránh trace nhiễu và thay đổi lớn trong worker.

### 4.2. Trường được phép gửi mặc định

- ID nội bộ dạng UUID/hash: operation, position, application, document, assessment, criteria version.
- Phiên bản: prompt, matching policy, deterministic rules, ranking policy, embedding index.
- Provider/model đã công khai trong runtime snapshot; không kèm API base chứa credential.
- Trạng thái và mã lỗi dạng enum/type: `COMPLETED`, `FAILED`, `LLMError`, `HTTPStatusError`; không gửi exception message chứa dữ liệu.
- Số lượng: số file, số chunk, số criterion, số finding, số token nếu provider trả về.
- Hash SHA-256 của text đã redaction khi cần đối chiếu đầu vào; hash không kèm text.
- Thời lượng do Langfuse tự đo theo observation.

### 4.3. Trường cấm gửi

- CV/JD/profile text, prompt đầy đủ và output đầy đủ khi chưa bật capture có kiểm soát.
- Quote bằng chứng, reasoning đầy đủ, tên/email/số điện thoại/địa chỉ của ứng viên.
- API key, token, cookie, database URL, Supabase service-role key.
- HR private notes, shortlist feedback có nội dung tự do.
- Thuộc tính nhạy cảm hoặc suy luận về tuổi, giới tính, quốc tịch, tôn giáo, sức khỏe và các đặc điểm được bảo vệ.

### 4.4. Score taxonomy

Score gắn ở trace assessment hoặc experiment, không dùng để thay đổi quyết định nghiệp vụ:

| Score | Kiểu | Ý nghĩa |
|---|---|---|
| `matching_score` | numeric | Điểm matching hiện tại; chỉ ghi khi khác `null`; không diễn giải là confidence |
| `evidence_coverage` | numeric 0–1 | Tỷ trọng tiêu chí đã có đủ bằng chứng để tính điểm |
| `needs_verification` | boolean | Hồ sơ cần HR xác minh theo gate hiện tại |
| `unclear_criterion_count` | numeric | Số tiêu chí `UNCLEAR` |
| `rule_decided_count` | numeric | Số tiêu chí do RULE quyết định |
| `llm_decided_count` | numeric | Số tiêu chí do LLM fallback quyết định |
| `evidence_verified_rate` | numeric 0–1 | Tỷ lệ finding có evidence verify được |
| `score_drift` | numeric | Độ lệch điểm trong evaluation/repeatability |
| `criterion_flip` | boolean/numeric | Có/không có criterion đổi outcome giữa hai run |
| `hr_agreement` | boolean/categorical | HR đồng ý/không đồng ý với finding; chỉ triển khai khi có nguồn nhãn HR hợp lệ và được duyệt |

Không gửi điểm từng ứng viên lên Langfuse Cloud với dữ liệu thật nếu chưa có phê duyệt. Ở LF-1, score chỉ bật cùng trace tại môi trường được phép.

## 5. Lựa chọn triển khai Langfuse

### 5.1. Langfuse Cloud

Phù hợp cho:

- Dev hoặc staging dùng dữ liệu tổng hợp.
- Kiểm chứng SDK/trace nhanh mà chưa cần dựng hạ tầng.

Điều kiện:

- `LANGFUSE_CAPTURE_CONTENT=false`.
- Không dùng CV/JD thật.
- Project/organization, quyền truy cập, khu vực lưu trữ và điều khoản xử lý dữ liệu phải được IT/Security chấp thuận trước pilot thật.

### 5.2. Self-host Langfuse

Đây là hướng ưu tiên cho pilot có dữ liệu thật sau khi qua gate. Một deployment self-host đầy đủ cần các thành phần như Langfuse web/worker, PostgreSQL, ClickHouse, Redis/Valkey và S3/blob storage. ClickHouse là thành phần bắt buộc cho trace/observation/score ở kiến trúc hiện tại; không dùng chung database nghiệp vụ của HRApp cho Langfuse.

Yêu cầu vận hành:

- Dựng project/môi trường riêng: dev, staging, production không dùng chung project key.
- Đặt Langfuse sau HTTPS/VPN/IP allowlist theo chính sách VinUni.
- Backup/restore, disk sizing, log retention và upgrade plan riêng.
- Kiểm tra tính năng data retention theo edition/version đang triển khai. Không giả định bản OSS tự xóa trace đúng hạn nếu tính năng retention thuộc gói khác; nếu không có retention tự động, phải có quy trình xóa/TTL ở hạ tầng được duyệt.
- Không coi project Supabase đã kết nối hiện tại là staging. Việc dựng Langfuse phải chờ DEP-01 environment mapping hoặc quyết định môi trường riêng được ghi rõ.

### 5.3. Khuyến nghị

| Giai đoạn | Lựa chọn |
|---|---|
| LF-1 code + kiểm thử local | Tắt mặc định; fake client trong unit test; không cần server thật |
| LF-2 staging tổng hợp | Langfuse Cloud project riêng hoặc self-host dev/staging sau DEP-01 |
| LF-3 evaluation/golden set | Self-host hoặc Cloud đã được Security/Privacy duyệt; dataset chỉ chứa dữ liệu tổng hợp/ẩn danh được phép |
| LF-4 pilot | Ưu tiên self-host cùng vùng mạng, metadata-only, retention và RBAC đã kiểm chứng |

## 6. Cấu hình dự kiến

```dotenv
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=
LANGFUSE_BASE_URL=
LANGFUSE_ENVIRONMENT=
LANGFUSE_RELEASE=
LANGFUSE_SAMPLE_RATE=1.0
LANGFUSE_CAPTURE_CONTENT=false
```

Quy tắc:

- `LANGFUSE_BASE_URL` được ưu tiên nếu có; nếu không dùng `LANGFUSE_HOST`.
- `LANGFUSE_ENVIRONMENT` để trống sẽ lấy `APP_ENV`.
- `LANGFUSE_CAPTURE_CONTENT=true` vẫn không được gửi nội dung khi `APP_ENV=production`; chỉ dành cho môi trường tổng hợp đã duyệt.
- `LANGFUSE_SAMPLE_RATE` phải nằm trong khoảng 0–1. Staging tổng hợp dùng `1.0`; production chỉ cân nhắc sau khi đo dung lượng/chi phí.
- Secret chỉ nằm trong secret manager/env của backend/worker; không đưa vào frontend, Git, ticket hoặc log.

Python SDK được chốt theo dòng v4 trong LF-1 để tương thích rộng hơn với self-host v3.63+ và giảm rủi ro lệch server/SDK. Khi nâng SDK v5 phải kiểm chứng server Langfuse v4 và chạy lại smoke/evaluation trước rollout.

## 7. Lộ trình triển khai thực tế

### LF-0 — Tài liệu, quyết định và khóa phạm vi

Trạng thái: **ĐÃ HOÀN THÀNH TÀI LIỆU**.

Công việc:

- Lưu plan này và cập nhật `Update_Excute_P2.md`.
- Chốt nguyên tắc metadata-first, fail-open, tắt mặc định.
- Chốt trace/score taxonomy và trường cấm gửi.
- Không thay đổi matching, prompt, model hoặc workflow.

Tiêu chí xong:

- Có plan, lộ trình, gate privacy/deployment và trạng thái triển khai rõ ràng.

### LF-1 — Observability foundation + LLM/worker/BGE tracing

Trạng thái: **ĐÃ TRIỂN KHAI Ở CODE — CHỜ STAGING**.

Phạm vi code:

- Thêm cấu hình Langfuse vào `backend/app/core/config.py` và env examples.
- Thêm dependency Python SDK dòng v4 trong `backend/pyproject.toml`.
- Tạo `backend/app/services/langfuse_observability.py`:
  - lazy singleton client;
  - no-op khi tắt/thiếu cấu hình/SDK lỗi;
  - sanitize metadata;
  - content summary bằng hash/count khi capture tắt;
  - span/generation/embedding context manager fail-open;
  - score helper;
  - status/flush/shutdown helper.
- Instrument `backend/app/services/llm_client.py` tại `_call_llm` và ba public task.
- Instrument worker operation/assessment ở mức trace gốc và score tổng hợp.
- Instrument BGE HTTP embedding ở mức observation không chứa text.
- Thêm endpoint Admin `GET /v1/admin/langfuse/health` chỉ trả trạng thái cấu hình an toàn, không trả host/key.
- Thêm script `backend/scripts/langfuse_smoke.py` chỉ gửi trace tổng hợp khi người vận hành chủ động chạy.
- Thêm unit test cho disabled/no-op, sanitize, content summary, fake generation/span/score và fail-open.

Ngoài phạm vi LF-1:

- Không dựng Langfuse server.
- Không bật Langfuse ở môi trường thật.
- Không gửi dataset/golden set.
- Không chuyển prompt sang Langfuse Prompt Management.
- Không tạo dashboard nghiệp vụ trong frontend HRApp.

Tiêu chí xong:

- Khi `LANGFUSE_ENABLED=false`, hành vi hiện tại không đổi và test cũ vẫn đạt.
- Khi thiếu key/host hoặc SDK lỗi, LLM/worker vẫn chạy; chỉ mất trace.
- Unit test chứng minh metadata nhạy cảm bị loại và content mặc định không rời ứng dụng.
- Backend test, Ruff phạm vi đổi, type/lint/build frontend không bị ảnh hưởng nếu không sửa frontend.
- Có commit/push và CI success; ghi hash/run vào `Update_Excute_P2.md`.

### LF-2 — Staging synthetic tracing và dashboard vận hành

Trạng thái: **LF-2A ĐÃ TRIỂN KHAI Ở CODE; LF-2B CHƯA MỞ VÌ DEP-01 CHƯA CÓ ENVIRONMENT MAPPING**.

LF-2A đã làm ở code:

- Bổ sung child span metadata-only cho document extraction, deterministic matching, semantic retrieval, evidence verification, scoring và ranking trong `backend/app/workers/processor.py`.
- Tạo runbook `doc/LANGFUSE_STAGING_RUNBOOK.md` cho gate, cấu hình, smoke, workflow tổng hợp, evaluation bridge, fail-open, rollback và tiêu chí đóng LF-2/LF-3.
- Không dựng Langfuse server trong sandbox vì không có Docker/Podman; không suy đoán project Supabase đã kết nối là staging.

Điều kiện mở khóa LF-2B:

- DEP-01 có environment mapping: backend/frontend URL, Supabase project, commit đang chạy, worker topology, chủ trì và cửa sổ triển khai.
- Chọn Cloud project riêng hoặc self-host dev/staging.
- Chỉ dùng fixture/CV tổng hợp hiện có.

Công việc:

- Bật `LANGFUSE_ENABLED=true`, `LANGFUSE_CAPTURE_CONTENT=false`, sample rate 1.0 ở staging tổng hợp.
- Chạy `langfuse_smoke.py` và kiểm tra trace xuất hiện đúng project/environment.
- Chạy luồng synthetic: tạo position/JD → criteria → upload CV → assessment → ranking.
- Tạo dashboard/lưu filter cho:
  - latency p50/p95 theo task/model;
  - lỗi provider/JSON/schema;
  - RULE vs LLM fallback rate;
  - UNCLEAR rate;
  - evidence verified fail rate;
  - BGE fallback/pgvector unavailable;
  - token/cost theo model nếu provider có usage/pricing.
- Bổ sung span chi tiết cho OCR/rule/verification/scoring nếu trace LF-1 chưa đủ chẩn đoán.

Tiêu chí xong:

- Ít nhất một operation tổng hợp truy được từ `operation_id`/`assessment_fingerprint` sang Langfuse trace.
- Không có CV/JD/prompt/output thật trong Langfuse.
- Có bằng chứng dashboard và runbook xử lý khi Langfuse không khả dụng.

### LF-3 — Dataset, experiment và evaluation

Trạng thái: **LF-3A ĐÃ TRIỂN KHAI CẦU NỐI EVALUATION Ở CODE; DATASET/EXPERIMENT ĐẦY ĐỦ CHƯA MỞ**.

LF-3A đã làm ở code:

- Tạo `backend/scripts/push_langfuse_evaluation.py`: đọc cùng snapshot JSON với `evaluate_matching.py`, tính lại `build_repeatability_report` và `compare_rankings`, mặc định chỉ dry-run/in JSON; chỉ gửi score tổng hợp khi có `--send` và Langfuse đã cấu hình.
- Score dự kiến/gửi gồm `repeatability_mean_score_drift`, `repeatability_max_score_drift`, `repeatability_p95_score_drift`, `criterion_flip_rate`, `fingerprint_reuse_rate`, `ranking_kendall_tau`, `ranking_top10_overlap`, `repeatability_passed` và score theo từng fingerprint group.
- Script không gửi snapshot thô, CV text, profile fact, evidence quote, reasoning hoặc chi tiết từng application lên Langfuse.
- HR agreement score chưa triển khai vì repo chưa có nguồn nhãn HR hợp lệ đã duyệt; không suy diễn từ trạng thái vận hành.

Điều kiện mở khóa phần còn lại:

- Có golden set tổng hợp hoặc dữ liệu đã ẩn danh/được phép theo `doc/MATCHING_STABILITY.md`.
- HR chốt nhãn và quy trình phân xử; không dùng trạng thái vận hành yếu thay gold label.

Công việc:

- Tạo dataset versioned cho criteria/profile/matching.
- Chạy experiment theo tổ hợp prompt/model/policy/rule version.
- Đẩy score từ `evaluation.py`: score drift, criterion flip, ranking Kendall/top-k, false MATCH, false NO_MATCH, unresolved rate.
- Tạo annotation/feedback loop có kiểm soát; nhãn HR thật vẫn lưu ở hệ thống nghiệp vụ khi F2.02/labeling được triển khai, Langfuse chỉ nhận score tổng hợp/pseudonymous nếu được duyệt.

Tiêu chí xong:

- Mỗi thay đổi prompt/model/policy có báo cáo experiment trước rollout.
- Không đạt ngưỡng ở `MATCHING_STABILITY.md` thì không phát hành policy mới.

### LF-4 — Pilot production có kiểm soát

Điều kiện mở khóa:

- DEP-01 và các gate triển khai liên quan đạt hoặc có chấp nhận rủi ro bằng văn bản.
- Privacy/Security duyệt đích đến dữ liệu, retention, RBAC, backup, xóa dữ liệu và xử lý sự cố.
- Ưu tiên self-host; nếu dùng Cloud phải có phê duyệt egress/dữ liệu rõ ràng.

Công việc:

- Bật metadata-only theo sample rate đã đo.
- Tạo alert cho lỗi provider, schema failure, UNCLEAR tăng bất thường, BGE fallback và latency/cost vượt ngưỡng.
- Kiểm tra xóa trace theo retention và quyền truy cập project.
- Đối chiếu định kỳ Langfuse với `assessment_runs`/worker health; không dùng Langfuse làm nguồn quyết định.

Tiêu chí xong:

- Có owner vận hành, dashboard, alert, retention evidence và rollback bằng cách đặt `LANGFUSE_ENABLED=false`.

### LF-5 — Prompt management và tối ưu vòng đời AI

Chỉ thực hiện sau LF-3/LF-4 ổn định:

- Đánh giá chuyển prompt từ code sang Langfuse Prompt Management hoặc giữ code là nguồn chuẩn và chỉ link version.
- Nếu chuyển nguồn prompt, phải thiết kế cache/fallback khi Langfuse sập, quy trình duyệt prompt, mapping sang `*_PROMPT_VERSION` và fingerprint.
- Không để prompt production thay đổi ngoài quy trình version/release của HRApp.

## 8. Kế hoạch kiểm thử

### 8.1. Unit test

- Disabled: mọi context manager là no-op, score không gửi.
- Thiếu key/host: không khởi tạo client, không raise.
- SDK/client raise: nghiệp vụ vẫn nhận kết quả gốc.
- Metadata sanitize: loại key chứa `key`, `token`, `secret`, `password`, `cv`, `prompt`, `content`, `email`, `phone`; chuyển ID/count thành scalar an toàn.
- Content summary: có hash/count nhưng không chứa chuỗi CV mẫu.
- Generation success/error: fake client ghi đúng task/model/version và trạng thái lỗi.
- Score helper: tên score và giá trị giữ đúng taxonomy.
- Admin health: không chứa public/secret key hoặc host.

### 8.2. Regression

- Chạy test LLM client hiện có để bảo đảm `_call_llm` không đổi contract.
- Chạy backend full test ở môi trường không có `TEST_DATABASE_URL`; integration DB được CI chạy bằng PostgreSQL dùng một lần.
- Chạy Ruff trên file mới/sửa.
- Nếu sửa frontend ở batch sau mới chạy type-check/lint/build/i18n tương ứng.

### 8.3. Staging smoke

1. Kiểm tra `/v1/admin/langfuse/health`: `enabled=true`, `configured=true`, `client_ready=true` sau lần gửi đầu.
2. Chạy script smoke tổng hợp.
3. Tạo một operation synthetic và đối chiếu `operation_id` trong DB với trace metadata.
4. Tắt Langfuse host tạm thời hoặc dùng key sai trong môi trường test để xác nhận worker vẫn hoàn thành operation.
5. Kiểm tra Langfuse không chứa prompt/CV/output khi capture tắt.

## 9. Rollback

Rollback LF-1 không cần migration:

1. Đặt `LANGFUSE_ENABLED=false` và restart API/worker.
2. Nếu cần rollback code, quay lại commit trước LF-1 sau khi drain worker theo quy trình hiện tại.
3. Không xóa assessment/audit trong PostgreSQL; Langfuse không phải nguồn sự thật.
4. Xóa hoặc hết hạn trace Langfuse theo chính sách của project nếu có sự cố dữ liệu.

## 10. Quyết định và blocker

| Mã | Quyết định/blocker | Trạng thái | Điều kiện mở khóa |
|---|---|---|---|
| LF-D01 | Cloud hay self-host cho staging | CHƯA CHỐT | DEP-01 environment mapping + IT/Security chọn đích đến |
| LF-D02 | Retention trace và quyền xóa | CHƯA CHỐT | Privacy/Security duyệt theo edition/hạ tầng Langfuse |
| LF-D03 | Capture content ở môi trường tổng hợp | MẶC ĐỊNH KHÔNG | Chỉ bật khi có nhu cầu debug và dữ liệu tổng hợp đã duyệt |
| LF-D04 | Dataset/golden set trên Langfuse | CHƯA MỞ | Có dữ liệu được phép và quy trình nhãn HR |
| LF-D05 | Prompt Management | HOÃN | Sau LF-3/LF-4; cần thiết kế fallback/version/fingerprint |
| LF-B01 | DEP-01 chưa có staging mapping | ĐANG CHẶN TRIỂN KHAI SERVER/STAGING | Có inventory môi trường, owner và cửa sổ triển khai |

## 11. Nguồn tham khảo

- Langfuse Observability: https://langfuse.com/docs/observability/overview
- Langfuse Python/JS SDK: https://langfuse.com/docs/observability/sdk/overview
- Langfuse Instrumentation: https://langfuse.com/docs/observability/sdk/instrumentation
- Langfuse Scores: https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk
- Langfuse Self-hosting/ClickHouse: https://langfuse.com/docs/deployment/v3/components/clickhouse
- Langfuse Data Retention: https://langfuse.com/docs/administration/data-retention
- Langfuse Masking: https://langfuse.com/docs/observability/features/masking
