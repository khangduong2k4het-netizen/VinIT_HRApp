# Rà soát UI/UX – HR & Hiring Manager (báo cáo, chưa sửa code)

- Nhánh: `arena/ea6e2570-vinit-hrapp`, HEAD `f871deb` (đã push, CI run 44452044131 xanh).
- Phạm vi: **chỉ trải nghiệm UI/UX của HR/HM** trên ba màn Dashboard – Applicant Ranking – Candidate Review. Không đi sâu logic backend/API/kiến trúc nghiệp vụ, không đổi API/DB/quyền/consent/approval/matching/thứ hạng.
- Lượt này **chỉ báo cáo**: mỗi mục theo đúng 5 phần Finding → Evidence → Impact → Proposed fix → Regression tests. Chưa có thay đổi mã nguồn nào.
- Ảnh chụp thật (gửi kèm báo cáo): `doc/ui-review/01-dashboard.png`, `02-applicant-ranking.png`, `03-candidate-review.png`. Ảnh chụp trên **production build** (`next build` + `next start`), viewport 1440, locale `vi`, dữ liệu mock cố định — không phải hồ sơ thật, không có dữ liệu cá nhân nào của ứng viên ngoài đời.

## 0. Cách đọc báo cáo

Mỗi phát hiện có mã `UX-Rn`, và mỗi kết luận đều trỏ tới một trong ba nguồn kiểm chứng được:

| Nguồn | Nội dung | Cách tái lập |
| --- | --- | --- |
| **Ảnh** | `doc/ui-review/0{1,2,3}-*.png` | `node tests/ui-screenshots.cjs` |
| **Số đo giao diện** | `doc/ui-review/metrics.json` | `node tests/ui-ux-metrics.cjs` |
| **Số liệu dữ liệu** | `backend/scripts/probe_queue_drift.py` | `cd backend && ./.venv/bin/python scripts/probe_queue_drift.py` (chỉ đọc, không chạm DB) |

Điểm quan trọng trước khi đọc tiếp: **ba màn này không thiếu tính năng**. Vấn đề còn lại là *thông tin đặt sai chỗ*, *số liệu đếm theo ba định nghĩa khác nhau*, và *ngữ cảnh duyệt hồ sơ không bền*. Vì vậy mọi đề xuất dưới đây đều là tái bố cục / thống nhất nguồn số / bền hoá URL — không có đề xuất nào cần module mới.

---

## 1. UX-R1 (P0) — Ba màn đang đếm "cần xác minh" theo ba định nghĩa khác nhau

### Finding

Cùng một câu "cần xác minh" nhưng Dashboard/Work Queue, danh sách xếp hạng và API ranking không trả cùng một con số, vì hai khác biệt độc lập:

1. **Khác tập hồ sơ được xét.** `_APPLICATIONS_QUERY` (Dashboard + Work Queue) **không lọc `application_status`**, nên đếm cả hồ sơ đã `REJECTED_SCREENING`, `INTERVIEW`, `OFFERED`. API ranking chỉ trả `NEW/IN_REVIEW/SHORTLIST`. Hai bên nhìn hai tập khác nhau.
2. **Khác định nghĩa một hồ sơ "cần xác minh".** `summarize_applications` cộng `needs_verification` **sau** nhánh `continue` cho hồ sơ `NOT_ASSESSED`, nên hồ sơ chưa matching không bao giờ vào nhóm này ở backend. Frontend `needsVerification()` không loại `NOT_ASSESSED`, nên hồ sơ chưa matching có `evidence_coverage < 0.7` **có** vào chip "Cần xác minh".

Hệ quả trực tiếp: bấm "5 hồ sơ cần xác minh" trên Dashboard mở ra danh sách có **6** dòng (xem ảnh 01 và 02). Đây đúng là kịch bản GPT nêu: con số trên Dashboard phải mở ra đúng số hồ sơ đó.

### Evidence

Ba nguồn độc lập, cùng một bộ dữ liệu 15 hồ sơ (12 đang sàng lọc + 3 đã qua/đã loại). Chạy `cd backend && ./.venv/bin/python scripts/probe_queue_drift.py` (dùng chính `summarize_applications` của backend):

```
hàng đợi                  Dashboard/WorkQueue   trang xếp hạng   lệch
Cần kiểm tra file                           3                2      1
Cần xác minh                                6                4      2
Cảnh báo trùng                              3                2      1
Chưa đáp ứng                                2                2      0
Chưa matching                               3                2      1
Tổng hồ sơ                                 15               12      3
```

**Bốn trong sáu hàng đợi lệch**, không riêng "cần xác minh". Hai nguyên nhân chồng lên nhau, và vì thế các con số không thể khớp bằng cách sửa một chỗ:

- Cột "Dashboard" đếm cả hồ sơ ngoài sàng lọc → cộng thêm 1–3 ở hầu hết hàng.
- Cột "trang xếp hạng" ở đây là `summarize_applications` trên tập đang sàng lọc, tức **vẫn theo định nghĩa backend** (loại `NOT_ASSESSED` khỏi "cần xác minh"). Chip thật trên UI lại đếm theo `needsVerification()` của frontend, không loại `NOT_ASSESSED`, nên ra **6** cho "Cần xác minh" — trùng số với Dashboard nhưng vì lý do khác hẳn. Đây là kiểu "đúng số, sai lý do" khó phát hiện nhất.

- Backend: `backend/app/services/workspace.py:58-65` — tính `needs_verification` rồi `continue` khi `NOT_ASSESSED`.
- Backend: `backend/app/api/dashboard.py:42-84` (`_APPLICATIONS_QUERY`) — **không** có điều kiện `application_status IN (...)` như `backend/app/api/assessments.py:140`.
- Frontend: `frontend/src/lib/applicantReview.ts:80-86` (`needsVerification`) không loại `NOT_ASSESSED`; `applicantQueueCounts` (`:111-120`) đếm độc lập từng nhóm nên cùng một hồ sơ nằm ở cả "Cần xác minh" và "Chưa matching".
- Ngưỡng `0.7` đang có **8 chỗ hard-code ở frontend** (`applicants/page.tsx:647,748,799`, `[applicantId]/page.tsx:440,456,476,482`, `applicantReview.ts:84`) và 1 nguồn backend (`app/core/config.py:99`). Đây là ngưỡng quyết định "có xếp hạng được không", nên tách rời khỏi backend là rủi ro thật.
- Ảnh: `01-dashboard.png` hàng "Hồ sơ cần xác minh bằng chứng" = **4** (mock dựng theo đúng nhánh `continue` của backend); `02-applicant-ranking.png` chip "Cần xác minh" = **6**. Cùng 12 hồ sơ, hai con số.

### Impact

- HR mất niềm tin vào mọi con số trên Dashboard: bốn hàng đợi cùng lệch, nên không có con số nào tự bảo vệ được.
- Kịch bản sáu bước đã chốt (Ranking → lọc cần xác minh → tìm tên → mở CV → quay lại → kiểm tra bộ lọc) **không thể nghiệm thu** khi điểm xuất phát và đích đến đếm khác nhau.
- Nguy cơ nghiệp vụ: hồ sơ `NOT_ASSESSED` bị xếp vào nhóm "cần xác minh" dễ bị đọc thành "đã đánh giá nhưng thiếu bằng chứng", trong khi thực tế **chưa có điểm** — đúng điều cấm "không suy diễn nghiệp vụ mới từ field cũ".

### Proposed fix (thuần UI + một chỗ backend thuần truy vấn, không đổi schema)

1. **Một định nghĩa, một nguồn.** Chốt: nhóm "cần xác minh" = hồ sơ **đã đánh giá** (`matching_status != NOT_ASSESSED`) và (`NEEDS_HR_VERIFICATION` hoặc `coverage < ngưỡng`). Hồ sơ `NOT_ASSESSED` chỉ thuộc nhóm "Chưa matching" — sửa `needsVerification()` loại `NOT_ASSESSED`, để chip và backend khớp. Lưu ý: sau khi sửa, chip tụt từ 6 xuống 4, **không phải** vì mất hồ sơ mà vì bớt đếm nhầm — cần ghi rõ trong release note để HR không tưởng dữ liệu biến mất.
2. **Một tập hồ sơ.** Thêm điều kiện `application_status IN ('NEW','IN_REVIEW','SHORTLIST')` vào `_APPLICATIONS_QUERY`, hoặc — nếu nghiệp vụ cần đếm cả hồ sơ đã loại — ghi rõ trên nhãn ("… trong hồ sơ đang sàng lọc"). Tôi nghiêng phương án lọc, vì Dashboard đang được đọc như "việc còn phải làm".
3. **Ngưỡng một chỗ.** Trả `coverage_threshold` trong payload ranking/work-queue (đã có sẵn `settings.MIN_EVIDENCE_COVERAGE`), frontend dùng giá trị đó thay 8 chỗ `0.7`. Không đổi hành vi, chỉ bỏ số ma thuật.
4. **Nhãn tự giải thích.** Card/chip ghi "Cần xác minh (đã đánh giá, thiếu bằng chứng)" để phân biệt rõ với "Chưa matching".

### Regression tests

- **Backend**: `pytest tests/test_workspace.py` — bảng 12 dòng dữ liệu mẫu, khẳng định `needs_verification` **không** chứa `NOT_ASSESSED`; và một test khẳng định `_APPLICATIONS_QUERY` và truy vấn ranking trả **cùng** `total` cho cùng vị trí.
- **Backend**: test dạng bảng cho **cả 6 hàng đợi** (`file_review`, `needs_verification`, `duplicate_pending`, `possible_mismatch`, `not_assessed`, `total`) trên fixture có hồ sơ ngoài sàng lọc — chính là bảng ở trên, viết thành assertion. Đây là test bắt được lỗi hiện tại ở 4/6 dòng.
- **Xuyên tầng** (test đang thiếu, đây là test quan trọng nhất): một fixture JSON dùng chung, chạy `summarize_applications` cho ra số, đồng thời chạy `applicantQueueCounts(items)` của TS trên **cùng fixture**, assert hai bên bằng nhau. Test này sẽ fail ngay hôm nay với fixture 15 hồ sơ ở trên.
- **Browser mock**: từ Dashboard bấm item "cần xác minh" → đếm số dòng thực tế trong bảng == `count` hiển thị trên item.
- **Không được làm**: cộng các nhóm giao nhau thành "tổng" (chip vẫn đếm độc lập, đã đúng).

---

## 2. UX-R2 (P0) — Prev/Next sống bằng `sessionStorage`: mất khi mở tab mới, không có TTL

### Finding

Nút "Hồ sơ trước / Hồ sơ tiếp theo" và dòng "Hồ sơ 3/6 trong hàng đợi" chỉ hoạt động khi `sessionStorage` còn ngữ cảnh. Mở link hồ sơ ở tab mới, gửi link cho đồng nghiệp, hoặc đóng/mở trình duyệt → hai nút **bị disable**, không có thông báo vì sao. Bản thân URL đã mang `queue/sort/q` nhưng **không mang danh sách `applicationIds`**, mà danh sách này chỉ nằm trong storage.

Thêm hai điểm yếu đã xác nhận trong code:
- `storedAt` được ghi (`applicants/page.tsx:432`) nhưng **không chỗ nào đọc** → không có TTL, ngữ cảnh cũ có thể tồn tại qua nhiều ngày làm việc.
- Khoá storage là **một khoá cho mỗi vị trí** (`applicantNavigationKey(positionId)`), nên hai tab cùng vị trí ghi đè nhau; tab A đang ở "Cần xác minh" có thể bị tab B (đang ở "Đã shortlist") ghi đè.

### Evidence

`metrics.json` → `candidateDeepLink`:

```json
"candidateFromList": { "prevNextEnabled": 2, "prevNextTotal": 2, "counterText": "Hồ sơ 3/6 trong hàng đợi" },
"candidateDeepLink": { "prevNextEnabled": 0, "prevNextTotal": 2, "counterText": null }
```

Ảnh `03-candidate-review.png` (mở trực tiếp bằng URL có `queue=NEEDS_VERIFICATION`) cho thấy đúng trạng thái này: cả hai nút xám, phụ đề chỉ còn "Đang xem chi tiết hồ sơ".

Mã liên quan: `applicantReview.ts:213-231` (`storeApplicantNavigation`, `readApplicantNavigation`), `applicants/[applicantId]/page.tsx:282-285` (điều kiện `navigationIndex >= 0`), `applicants/page.tsx:425-435` (ghi context).

### Impact

Trực tiếp chặn mục tiêu "duyệt CV liên tục" (P0 theo GPT): HR mở 3–4 tab để so sánh ứng viên là cách làm phổ biến, và đúng lúc đó tính năng duyệt liên tục biến mất mà không có lời giải thích. Người dùng sẽ kết luận "tính năng hỏng" chứ không phải "thiếu ngữ cảnh".

### Proposed fix

1. Ngữ cảnh duyệt **dẫn xuất từ URL**, không từ storage: danh sách để duyệt = kết quả `filterAndSortApplicantItems(rankingItems, queue, search, sort)` đọc từ `?queue&sort&q` khi trang hồ sơ tự tải ranking của vị trí. Storage chỉ còn là bộ nhớ đệm cho `scrollY`.
2. Khi thật sự không có ngữ cảnh (API chưa trả, hoặc URL trần): thay cặp nút xám bằng **một dòng giải thích + nút "Mở danh sách có bộ lọc này"** thay vì để nút chết.
3. Thêm TTL đọc `storedAt` (ví dụ 30 phút) và khoá theo `positionId + queue + sort + q` để hai tab không ghi đè.
4. Không đưa `applicationIds` vào URL (URL dài, và tránh lộ dữ liệu hồ sơ) — chỉ đưa **bộ lọc**, rồi tính lại danh sách ở client. Đây là hướng đã đúng ở `applicantProfileHref`, chỉ cần dùng nó để dựng prev/next.

### Regression tests

- Mở thẳng `/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY` trong context **không có sessionStorage** → `prevNextEnabled` phải bằng 2 và `counterText` khác null. Test này hiện fail (0/2) — chính là tiêu chí nghiệm thu.
- Mở cùng vị trí ở 2 tab với 2 bộ lọc khác nhau, tab A bấm prev → vẫn đi theo hàng đợi của A.
- Đặt `storedAt` cũ hơn TTL → không khôi phục, và có thông báo thay vì nút chết.
- Giữ nguyên test cũ: đi từ danh sách → prev/next vẫn đúng 2/2, "Quay lại" giữ `queue/sort/q` + `restore=scroll`.

---

## 3. UX-R3 (P1) — Đổi bộ lọc dùng `replaceState`: Back của trình duyệt đưa người dùng ra khỏi ứng dụng

### Finding

Trang xếp hạng đồng bộ bộ lọc vào URL bằng `window.history.replaceState` (`applicants/page.tsx:306`). Mỗi lần HR đổi hàng đợi hay gõ tìm kiếm, URL đổi nhưng **không sinh history entry**. Vì vậy nút Back của trình duyệt không quay về bộ lọc trước, mà nhảy về trang trước đó — thường là trang ngoài danh sách. Đồng thời không có listener `popstate` nào trên trang này, nên nếu có entry thì UI cũng không đọc lại URL.

### Evidence

Đo trực tiếp bằng Playwright (production build):

```
1 start   : /positions/p1/applicants?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY   history.length = 2
2 chip    : /positions/p1/applicants?queue=SHORTLIST&sort=REVIEW_PRIORITY             history.length = 2   ← không tăng
3 back    : about:blank                                                               ← ra khỏi ứng dụng
4 forward : /positions/p1/applicants?queue=SHORTLIST&sort=REVIEW_PRIORITY
6 reload  : ?queue=NOT_ASSESSED&sort=REVIEW_PRIORITY  | "Hiển thị 2/12 hồ sơ … Hàng đợi: Chưa matching."
```

Bước 6 là tin tốt: **reload giữ nguyên bộ lọc** (URL là nguồn). Bước 3 là vấn đề: Back phá vỡ kỳ vọng.

### Impact

HR đang soát danh sách, bấm nhầm hoặc muốn quay lại bộ lọc trước → mất toàn bộ phiên làm việc. Mức độ: khó chịu, không mất dữ liệu (vì không có ghi nào), nhưng làm giảm niềm tin vào "trình duyệt hoạt động bình thường".

### Proposed fix

- `replaceState` **giữ nguyên** cho thao tác gõ tìm kiếm (tránh 1 entry mỗi ký tự), nhưng dùng `pushState` cho **đổi hàng đợi** và **đổi kiểu sắp xếp** — hai thao tác rời rạc, mỗi thao tác là một "chỗ đứng" hợp lý.
- Thêm `popstate` → đọc lại `?queue&sort&q` và set state (không gọi lại API nếu dữ liệu đã có).
- Kiểm `history.length` trong test để tránh tái phát.

### Regression tests

- Đổi hàng đợi 2 lần → `history.length` tăng 2 → Back hai lần quay đúng hai bộ lọc trước, danh sách và dòng đếm khớp lại.
- Gõ 5 ký tự vào ô tìm → `history.length` **không** tăng.
- Back về bộ lọc trước → không có request ranking mới (kiểm bằng bộ đếm route mock).

---

## 4. UX-R4 (P1) — Trang Candidate Review: hai nút chính bị đẩy xuống dưới tiêu đề, và thanh ngữ cảnh chiếm chỗ

### Finding

Ở 1440×900, mở hồ sơ từ danh sách:

- `StickyActionBar` (tên hồ sơ + "Hồ sơ trước/tiếp theo") nằm **trên** `h1` và **lặp lại đúng tên ứng viên**, nên tên xuất hiện hai lần trong ~240px đầu trang (ảnh 03: "Lê Thu Hà" ở thanh trên, rồi "Lê Thu Hà" ở `h1` ngay dưới).
- Nút hành động chính "Tải CV gốc" và "Cập nhật trạng thái" nằm **cùng hàng với h1**. Đo ở 1440×900: `h1` ở **239px**, banner cảnh báo ở **318px**, ô điểm 69% ở **426px**, phần "Kết quả đánh giá theo tiêu chí" ở **537px**. Tức **60% màn hình đầu** là tiêu đề lặp, thanh ngữ cảnh và banner — chưa có một tiêu chí nào để đọc.

### Evidence

- `metrics.json` → `candidateFromList`: `hiddenPageHeight: 1842`, viewport 900 → trang dài **2.05 màn hình**; `cvRequestedOnOpen: true` (trạng thái "CV gốc chưa được tải" hiển thị đúng, tức lazy-load vẫn hoạt động). Số đo offset ở trên lấy từ cùng phiên Playwright, production build.
- Ảnh `03-candidate-review.png`: banner vàng "Chưa đủ dữ liệu để xếp hạng ổn định…" (3 dòng) đứng **trước** cả ba ô số liệu; ba ô (69% / 61% / 4) đứng trước phần nội dung HR cần đọc.
- Mã: `applicants/[applicantId]/page.tsx:314-341` (StickyActionBar + h1 cùng khối), `:344-363` (Alert cảnh báo), `:440-490` (ba ô số liệu).

### Impact

Với hồ sơ cần xác minh — đúng nhóm HR phải xử lý nhiều nhất — thông tin *quyết định* (tiêu chí nào thiếu bằng chứng, trích dẫn nào chưa xác minh) nằm dưới màn hình đầu. Đây là "cognitive load" mà GPT nêu: người dùng phải cuộn qua phần tóm tắt lặp lại trước khi tới việc.

### Proposed fix (chỉ bố cục, không đổi dữ liệu)

1. Gộp `StickyActionBar` với `h1`: thanh trên giữ **tên + trạng thái + prev/next**, bỏ `h1` trùng; hoặc hạ thanh xuống dưới `h1`.
2. Đưa **ba ô số liệu lên cùng hàng với tên** (thay vì thành grid riêng), để "69% / 61% / 4" đọc được ngay khi mở.
3. Banner "Chưa đủ dữ liệu để xếp hạng ổn định" gộp vào ô "Độ phủ bằng chứng" dưới dạng phụ đề — nội dung đã có sẵn ở đó, đang bị nói hai lần.
4. Không đổi thứ tự hai cột (bằng chứng trái, CV phải) — bố cục đó đúng và đã được kiểm.

### Regression tests

- Đo offset của ô điểm "69%" **< 320px** ở 1440×900 (hiện 426px), và của phần "Kết quả đánh giá theo tiêu chí" **< 440px** (hiện 537px).
- Tên ứng viên chỉ xuất hiện **một lần** phía trên phần nội dung: đếm phần tử chứa tên trong 260px đầu trang == 1 (hiện 2).
- Các test cũ phải giữ: không request `cv-file` khi mở hồ sơ; bấm "Xem CV gốc" → đúng 1 request; đổi hồ sơ → blob cũ bị xoá.

---

## 5. UX-R5 (P1) — Không có mốc thời gian nào trên Dashboard, dù dữ liệu hạn đã có sẵn

### Finding

GPT xếp "Dashboard nổi bật việc quá hạn / sắp hạn" là P0. Đối chiếu code: **dữ liệu đã tồn tại nhưng không được đưa lên Dashboard**:

- `positions.application_deadline_at` có trong model và đã được trả về ở `GET /positions` (`_POSITION_WITH_STATS` dùng `p.*`) — nhưng khu vực "Việc cần làm" **không** có item nào về hạn ứng tuyển.
- `scorecards` có `due_at`, và đã có `GET /scorecards/reminders` trả `overdue_count` / `due_soon_count` — Dashboard **đã** hiển thị khối "Nhắc hạn scorecard" (ảnh 01). Vậy nửa HM đã có hạn; nửa HR (hạn vị trí, hồ sơ chờ quá lâu) thì không.
- Work queue item không có trường thời gian: `WorkQueueItem` (`types/index.ts:62-72`) chỉ có `priority`, `count`, `target` — không có `due_at`, `age_days`.

### Evidence

- Ảnh `01-dashboard.png`: khối "Nhắc hạn scorecard" nằm **trên** "Việc cần làm", và ở trạng thái trống chỉ có một dòng chữ nhạt; 4 KPI card phía trên không có mốc thời gian nào.
- `metrics.json` → `dashboard`: `kpiCards: 4`, `queueItemCards: 7`, `scrollsToReachQueue: 0.48` (danh sách việc nằm ngay trong màn hình đầu — tốt), nhưng không có phần tử nào biểu diễn "quá hạn".
- Mã: `WorkQueueItem` interface (`frontend/src/types/index.ts:62-72`); `backend/app/api/dashboard.py:283-284` sort `items` theo `priority` rồi `count`, không có chiều thời gian.

### Impact

HR/HM chỉ thấy *khối lượng* (ví dụ "5 hồ sơ cần xác minh") mà không thấy *áp lực thời gian* (trong 5 hồ sơ đó, hồ sơ nào đã chờ lâu nhất). Hai thông tin khác nhau và cùng quyết định thứ tự làm việc. Đây là loại thông tin quyết định thứ tự làm việc, và đang là khoảng trống lớn nhất so với đề xuất của GPT — nhưng nó **không** đòi module mới, chỉ đòi thêm một trường dẫn xuất vào payload đã có.

### Proposed fix — theo hai mức, để anh chọn

- **Mức A (thuần UI, không đổi API):** dùng dữ liệu đã có — `application.created_at` đã nằm trong response `/applications`; hiển thị "chờ N ngày" trên từng dòng và thêm chip "Chờ lâu nhất" vào đầu danh sách. Không cần backend.
- **Mức B (một trường dẫn xuất, không đổi schema):** trả `age_days`/`due_at` trong `WorkQueueItem`, cho phép sort "quá hạn trước". Đây là thay đổi payload, cần anh duyệt vì chạm API.
- Với hạn ứng tuyển: thêm item `POSITION_DEADLINE_SOON` khi `application_deadline_at` trong 7 ngày, dùng lại đúng cơ chế `add(...)` đang có.

### Regression tests

- Unit backend: vị trí có `application_deadline_at` trong 3 ngày → sinh item `POSITION_DEADLINE_SOON`, quá hạn → priority `HIGH`.
- Browser mock: item quá hạn đứng trước item cùng loại nhưng chưa tới hạn.
- Không được: bịa "0 quá hạn" khi dữ liệu hạn là null (giữ nguyên tinh thần `hr_override_rate: None` mà code đang theo).

---

## 6. UX-R6 (P2) — Danh sách xếp hạng: 16 phần tử điều khiển trước dòng dữ liệu đầu tiên

### Finding

Trước khi thấy dòng ứng viên đầu tiên, HR phải đi qua: 3 nút hành động, 4 KPI card, 2 nút chế độ xem, 1 banner giải thích, 8 chip hàng đợi, 1 ô tìm kiếm, 1 select sắp xếp, 1 dòng đếm, 1 banner "Cách đọc danh sách" (3 dòng).

### Evidence

`metrics.json` → `ranking`:

```json
"filterControlsAboveTable": 16,
"chipsWithCounts": 8,
"tableHeaderOffsetPx": 815,
"firstRowOffsetPx": 896,
"pageHeight": 1639, "scrollPages": 1.82,
"rowsWithInlineReason": 4, "totalRows": 6
```

Tức ở viewport 900px, **dòng dữ liệu đầu tiên nằm dưới mép màn hình** (896px). Ảnh 02 xác nhận: màn hình đầu là bộ lọc và banner, chưa có ứng viên nào.

Điểm tích cực đáng giữ: `stickyHeader: true`, `tableMaxHeight: 648px` — bảng đã cuộn trong khung riêng, tiêu đề dính. Và 4/6 dòng đã có lý do hiển thị inline.

### Impact

Người dùng lặp lại thao tác "chọn hàng đợi → xem ứng viên" nhiều lần trong ngày; mỗi lần trả giá bằng gần một màn hình cuộn. Là chi phí nhỏ nhưng nhân với tần suất.

### Proposed fix (P2, làm sau khi R1–R4 xong)

- Gộp 3 nút ("Làm mới", "Chia sẻ Shortlist", "Chạy đánh giá & xếp hạng") vào một menu "Hành động", giữ "Chạy đánh giá" làm nút chính.
- Thu banner "Cách đọc danh sách" thành tooltip/accordion — nội dung đúng nhưng chiếm 3 dòng mỗi lần vào trang.
- Gộp 4 KPI card thành một hàng chip nhỏ gắn liền dải chip hàng đợi (hai thứ đang đếm cùng khái niệm ở hai nơi).
- **Không** bỏ chip hay bộ lọc: chúng là phần đã được nghiệm thu ở đợt P0/P1.

### Regression tests

- `firstRowOffsetPx` ≤ 640 ở 1440×900 (hiện 896).
- `filterControlsAboveTable` ≤ 8.
- Toàn bộ test `ranking-context-mock` hiện có phải xanh nguyên (8 section).

---

## 7. Đối chiếu với 6 nhóm ưu tiên của GPT

| Nhóm GPT đề xuất | Trạng thái thực tế trong code | Kết luận của tôi |
| --- | --- | --- |
| Dashboard nổi bật việc quá hạn/sắp hạn (P0) | Nhắc hạn scorecard **đã có**; hạn ứng tuyển & tuổi hồ sơ **chưa** lên Dashboard dù dữ liệu có sẵn | Không làm lại Dashboard. Chỉ thêm mốc thời gian — **UX-R5**, chia 2 mức A/B để anh chọn mức nào chạm API |
| Applicant Ranking phân cấp thị giác + lý do vào nhóm (P0) | Nhóm matching đã có badge + màu; lý do **đã có** trong `renderCriterionBreakdown` và dòng mở rộng | Phần "phân cấp" còn yếu vì dòng dữ liệu bị đẩy xuống dưới màn hình — **UX-R6**; nhưng đây là P2 về giá trị, **không** phải P0 |
| Candidate Review tỷ lệ CV/đánh giá, giảm cuộn (P0) | Hai cột + lazy CV đã đúng; phần lặp tiêu đề/banner đẩy nội dung xuống | **UX-R4**, P1. Đây là mục gần với đề xuất GPT nhất và chi phí thấp |
| Workflow (P1) | `build_workflow` + `NextActionCard` đã có, deep link đã sửa ở commit `b3d9e88` | Không làm mới; chỉ còn lỗ hổng số liệu **UX-R1** |
| Design System (P1) | MUI theme + token màu đã dùng nhất quán; còn 8 chỗ hard-code `0.7` và màu hex rải rác | Không mở đợt "design system". Chỉ tập trung hoá **ngưỡng** (UX-R1 mục 3) |
| Micro-interactions (P2) | Snackbar/Alert có nhưng không đều | Để sau; chưa đủ bằng chứng để ưu tiên hơn R1–R4 |

**Ba điểm tôi không đồng ý với đề xuất GPT** (dựa trên code, không dựa trên quan điểm):

1. "Ranking thiếu lý do vào nhóm" — sai với code hiện tại (`renderCriterionBreakdown`, `EvidenceCard` đã có). Vấn đề thật là **vị trí** thông tin, không phải sự thiếu.
2. "Dashboard chỉ toàn số liệu" — sai; Dashboard đã là "Tổng quan công việc" với danh sách việc và deep link.
3. "Cần drawer/split view" — hoãn, đúng như GPT tự hạ P2; chưa có bằng chứng usability nào cho thấy drawer giải quyết vấn đề lớn hơn R1/R2.

---

## 8. Thứ tự đề xuất

| Thứ tự | Mục | Vì sao trước | Chạm API? |
| --- | --- | --- | --- |
| 1 | UX-R1 (thống nhất định nghĩa + tập hồ sơ + ngưỡng) | Chặn toàn bộ kịch bản nghiệm thu; không có nó thì mọi số liệu khác không kiểm chứng được | Có 1 điều kiện WHERE; cần anh duyệt |
| 2 | UX-R2 (prev/next từ URL) | P0 của GPT, và test hiện đang fail 0/2 — có tiêu chí nghiệm thu rõ ràng | Không |
| 3 | UX-R3 (Back/popstate) | Rẻ, và nó là điều kiện để R2 "bền" thật sự | Không |
| 4 | UX-R4 (bố cục Candidate Review) | Giảm cuộn ở màn HR dùng nhiều nhất; thuần UI | Không |
| 5 | UX-R5 (mốc thời gian) | Giá trị cao nhưng cần anh chọn mức A (không API) hay B (đổi payload) | Tuỳ mức |
| 6 | UX-R6 (thu gọn điều khiển) | P2, làm sau khi 1–5 ổn định | Không |

**Gate nghiệm thu (không đổi):** CI xanh và mock E2E xanh **không thay thế** usability test trên staging. Kịch bản 6 bước đã chốt vẫn là điều kiện duyệt, và nên bổ sung một bước số 7: *mở link hồ sơ ở tab mới rồi bấm "Hồ sơ tiếp theo"* — chính là chỗ UX-R2 đang hỏng.

## 9. Những gì lượt này KHÔNG làm

- Không sửa một dòng code sản phẩm nào. Chỉ thêm công cụ đo và bằng chứng: `frontend/tests/fixtures/hr-screens.cjs`, `frontend/tests/ui-screenshots.cjs`, `frontend/tests/ui-ux-metrics.cjs`, `backend/scripts/probe_queue_drift.py` + `probe_queue_counts.py`, ba ảnh PNG và `metrics.json` trong `doc/ui-review/`.
- Không đổi API/schema/quyền/consent/approval/matching/thứ hạng.
- Không kết luận gì về backend ngoài phần cần để giải thích lệch số liệu (UX-R1) và nguồn dữ liệu hạn (UX-R5).
- Không thay thế usability test. Số đo trong báo cáo là **đo giao diện** (offset, số phần tử, số dòng), không phải đo người dùng.
