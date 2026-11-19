# Phase 3 — P3-1 (Talent Pool), P3-2 (chất lượng AI), P3-3 (cổng ứng tuyển công khai)

> Cập nhật 19/11/2026: đã có code, migration đến `00023` và kiểm thử local trên PostgreSQL dùng một lần. Chưa deploy hoặc áp migration lên Supabase/VPS. Spec thiết kế ở `doc/phase3/`; hướng dẫn nghiệm thu kênh web P3-3 ở [P3-3_PUBLIC_INTAKE.md](phase3/P3-3_PUBLIC_INTAKE.md). Không coi kiểm thử local là nghiệm thu môi trường đích.

## Phạm vi đã làm

| Mục | Nội dung | Migration | Test |
| :--- | :--- | :--- | :--- |
| P3-2 backend | `GET /v1/analytics/quality/trends`, `/quality/breakdown`, `/quality/markers`, `POST /quality/markers` (Admin). Mẫu ngẫu nhiên và nhóm rủi ro tách riêng; ô dưới 20 ca ẩn tỷ lệ; khoảng tin cậy Wilson 95%; không chia theo recruiter | `00019` | `test_ai_quality.py` |
| P3-2 giao diện | Trang `/reports/ai-quality` (mục "Chất lượng AI" ở thanh bên) | — | `frontend/tests/ai-quality-ui.test.cjs` |
| P3-3 cổng công khai | `/apply`, danh sách vị trí công khai, nộp CV; HR bật/tắt theo vị trí; một ô consent bắt buộc cho xử lý hồ sơ và Talent Pool (notice `v4`); rút consent bằng mã tại `/apply/withdraw` | `00020`, `00021` | `test_public_intake_talent_pool.py`, `test_public_intake_browser.py`, `public-apply-ui.test.cjs` |
| P3-1 pha 1–2 | Consent ghi lúc nộp; HR đánh dấu, danh sách pool; worker quét/chấm lại theo rubric vị trí mới; xếp hạng và trích dẫn kiểm chứng; ẩn kết quả hết điều kiện | `00020`, `00023` | `test_public_intake_talent_pool.py`, `test_talent_pool_scan.py` |
| Retention 5 năm | Chính sách `v2.0-60month`: 60 tháng từ ngày đóng vị trí; chu kỳ retention hủy case chưa xóa thuộc chính sách cũ, giữ nguyên legal hold | `00022` | `test_ocr_images_retention.py` |

## Cấu hình mới

| Biến | Mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `PUBLIC_INTAKE_ENABLED` | `false` | Bật tiếp nhận ở `/apply`; khi tắt vẫn cho rút consent Talent Pool |
| `PUBLIC_INTAKE_IP_SALT` | rỗng | Muối để băm địa chỉ IP (chỉ lưu bản băm) |
| `PUBLIC_INTAKE_MAX_PER_IP_HOUR` | `5` | Số lần thử tối đa mỗi giờ cho một địa chỉ |
| `PUBLIC_INTAKE_TRUSTED_PROXY_HOPS` | `0` | Số proxy tin cậy nối vào `X-Forwarded-For`; xem `DEPLOYMENT.md` |
| `PUBLIC_INTAKE_NOTICE_VERSION` | `v4` | Phải khớp `CONSENT_NOTICE_VERSION` ở frontend; thiếu/khác phiên bản khi nộp trả 409 |
| `MALWARE_SCAN_MODE` | `off` | `clamav` để quét qua clamd; production bắt buộc, nếu không hệ thống từ chối nhận hồ sơ |
| `CLAMD_HOST` / `CLAMD_PORT` / `CLAMD_TIMEOUT_SECONDS` | `127.0.0.1` / `3310` / `10` | Kết nối clamd |
| `TALENT_POOL_RETENTION_MONTHS` | `60` | Thời hạn dùng lại hồ sơ, tính từ lúc ứng viên tick đồng ý Talent Pool (`application_data_consents.granted_at`) |

## Audit

`RECEIVE_PUBLIC_CV`, `SET_PUBLIC_APPLY`, `MARK_TALENT_POOL`, `UNMARK_TALENT_POOL`, `WITHDRAW_TALENT_POOL_CONSENT`, `WITHDRAW_TALENT_POOL_CONSENT_BY_CANDIDATE`, `START_TALENT_POOL_SCAN`, `VIEW_TALENT_POOL_RESULTS`, `CREATE_QUALITY_MARKER`. Metadata chỉ chứa số đếm, kích thước và mã, không chứa tên, nội dung CV hay nội dung ghi chú.

## Chưa làm / điểm mở

- Talent Pool chưa có lưu quyết định `CONTACT/SKIP/LATER` hoặc cập nhật CV qua link.
- Theo yêu cầu mới nhất của chủ dự án ngày 19/11, notice `v4` có một ô đồng ý bắt buộc cho xử lý hồ sơ và Talent Pool, mặc định không chọn. Bản ghi `v1`/`v2`/`v3` giữ nguyên, không diễn giải lại hoặc tự cấp consent cho hồ sơ cũ. Cần HR Lead/Pháp chế xác nhận câu chữ phát hành.
- Retention hồ sơ = ngày đóng vị trí + 60 tháng; quyền dùng lại trong pool = ngày đồng ý + 60 tháng. Hết hạn pool/rút consent chặn dùng lại, không tự động xóa hồ sơ đang ứng tuyển.
- Chưa có CAPTCHA; đã có honeypot, rate limit, giới hạn body và quét ClamAV. Nghiệm thu staging với reverse proxy thật vẫn chưa thực hiện.
- P3-2 chưa có xuất golden set ẩn danh và đủ mọi chiều phân rã của spec.
- Nhận CV qua hộp thư (P3-3 bước 3) chưa triển khai; cần chọn Microsoft 365/Gmail/IMAP và cấp quyền kết nối.
- Reranker (P3-4) do người khác phụ trách.

## Chạy test local

```
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/hra_phase1_test pytest backend/tests
cd frontend && npm run test:unit && npm run test:i18n && npm run type-check
```
