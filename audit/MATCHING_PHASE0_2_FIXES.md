# Khắc phục audit Phase 0–2: Matching CV–JD

- **Ngày:** 07/11/2026
- **Audit gốc:** `audit/MATCHING_PHASE0_2_AUDIT.md`
- **Phạm vi sửa:** H1–H4, M1–M5 và L1–L3 ở mức code/test/migration có thể khép kín trong repo.

## Kết quả theo phát hiện

| ID | Trạng thái | Cách khắc phục |
|---|---|---|
| H1 | Đã sửa | Cộng các duration riêng biệt đã khử trùng theo câu; merged date intervals/profile total mới là tổng đáng tin cậy cho `NO_MATCH`. Duration rời rạc dưới ngưỡng thành unresolved. Quote của YEARS ưu tiên câu chứa duration/date. |
| H2 | Đã sửa | Thu thập mọi level IELTS/TOEIC/CEFR/định tính theo từng câu; mức mâu thuẫn cho cùng metric thành unresolved, không phụ thuộc thứ tự. Parser giữ số thập phân và splitter không cắt `7.0`. |
| H3 | Đã sửa | Degree chỉ quyết định từ quote CV parse được. Profile fact cao hơn quote CV thành unresolved. `NO_MATCH` chỉ khi có Education section parse được cấp bằng thấp hơn. |
| H4 | Đã sửa | Bỏ constituent-token tự thỏa mãn phrase; `programming` không còn đạt `Python programming`. Concept đã biết trong phrase vẫn là term group riêng. |
| M1 | Đã sửa | Thêm `requirement_spec` JSONB có cấu trúc, schema validate theo kind/threshold, HR sửa trong dialog tiêu chí, AI draft lưu spec suy luận, HR approval materialize spec còn thiếu trước khi HM duyệt. |
| M2 | Đã sửa | LLM fallback nhận rubric con và tối đa 5 candidate chunks theo criterion, yêu cầu `chunk_id`; finding lỗi được parse độc lập và hạ `UNCLEAR`. Strict JSON Schema là opt-in qua `LLM_STRICT_JSON_SCHEMA`. |
| M3 | Đã sửa | Fingerprint hash trực tiếp score map, coverage/strength thresholds, group weights, ranking policy, strict-schema flag và `evaluation_date`; tăng rules version lên `deterministic-rules-v1.1`. |
| M4 | Đã sửa | `provider_model_snapshot` được sanitize: người không có quyền vận hành chỉ thấy model provenance tối thiểu, không có Base URL/config ID/API key hint; ADMIN mới thấy public snapshot đầy đủ. |
| M5 | Đã bổ sung test, chưa chạy DB thật | Thêm integration test cho fingerprint reuse, rule-first không gọi lại LLM và fallback chỉ nhận rubric con/candidate chunks. Sandbox không có PostgreSQL/Docker nên test vẫn skip. |
| L1 | Đã sửa | Quote lặp lại được chọn theo page/chunk range gợi ý; page được tính từ chính span đã chọn. |
| L2 | Đã làm rõ | `HYBRID` là giá trị dự phòng cho quyết định hợp nhất tương lai; code hiện tại chỉ tạo `RULE`/`LLM`. Ranking dùng `ranking-v2.0`. |
| L3 | Đã sửa | Evaluation/CLI sắp xếp run theo `run_index`/`created_at`, Kendall chuyển sang tau-b có tie correction và có exporter DB chỉ đọc không xuất CV/profile/quote/provider snapshot. |

## Migration

- File: `supabase/migrations/00009_structured_requirement_specs.sql`
- Đã áp lên Supabase project `myrymlqdbyqmpynesiwk` với version `20261107021622 structured_requirement_specs`.
- Đã verify cột `app_private.criteria_items.requirement_spec` tồn tại với kiểu `jsonb`.

## Kiểm chứng đã chạy

```text
Backend pytest: 67 passed, 58 skipped
Ruff (F) trên deterministic/evaluation/matching/ai_config/scripts/tests mới: passed
Frontend i18n: 3 passed
Frontend type-check: passed
Frontend lint: passed
Frontend production build: passed
Evaluation CLI mẫu: passed, fingerprint reuse 1.0, P95 drift 0.0
git diff --check: passed
```

58 test bị skip gồm integration PostgreSQL dùng một lần và các test phụ thuộc môi trường; không được coi là bằng chứng integration DB thật đã đạt. Chưa dùng CV HR thật và chưa triển khai pgvector/BGE/LTR.
