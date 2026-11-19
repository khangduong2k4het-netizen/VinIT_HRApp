# Triển khai pgvector/BGE/LTR

## Phạm vi đã hoàn thành

- **pgvector:** migration `00010_pgvector_bge_ltr.sql` đã áp lên Supabase project `myrymlqdbyqmpynesiwk` với version `20261107022845`. Đã verify extension `vector`, bảng `app_private.cv_chunk_embeddings` dùng cột `vector(1024)`, HNSW cosine index, bảng registry `app_private.ltr_model_versions`, cột `ranking_runs.ltr_model_version`, `ranking_runs.ltr_mode` và `ranking_items.ltr_score`.
- **BGE:** provider OpenAI-compatible `/embeddings` với kiểm tra endpoint/dimension, chuẩn hoá vector và query instruction. `hash` chỉ là provider test/plumbing, không phải BGE.
- **Semantic retrieval:** worker embed CV chunks và requirement query, lưu/truy vấn pgvector theo document/chunk/text hash/model/index version, merge với lexical candidates và fallback in-memory/lexical khi provider hoặc pgvector lỗi. Semantic chunks chỉ bổ sung candidate cho LLM fallback, tối đa 5 chunk/criterion; không tạo finding hoặc thay đổi deterministic outcome.
- **Fingerprint:** khi semantic bật, provider/model/dimension/index version/top-k/min-similarity/query instruction được pin vào assessment fingerprint. Khi tắt, fingerprint không đổi so với hành vi trước.
- **LTR:** pairwise logistic ranker train offline, tách holdout theo group/position, fail-closed khi dữ liệu thiếu, có NDCG@10/pairwise accuracy cùng gate số ví dụ/group holdout. Registry luôn bắt đầu ở `DRAFT`; ACTIVE chỉ nhận artifact registry đã `APPROVED` hoặc artifact file do vận hành chỉ định và đạt gate.
- **Ranking:** `OFF` giữ nguyên policy; `SHADOW` ghi `ltr_score` nhưng không đổi thứ hạng; `ACTIVE` chỉ reorder trong cùng mandatory status và cùng coverage-eligibility gate. LTR không cho ứng viên vượt `POSSIBLE_MISMATCH`, `NOT_ASSESSED` hoặc coverage gate.

## Validation

- Targeted semantic/LTR tests: **15 passed**.
- Full backend suite: **82 passed, 58 skipped**. Các integration test bị skip khi không có PostgreSQL test cục bộ dùng một lần.
- Train CLI trên dữ liệu tổng hợp đạt NDCG@10 `1.0`, pairwise accuracy `1.0` và pass gate synthetic.
- Frontend: i18n **3 passed**, type-check, lint và production build đều đạt.
- Ruff `--select F` trên các module semantic/LTR/worker/scripts/test liên quan: đạt.

## Giới hạn production

- Chưa cấu hình BGE endpoint/model runtime thật trong môi trường này; cấu hình mặc định vẫn `SEMANTIC_RETRIEVAL_ENABLED=false`, `EMBEDDING_PROVIDER=disabled`.
- Dataset export hiện chỉ có weak label từ trạng thái vận hành, không phải HR gold label. Không bật `LTR_MODE=ACTIVE` cho tới khi có labelled dataset HR đủ lớn, holdout đạt gate và artifact được phê duyệt rõ ràng.
- Không có tuyên bố production-ready cho chất lượng semantic/LTR trên CV thật cho tới khi đo trên golden set HR thật.

## Đồng bộ tài liệu

Các tài liệu liên quan đã được cập nhật để phản ánh trạng thái trên: `README.md`, `DEPLOYMENT.md`, `doc/MATCHING_STABILITY.md`, `doc/HRA_ArchitectureDesign.md`, `doc/HRA_DatabaseDesign.md`, `doc/HRA_LLM_Architecture.md`, `doc/HRA_Phase1_Architecture.md`, `doc/HRA_TechnicalRecomment.md`, `doc/HRA_InterfaceDesign.md`, `doc/HRA_NextPhase.md`, `doc/VPS_DEPLOYMENT.md`, `doc/VPS_DEPLOYMENT_NO_DOCKER.md` và các file `.env.example`. Các tài liệu audit lịch sử không bị viết lại; báo cáo này là điểm truy vết cho vòng triển khai pgvector/BGE/LTR.
