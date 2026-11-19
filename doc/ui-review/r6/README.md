# R6 — thu gọn phần đầu màn Applicant Ranking, và ngưỡng thời gian thành cài đặt

Ảnh và số đo trong thư mục này để GPT review **trước khi** chuyển sang UX-02.
Mọi ảnh đều chụp từ **ứng dụng thật** (production build, mock API của
`frontend/tests/fixtures/hr-screens.cjs`), không phải dựng lại bằng HTML.

## Đọc ảnh theo thứ tự này

| Ảnh | Là gì |
| --- | --- |
| `before/01-dashboard.png` … `before/03-candidate-review.png` | Ứng dụng **trước** đợt này, commit `22888b4`, build riêng rồi chụp |
| `after/01-dashboard.png` … `after/03-candidate-review.png` | Ứng dụng **sau** đợt này, cùng mock, cùng viewport |
| `after/04-hr-settings-desktop.png` | Màn Cài đặt HR mới, 1440×1000 |
| `after/05-hr-settings-mobile.png` | Cùng màn, 390×844 |

`before/` không có màn Cài đặt vì trước đợt này **chưa có** màn đó.

`before/applicant-ranking.png` là bằng chứng cho con số 896px mà báo cáo
`doc/DE_XUAT_R5B_R6.md` §2.1 đã dùng — đo lại trên chính ảnh đó cho ra đúng 896px,
nên bảng số đo cũ không phải số ước lượng.

## Số đo (1440×900, cùng fixture)

| Chỉ số | Trước | Sau | Ghi chú |
| --- | --- | --- | --- |
| `firstRowOffsetPx` — dòng dữ liệu đầu tiên | **896** | **669** | −227px; ở 900px màn hình thấy 2 dòng |
| `tableHeaderOffsetPx` — đầu bảng | 815 | 588 | −227px |
| `filterControlsAboveTable` — đích nhấn trước bảng | **12** | **6** | xem cảnh báo bên dưới |
| `pageHeight` | 1500 | 1274 | −226px |
| `scrollPages` | 1.67 | 1.42 | |
| `chipsWithCounts` — chip lọc kèm số | 8 | **8** | không mất nhóm lọc nào |

### Cảnh báo về `filterControlsAboveTable`

Con số **12** trong báo cáo cũ là **đếm sai**, em đã kiểm lại bằng cách liệt kê
từng phần tử. Phép đo cũ là `document.querySelectorAll('thead ~ * button, [role="group"] button')`:

- `thead ~ *` không khớp phần tử nào trong DOM thật (bảng không có sibling đứng sau `thead`),
  nên vế này **luôn bằng 0**;
- vế `[role="group"] button` bắt cả nút **VI/EN** ở header toàn cục, không liên quan màn này.

Số thật trước R6 là **9** đích nhấn phía trên bảng (2 nút chế độ xem, 8 chip, ô tìm,
ô sắp xếp, nút "Xoá bộ lọc" khi đang lọc — trừ đi phần trùng). Nay là **6**.
Nghĩa là mức cải thiện thật **nhỏ hơn** con số 12→8 mà đề xuất dự kiến, nhưng hướng
thay đổi đúng. Em đã sửa phép đo trong `frontend/tests/ui-ux-metrics.cjs` để lần sau
không tái diễn; số cũ trong báo cáo UX vẫn giữ nguyên để đối chiếu lịch sử.

## Ba thay đổi đã làm, và một chỗ em không làm theo đề xuất

**R6-a — một hành động chính, phần phụ vào menu.** "Chạy đánh giá & xếp hạng" ở lại;
"Làm mới" và "Chia sẻ Shortlist" vào menu `⋮` (có `aria-label="Hành động khác"`,
mở bằng bàn phím được). Không tiết kiệm chiều cao, nhưng header từ 3 đích nhấn
ngang hàng còn 2.

**R6-b — "Cách đọc danh sách" thu gọn.** Nội dung giữ **nguyên từng chữ**, mặc định
đóng, mở bằng nút có `aria-expanded`. Có e2e khẳng định cả ba câu nghiệp vụ vẫn còn
(điểm một phần ≠ điểm cuối; ô chọn chỉ để chọn khi chia sẻ; mở rộng dòng để xem tiêu chí).

**R6-c — bản cân bằng, không làm đúng như đề xuất GPT.** Đề xuất gộp **cả bốn** thẻ KPI
thành chip, gồm cả "Tổng hồ sơ" và "Có trong xếp hạng". Em **không** làm vậy vì hai số
đó đo hai thứ khác nhau (12 hồ sơ ≠ 10 hồ sơ đã xếp hạng — chênh lệch chính là việc
cần làm), gộp thành chip sẽ mất phép so sánh. Thay vào đó:

- giữ hai số đó, nhưng thành **một dòng** `10/12 hồ sơ đã có trong xếp hạng` (89px → 20px);
- **bỏ** hai thẻ "Cần HR xác minh" và "Cảnh báo trùng lặp" vì chip `Cần xác minh (4)` và
  `Cảnh báo trùng (2)` ngay dưới đếm đúng hai thứ đó kèm số — giữ cả hai là nói cùng một
  câu hai lần;
- dòng đếm `Hiển thị 4/12` gộp vào hàng tìm kiếm; nút "Cách đọc" chuyển sang phải hàng đó.

Bốn hành vi lọc từng nằm trên thẻ đều còn: **Đã shortlist**, **Cần xác minh**,
**Cảnh báo trùng**, **Tất cả** — mỗi nhóm có chip kèm số và đã có e2e bấm từng chip,
kiểm URL `?queue=…` rồi quay lại.

## Ngưỡng 7 ngày thành cài đặt được

- Bảng mới `app_private.app_settings` (migration `00033`), hai khoá
  `deadline_soon_days` (1–60) và `waiting_attention_days` (1–90), mặc định 7 — trùng
  giá trị code cũ nên deploy không đổi gì cho tới khi ai đó sửa.
- Chỉ **ADMIN** đọc/ghi được; mọi thay đổi ghi `audit_events` kèm giá trị cũ và mới.
- Ngoài khoảng hoặc khoá lạ ⇒ **400** kèm câu nêu khoảng, không ghi gì.
- Work queue trả về `summary.deadline_soon_days` và `summary.waiting_attention_days`,
  nên Dashboard nói đúng con số đang áp dụng thay vì hard-code "7 ngày".
- Màn: tab "Cài đặt HR" trong `/admin`, và route riêng `/admin/settings`.

## Cách tái lập

```bash
# sau (code hiện tại)
cd frontend
HRA_E2E_BASE_URL=http://localhost:3015 \
HRA_E2E_CHROMIUM_EXECUTABLE=/tmp/chromium HRA_E2E_CHROMIUM_ARGS='["--no-sandbox"]' \
node tests/ui-screenshots.cjs ../doc/ui-review/r6/after
node tests/ui-ux-metrics.cjs      > ../doc/ui-review/r6/after-metrics.json
node tests/settings-screenshots.cjs ../doc/ui-review/r6/after

# trước: build từ commit trước đợt này
git stash && git checkout 22888b4 -- . && npm run build   # rồi chụp vào before/
```

## Câu hỏi cho GPT review

1. Dòng đầu ở 669px (mục tiêu đề xuất là ≤640) — có đáng ép thêm không, và nếu có thì
   lấy từ đâu: bỏ hẳn 2 nút chế độ xem (đã có trong ô "Sắp xếp"), hay gộp luôn dòng
   "10/12 hồ sơ đã có trong xếp hạng" vào tiêu đề?
2. Alert giải thích chế độ xem ("Danh sách ưu tiên vấn đề cần xử lý…") vẫn chiếm 48px
   mỗi lần đổi chế độ. Có nên đổi thành tooltip trên nút chế độ xem?
3. Việc bỏ hai thẻ KPI: thông tin có còn dễ thấy không, hay nên giữ "Cần HR xác minh"
   dạng số ngay trên dòng `10/12`?
