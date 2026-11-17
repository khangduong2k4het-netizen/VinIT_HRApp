# Phase 3 — P3-1 (Talent Pool, pha 1), P3-2 (chất lượng AI), P3-3 (cổng ứng tuyển công khai)

> Trạng thái: **đã có code và test local**, chưa deploy, chưa áp migration lên Supabase/VPS. Spec thiết kế ở `doc/phase3/`. Mọi mục dưới đây chưa được coi là hoàn thành trên môi trường đích.

## Phạm vi đã làm

| Mục | Nội dung | Migration | Test |
| :--- | :--- | :--- | :--- |
| P3-2 backend | `GET /v1/analytics/quality/trends`, `/quality/breakdown`, `/quality/markers`, `POST /quality/markers` (Admin). Mẫu ngẫu nhiên và nhóm rủi ro tách riêng; ô dưới 20 ca ẩn tỷ lệ; khoảng tin cậy Wilson 95%; không chia theo recruiter | `00019` | `test_ai_quality.py` |
| P3-2 giao diện | Trang `/reports/ai-quality` (mục "Chất lượng AI" ở thanh bên) | — | `frontend/tests/ai-quality-ui.test.cjs` |
| P3-3 cổng công khai | Trang `/apply`; `GET /v1/public/positions`, `POST /v1/public/positions/{code}/apply`; HR bật theo vị trí qua `PUT /v1/positions/{id}/public-apply` | `00020` | `test_public_intake_talent_pool.py` |
| P3-1 pha 1 | Consent ghi lúc nộp (`application_data_consents`), HR đánh dấu vào pool, luật đủ điều kiện (5 năm từ ngày nhận CV), rút đồng ý. **Chưa có quét/xếp hạng** | `00020` | `test_public_intake_talent_pool.py` |

## Cấu hình mới

| Biến | Mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `PUBLIC_INTAKE_ENABLED` | `false` | Bật cổng `/apply`. Tắt thì mọi endpoint công khai trả 404 |
| `PUBLIC_INTAKE_IP_SALT` | rỗng | Muối để băm địa chỉ IP (chỉ lưu bản băm) |
| `PUBLIC_INTAKE_MAX_PER_IP_HOUR` | `5` | Số lần thử tối đa mỗi giờ cho một địa chỉ |
| `PUBLIC_INTAKE_TRUSTED_PROXY_HOPS` | `0` | Số proxy tin cậy nối vào `X-Forwarded-For`; xem `DEPLOYMENT.md` |
| `PUBLIC_INTAKE_NOTICE_VERSION` | `v1` | Phiên bản câu chữ ô đồng ý; đổi câu chữ thì phải tăng |
| `MALWARE_SCAN_MODE` | `off` | `clamav` để quét qua clamd; production bắt buộc, nếu không hệ thống từ chối nhận hồ sơ |
| `CLAMD_HOST` / `CLAMD_PORT` / `CLAMD_TIMEOUT_SECONDS` | `127.0.0.1` / `3310` / `10` | Kết nối clamd |
| `TALENT_POOL_RETENTION_MONTHS` | `60` | Thời hạn dùng lại hồ sơ, tính từ ngày nhận CV |

## Audit

`RECEIVE_PUBLIC_CV`, `SET_PUBLIC_APPLY`, `MARK_TALENT_POOL`, `UNMARK_TALENT_POOL`, `WITHDRAW_TALENT_POOL_CONSENT`, `CREATE_QUALITY_MARKER`. Metadata chỉ chứa số đếm, kích thước và mã, không chứa tên, nội dung CV hay nội dung ghi chú.

## Chưa làm / điểm mở

- Quét và xếp hạng Talent Pool (P3-1 pha 2) và giao diện đánh dấu/danh sách pool.
- Câu chữ hai ô đồng ý trên `/apply` là **bản nháp chưa được HR Lead/Pháp chế duyệt**; không bật cổng trên dữ liệu thật trước khi duyệt.
- Mốc 5 năm của pool (từ ngày nhận CV) lệch với hàng đợi xóa hiện có (12 tháng sau khi đóng vị trí). Chưa đổi gì ở phần xóa; cần HR Lead chọn hướng (xem `doc/phase3/P3-1_TALENT_POOL_SPEC.md`, mục 5).
- Chưa có CAPTCHA; chưa thử quét mã độc với ClamAV thật (mới kiểm tra giao thức bằng máy chủ giả).
- Nhận CV qua hộp thư (P3-3 bước 3) tạm gác, chưa có phương án.
- Reranker (P3-4) do người khác phụ trách.

## Chạy test local

```
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/hra_phase1_test pytest backend/tests
cd frontend && npm run test:unit && npm run test:i18n && npm run type-check
```
