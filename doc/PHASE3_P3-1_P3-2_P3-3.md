# Phase 3 — P3-1 (Talent Pool), P3-2 (chất lượng AI), P3-3 (cổng ứng tuyển công khai & Partner API)

> Trạng thái: **đã hoàn thiện code và test local/PostgreSQL**, câu chữ đồng ý một ô bắt buộc (`notice v2`) đã được chốt pháp lý; chưa deploy lên VPS/Supabase production. Spec thiết kế ở `doc/phase3/`.

## Phạm vi đã làm

| Mục | Nội dung | Migration | Test |
| :--- | :--- | :--- | :--- |
| P3-2 backend | `GET /v1/analytics/quality/trends`, `/quality/breakdown` (khối ngành, phòng ban, lý do override, loại cờ QA, phiên bản chính sách, loại tệp, loại tiêu chí), `/quality/markers`, `POST /quality/markers` (Admin), `GET /v1/analytics/quality/golden-set/export` (HR Lead/Admin, JSON/CSV ẩn danh + audit). Mẫu ngẫu nhiên và nhóm rủi ro tách riêng; ô dưới 20 ca ẩn tỷ lệ; khoảng tin cậy Wilson 95%; không chia theo recruiter | `00019` | `test_ai_quality.py` |
| P3-2 giao diện | Trang `/reports/ai-quality` (bộ lọc phòng ban/khối ngành/vị trí, trục thời gian lấp kỳ trống, mốc thay đổi, phân rã đa chiều, xuất tập nhãn ẩn danh cho HR Lead/Admin) | — | `frontend/tests/ai-quality-ui.test.cjs` |
| P3-3 cổng công khai & Partner API | Trang `/apply` (hiện `posting_content` + JD, hỗ trợ `?code=...`, tải/sao chép mã rút đồng ý) và `/apply/withdraw`; `GET /v1/public/positions`, `GET /v1/public/positions/{code}`, `POST /v1/public/positions/{code}/apply`, `POST /v1/public/talent-pool/withdraw`; HR bật theo vị trí qua `PUT /v1/positions/{id}/public-apply`; Partner API server-to-server `/v1/intake/*` (`X-Intake-Key`, `posting_content`, CLI `scripts/intake_clients.py`); tự động gom CV bị giữ (cả `PORTAL` lẫn `PARTNER_SITE`) | `00020`, `00021`, `00026` | `test_public_intake_talent_pool.py`, `test_partner_intake.py`, `frontend/tests/public-intake-talent-pool.test.cjs` |
| P3-1 Talent Pool (pha 1 + pha 2) | Consent 1 ô bắt buộc (`notice v2`) ghi lúc nộp kèm mã rút đồng ý một lần, HR đánh dấu/bỏ đánh dấu vào pool, HR Lead/Admin ghi nhận rút đồng ý kèm tham chiếu, quét pool nền qua worker (`TALENT_POOL_SCAN`, rules-only, loại người đã nộp + khử trùng email/SĐT), quyết định `CONTACT/LATER/SKIP`, mở thông tin liên hệ + xem trước email có audit (`POST /scans/{id}/results/{app}/contact`), hòa giải retention 5 năm theo consent + nhắc hạn theo từng ngày đến hạn (`due_on`), trang `/talent-pool` (lọc/tìm kiếm) & `/positions/[id]/talent-pool` | `00020`–`00025`, `00027` | `test_public_intake_talent_pool.py`, `test_talent_pool_scan.py`, `test_retention_consent.py` |

## Cấu hình mới

| Biến | Mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `PUBLIC_INTAKE_ENABLED` | `false` | Bật cổng `/apply`. Tắt thì mọi endpoint công khai trả 404 (riêng `/talent-pool/withdraw` luôn mở) |
| `INTAKE_API_ENABLED` | `false` | Bật Partner API `/v1/intake`. Ngoài dev/testing bắt buộc `MALWARE_SCAN_MODE=clamav` |
| `PUBLIC_INTAKE_IP_SALT` | rỗng | Muối để băm địa chỉ IP (chỉ lưu bản băm) |
| `PUBLIC_INTAKE_MAX_PER_IP_HOUR` | `5` | Số lần nộp tối đa mỗi giờ cho một địa chỉ |
| `PUBLIC_WITHDRAW_MAX_PER_IP_HOUR` | `20` | Số lần gọi rút đồng ý tối đa mỗi giờ cho một địa chỉ |
| `PUBLIC_INTAKE_TRUSTED_PROXY_HOPS` | `0` | Số proxy tin cậy nối vào `X-Forwarded-For`; xem `DEPLOYMENT.md` |
| `PUBLIC_INTAKE_NOTICE_VERSION` | `v2` | Phiên bản câu chữ đồng ý (1 ô bắt buộc gồm dùng AI, lưu 5 năm và Talent Pool) |
| `MALWARE_SCAN_MODE` | `off` | `clamav` để quét qua clamd; ngoài dev/testing bắt buộc khi bật cổng hoặc Partner API |
| `CLAMD_HOST` / `CLAMD_PORT` / `CLAMD_TIMEOUT_SECONDS` | `127.0.0.1` / `3310` / `10` | Kết nối clamd |
| `TALENT_POOL_RETENTION_MONTHS` | `60` | Thời hạn dùng lại hồ sơ, tính từ lúc ứng viên đồng ý (`application_data_consents.granted_at`) |
| `TALENT_POOL_SCAN_MAX` | `300` | Số hồ sơ tối đa một lượt quét nền |

## Audit

`RECEIVE_PUBLIC_CV`, `RECEIVE_PARTNER_CV`, `QUEUE_HELD_PUBLIC_CVS`, `SET_PUBLIC_APPLY`, `MARK_TALENT_POOL`, `UNMARK_TALENT_POOL`, `WITHDRAW_TALENT_POOL_CONSENT`, `WITHDRAW_TALENT_POOL_CONSENT_BY_CANDIDATE`, `REQUEST_TALENT_POOL_SCAN`, `SCAN_TALENT_POOL`, `VIEW_TALENT_POOL_SCAN`, `DECIDE_TALENT_POOL_RESULT`, `REVEAL_TALENT_POOL_CONTACT`, `CREATE_QUALITY_MARKER`, `EXPORT_QUALITY_GOLDEN_SET`. Metadata chỉ chứa mã/số đếm/kích thước, không chứa tên, email, SĐT, nội dung CV hay nội dung ghi chú.

## Điểm mở cho giai đoạn deploy / sau pilot

- Chưa có CAPTCHA; chưa thử quét mã độc với `clamd` thật (mới kiểm tra giao thức bằng máy chủ giả).
- Quét Talent Pool hiện chạy `RULES_ONLY`; LLM fallback và tiền lọc BGE chờ gate DEP-05.
- Nhận CV qua hộp thư (`recruitment@vinuni.edu.vn`) tạm gác; Reranker (P3-4) do thành viên khác phụ trách.

## Chạy test local

```powershell
$env:TEST_DATABASE_URL="postgresql://postgres:MAT_KHAU@127.0.0.1:5432/hra_local_test"
cd backend; .\.venv\Scripts\pytest.exe -q --basetemp=.pt tests
cd ..\frontend; npm run test:unit; npm run test:i18n; npm run type-check; npm run lint
```
