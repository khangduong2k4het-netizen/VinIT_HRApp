# Nhật ký thay đổi — công việc UI/UX tuyển dụng

Mỗi mục ghi lại một tính năng đã hoàn tất: vấn đề, thay đổi, phạm vi giữ nguyên,
kiểm thử đã chạy và phần chưa kiểm. Mục mới nhất nằm trên cùng.

**Quy trình.** Sau khi một tính năng UI/UX code xong và kiểm thử liên quan đã
chạy: (1) thêm mục nhật ký vào file này, (2) commit cùng phần code và test của
nhánh đang làm, (3) push lên nhánh đó. Nhánh chung duy nhất của dự án:
`freebuff/1434fda45407dc1a68600843` (nhánh `feature/ux-finish-application` đã được
bỏ; nội dung của nó nằm trọn trong nhánh chung).

## 2026-11-19 — Chọn nhiều dòng và xử lý hàng loạt trên trang xếp hạng

**Vấn đề.** Mỗi lần shortlist hay loại, HR phải mở từng hồ sơ. Ô chọn ở đầu
dòng lại chỉ bật cho hồ sơ đã shortlist (dùng để chia sẻ), nên không thể xử lý
một lô hồ sơ mới. Trang xếp hạng vì thế không dùng được như bàn làm việc.

**Thay đổi (giữ nguyên schema và ma trận chuyển trạng thái).**

- `frontend/src/app/positions/[id]/applicants/page.tsx`
  - Mọi hồ sơ còn trong vòng sàng lọc (`NEW`, `IN_REVIEW`, `SHORTLIST`) đều
    chọn được; hồ sơ ngoài sàng lọc bị khoá và có tooltip giải thích. Chọn tất
    cả chỉ áp dụng cho các dòng đang hiển thị trong vòng sàng lọc.
  - Thanh hành động nổi (`bulk-action-bar`, cố định đáy màn hình) hiện khi có
    lựa chọn: đếm số đã chọn, `Bỏ chọn`, `Shortlist N hồ sơ`, `Loại N hồ sơ`,
    `Chia sẻ Shortlist`.
  - Mỗi hành động mở dialog xác nhận: liệt kê hồ sơ sẽ đổi, nêu số bị bỏ qua,
    và lý do chung (bắt buộc khi loại, tuỳ chọn khi shortlist).
  - Shortlist hàng loạt chỉ áp dụng cho hồ sơ `IN_REVIEW` — đúng ma trận hiện
    tại (`NEW → SHORTLIST` không hợp lệ, hồ sơ đã Shortlist không cần làm lại);
    số còn lại được báo “Bỏ qua N hồ sơ”.
  - Loại hàng loạt gửi `REJECTED_SCREENING` kèm lý do chung cho từng hồ sơ.
  - Gọi tuần tự endpoint hiện có `PATCH /applications/{id}/status` cho từng hồ
    sơ; lỗi một hồ sơ không xoá kết quả của các hồ sơ đã lưu — banner báo
    “Đã cập nhật a/b hồ sơ” kèm danh sách lỗi.
  - Chia sẻ Shortlist vẫn chỉ gửi hồ sơ `SHORTLIST` trong lựa chọn.
- `frontend/src/i18n/en.json`: 27 chuỗi mới (thanh hành động, dialog, thông báo).
- `frontend/tests/bulk-actions.e2e.cjs` + `npm run test:e2e:bulk-actions`;
  ghi chú trong `frontend/tests/README.md`.

**Kiểm thử đã chạy (pass).**

| Lệnh | Kết quả |
| --- | --- |
| `npm run type-check` | pass |
| `npm run lint` | pass |
| `npm run test:i18n` | 3/3 |
| `npm run test:unit` | 43/43 |
| `npm run build` | pass |
| `npm run test:e2e:bulk-actions` | pass (Chromium, mock `/v1`) |
| `npm run test:e2e:finish-application` | pass |
| `npm run test:e2e:ux02-review` | pass |

**Chưa kiểm.** Chưa chạy với backend/DB thật. `test:e2e:applicants-mock` đang
fail sẵn trên HEAD (dev server bật `reactStrictMode` nên effect chạy hai lần,
`pagesRequested` thành `[1,1,2,2]`); đã đối chiếu bằng cách chạy lại với file
`page.tsx` của HEAD — cùng một lỗi, không phải hồi quy của thay đổi này.

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
