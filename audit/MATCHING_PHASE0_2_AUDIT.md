# Audit Phase 0–2: Matching CV–JD ổn định

- **Ngày audit:** 07/11/2026
- **Phạm vi:** `2243aea..9a20ad8`
- **Commit được audit:**
  - `f4eacd9` — nền tảng đánh giá xác định/fingerprint
  - `bb05950` — rule engine xác định
  - `233070b` — sửa chọn câu bằng chứng
  - `9a20ad8` — đo ổn định và golden set
- **Quy mô diff:** 25 file, khoảng 2.354 dòng thêm và 93 dòng xóa.
- **Phương pháp:** rà diff/code, chạy probe độc lập cho rule engine, chạy test/lint/build, đối chiếu migration và dữ liệu remote. Vòng audit này chỉ ghi nhận phát hiện, không sửa code.

## Kết luận tóm tắt

Không phát hiện lỗi **Critical** về lộ secret, sai position scope, phá worker fencing hoặc làm mất audit trail. Tuy nhiên có **4 phát hiện High** trong rule engine có thể tạo `MATCH`/`NO_MATCH` sai cho tiêu chí bắt buộc. Vì vậy:

> Chưa nên coi rule `NO_MATCH` hiện tại là đủ tin cậy cho quyết định loại/shortlist nếu HR chưa đối chiếu CV. Cần sửa các phát hiện High và bổ sung regression test trước khi mở rộng pilot.

| Mức | Số lượng |
|---|---:|
| Critical | 0 |
| High | 4 |
| Medium | 5 |
| Low | 3 |

## Những phần đã xác nhận đúng

- Migration `00008` có trên Supabase remote ở version `20261107012433 deterministic_assessment_foundation`.
- Remote có đủ 4 cột mới trên `assessment_runs`, 4 cột mới trên `criterion_assessment_results`, unique partial index cho fingerprint `COMPLETED`, và policy `assessment-v2.0`.
- Fingerprint bao gồm application/position, JD/criteria version, rubric, profile version/facts, CV text hash, runtime AI công khai, seed, prompt version, matching policy và rules version.
- Runtime snapshot dùng `public_runtime`, không chứa API key plaintext/ciphertext.
- CV được redaction trước deterministic matching và trước LLM fallback.
- Rule engine chạy local, không gửi dữ liệu ra dịch vụ ngoài.
- LLM fallback chỉ nhận rubric con chưa được rule quyết định.
- Điểm/coverage/status vẫn do `MatchingEngine` xác định tính; LLM không trực tiếp ghi điểm cuối.
- Quote được verify lại bằng span trên CV text trước khi lưu evidence.
- Không thay đổi logic position scope, worker fencing/ownership, approved criteria immutable hoặc audit trail hiện hữu.

## Phát hiện High

### H1. Rule số năm có thể tạo `NO_MATCH` sai và quote không chứng minh được kết luận

**Vị trí:**

- `backend/app/services/deterministic_matching.py:616` — `candidate_years_experience`
- `backend/app/services/deterministic_matching.py:698` — `_best_quote`
- `backend/app/services/deterministic_matching.py:754` — `_evaluate_years`

**Bằng chứng tái hiện:**

Hai công việc riêng biệt, mỗi việc ghi 3 năm, yêu cầu 5 năm:

```text
Python Engineer at A. Built APIs for 3 years.
Python Engineer at B. Built services for 3 years.
```

Kết quả hiện tại:

- `candidate_years_experience = 3.0`
- Outcome: `NO_MATCH`
- Quote lưu: `Python Engineer at B.`

**Nguyên nhân:**

- Các duration tường minh được lấy giá trị lớn nhất, không cộng các khoảng công việc riêng biệt; chỉ date interval mới được merge/cộng.
- `_best_quote` ưu tiên số term khớp trước tín hiệu duration, nên có thể chọn câu chức danh thay vì câu chứa số năm.

**Tác động:** Tiêu chí must-have có thể bị gắn mismatch dù tổng kinh nghiệm thực tế đủ; quote hiển thị cho HR không chứng minh reasoning.

**Khuyến nghị:**

1. Chỉ trả `NO_MATCH` khi tổng số năm đáng tin cậy, ví dụ profile total hoặc date intervals đã merge.
2. Nếu có nhiều duration riêng lẻ mà không biết chồng lấp, trả unresolved thay vì `NO_MATCH`.
3. Quote của YEARS rule bắt buộc chứa duration/date evidence; nếu cần, lưu nhiều evidence item cho nhiều khoảng việc.
4. Thêm regression test cho nhiều công việc, duration chồng lấp và quote chứa số năm.

### H2. Rule ngoại ngữ phụ thuộc thứ tự câu và có thể chọn mức thấp hơn để kết luận

**Vị trí:** `backend/app/services/deterministic_matching.py:854` — `_evaluate_language`

**Bằng chứng tái hiện:**

Cùng nội dung, chỉ đổi thứ tự hai câu IELTS:

- `English IELTS 7.0. English IELTS 5.5.` → `MATCH`
- `English IELTS 5.5. English IELTS 7.0.` → `NO_MATCH`

**Nguyên nhân:** Level được trích từ một chunk được chọn và regex lấy lần xuất hiện đầu tiên; engine không tổng hợp mức cao nhất đáng tin cậy trên toàn bộ bằng chứng ngôn ngữ.

**Tác động:** Kết quả thay đổi theo thứ tự trình bày trong CV dù nội dung nghiệp vụ không đổi; có thể tạo false `NO_MATCH` cho IELTS/TOEIC/CEFR.

**Khuyến nghị:**

- Thu thập mọi level theo từng ngôn ngữ, ưu tiên level cao nhất có quote hợp lệ.
- Nếu nhiều level mâu thuẫn không rõ chứng chỉ nào còn hiệu lực, gắn `UNCLEAR`/cần HR xác minh thay vì lấy câu đầu tiên.
- Quote phải chứa nguyên vẹn level, ví dụ không cắt `IELTS 7.0` thành `IELTS 7.`.

### H3. Rule bằng cấp trộn profile fact với quote CV không tương ứng

**Vị trí:** `backend/app/services/deterministic_matching.py:794` — `_evaluate_degree`

**Bằng chứng tái hiện:**

- CV quote: `Bachelor of Computer Science, Example University.`
- Profile fact: bằng Master's.
- Yêu cầu: Master's degree.
- Kết quả: `MATCH`, reasoning nói education level 4, nhưng quote chỉ chứng minh Bachelor.

**Nguyên nhân:** `highest` được nâng bởi profile facts, trong khi `best_chunk`/quote vẫn là chunk có bằng thấp hơn. Ngoài ra, `NO_MATCH` được suy từ cấp bằng cao nhất parse được; nếu section Education bị chunk/parse thiếu, kết luận có thể quá mạnh.

**Tác động:** HR thấy quote không chứng minh outcome; có rủi ro false match hoặc false no-match khi profile extraction/HR correction lệch với CV.

**Khuyến nghị:**

- Chỉ quyết định từ chunk mà chính quote parse được cấp bằng yêu cầu.
- Nếu chỉ profile fact đạt nhưng quote CV không đạt, trả unresolved hoặc tạo loại evidence riêng cho profile fact, không dùng quote CV thấp hơn làm bằng chứng.
- Chỉ dùng degree `NO_MATCH` khi education evidence được xác định đầy đủ theo policy HR.

### H4. Constituent token của phrase có thể tạo false `MATCH` cho kỹ năng

**Vị trí:**

- `backend/app/services/deterministic_matching.py:399` — `_add_term`
- `backend/app/services/deterministic_matching.py:909` — `_evaluate_generic`

**Bằng chứng tái hiện:**

- Tiêu chí: `Python programming`, keyword `Python programming`.
- CV: `Programming reliable business systems for clients.`
- Kết quả: `MATCH`, matched labels gồm `python programming, programming` dù CV không hề nhắc Python.

**Nguyên nhân:** Một multi-word phrase được mở rộng thành các token cấu thành và các token đó vẫn tính là cùng term group; coverage do đó đủ ngưỡng quyết định.

**Tác động:** Kỹ năng bắt buộc có thể được coi là đạt chỉ vì một từ chung như `programming`, làm tăng điểm và coverage sai.

**Khuyến nghị:**

- Token cấu thành chỉ dùng để retrieval候補, không tự tính coverage đạt yêu cầu.
- Muốn decisive, chunk phải chứa canonical concept hoặc đầy đủ các concept bắt buộc của phrase.
- Thêm test phủ định cho `programming` không có Python, `development` không có Java, và các phrase tương tự.

## Phát hiện Medium

### M1. Requirement spec chưa phải atomic requirement được HR duyệt tường minh

**Vị trí:**

- `backend/app/schemas/criteria.py:30`
- `backend/app/services/deterministic_matching.py:462`

Criterion hiện có name/description/category/weight/keywords/guidance, nhưng chưa có requirement type, operator, threshold, unit, ontology ID hoặc accepted evidence dạng cấu trúc. Rule engine tự suy loại/threshold từ văn bản tự do tại runtime.

**Rủi ro:** Cùng một câu chữ có thể bị hiểu khác ý HR, ví dụ “Bachelor preferred”, “5 years in a team of 10” hoặc yêu cầu nhiều kỹ năng trong một criterion.

**Khuyến nghị:** Bổ sung requirement spec có cấu trúc vào rubric, cho HR xem/duyệt/sửa trước approval; bản suy tự động chỉ là bản nháp.

### M2. LLM fallback chưa tuân thủ hoàn toàn kiến trúc chunk-ID và một finding lỗi có thể làm fail toàn bộ application

**Vị trí:**

- `backend/app/services/llm_client.py:66`
- `backend/app/services/llm_client.py:438`
- `backend/app/workers/processor.py:763`

Hiện tại:

- Provider vẫn được gọi bằng `response_format={"type":"json_object"}`; JSON Schema được kiểm bằng Pydantic ở client, không phải provider strict structured output.
- Một finding có outcome ngoài enum làm toàn bộ payload bị reject và assessment của application bị fail, thay vì chỉ hạ riêng criterion đó thành `UNCLEAR`.
- LLM fallback vẫn nhận toàn bộ CV text đã redaction và tự sinh quote; chưa nhận candidate chunks/chunk IDs để chỉ chọn bằng chứng.

**Khuyến nghị:** Dùng provider JSON Schema strict nếu endpoint hỗ trợ; parse từng finding độc lập và canonical hóa finding lỗi thành `UNCLEAR`; chuyển fallback sang candidate chunk IDs trong bước kiến trúc tiếp theo.

### M3. Fingerprint chưa tự chứa mọi tham số điểm/coverage và thời gian hiện tại

**Vị trí:**

- `backend/app/core/config.py:69-80`
- `backend/app/workers/processor.py:691`

Fingerprint chứa version string do con người tăng thủ công, nhưng không hash trực tiếp `STRONG_MATCH_SCORE`, `MATCH_SCORE`, `MIN_EVIDENCE_COVERAGE` hoặc group policy thực tế. Nếu chỉ thay các giá trị môi trường này mà quên tăng `MATCHING_POLICY_VERSION`, assessment cũ vẫn được tái sử dụng.

Ngoài ra date interval dùng `date.today()` nhưng ngày hiện tại không nằm trong fingerprint/rules version.

**Khuyến nghị:** Đưa score map, coverage threshold và các policy parameter thực tế vào fingerprint payload; ghi rõ rule dùng mốc thời gian nào khi tính current role.

### M4. Assessment API phơi provider snapshot rộng hơn cần thiết

**Vị trí:** `backend/app/schemas/applications.py:126`

`AssessmentRun.provider_model_snapshot` được trả qua application/assessment API. Snapshot không có secret plaintext/ciphertext, nhưng có thể chứa provider, Base URL, model và `api_key_hint`.

**Rủi ro:** Người dùng chỉ cần xem kết quả ứng viên, kể cả HM summary-only, không cần metadata vận hành AI hoặc hint của API key.

**Khuyến nghị:** Chỉ trả snapshot này cho Admin/HR có quyền vận hành; với HM và summary response, loại bỏ `api_key_hint`, Base URL và thông tin provider không cần thiết.

### M5. Integration/reuse chưa được kiểm chứng end-to-end và remote chưa có dữ liệu matching mới

**Bằng chứng:**

- Backend test trong sandbox: 52 passed, 57 skipped; integration bị skip vì không có `TEST_DATABASE_URL` phù hợp.
- Tại thời điểm audit, Supabase remote có `fingerprinted_runs = 0` và `rule_results = 0`.

**Ý nghĩa:** Migration đã sẵn sàng nhưng code matching mới chưa được chứng minh trên VPS/remote bằng một operation thật hoặc integration DB dùng một lần. Chưa có test end-to-end riêng cho fingerprint reuse 100%, rule-first không gọi LLM, và LLM fallback chỉ nhận rubric con.

**Khuyến nghị:** Chạy integration trên PostgreSQL `_test` cục bộ và một smoke operation bằng dữ liệu tổng hợp sau deploy; không dùng CV thật cho smoke chưa được phê duyệt.

## Phát hiện Low

### L1. Quote span lấy lần xuất hiện đầu tiên khi phrase lặp lại

**Vị trí:** `backend/app/services/matching.py` — `find_quote_span`/`quote_pages`

Nếu cùng câu/skill xuất hiện ở nhiều page, hệ thống lấy span đầu tiên. Page và quote vẫn thuộc CV nhưng có thể không phải vị trí HR/LLM dự định. Nên lưu chunk/offset từ rule hoặc chọn span theo page gợi ý hợp lệ.

### L2. `HYBRID` chưa có đường code nào tạo ra

DB/UI hỗ trợ `HYBRID`, nhưng worker hiện gán từng criterion là `RULE` hoặc `LLM`. Nhãn này hiện chỉ là khả năng dự phòng, không nên mô tả là đã dùng cho quyết định hợp nhất.

Ngoài ra `ranking_runs.policy_version` vẫn ghi `v1.0` trong khi assessment policy là `assessment-v2.0`; cần thống nhất ý nghĩa version giữa assessment và ranking.

### L3. CLI evaluation còn phụ thuộc thứ tự input và chưa có exporter chính thức

**Vị trí:**

- `backend/app/services/evaluation.py:158`
- `backend/scripts/evaluate_matching.py:30`

CLI suy candidate ranking từ lần xuất hiện cuối trong file, nên file không sắp xếp theo thời gian có thể cho báo cáo sai. Kendall hiện là dạng đơn giản, chưa xử lý ties kiểu tau-b đầy đủ. Chưa có endpoint/exporter chính thức từ assessment DB sang snapshot JSON.

**Khuyến nghị:** Yêu cầu `created_at`/`run_index`, sort tường minh, ghi rõ công thức Kendall, và bổ sung exporter chỉ đọc cho QA.

## Khoảng trống so với kiến trúc đích

Các mục sau không tính là lỗi hồi quy vì đã được ghi là bước tiếp theo, nhưng chưa hoàn thành:

1. Chưa có pgvector/FTS hybrid production schema, embedding BGE, cross-encoder reranker hoặc NLI service.
2. Chưa có golden set CV thật do HR gán nhãn; fixture hiện tại là dữ liệu tổng hợp.
3. Chưa có nút/API “force rerun” tường minh; muốn chạy lại hiện phải tạo thay đổi có version mới.
4. Chưa cân nhắc Learning-to-Rank; điều này đúng chủ trương vì chưa có nhãn HR thật.

## Kiểm tra đã chạy

```text
Backend pytest: 52 passed, 57 skipped
Ruff các file matching/evaluation mới: passed
Frontend i18n: 3 passed
Frontend type-check: passed
Frontend lint: passed
Frontend production build: passed
Supabase migrations: 8 migrations, mới nhất 20261107012433
Remote schema: đủ cột/index/policy 00008
Remote tại thời điểm audit: 0 fingerprinted runs, 0 RULE results
```

57 integration test bị skip do không có `TEST_DATABASE_URL`; đây là giới hạn môi trường kiểm thử, không phải bằng chứng integration đạt.

## Thứ tự xử lý khuyến nghị

1. Sửa H1–H4 và thêm regression test cho từng probe.
2. Tăng `DETERMINISTIC_RULES_VERSION` sau khi sửa rule.
3. Chạy integration DB dùng một lần và smoke tổng hợp trên staging/VPS.
4. Bổ sung structured requirement spec cho HR duyệt (M1).
5. Thu hẹp provider snapshot theo quyền (M4) và đưa policy parameters vào fingerprint (M3).
6. Sau khi có golden set HR thật, mới hiệu chuẩn rule/LLM fallback và cân nhắc semantic retrieval.
