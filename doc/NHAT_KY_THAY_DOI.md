# Nhật ký thay đổi — công việc UI/UX tuyển dụng

Mỗi mục ghi lại một tính năng đã hoàn tất: vấn đề, thay đổi, phạm vi giữ nguyên,
kiểm thử đã chạy và phần chưa kiểm. Mục mới nhất nằm trên cùng.

**Quy trình.** Sau khi một tính năng UI/UX code xong và kiểm thử liên quan đã
chạy: (1) thêm mục nhật ký vào file này, (2) commit cùng phần code và test của
nhánh đang làm, (3) push lên nhánh đó. Nhánh chung duy nhất của dự án:
`freebuff/1434fda45407dc1a68600843` (nhánh `feature/ux-finish-application` đã được
bỏ; nội dung của nó nằm trọn trong nhánh chung).

## 2026-11-19 — Xem CV DOCX ngay trong màn hồ sơ (UX mục 4)

**Vấn đề.** Khung “CV gốc” chỉ nhúng được PDF. Với CV `.docx`, HR chỉ thấy dòng
“Tệp DOCX cần được tải xuống để xem.” — phải tải tệp ra ngoài rồi mở bằng Word
mới đọc được, trong khi việc đang làm là đối chiếu bằng chứng AI với nội dung CV
ngay trên màn hình.

**Phương án đã chọn.** Đọc tệp ngay trong trình duyệt, **không đổi backend và
không thêm thư viện tài liệu**:

- `.docx` là một ZIP chứa `word/document.xml`. Trình duyệt đã có
  `DecompressionStream('deflate-raw')`, nên chỉ cần đọc central directory của
  ZIP, giải nén đúng entry đó và lấy text từ các run `<w:t>` (kèm `w:tab`,
  `w:br`). File mới: `frontend/src/lib/docxText.ts`.
- Nội dung được render thành các đoạn văn bằng React text node, **không dùng
  `innerHTML`**, nên tệp CV không thể chèn HTML/script vào app.
- `CVDocumentViewer` thêm nhánh hiển thị văn bản DOCX cuộn được, kèm ghi chú
  “bố cục gốc có thể khác, tải CV gốc để xem đúng định dạng”. Nút chuyển trang
  vẫn tắt vì bản xem này không có số trang.
- Trang hồ sơ chỉ đọc DOCX **sau khi HR bấm “Xem CV gốc”** (giữ nguyên nguyên tắc
  tải theo yêu cầu); nếu không đọc được (tệp hỏng, `.doc` đổi đuôi, ZIP mã hoá)
  thì hiện thông báo và giữ nguyên nút tải bản gốc — không bao giờ mất đường lấy
  tệp.
- Lý do không chọn các phương án khác: chuyển DOCX→PDF ở server cần thêm
  LibreOffice/converter vào đường request (rủi ro vận hành, đổi backend); dùng
  thư viện render DOCX phía client (mammoth…) thêm dependency nặng và mở thêm bề
  mặt render HTML. Cách này chỉ thêm một file thuần TS đọc văn bản.

**Kiểm thử.**

| Lệnh | Kết quả |
| --- | --- |
| `npm run type-check` / `npm run lint` / `npm run test:i18n` / `npm run test:unit` | pass |
| `npm run build` | pass |
| `npm run test:e2e:docx-preview` (mới) | pass |
| `npm run test:e2e:ux04-sticky-viewer`, `ux02-review`, `finish-application`, `verify-only` | pass |

E2E mới dựng **DOCX thật** trong fixture (tự viết ZIP + WordprocessingML, nén
DEFLATE) và xác nhận: mở hồ sơ không tải CV; sau khi bấm chỉ có đúng một request
`cv-file`; văn bản hiện đủ từng đoạn, đoạn đầu đúng thứ tự; không có iframe PDF;
không có XML thô trong DOM; nút “Trang sau” bị tắt; có câu nhắc tải bản gốc;
không có exception phía client.

**Chưa kiểm.** Chưa thử với tệp DOCX thật nhiều trang/bảng biểu từ Word (fixture
là DOCX tối giản, có nén): bảng và cột sẽ được làm phẳng thành đoạn văn, không
giữ bố cục. Chưa xử lý `.doc` cũ (không phải ZIP) — sẽ rơi vào thông báo “không
đọc được” kèm nút tải gốc. Tệp DOCX có mật khẩu cũng rơi vào nhánh đó. Chưa đo
hiệu năng với CV dài trên thiết bị yếu.

## 2026-11-19 — Nút “Đã xử lý xong hồ sơ này” cho người chỉ có quyền xác minh

**Vấn đề.** Nút hoàn tất hồ sơ và cả nút xác nhận/xoá từng tiêu chí đều bị khoá
theo `can_update_status`. Backend lại cho phép xác minh bằng chứng theo
`can_manage_hr_notes` (`POST /assessments/results/{id}/review`). Người chỉ được
xác minh bằng chứng vì vậy không có cách nào đưa hồ sơ ra khỏi hàng đợi “Cần xác
minh” — vòng hoàn tất bị khoá cứng.

**Thay đổi** (chỉ frontend; không thêm endpoint, không đổi state machine, không
đổi quyền ở backend):

- `frontend/src/app/positions/[id]/applicants/[applicantId]/page.tsx`: nút hoàn
  tất và nút xác nhận tiêu chí hiện khi người dùng **xác minh được bằng chứng
  hoặc đổi được trạng thái** (`can_manage_hr_notes || can_update_status`), không
  còn phụ thuộc riêng `can_update_status`.
- Hộp thoại hoàn tất: phần chọn trạng thái (dropdown, lý do loại, ghi chú) chỉ
  hiện khi có quyền đổi trạng thái. Khi không có quyền đó, hộp thoại ghi rõ
  “Bạn chỉ có quyền xác minh bằng chứng; hồ sơ giữ nguyên trạng thái sau khi
  hoàn tất.” và `handleFinish` không gọi API đổi trạng thái.
- Thanh điều hướng hồ sơ trước/tiếp theo và đường quay lại danh sách xếp hạng
  cũng dùng điều kiện trên, để người chỉ xác minh vẫn đi hết hàng đợi.
- `frontend/src/i18n/en.json`: thêm bản dịch cho câu giải thích mới.

**Kiểm thử.**

| Lệnh | Kết quả |
| --- | --- |
| `npm run type-check` / `npm run lint` / `npm run test:i18n` / `npm run test:unit` | pass |
| `npm run build` | pass |
| `npm run test:e2e:verify-only` (mới) | pass |
| `npm run test:e2e:finish-application`, `ux02-review`, `ux04-sticky-viewer`, `ux08-feedback`, `ranking-compact`, `duplicate-warning` | pass |

E2E mới dùng hồ sơ giả `app-verifier` (`can_update_status: false`,
`can_manage_hr_notes: true`) và xác nhận: nút hoàn tất hiện; hộp thoại không có
`finish-status` nhưng có thông báo giải thích; vẫn bắt buộc tick xác nhận đã xem
bằng chứng; khi xác nhận chỉ gọi `POST .../review` cho từng tiêu chí, **không**
gửi `PATCH .../status`; sau đó chuyển sang danh sách kèm cờ `completed=1`.

**Chưa kiểm.** Chưa chạy với backend thật. Nhánh quyền chỉ-xác-minh hiện chỉ
được dựng bằng mock; nếu backend đổi cổng quyền của endpoint review thì frontend
phải đổi theo cùng. Khi người dùng chỉ có quyền đổi trạng thái (ví dụ ADMIN toàn
cục, `can_manage_hr_notes` false) nút xác nhận tiêu chí vẫn hiện như trước và
backend vẫn có thể trả 403 — hành vi cũ, không thuộc phạm vi thay đổi này.

## 2026-11-19 — Một bộ từ vựng hàng đợi, bỏ thuật ngữ “matching”, ngày theo ngôn ngữ

**Vấn đề.** Dashboard và trang xếp hạng gọi cùng một việc bằng hai tên khác nhau
(“File CV cần HR kiểm tra” / “Cần kiểm tra file”; “Hồ sơ cần xác minh bằng chứng” /
“Cần xác minh”), nên HR phải học lại từ vựng khi đổi màn hình. UI còn dùng chữ
“matching” của lập trình viên, và nhiều chỗ format ngày cứng `vi-VN` dù người
dùng đã chọn tiếng Anh.

**Thay đổi.**

- `frontend/src/lib/workVocabulary.ts` (mới): một nguồn duy nhất cho tên việc và
  ba cụm **Cần tôi xử lý / Cần tôi quyết / Đã quyết**, kèm hàm xếp từng loại
  việc Dashboard và từng hàng đợi xếp hạng vào cụm.
- `frontend/src/lib/applicantReview.ts` và `frontend/src/lib/workQueueLabels.ts`
  lấy nhãn từ module đó: chip lọc và việc trên Dashboard dùng đúng một cách gọi.
- Dashboard: `WorkQueueList` nhóm việc theo ba cụm có tiêu đề và số lượng; cụm
  “Đã quyết” hiện số hồ sơ đã xác minh xong (giữ `data-testid`
  `verification-complete-summary`), thay cho dòng rời phía trên.
- Trang xếp hạng: chip lọc được nhóm theo cùng ba cụm, ghi cụm ngay trước các
  chip trên cùng dòng chảy để không đẩy bảng dữ liệu xuống (đo lại: dòng đầu
  647px, vẫn dưới ngưỡng 720px của `ranking-compact`).
- Bỏ thuật ngữ “matching” khỏi UI: `Nhóm matching` → `Mức phù hợp`,
  `Điểm matching cao nhất` → `Điểm phù hợp cao nhất`, `Chưa matching` →
  `Chưa đánh giá`, `Đã matching` → `Đã đánh giá`, `Chạy matching` →
  `Chạy đánh giá`, `Matching & HR rà soát` → `Đánh giá & HR rà soát`.
- Định dạng ngày dùng `dateLocale` của ngôn ngữ đang chọn thay cho `vi-VN` cứng
  ở: `EvidenceCard`, `careers`, `careers-demo`, `talent-pool`,
  `talent-pool-demo`, `gmail-test`.
- `frontend/src/i18n/en.json`: 13 chuỗi mới cho cụm, nhãn và thông báo.
- Test: thêm assertion cụm/từ vựng vào `work-queue-labels.test.cjs`; loader của
  `workspace-ui` và `queue-contract` biết shim `./workVocabulary`; e2e mới
  `vocabulary-locale.e2e.cjs`; `ranking-context` mock thêm endpoint cảnh báo
  trùng (trang tự tải từ mục trước). `loadDuplicates` giờ chịu được payload
  không phải mảng thay vì làm sập cả trang.

**Kiểm thử đã chạy (pass).**

| Lệnh | Kết quả |
| --- | --- |
| `npm run type-check` / `npm run lint` | pass |
| `npm run test:i18n` | 3/3 |
| `npm run test:unit` | 44/44 (thêm test cụm) |
| `npm run build` | pass |
| `npm run test:e2e:vocabulary-locale` | pass |
| `npm run test:e2e:ux03-dashboard` | pass |
| `npm run test:e2e:ranking-compact` | pass (dòng đầu 647px) |
| `npm run test:e2e:ranking-context` | pass |
| `npm run test:e2e:duplicate-warning`, `bulk-actions`, `finish-application`, `deadline-mock` | pass |

E2E xác nhận: Dashboard và chip xếp hạng cùng có ba cụm “Cần tôi xử lý / Cần tôi
quyết / Đã quyết” và cùng từ ngữ cho từng việc; không còn chữ “matching” trong
nội dung hiển thị của Dashboard và trang xếp hạng; với ngôn ngữ tiếng Anh, hạn
ứng tuyển hiển thị `11/25/2026` thay vì `25/11/2026`.

**Chưa kiểm.** Chưa chạy với backend thật. Các trang public (careers, talent-pool)
đã dùng `dateLocale` nhưng chỉ được kiểm qua `careers-demo`; chưa xem trực quan
ở breakpoint khác ngoài 1440×1000.

## 2026-11-19 — Cảnh báo trùng không còn ngõ cụt

**Vấn đề.** Dòng bị gắn cờ chỉ hiện “Hồ sơ trùng lặp” mà không nói trùng với ai.
Muốn biết phải cuộn xuống cuối trang và bấm “Tải cảnh báo trùng”; vào hàng đợi
“Cảnh báo trùng” cũng không tự có dữ liệu. Cảnh báo vì thế không dẫn tới hành
động nào.

**Thay đổi (chỉ UI).**

- `frontend/src/app/positions/[id]/applicants/page.tsx`
  - Ngay trên dòng bị gắn cờ (bảng desktop và card mobile) có khối
    `duplicate-counterpart-{application_id}`: “Trùng với:” + tên hồ sơ đối ứng,
    là link mở thẳng hồ sơ đó (giữ nguyên queue/sort/từ khoá hiện tại).
  - Trạng thái của khối: đang tải thì báo đang tải; lỗi thì có nút thử lại;
    chưa có cặp thì nói rõ — không còn im lặng.
  - Danh sách cảnh báo trùng **tự tải** khi vào hàng đợi `DUPLICATE` và khi
    danh sách có dòng bị gắn cờ (một request cho mỗi lượt xem); `loadDuplicates`
    chuyển thành `useCallback` để effect không lặp vô hạn khi lỗi.
  - Card “Cặp cảnh báo trùng” ở cuối trang vẫn còn làm nơi xem toàn bộ cặp.
- `frontend/src/i18n/en.json`: 5 chuỗi mới.
- `frontend/tests/fixtures/hr-screens.cjs`: thêm một cặp cảnh báo trùng
  (`app-3` ↔ `app-9`) thay cho danh sách rỗng, dùng chung cho các e2e hiện có.
- `frontend/tests/duplicate-warning.e2e.cjs` + `npm run test:e2e:duplicate-warning`;
  ghi chú trong `frontend/tests/README.md`.

**Kiểm thử đã chạy (pass).**

| Lệnh | Kết quả |
| --- | --- |
| `npm run type-check` | pass |
| `npm run lint` | pass |
| `npm run test:i18n` | 3/3 |
| `npm run test:unit` | 43/43 |
| `npm run build` | pass |
| `npm run test:e2e:duplicate-warning` | pass (Chromium, mock `/v1`) |
| `npm run test:e2e:ranking-compact` | pass (dòng đầu vẫn ở 607px) |
| `npm run test:e2e:bulk-actions` | pass |
| `npm run test:e2e:finish-application` | pass |

E2E xác nhận: dòng bị gắn cờ hiện đúng tên đối ứng mà không cần bấm gì; chỉ
một request cảnh báo trùng được gửi; link mở hồ sơ `app-9`; vào
`?queue=DUPLICATE` tự tải cảnh báo và chỉ còn 2 dòng bị gắn cờ, mỗi dòng nêu
đúng đối ứng; dòng không bị gắn cờ không có khối này; không có request `/v1`
ngoài mock.

**Chưa kiểm.** Chưa chạy với backend/DB thật (không đổi backend). Khối đối ứng
trên card mobile nằm cùng component nhưng chỉ được kiểm ở desktop; chưa xem
trực quan ở các breakpoint khác. `test:e2e:applicants-mock` vẫn fail sẵn trên
HEAD vì `reactStrictMode` (đã đối chiếu ở mục trước).

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
