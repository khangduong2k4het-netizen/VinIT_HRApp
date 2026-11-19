# Nhật ký thay đổi — công việc UI/UX tuyển dụng

Mỗi mục ghi lại một tính năng đã hoàn tất: vấn đề, thay đổi, phạm vi giữ nguyên,
kiểm thử đã chạy và phần chưa kiểm. Mục mới nhất nằm trên cùng.

**Quy trình.** Sau khi một tính năng UI/UX code xong và kiểm thử liên quan đã
chạy: (1) thêm mục nhật ký vào file này, (2) commit cùng phần code và test của
nhánh đang làm, (3) push lên nhánh đó. Nhánh hiện tại: `feature/ux-finish-application`.

## 2026-11-19 — Hoàn tất hồ sơ trong một hành động

**Vấn đề.** Vòng duyệt một hồ sơ đang phải bấm rời rạc: xác nhận từng trích dẫn,
mở dropdown đổi trạng thái, xác nhận dialog, rồi bấm "Hồ sơ tiếp theo". Mỗi hồ sơ
tốn nhiều lần bấm và HR dễ bỏ dở giữa chừng, hàng đợi không được dọn.

**Thay đổi (chỉ UI, không đổi state machine/API).**

- `frontend/src/app/positions/[id]/applicants/[applicantId]/page.tsx`
  - Nút chính **"Đã xử lý xong hồ sơ này"** đặt trong `StickyActionBar` sẵn có
    (không thêm thanh mới, giữ nguyên layout đã đo). Chỉ hiển thị khi
    `application.can_update_status` và không ở chế độ chia sẻ (`share`).
  - Dialog hoàn tất gồm: danh sách tiêu chí còn chờ xác minh, checkbox attest
    ("Tôi đã đối chiếu … và xác nhận trích dẫn là đúng"), select trạng thái
    (mặc định giữ nguyên, lý do bắt buộc khi chọn `REJECTED*`), checkbox chuyển
    sang hồ sơ kế tiếp.
  - Trình tự gọi API giữ nguyên: `reviewCriterionResult` cho từng tiêu chí còn
    chờ → `updateStatus` nếu trạng thái đổi → điều hướng `keepContext()` sang hồ
    sơ kế tiếp với cờ `completed=1`, hoặc quay lại danh sách khi hết hàng đợi.
  - Trang đích hiện banner "Đã xử lý xong hồ sơ trước. Đang xem hồ sơ tiếp theo."
    rồi xoá `completed` khỏi URL bằng `replaceState` để refresh không lặp lại.
  - Lỗi giữa chừng: báo "một số bước có thể đã được lưu nhưng hồ sơ chưa được
    chuyển", không điều hướng và không tuyên bố hoàn tất.
- `frontend/src/i18n/en.json`: thêm bản dịch tiếng Anh cho 16 chuỗi mới.
- `frontend/tests/fixtures/hr-screens.cjs`: mock tổng quát cho `app-*` (chi tiết,
  `PATCH /status`, status-events, profile, cv-file) để trang hồ sơ kế tiếp tải được.
- `frontend/tests/finish-application.e2e.cjs` + `npm run test:e2e:finish-application`;
  ghi chú trong `frontend/tests/README.md`.

**Giữ nguyên.** Không thêm endpoint, không đổi `APPLICATION_TRANSITIONS`, quyền,
consent, matching hay luồng phê duyệt. Việc ghi `CONFIRMED` chỉ xảy ra khi HR tick
attestation — không có xác nhận tự động.

**Kiểm thử đã chạy (pass).**

| Lệnh | Kết quả |
| --- | --- |
| `npm run type-check` | pass |
| `npm run lint` | pass |
| `npm run test:i18n` | 3/3 |
| `npm run test:unit` | 43/43 |
| `npm run build` | pass |
| `npm run test:e2e:finish-application` | pass (Chromium, mock toàn bộ `/v1`) |
| `npm run test:e2e:ux02-review` | pass (không hồi quy luồng xác minh cũ) |

E2E xác nhận: nút xuất hiện một lần; nút hoàn tất bị khoá khi còn tiêu chí chưa
attest; hoàn tất gửi đúng các `POST …/review` với `CONFIRMED` và **không** gửi
PATCH trạng thái; chuyển hồ sơ giữ `queue` + `completed=1` và hiện banner; khi chọn
`REJECTED_SCREENING` vẫn bắt buộc lý do và PATCH đúng payload; không có request
`/v1` nào ngoài mock.

**Chưa kiểm.** Chưa chạy với backend/DB thật (không đổi backend). Chỉ kiểm giao
diện ở 1440×900; chưa xem lại các breakpoint khác.
