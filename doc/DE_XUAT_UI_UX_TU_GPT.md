# Đề xuất cải thiện UI/UX – đúc kết từ ý kiến GPT và đối chiếu mã nguồn

- Nguồn tham khảo: hội thoại ChatGPT chia sẻ `https://chatgpt.com/share/6afe6478-0564-83ec-a9ff-d3171a8631cd` ("Tối ưu UI UX HR"), đọc đủ 9 phần ngày 2026-11-19.
- Đối chiếu với: nhánh `arena/ea6e2570-vinit-hrapp` tại commit `4947a80` (176 commit so với `origin/main`).
- Lưu ý phương pháp: GPT đọc `README`, `HRA_Wireframe.md`, `HRA_InterfaceDesign.md`, `HRA_ui-style-guide.md` và các trang trên **`origin/main`**, tức bản cũ hơn nhánh làm việc. Vì vậy một số đề xuất của nó ("Dashboard chỉ toàn số liệu", "Ranking chỉ có 2 state lọc", "chưa có bảo vệ form") đúng với bản nó đọc nhưng **không còn đúng với code hiện tại**. Bảng đối chiếu dưới đây tách rõ phần nào còn giá trị.

## 1. Chuỗi lập luận của GPT (để anh nắm mạch, không phải để làm lại)

1. **Đánh giá ban đầu (rộng):** hệ thống tổ chức theo *chức năng phần mềm*, HR cần tổ chức theo *việc phải hoàn thành trong ngày*. Đề xuất HR Work Center, 5 giai đoạn tuyển dụng, master–detail Candidate Review, bulk actions, HR Copilot, đổi sidebar thành nhóm công việc.
2. **Anh phản hồi "nhiều tính năng đã có rồi, chỉ tập trung cải tiến":** GPT tự thu hẹp phạm vi, bỏ đề xuất xây lại, chuyển sang 8 hạng mục UX-01…UX-08.
3. **Bản cuối (sau khi tự đọc lại code):** chỉ còn **2 việc P0** — giữ ngữ cảnh Ranking khi mở hồ sơ (UX-01) và bộ lọc nhanh + số lượng theo nhóm (UX-02) — cộng 1 việc P1 (điều hướng từ Dashboard) và Drawer để P2. Kèm "những việc không nên làm" và một prompt giao Agent.

Điểm đáng giữ nhất trong cách GPT làm **không phải** danh sách tính năng, mà là 4 nguyên tắc nó đặt ra ở bản cuối:

- Không thay API/DB khi vấn đề chỉ nằm ở bố cục UI.
- Không tạo task engine/workflow mới chỉ để hiển thị một danh sách việc.
- Không suy diễn nghiệp vụ từ dữ liệu thiếu (ví dụ biến "cần xác minh" thành "không đạt", hoặc cộng các nhóm lọc giao nhau để ra "tổng").
- Không thêm AI trước khi các thao tác hiện tại đã được tối ưu.

## 2. Đối chiếu 8 hạng mục GPT đề xuất với code hiện tại

| Mã của GPT | Nội dung | Trạng thái trong code hiện tại | Kết luận |
| --- | --- | --- | --- |
| UX-01 | Giữ bộ lọc/từ khóa khi mở hồ sơ rồi quay lại; đưa state vào URL | **Đã có một nửa.** `applicants/page.tsx` đã đồng bộ `queue`/`sort`/`q` vào URL (đọc khi mount, `replaceState` khi đổi) và lưu thêm "navigation context" vào `sessionStorage` để nút Back về đúng danh sách đã lọc. | Phần cốt lõi đã xong; còn 2 lỗ hổng nhỏ (mục 3.1). |
| UX-02 | Bộ lọc nhanh theo nhóm + số lượng + xóa lọc | **Đã có.** `QueueFilterChips` có 8 hàng đợi (Tất cả, Đã shortlist, Cần kiểm tra file, Cần xác minh, Cảnh báo trùng, Có dấu hiệu chưa đáp ứng, Chưa matching, Đáp ứng bắt buộc) kèm số lượng, tính độc lập từng nhóm. | Không làm lại; chỉ thêm "Xóa bộ lọc" và làm rõ nghĩa số lượng (mục 3.2). |
| UX-03 | Dashboard dẫn thẳng tới nơi xử lý | **Đã có, và hơn thế.** `/dashboard` đã là "Tổng quan công việc": 4 card KPI có link, `WorkQueueList` (API `/dashboard/work-queue`) trả về item theo loại + vị trí + `count` + `target` deep link đúng tab/queue. | GPT đề xuất đúng hướng nhưng đã lỗi thời. Việc còn lại là *nối cho hết* deep link (mục 3.3). |
| UX-04 | Drawer/split view cho chi tiết ứng viên | **Chưa có** (vẫn là trang riêng). GPT tự hạ xuống P2 và khuyên **không làm ngay** vì ảnh hưởng CV viewer, ghi chú HR, lịch sử, phân quyền. | Đồng ý hoãn. Xem mục 3.4 để biết cái gì nên làm trước khi cân nhắc drawer. |
| UX-05 | Tìm kiếm/lọc ở danh sách vị trí | **Chưa có**: `/positions` chỉ có 4 chip trạng thái, không có ô tìm theo tên/mã. Khi số vị trí tăng, HR phải cuộn mắt. | Nên làm, chi phí thấp, thuần frontend (mục 3.5). |
| UX-06 | Kiểm tra lỗi ngay tại trường; giữ dữ liệu form khi API lỗi | **Đã có phần lớn** ở trang tạo vị trí mới: giữ nguyên payload, khóa fieldset, nút "Thử lại cùng yêu cầu" với `request_id`, cảnh báo "kiểm tra danh sách". Còn thiếu: validate tại chỗ và **nút lưu nháp** (backend không có trạng thái `DRAFT`) (mục 3.6). |
| UX-07 | Tập trung xử lý file ngoại lệ | **Đã có một nửa.** `OperationProgressPanel` và tab hồ sơ hiển thị `invalid_files` (tên file + lý do) sau khi lô xong; hàng đợi `FILE_REVIEW` lọc được các hồ sơ cần HR xem lại. | Còn thiếu đường đi một phát từ "file lỗi" sang đúng hồ sơ (mục 3.7). |
| UX-08 | Phản hồi rõ cho mọi thao tác | Một phần: có Snackbar/Alert rải rác, nhưng không nhất quán; nhiều thao tác async (`Lưu nháp scorecard`, đổi trạng thái, chia sẻ) chỉ đổi nhãn nút. | Nên làm, nhưng là việc "đánh bóng" — ưu tiên sau (mục 3.9). |

### Những chỗ GPT nói đúng mà code hiện tại chưa xử lý

- **Rời danh sách để xem chi tiết vẫn là "đi vòng".** `Prev/Next` đã có, nhưng khi chuyển hồ sơ bằng Prev/Next, URL mất `?queue=…&q=…` (nút Prev/Next chỉ dựng `/applicants/{id}`), nên nút "Quay lại danh sách" đọc context từ `sessionStorage` chứ không phải URL. Mở link trực tiếp hoặc mở tab mới là mất ngữ cảnh.
- **CV gốc tải ngay khi mở hồ sơ.** `loadData()` gọi `getCvBlob` ngay nếu `can_view_cv`, trước khi HR có ý định xem. GPT nêu đúng: nên tải khi HR chủ động mở. Đây vừa là hiệu năng vừa là tối thiểu hoá truy cập dữ liệu.
- **Vị trí cuộn danh sách không được khôi phục.** Không có `scrollRestoration` hay lưu `scrollY`; quay lại từ hồ sơ luôn về đầu danh sách, mất chỗ đang đọc (nhất là danh sách 123 hồ sơ đã mount 50 dòng).
- **Bulk action chỉ có đúng một cái** (chọn để chia sẻ shortlist). Các thao tác còn lại vẫn phải mở từng hồ sơ. Điều này **đúng về nghiệp vụ** (đổi trạng thái cần lý do/xác nhận riêng), nên không nên "bulk hoá" thêm — nhưng nên nói rõ trên UI là chỉ shortlist mới chọn hàng loạt được.

## 3. Đề xuất nên thay đổi (đã lọc, xếp theo giá trị/công sức)

Mỗi mục ghi rõ: vấn đề quan sát được, thay đổi đề xuất, phạm vi (frontend/backend), và cách nghiệm thu. Không mục nào đổi logic matching, quyền, consent, approval hay enum nghiệp vụ.

### 3.1. P0 – Nối liền ngữ cảnh giữa danh sách và hồ sơ (hoàn thiện UX-01)

**Vấn đề.** Ba lỗ hổng trên cùng một luồng:
1. Prev/Next ở trang hồ sơ dựng URL `/positions/{p}/applicants/{id}` **không kèm** `queue/sort/q`, nên sau vài lần Next là mất ngữ cảnh URL (chỉ còn `sessionStorage`).
2. Link trong khối "cảnh báo trùng" cũng không kèm context, cũng không gọi `storeNavigationContext` → quay lại ra danh sách mặc định.
3. Vị trí cuộn không được khôi phục.

**Đề xuất.**
- Dựng một helper dựng URL hồ sơ duy nhất: luôn mang `queue`, `sort`, `q` (nếu khác mặc định) và `share` khi có; dùng cho Prev/Next, link cảnh báo trùng, và "Xem chi tiết".
- Lưu `scrollY` của danh sách cùng `ApplicantNavigationContext` (đã có sẵn chỗ lưu), khôi phục sau khi danh sách render xong lần đầu.
- Trang hồ sơ: nếu URL có `queue/sort/q` thì **ưu tiên URL** hơn `sessionStorage` (để mở tab mới/deep link vẫn đúng).

**Phạm vi.** Frontend thuần (`app/positions/[id]/applicants/page.tsx`, `[applicantId]/page.tsx`, `lib/applicantReview.ts`). Không đổi API.

**Nghiệm thu.** Lọc "Cần xác minh" + tìm tên → mở hồ sơ → Next 3 lần → Back: vẫn đúng bộ lọc, đúng từ khóa, đúng vị trí cuộn. Mở link hồ sơ ở tab mới (có query) → Back về đúng danh sách đã lọc.

### 3.2. P0 – Làm rõ "con số" trên bộ lọc (hoàn thiện UX-02)

**Vấn đề.** Số trên chip đang tính trên **toàn bộ** danh sách, không theo từ khóa đang gõ. Nhãn "Đang hiển thị N hồ sơ trong hàng đợi" cũng không nói rõ N là sau khi lọc theo tên hay trước. HR dễ tưởng "Cần xác minh (12)" là 12 kết quả của lần tìm hiện tại. Ngoài ra **không có nút xoá toàn bộ lọc** ở trang này (chỉ có ở `/shortlist`).

**Đề xuất.**
- Chip giữ số theo toàn danh sách nhưng thêm tooltip/`aria-describedby`: "Tính trên toàn bộ hồ sơ của vị trí, không theo từ khóa".
- Dòng đếm đổi thành 2 phần rõ ràng: "Hiển thị **N** / **M** hồ sơ trong hàng đợi · lọc theo tên: 'abc'".
- Thêm nút "Xoá bộ lọc" (reset `queue=ALL`, `sort` mặc định, `q=''`) — chỉ hiện khi có ít nhất một bộ lọc khác mặc định.
- Khi không có kết quả sau khi lọc, empty state phải nêu đúng nguyên nhân (đang lọc theo tên vs đang ở hàng đợi trống).

**Phạm vi.** Frontend thuần (`QueueFilterChips.tsx`, trang applicants). Có unit test sẵn (`workspace-ui.test.cjs`) để mở rộng.

**Nghiệm thu.** Chip count không đổi khi gõ tên; dòng đếm đổi; "Xoá bộ lọc" đưa về danh sách đầy đủ và URL sạch; screen reader đọc được ý nghĩa con số.

### 3.3. P0 – Nối hết deep link của Work Queue (hoàn thiện UX-03)

**Vấn đề phát hiện khi đối chiếu — đây là **lỗi thật**, không phải ý kiến:**
- Backend `app/services/workspace.py` phát deep link dạng **snake_case**: `?queue=file_review`, `?queue=needs_verification`, `?queue=duplicate`, `?queue=possible_mismatch`, `?queue=not_assessed`.
- Frontend `lib/applicantReview.ts` chỉ chấp nhận **UPPER_SNAKE**: `FILE_REVIEW`, `NEEDS_VERIFICATION`… (`isApplicantQueue` trả `false` cho `file_review` — đã kiểm chứng bằng cách transpile và chạy hàm).
- Hệ quả: bấm "Kiểm tra file"/"Xác minh hồ sơ" từ Dashboard hoặc từ `NextActionCard`/`WorkflowStepper` trong workspace vị trí sẽ mở danh sách **không được lọc** — đúng kiểu "deep link giả" mà GPT cảnh báo. Test backend hiện chỉ assert chuỗi `queue=file_review`, không có test xuyên hai tầng.
- Ngoài ra `PositionSummary` dùng `?queue=FILE_REVIEW` (đúng), tức trong cùng một app có **hai chuẩn viết** cho cùng một tham số.

**Đề xuất.**
- Chọn **một** chuẩn: giữ UPPER_SNAKE ở URL (khớp enum FE và `PositionSummary`), sửa `_applicants_target` ở backend cho khớp; hoặc chấp nhận cả hai ở `isApplicantQueue` (map lower→upper) và giữ backend nguyên.
- Khuyến nghị: **chuẩn hoá ở backend** (một nguồn sự thật) **và** cho FE đọc khoan dung cả hai để link cũ/bookmark không chết.
- Thêm test xuyên tầng: lấy `target.search` từ payload work-queue, đưa qua `isApplicantQueue`, assert `true`.

**Phạm vi.** Backend 1 hàm + 1 test; Frontend 1 hàm + 1 test. Không đổi schema, không đổi quyền.

**Nghiệm thu.** Mọi `target` trong `/dashboard/work-queue` mở đúng hàng đợi đã lọc; link cũ dạng thường vẫn chạy.

### 3.4. P1 – Tải CV khi HR chủ động mở, không tải ngay (điểm GPT nêu đúng)

**Vấn đề.** Mở hồ sơ là gọi `GET /applications/{id}/cv-file` ngay, kể cả khi HR chỉ định xem bằng chứng/ghi chú. Với CV nặng hoặc mạng chậm, trang chi tiết chậm và tốn băng thông; mỗi lần Next còn tải lại một file.

**Đề xuất.**
- Giữ nguyên quyền: backend vẫn quyết định `allow_cv_view` và audit từng lần tải; chỉ đổi **thời điểm** gọi từ "mount" sang "HR bấm Xem CV" (nút/khung xem có nút "Tải CV để đối chiếu").
- Bằng chứng AI và số trang trích dẫn vẫn hiển thị trước; khi HR bấm "nhảy tới trang N" thì mới tải file.
- Ghi rõ trên UI: "CV chưa tải — bấm để xem bản gốc" để không ai tưởng CV bị thiếu.

**Phạm vi.** Frontend; **không** đổi API. Cần cập nhật test a11y/mock hiện có (đang giả định `cvUrl` có sau mount).

**Nghiệm thu.** Mở hồ sơ không phát sinh request `cv-file`; bấm Xem CV → có request, có audit; nút "nhảy tới trang" hoạt động sau khi tải; 403 vẫn hiện thông báo quyền như cũ.

### 3.5. P1 – Tìm và lọc ở danh sách vị trí (UX-05)

**Vấn đề.** `/positions` chỉ có 4 chip trạng thái; không tìm theo tên/mã. HR có 6 vị trí thì ổn, 30 vị trí thì phải quét mắt.

**Đề xuất.**
- Ô tìm theo **tên hoặc mã vị trí** (client-side, dữ liệu đã tải).
- Đồng bộ `?status=` và thêm `?q=` vào URL (đã có tiền lệ `replaceState` trong file); giữ hành vi link `/positions?status=OPEN` từ Dashboard.
- Sắp xếp mặc định **không đổi** (đang theo `created_at`), tránh "thuật toán ưu tiên chưa được duyệt" như GPT cảnh báo.
- Hiển thị số lượng theo chip trạng thái để biết đang bị lọc mất bao nhiêu.

**Phạm vi.** Frontend thuần.

**Nghiệm thu.** Gõ mã vị trí → lọc đúng; URL chia sẻ được và mở lại đúng; chip vẫn hoạt động; empty state phân biệt "chưa có vị trí" và "không khớp tìm kiếm".

### 3.6. P1 – Tạo vị trí: validate tại chỗ + nói rõ vì sao nút bị khoá (UX-06)

**Vấn đề.** Nút "Tạo vị trí và tiếp tục" bị `disabled` khi thiếu trường, nhưng không nói **thiếu cái gì**; HR phải tự dò. Không có "Lưu nháp" (backend chưa có trạng thái nháp — **không tự thêm**).

**Đề xuất.**
- `helperText` + `error` ngay dưới từng trường bắt buộc sau lần blur đầu tiên; kèm tóm tắt "Còn thiếu: Đơn vị, Hiring Manager" ngay trên nút.
- Giữ nguyên toàn bộ cơ chế idempotency/uncertain hiện có (đã tốt, không đụng vào).
- **Không** thêm nút "Lưu nháp" cho tới khi backend có trạng thái tương ứng; thay vào đó ghi rõ trong UI "Nội dung được giữ trên trang này cho tới khi tạo xong" (đúng với hành vi hiện tại + hook chặn rời trang).
- Nếu sau này cần nháp thật: đó là việc **backend** (thêm `DRAFT` + quyền + migration), không phải chỉnh UI.

**Phạm vi.** Frontend; mục "lưu nháp" hoãn có chủ đích.

**Nghiệm thu.** Bấm vào form trống → thấy rõ trường thiếu; sửa đủ → nút bật; không có thay đổi nào trong luồng gửi/retry.

### 3.7. P1 – Từ "file lỗi" tới đúng hồ sơ (UX-07)

**Vấn đề.** Sau khi upload, UI liệt kê `invalid_files` (tên file + lý do) — nhưng đó là danh sách **file**, không phải **hồ sơ**. HR phải tự sang trang xếp hạng, lọc `FILE_REVIEW`, rồi đoán hồ sơ nào ứng với file vừa lỗi.

**Đề xuất.**
- Sau khi lô xong, thêm nút "Xem hồ sơ cần xử lý" trỏ thẳng `?queue=FILE_REVIEW` (phụ thuộc mục 3.3 được sửa trước).
- Với file lỗi **có** tạo hồ sơ: hiện thêm liên kết tới hồ sơ đó (dùng `invalid_files` + mapping application nếu API đã trả; nếu chưa có `application_id` trong `cv_batch_items` thì đây là việc backend nhỏ — thêm field, không đổi nghiệp vụ).
- Với file bị từ chối trước khi tạo hồ sơ: nói rõ "tệp này không tạo hồ sơ, chỉ cần tải lại đúng định dạng" — tránh HR đi tìm một hồ sơ không tồn tại.
- Không tải lại cả lô chỉ vì một file lỗi (đã đúng hiện tại, giữ nguyên).

**Phạm vi.** Chủ yếu frontend; tùy chọn 1 field backend.

**Nghiệm thu.** Sau lô có 2 file lỗi: từ thông báo bấm được tới đúng danh sách đã lọc; phân biệt rõ file không tạo hồ sơ vs hồ sơ cần kiểm tra.

### 3.8. P2 – Chỉnh sửa tiêu chí tại chỗ (thay vì mở dialog từng tiêu chí)

**Vấn đề.** Bảng tiêu chí hiện mở **dialog** để sửa từng dòng (`editingCriterion`). Với 8–12 tiêu chí, HM/HR phải mở–đóng dialog nhiều lần. GPT nêu đúng điểm này ở bản đầu (mục 3.2 của nó) nhưng bị bỏ khi thu hẹp.

**Đề xuất.** Cho phép sửa `name/description/weight` **inline** trong bảng (click để sửa, Enter để lưu, Esc để huỷ), giữ dialog cho thao tác nặng (tạo mới, đổi nhóm trọng số). **Giữ nguyên** quy tắc hai người phê duyệt và không tự publish rubric.

**Phạm vi.** Frontend; có thể cần thêm endpoint "patch một tiêu chí" nếu API hiện chỉ nhận cả version — **kiểm tra trước khi hứa**.

**Nghiệm thu.** Sửa 5 tiêu chí liên tiếp không mở dialog; tổng trọng số vẫn validate; trạng thái phê duyệt vẫn reset như cũ.

### 3.9. P2 – Phản hồi nhất quán cho thao tác async (UX-08)

**Vấn đề.** Cùng một loại hành động nhưng phản hồi khác nhau: có chỗ dùng Snackbar, có chỗ Alert, có chỗ chỉ đổi nhãn nút; không có `aria-live` chung cho thông báo thành công.

**Đề xuất.** Một component `useActionFeedback` (thành công → Snackbar + `aria-live="polite"`; lỗi → Alert tại chỗ, không tự biến mất). Áp dần cho: lưu scorecard, nộp scorecard, đổi trạng thái hồ sơ, chia sẻ shortlist, gửi phản hồi.

**Phạm vi.** Frontend, không đổi nghiệp vụ. Đây là việc "đánh bóng" nên xếp sau.

### 3.10. Việc **không** nên làm (đồng ý với GPT, ghi để chặn scope creep)

- Không thay Dashboard bằng "Work Center" mới — Dashboard hiện **đã** là work queue; chỉ nối deep link (3.3).
- Không tạo task engine/bảng task mới: danh sách việc đã suy ra từ dữ liệu hiện có (`build_work_queue_items`).
- Không làm drawer/split view ngay: 3.1 giải quyết phần lớn ma sát với chi phí nhỏ hơn nhiều; drawer để P2 sau khi đo lại.
- Không bulk-hoá đổi trạng thái/loại ứng viên: cần lý do + kiểm tra quyền từng hồ sơ.
- Không thêm AI Copilot/chatbot trước khi 3.1–3.7 xong.
- Không hard-code ngưỡng mới (ví dụ 70% độ phủ) vào UI nếu chưa đối chiếu backend: hiện `COVERAGE_THRESHOLD = 0.7` có trong `workspace.py` và FE cũng dùng `< 0.7` ở `applicantReview.ts` — **đã khớp**, nhưng nếu đổi thì phải đổi cả hai, nên đưa vào hằng số cấu hình thay vì rải literal.
- Không thêm "Lưu nháp vị trí" khi backend chưa có `DRAFT`.

## 4. Thứ tự triển khai đề xuất

| Đợt | Hạng mục | Vì sao trước | Công sức |
| --- | --- | --- | --- |
| 1 | **3.3** sửa deep link queue (bug thật) + test xuyên tầng | Đang làm hỏng đúng luồng "việc cần làm → xử lý", là giá trị cốt lõi của Dashboard | S–M |
| 2 | **3.1** giữ ngữ cảnh trọn vẹn (Prev/Next mang query, khôi phục cuộn, ưu tiên URL) | Giảm thao tác lặp nhiều nhất mỗi ngày | M |
| 3 | **3.2** làm rõ số đếm + xoá bộ lọc | Tránh hiểu sai số liệu, chi phí rất thấp | S |
| 4 | **3.4** lazy-load CV | Hiệu năng + tối thiểu hoá truy cập dữ liệu | S–M |
| 5 | **3.5** tìm/lọc vị trí, **3.6** validate tạo vị trí | Ma sát rõ nhưng tần suất thấp hơn | S mỗi mục |
| 6 | **3.7** file lỗi → hồ sơ, **3.9** phản hồi nhất quán | Hoàn thiện trải nghiệm lỗi | M |
| 7 | **3.8** sửa tiêu chí inline | Cần kiểm tra API trước | M–L |

## 5. Cách nghiệm thu (không nghiệm thu bằng "trông đẹp hơn")

Đo **trước** và **sau** trên cùng nhóm HR, cùng loại dữ liệu:
- Số lần chuyển trang để hoàn tất một vòng "lọc → mở hồ sơ → xem bằng chứng → đổi trạng thái → quay lại".
- Số lần bấm để mở 10 hồ sơ liên tiếp.
- Số lần phải làm lại do mất bộ lọc/ngữ cảnh.
- Thời gian từ "thấy cảnh báo file lỗi" tới "mở đúng hồ sơ".
- Với 3.4: số request `cv-file` mỗi vòng rà soát 10 hồ sơ (kỳ vọng giảm mạnh).

Tiêu chí cứng (không được hy sinh để giảm click): RBAC theo vai trò/vị trí, consent, phê duyệt hai bước của tiêu chí, audit tải CV, ba miền trạng thái (file / matching / hồ sơ) không bị trộn, "cần xác minh" ≠ "không đạt".

## 6. Tóm lại cho anh

GPT đưa ra một khung tư duy đúng (làm việc theo *việc cần hoàn thành*, không theo *menu chức năng*), nhưng vì đọc bản `origin/main` cũ nên phần lớn "đề xuất xây mới" của nó mà dự án **đã có**: Dashboard đã là work queue có deep link, Ranking đã có 6+ hàng đợi lọc kèm số lượng và URL state, form tạo vị trí đã idempotent và giữ dữ liệu. Giá trị thật nằm ở **5 việc nhỏ, đo được**:

1. Sửa deep link `queue` sai chuẩn (bug thật, đang làm hỏng luồng work-queue).
2. Prev/Next và link cảnh báo trùng mang đủ query + khôi phục vị trí cuộn.
3. Nói rõ nghĩa con số trên bộ lọc + nút xoá lọc.
4. Tải CV khi HR chủ động mở.
5. Tìm/lọc vị trí, validate tại chỗ, nối file lỗi với hồ sơ.

Ba việc nên **hoãn có chủ đích**: drawer/split view, sửa tiêu chí inline (cần kiểm API), và mọi thứ thuộc AI Copilot. Không có mục nào trong tài liệu này đã được triển khai — đây là đề xuất chờ anh duyệt thứ tự.

## 7. Trạng thái thực hiện (cập nhật 2026-11-19)

Đợt 1–5 trong bảng thứ tự ở mục 4 **đã triển khai** trên nhánh `arena/ea6e2570-vinit-hrapp`; mục 3.7, 3.8, 3.9 vẫn để sau.

| Mục | Nội dung đã làm | Kiểm chứng |
| --- | --- | --- |
| 3.3 | `_applicants_target` phát `queue=FILE_REVIEW` (UPPER_SNAKE) khớp enum của trang xếp hạng; FE đọc khoan dung cả `file_review` để link cũ/bookmark không chết. Thêm 2 test backend: mọi deep link phải dùng mã trang xếp hạng hiểu được, và không trỏ sang vị trí khác. | `pytest tests/test_workspace.py` 7 passed; đã thử revert bản sửa thì 2 test fail đúng như mong đợi |
| 3.1 | `applicantProfileHref`/`applicantSearchParams` dùng chung cho "Xem chi tiết", biểu tượng mắt, mở rộng dòng tiêu chí và cảnh báo trùng → mọi link sang hồ sơ mang `queue/sort/q`. Trang hồ sơ ưu tiên ngữ cảnh trong URL hơn `sessionStorage`, nên tab mới/deep link vẫn đúng; Prev/Next giữ nguyên bộ lọc. Nút quay lại thêm `restore=scroll`; danh sách lưu `scrollY` vào navigation context và khôi phục sau khi render. | `ranking-context-mock` (3 lần liên tiếp), unit `applicantProfileHref` |
| 3.2 | Chip giữ số theo toàn vị trí nhưng có `aria-label`/tooltip nói rõ; dòng đếm tách "Hiển thị N/M · lọc theo tên · hàng đợi"; thêm "Xoá bộ lọc và tìm kiếm" chỉ hiện khi có lọc. Nhãn hàng đợi gom về `APPLICANT_QUEUE_LABELS` để chip và dòng đếm không lệch nhau. | `ranking-context-mock` bước 3–4, unit nhãn hàng đợi |
| 3.4 | `CVDocumentViewer` không tự tải nữa: trạng thái "chưa tải → bấm Xem CV gốc" (ghi rõ truy cập được ghi nhận lúc bấm), có spinner, có lỗi; bấm vào trang trích dẫn của bằng chứng cũng tải file. Đổi hồ sơ thì xoá blob cũ; mất quyền thì bỏ bản đã tải. | `ranking-context-mock` bước 6–7: mở hồ sơ 0 request `cv-file`, bấm mới có đúng 1, reload không tự tải lại |
| 3.5 | `/positions` có tìm theo tên **hoặc mã**, chip trạng thái kèm số lượng, dòng đếm N/M, "Xoá bộ lọc và tìm kiếm", `?status=` + `?q=` đồng bộ vào URL; empty state phân biệt "chưa có vị trí" với "không khớp". | `ranking-context-mock` bước 8 |
| 3.6 | Form tạo vị trí báo lỗi tại trường sau lần blur đầu, và tóm tắt "Còn thiếu: …" ngay trên nút tạo. Không thêm "Lưu nháp" vì backend chưa có trạng thái `DRAFT` (giữ nguyên quyết định hoãn). | `workflow-create-mock` (bổ sung 2 assertion) |

**Không đổi:** API/DB (trừ 1 chuỗi query ở backend), RBAC, consent, phê duyệt hai bước, enum trạng thái, công thức matching/ranking, hành vi chia sẻ shortlist. Không thêm phụ thuộc mới.

**Đã đo:** unit 20/20, i18n 3/3, backend `tests/` 266 passed/170 skipped, type-check/lint/`next build` pass, **8 bộ browser mock** pass trên production build (ranking-context, drafts, workflow, shortlist, applicants 123, a11y, accounts, intake).

**Đã push:** `b3d9e88` (sửa deep link), `babf2b3` (ngữ cảnh + CV theo yêu cầu + tìm vị trí + validate), `613725f` (tài liệu). CI run **44452044131 success** cả ba job (backend unit, frontend i18n/type-check/lint/build, backend integration PostgreSQL 17 + pgvector với đủ 32 migration).

**Còn lại:** 3.7 (file lỗi → hồ sơ), 3.8 (sửa tiêu chí inline — cần kiểm API), 3.9 (phản hồi async nhất quán), drawer P2, và toàn bộ nhóm AI. Chưa thử Safari/iOS, chưa E2E với Supabase/Storage/ClamAV thật, chưa usability test.
