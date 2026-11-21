# Nhật ký thay đổi — công việc UI/UX tuyển dụng

Mỗi mục ghi lại một tính năng đã hoàn tất: vấn đề, thay đổi, phạm vi giữ nguyên,
kiểm thử đã chạy và phần chưa kiểm. Mục mới nhất nằm trên cùng.

**Quy trình.** Sau khi một tính năng UI/UX code xong và kiểm thử liên quan đã
chạy: (1) thêm mục nhật ký vào file này, (2) commit cùng phần code và test của
nhánh đang làm, (3) push lên nhánh đó. Nhánh chung duy nhất của dự án:
`freebuff/1434fda45407dc1a68600843` (nhánh `feature/ux-finish-application` đã được
bỏ; nội dung của nó nằm trọn trong nhánh chung).

## 2026-11-21 — Bố cục lại trang chi tiết vị trí: một việc chính, không lặp CTA

**Vấn đề.** Trang `/positions/[id]` là nơi HR ở lâu nhất nhưng bố cục buộc họ
đọc lại cùng một thông tin nhiều lần và cuộn mới bấm được việc chính:

1. Header có 6 nút cùng cỡ (Ứng viên, Đổi Hiring Manager, Dùng rubric, Chỉnh sửa
   vị trí, Đề xuất tiêu chí AI, Tải lên CV) — không nút nào nổi bật, xuống dòng
   lung tung ở màn hình 1280px.
2. Trước khi tới nội dung phải đi qua 3 khối xếp chồng: 6 thẻ số liệu, stepper,
   thẻ "hành động tiếp theo" — cùng nhắc lại một việc.
3. Tab "Danh sách ứng viên" lặp lại 4 thẻ số liệu đã có ở trên, cộng 2 nút dẫn
   tới cùng một trang xếp hạng, trong khi việc thật của tab là nhận CV.
4. Tab tiêu chí mở bằng nguyên văn JD (đã có tab JD riêng), rồi danh sách tiêu
   chí, lịch sử duyệt, và **nút duyệt nằm cuối cùng** — phải cuộn hết trang.
5. Đổi tab xong tải lại trang là quay về tab đầu; không gửi link thẳng cho đồng
   nghiệp được.
6. Nút "Tải lên CV" bị khoá mà không nói vì sao.

**Đã làm.**

- **Header hai tầng.** Hàng chính chỉ còn `Ứng viên (N)` và `Nhận CV` (nút thứ
  hai có tooltip giải thích khi bị khoá: cần bộ tiêu chí đã duyệt và vị trí đang
  mở). Hàng phụ cỡ nhỏ: `Đề xuất tiêu chí AI`, `Chỉnh sửa vị trí`, `Đổi Hiring
  Manager`. `Dùng rubric đã xuất bản` chuyển vào thanh công cụ của tab tiêu chí —
  đúng nơi HR chọn nguồn tiêu chí.
- **Ba khối thành một thẻ tổng quan.** `WorkflowStepper` thành dải chip 5 bước
  (bước hiện tại tô đậm, bước bị chặn đỏ, tooltip trạng thái); `PositionSummary`
  thành dải 6 số ngang vẫn bấm được để mở đúng hàng đợi; `NextActionCard` thêm
  biến thể `bare` để nằm cùng thẻ. Bớt ~2 khung và ~300px cuộn trước nội dung.
- **Tab ứng viên.** Bỏ 4 thẻ số liệu trùng và nút trùng: còn khung nhận CV (việc
  chính) + một dòng số liệu + một nút `Mở trang xếp hạng`.
- **Duyệt tiêu chí lên đầu tab.** Thẻ duyệt (trạng thái, vai trò của bạn, nút
  Từ chối / HR duyệt & gửi HM / duyệt trực tiếp / HM duyệt) nằm ngay dưới các
  cảnh báo, trên danh sách tiêu chí. Bỏ khối JD đầy đủ ở đầu tab, thay bằng nút
  `Xem JD · vN` trong thanh trọng số.
- **Tab gắn URL.** `?tab=criteria|applications|shortlist|jd` cập nhật bằng
  `replaceState` (Back vẫn về trang trước), áp dụng cho cả nút `Nhận CV` và
  "hành động tiếp theo". Nhãn tab kèm số đếm: `Tiêu chí (7)`, `Ứng viên (12)`,
  `Shortlist (4)`, `Mô tả công việc (JD) · v3`.
- **Chi tiết nhỏ.** Chip nhóm vị trí + hạn ứng tuyển ngay dưới tiêu đề (trước đây
  hạn chỉ thấy trong hộp thoại chỉnh sửa). `ApplyRubric`/`HiringManagerChange`
  nhận prop `size` để dùng được ở hàng phụ.

**Kiểm thử đã chạy (pass).**

| Lệnh | Kết quả |
| --- | --- |
| `npx tsc --noEmit` | 0 lỗi |
| `npx eslint` (6 file đã sửa) | 0 lỗi |
| `npm run test:i18n` | 3/3 pass (đã bổ sung 8 khoá tiếng Anh) |
| `npm run test:unit` | 114/114 pass |
| `npm run build` | build thành công, `/positions/[id]` 24.6 kB |

**Chưa kiểm.** Chưa mở giao diện bằng trình duyệt (môi trường không có backend
và trình duyệt): bố cục header, dải chip bước, vị trí thẻ duyệt và hành vi
`?tab=` mới chỉ được xác nhận qua biên dịch/build, chưa được nhìn tận mắt.

## 2026-11-20 — Sáu cải tiến vòng duyệt hồ sơ: hàng đợi, phím tắt, lý do loại, ghi chú, người phụ trách

**Vấn đề.** Sáu chỗ HR phải làm lại việc máy đã biết, đo trên chính luồng duyệt
hồ sơ:

1. Dashboard báo "17 hồ sơ chờ xác minh" nhưng bấm vào chỉ mở **danh sách**, rồi
   HR tự tìm hàng đầu tiên — mỗi lượt mất thêm hai lần bấm và một lần đọc.
2. Xác minh 10–15 tiêu chí toàn bằng chuột; bàn tay đang ở bàn phím vẫn phải rời ra.
3. Khi loại hồ sơ, HR gõ lại cùng một lý do cho hàng chục hồ sơ cùng vị trí,
   trong khi hệ thống đã biết tiêu chí nào `NO_MATCH`/`UNCLEAR`.
4. Nhận xét về một tiêu chí bị dồn xuống ô ghi chú chung cuối trang, mất ngữ cảnh.
5. Hai HR cùng một vị trí không biết ai đang giữ hồ sơ nào, nên làm trùng hoặc
   cùng bỏ sót.
6. Không có tín hiệu nào cho biết "có gì mới" từ lần mở app trước.

**Đã làm (theo đúng thứ tự commit).**

- **Hàng đợi mở thẳng hồ sơ.** `backend/app/services/workspace.py` thêm
  `next_application_id` tính đúng định nghĩa của từng loại việc, dùng lại chính
  các hàm đếm (`_needs_verification`, `_in_screening`, `_WORK_TYPE_QUEUES`) để
  con số trên dashboard và hồ sơ được mở không lệch nhau; `api/dashboard.py` gắn
  id đó vào item. Frontend `lib/workQueueEntry.ts` dựng href, giữ `?queue=` để
  trang hồ sơ dựng lại hàng đợi và tiến độ 3/17 sẵn có.
- **Phím tắt xác minh.** `lib/reviewKeyboard.ts` (logic thuần): `j`/`k` hoặc mũi
  tên di chuyển tiêu chí (dừng ở hai đầu, không vòng), `y`/`n` xác nhận/từ chối.
  Chặn khi đang gõ trong input/textarea, khi có dialog mở, và bỏ qua phím có
  Ctrl/Meta/Alt — để không cướp phím của trình duyệt hay của ô ghi chú.
- **Gợi ý lý do loại.** `lib/rejectionReasons.ts` nhớ lý do đã dùng **theo vị
  trí** trong localStorage và đề xuất từ tiêu chí `NO_MATCH`/`UNCLEAR` của chính
  hồ sơ (kèm tên tiêu chí). Chọn bằng chip, không thêm combobox; không đổi API.
- **Ghi chú cạnh tiêu chí.** Migration `00036` thêm
  `application_private_notes.criterion_id`; `POST /private-notes` nhận
  `criterion_id` và **kiểm tra tiêu chí thuộc đúng vị trí** của hồ sơ. Trang hồ
  sơ gom ghi chú về một nguồn: ghi chú theo tiêu chí hiện trong `EvidenceCard`,
  ghi chú chung ở panel cuối trang, chip "N ghi chú riêng tư" ở đầu hồ sơ cuộn
  tới panel.
- **Người phụ trách hồ sơ.** Migration `00036` thêm `assigned_to`/`assigned_at` +
  index; `PATCH /applications/{id}/assignment` cho HR tự nhận/bỏ nhận, giao cho
  người khác chỉ HR Lead/Admin và người nhận phải là HR của vị trí; mọi thay đổi
  ghi `audit_events`. Danh sách/chi tiết trả thêm `assigned_to_name`. UI: chip
  "Phụ trách: …" + nút Nhận/Bỏ nhận; danh sách ứng viên có bộ lọc
  **Của tôi / Chưa ai nhận** kèm số đếm trên toàn vị trí.
- **Nhắc việc mới.** `lib/workQueueDigest.ts` so snapshot work-queue lần trước
  (localStorage) với hiện tại; badge số việc trên header và dải "có gì mới" trên
  dashboard. Không thêm bảng/endpoint: số liệu đã có sẵn ở work-queue.

**Kiểm thử đã chạy (pass).**

| Lệnh | Kết quả |
| --- | --- |
| `node --test tests/work-queue-entry.test.cjs` | 4/4 |
| `node --test tests/review-keyboard.test.cjs` | 6/6 |
| `node --test tests/rejection-reasons.test.cjs` | 6/6 |
| `node --test tests/work-queue-digest.test.cjs` | 6/6 |
| `node --test tests/criterion-notes.test.cjs tests/applicant-ownership.test.cjs` | 8/8 |
| `node --test tests/ux-metrics.test.cjs` | 11/11 |
| `node --test tests/i18n.test.cjs` | 3/3 |
| `npx tsc --noEmit` / `npx eslint` (các file đã sửa) | pass |
| `python -m py_compile` (`applications.py`, `candidate_details.py`, `schemas/applications.py`) | pass |

**Việc còn chờ / lưu ý.**

- **Migration `00036` chưa áp lên database nào.** Phải chạy trước khi thử: nhận
  hồ sơ, ghi chú theo tiêu chí, lọc "Của tôi".
- **Chưa chạy backend thật.** Môi trường này không có Postgres/pytest, nên các
  endpoint mới (`PATCH …/assignment`, `criterion_id` trong notes) mới chỉ được
  biên dịch, chưa được gọi. Cần thử bằng tài khoản HR và HR Lead thật, gồm cả
  trường hợp HR thường cố giao hồ sơ cho người khác (phải 403).
- **Hàng đợi/dashboard chưa lọc theo người phụ trách** — số liệu vẫn là toàn vị
  trí; chỉ màn danh sách ứng viên có bộ lọc mới. Nếu muốn "việc của tôi" ở
  dashboard thì phải thêm tham số lọc vào work-queue (việc riêng, chưa làm).
- **Lý do loại chỉ lưu ở trình duyệt** (localStorage theo vị trí), chưa lên
  backend; đổi máy/người là mất gợi ý. Cố ý, để không phải mở API mới.
- **Chưa kiểm giao diện/e2e.** Không có Chromium trong môi trường này; chip,
  ô ghi chú và phím tắt mới chỉ được typecheck/lint và test logic thuần.
- Email nhắc việc định kỳ (bước b của mục nhắc việc) **chưa làm** — cần chọn dịch
  vụ gửi email trước.

## 2026-11-19 — Tích hợp nhánh `freebuff` vào nhánh làm việc, gộp hai backlog

**Vấn đề.** Công việc UI/UX nằm trên `freebuff/1434fda45407dc1a68600843` (18
commit, rẽ từ `6aa867f`), còn các bản sửa tiêu chí nằm trên
`arena/ea6e2570-vinit-hrapp`. Hai nhánh chưa từng gặp nhau, và cả hai đều sửa
`frontend/src/i18n/en.json` — file dùng chung, nên không thể deploy riêng lẻ.

**Đã làm.** Nhánh `freebuff` đã tự merge `arena` vào trước (`4ff30da`), nên lần
này chỉ cần fast-forward, **không phát sinh xung đột**. Đã kiểm:

- `en.json`: giữ đủ 1694 key của freebuff **và** 18 key của phần sinh tiêu chí;
  không key nào bị mất. Tổng 1712 key.
- Bộ dữ liệu demo **vẫn là bản tiếng Anh** (`CV_01_daniel_whitfield.docx`…) —
  yêu cầu bắt buộc, không bị ghi đè.
- Không file nào trong phần sinh tiêu chí bị freebuff sửa: `criteriaGeneration.ts`,
  `CreatePositionProgressDialog.tsx`, `positions/new`, `deterministic_matching.py`,
  `api/criteria.py` đều giữ nguyên.
- Hai effect đọc `?tab=` trong trang vị trí vẫn không nhân đôi (một khi mount, một
  trong `handleAction`).

**Kiểm thử trên code đã hợp nhất.** Backend **432 passed**, 174 skipped. Frontend:
`tsc` sạch, unit **84 passed**, i18n 3/3, `next build` thành công, eslint sạch.
Con số unit 84 khớp chính xác phép cộng 49 + 27 + 8.

**Dọn dẹp.** Gộp `doc/HANG_CHO_VIEC.md` vào cuối `doc/VIEC_CHO_LAM.md` (phần B) và
xoá file cũ: hai backlog tên gần giống nhau là nguồn gây nhầm. Ghi chú bàn giao
nằm ngay dưới phần hướng dẫn dùng file.

**Chưa kiểm.** Không có Chromium trong môi trường này nên **toàn bộ e2e mới chưa
chạy được** — chỉ unit/contract test và build. Cần chạy các e2e đó trên máy có
trình duyệt trước khi tin vào các luồng hành động hàng loạt, retention và đo
lường UX.

## 2026-11-19 — Đo tác động của chính các cải tiến UX (thời gian xử lý, hồ sơ quá hạn, mức dùng lô)

**Vấn đề.** Dashboard chỉ có số lượng hàng đợi, nên bốn lượt cải tiến trước đều dừng
ở “cảm giác tốt hơn”: không có số nào cho biết HR mất bao lâu để đóng một hồ sơ cần
xác minh, hay còn bao nhiêu hồ sơ chờ quá 7 ngày. Không đo thì không biết việc nào
thật sự giúp, và cũng không có dữ liệu để chọn việc tiếp theo.

**Thay đổi.**

- `frontend/src/lib/uxMetrics.ts` (mới): bốn event nhẹ — `PROFILE_OPENED`,
  `PROFILE_CLOSED` (kèm thời lượng), `VERIFICATION_COMPLETED`, `BULK_RUN` (số hồ sơ,
  số lỗi, thời gian). Ghi vào `localStorage` của chính máy HR, giới hạn 500 event gần
  nhất, đọc lại có kiểm tra kiểu/bounds nên dữ liệu hỏng không dựng ra số đo giả.
  **Không gửi lên máy chủ và không ghi tên, CV hay nội dung hồ sơ** — chỉ id hồ sơ,
  thời điểm, thời lượng; unit test khẳng định việc này.
- Gắn đo tại đúng ba chỗ người dùng nêu: mở/rời hồ sơ (`applicants/[applicantId]`,
  một cặp event mỗi lượt xem), hoàn tất hồ sơ (ghi khi `handleFinish` thành công,
  không ghi khi lỗi), và chạy lô (`runBulkRows`, ghi cả lô lẫn phần lỗi để thấy lô có
  thật sự thay được việc làm từng hồ sơ). Đo lường không chạm vào luồng nghiệp vụ:
  mọi lỗi storage đều bị nuốt.
- Khối **“Tác động của cải tiến UX”** trên dashboard: trung vị thời gian ở trong hồ
  sơ, thời gian từ lần mở đầu tiên đến lúc hoàn tất (ghép với lần mở *sớm nhất* để
  mở lại không làm thời gian ngắn đi giả tạo), số hồ sơ đã hoàn tất, mức dùng lô
  (số hồ sơ · lỗi · thời gian trung bình), và **hồ sơ chờ xác minh quá hạn** lấy từ
  `work-queue` của máy chủ. Nút “Xoá số đo” chỉ xoá khoá của module này.
- Hai loại số đo được nói rõ ngay trên màn hình: số cục bộ chỉ tính trên trình duyệt
  này; số hồ sơ quá hạn và tuổi hồ sơ lâu nhất là số toàn hệ thống từ máy chủ.

**Phạm vi giữ nguyên.** Không sửa backend, không thêm bảng/endpoint, không đổi luồng
nghiệp vụ hay quyền.

**Kiểm thử.** `frontend/tests/ux-metrics.test.cjs` (mới, 9 test): ghi nối tiếp + giới
hạn 500 event, bỏ event hỏng/lạ, chỉ lưu id và thời lượng (không có tên/email/CV), trung vị thời gian ở hồ sơ không
bị lệch bởi một lượt rất dài, thời gian hoàn tất tính từ lần mở đầu tiên và không
ghép bừa khi thiếu mốc mở, tổng hợp lô (tỉ lệ lỗi 0.167 cho 5/30), chưa có event thì
mọi số đo là `null` chứ không phải 0, xoá số đo không đụng token phiên, và storage
bị chặn không làm hỏng luồng gọi.
`frontend/tests/ux-metrics.e2e.cjs` (mới) chạy dashboard thật với event đã gieo: khối
hiện 2,5 phút (trung vị), 20 phút (mở → hoàn tất), 1 lô với 12 hồ sơ · 1 lỗi, số quá
hạn 6 lấy từ máy chủ; nút xoá chỉ xoá khoá của module; mở một hồ sơ thật rồi rời đi
thì event `PROFILE_OPENED`/`PROFILE_CLOSED` được ghi đúng id và thời lượng, và
không có tên ứng viên hay email trong storage.
Hồi quy xanh: `ux03-dashboard`, `bulk-actions`, `finish-application` (ba màn vừa được
gắn đo) — `bulk-actions` còn khẳng định lô vẫn chạy đúng endpoint cũ sau khi thêm đo.

**Chưa kiểm.** Số đo hoàn toàn cục bộ: chưa có bảng event/endpoint tổng hợp phía máy
chủ, nên chưa đo được toàn bộ nhóm HR hay nhiều máy — đó là việc tiếp theo nếu cần
số liệu để bảo vệ quyết định. E2E mới chỉ khẳng định event mở/rời hồ sơ; việc ghi
`BULK_RUN` và `VERIFICATION_COMPLETED` mới được kiểm ở mức unit test của lib và qua
hồi quy luồng, chưa có assert riêng trong e2e. Chưa thử trên dữ liệu staging thật.

## 2026-11-19 — Màn “Dữ liệu & lưu trữ”: hàng đợi retention và timeline quyết định theo hồ sơ

**Vấn đề.** Backend đã có `backend/app/api/retention.py` từ trước (liệt kê case, tạo,
xác nhận, huỷ) nhưng frontend không có màn nào, nên muốn xử lý hàng đợi lưu trữ/xoá
dữ liệu thì phải gọi API tay. HR cũng không có chỗ xem lại chuỗi quyết định của một
hồ sơ khi đối chiếu với trường hợp xoá.

**Thay đổi.**

- `frontend/src/lib/api.ts`: thêm `retentionApi` với đúng bốn thao tác người dùng làm
  được — `listCases`, `generateCases`, `confirmCase`, `cancelCase`. Hai endpoint còn
  lại của backend (`execute`, `recover`) **không** được đưa lên màn hình: chúng xoá
  dữ liệu thật và cần quy trình vận hành riêng; thêm nút đó là vượt phạm vi và tăng
  rủi ro.
- `frontend/src/lib/retention.ts` (mới): kiểu `RetentionCase`, nhãn trạng thái (Chờ
  xác nhận / Đã lên lịch xoá / Đã xoá dữ liệu / Đã huỷ), nhãn thực thi, `summarize`,
  và quan trọng nhất là **quy tắc hiển thị đúng như máy chủ sẽ chấp nhận**:
  `canConfirmRetentionCase` chỉ bật khi case `PENDING`, đã đến hạn và không có lần
  thực thi đang chạy (backend trả 422 nếu chưa đến hạn, 409 nếu đã xoá/đang xoá);
  `canCancelRetentionCase` không bật khi đang thực thi; `hasApplicationTimeline`
  tắt timeline với hồ sơ đã xoá.
- `frontend/src/app/data-retention/page.tsx` (mới): chọn vị trí (tự chọn vị trí đã
  đóng đầu tiên), dòng tổng hợp (tổng · đến hạn · chờ xác nhận · đã lên lịch · đã
  huỷ), bảng trường hợp với mã ẩn danh, hạn xoá, trạng thái, trạng thái thực thi,
  thời điểm xác nhận và nút hành động. “Tạo trường hợp lưu trữ” mở hộp thoại giải
  thích rằng chỉ vị trí đã đóng và quá hạn mới sinh case, bước này chưa xoá gì; kết
  quả nói rõ tạo được bao nhiêu case (hoặc vì sao không tạo được). Xác nhận/huỷ đều
  có hộp thoại riêng nói rõ hậu quả, gọi đúng endpoint `POST …/confirm` và
  `POST …/cancel`, rồi cập nhật đúng dòng đó.
- **Timeline theo hồ sơ**: mỗi dòng mở được lịch sử quyết định của chính hồ sơ đó
  bằng endpoint sẵn có `GET /applications/{id}/status-events` (ai đổi, khi nào, từ
  trạng thái nào sang đâu, lý do, ghi chú). 403 hiện thông báo “chỉ HR phụ trách”,
  hồ sơ đã xoá thì nút timeline bị tắt kèm giải thích.
- 403 khi tải danh sách (vị trí ngoài phạm vi) hiện đúng thông báo thay vì bảng
  rỗng gây hiểu nhầm là “không có case”. Sidebar có mục **Dữ liệu & lưu trữ**
  (nhóm HR, cạnh Shortlist); quyền thật vẫn do backend quyết định.
- Toàn bộ chuỗi mới đi qua `t()` và có bản dịch tiếng Anh.

**Phạm vi giữ nguyên.** Không sửa backend, không đổi schema, không thêm endpoint:
chỉ dùng đúng hợp đồng retention và status-events đang có.

**Kiểm thử.** `frontend/tests/retention-cases.test.cjs` (mới, 6 test) cho tổng hợp
đếm, nút xác nhận/huỷ đúng điều kiện máy chủ chấp nhận, hồ sơ đã xoá không có
timeline, nhãn lạ không render `undefined`, và đếm ngày đến hạn với ngày thiếu/sai.
`frontend/tests/retention-ui.e2e.cjs` (mới) chạy trang thật với API giả: danh sách
case + tổng hợp, nút Confirm bật/tắt đúng, tạo case báo kết quả và tải lại danh sách,
xác nhận/huỷ gửi đúng POST và đổi chip của dòng, timeline mở đúng lịch sử quyết định
và đóng lại được, case đã xoá không có timeline, và vị trí 403 hiện thông báo.
Hồi quy `a11y-mock` pass sau khi thêm mục sidebar.

**Chưa kiểm.** VM này không có backend/Postgres nên mọi phản hồi retention (kể cả
403, 409, 422) chỉ mô phỏng bằng mock; chưa thử trên dữ liệu thật ở staging.
Bước `execute`/`recover` chưa có UI — cố ý, xem phần Phạm vi.

## 2026-11-19 — Trang tuyển dụng công khai: song ngữ, form tệp dùng được trên điện thoại

**Vấn đề.** `/careers` là bề mặt duy nhất ứng viên thấy, nhưng tiêu đề, nhãn form,
nút và phần đồng ý Talent Pool đều hardcode tiếng Việt, không có chuyển ngôn ngữ;
chỉ có thông báo lỗi đi qua `t()`. Ô tệp là `<input type="file">` mặc định của trình
duyệt — trên điện thoại nó bé, khó bấm và không nói đã chọn CV nào, nên sinh viên
nộp bằng điện thoại dễ bỏ cuộc ngay từ cửa.

**Thay đổi.**

- Toàn bộ chuỗi của trang đi qua `t()`: tiêu đề, cảnh báo chỉ dùng dữ liệu tổng hợp,
nút ứng tuyển, nhãn từng trường, mô tả Talent Pool, mã rút, thông báo thành công và
thông báo lỗi tải danh sách. Khoảng 25 khoá mới có bản dịch tiếng Anh trong
`src/i18n/en.json`.
- `LanguageSwitcher` đặt ở góc phải tiêu đề trang (cùng thành phần các trang công khai
khác đang dùng), nên ứng viên đổi VI/EN ngay tại chỗ; `<html lang>` đổi theo.
- Form được làm lại: các trường `fullWidth` với `autoComplete` đúng loại, nút chọn
CV là `Button component="label"` cao 44px chứa input tệp (vẫn giữ `name="cv"`,
`accept=".pdf,.docx"`), tên tệp đã chọn hiện ngay dưới nút, hai nút gửi/hủy xếp dọc
trên điện thoại và cao 44px. Bỏ `required` trên input tệp ẩn (trình duyệt báo
“invalid form control … is not focusable”) và kiểm tra tệp trước khi gửi, với thông
báo rõ ràng.
- Không đổi API hay payload: vẫn `POST /v1/careers/jobs/{id}/apply` với
`request_id`, `pool_opt_in`, `pool_token` và tệp multipart.

**Kiểm thử.** `frontend/tests/careers-public.e2e.cjs` (mới) với API tuyển dụng giả:
đổi sang EN thì tiêu đề/nhãn/nút/đồng ý/thông báo đều đổi và `html[lang]=en`, đổi lại
VI vẫn đúng; trên 390×844 form không cuộn ngang, mọi nút ≥ 44px và nằm trong màn
hình, chọn tệp xong thấy tên `careers-cv.pdf`, gửi đi đúng một request multipart có
`request_id` + `pool_opt_in` + tệp và hiện thông báo đã nhận. `docx`/`tsc`/`eslint`/unit
đều giữ nguyên xanh.

**Chưa kiểm.** Chưa thử trên thiết bị thật (e2e dùng viewport 390×844, có touch);
chưa có backend thật ở VM này nên phản hồi 202/409/422 của API tuyển dụng chỉ mô
phỏng bằng mock. Trang demo `/careers-demo` vẫn tiếng Việt — ngoài phạm vi yêu cầu.

## 2026-11-19 — Lô hàng loạt sống sót khi đóng tab: biên bản được giữ, chỗ dừng trung thực

**Vấn đề.** Mục 5 của danh sách cải tiến có ba phần: tiến trình, kết quả từng hồ sơ
và thử lại phần lỗi (đã làm ở mục trước), còn phần thứ ba chưa xong — **đóng tab là
mất dấu việc đang chạy**. Lô 30–50 hồ sơ chỉ cần một lần rớt mạng là HR mất biên bản:
không biết hồ sơ nào đã ghi, hồ sơ nào lỗi, và hồ sơ đang ghi dở thì đã sang trạng
thái mới hay chưa.

**Thay đổi.**

- `frontend/src/lib/bulkActionRun.ts`: biên bản lô được tuần tự hóa (`version`,
  `position_id`, `mode`, `reason`, `rows`, `saved_at`) và đọc lại qua
  `parseStoredBulkRun()`. Dữ liệu sai phiên bản, của vị trí khác, JSON hỏng, hoặc dòng
  có bước không hợp lệ bị bỏ toàn bộ — không dựng ra biên bản giả.
- Trạng thái mới `interrupted`: dòng đang chạy đúng lúc lô bị dừng được đánh dấu
  **“Chưa rõ kết quả”**, giữ số bước đã biết nhưng **không** được tự thử lại, vì bước
  cuối có thể đã lưu. `retryFailed()` chỉ đụng dòng `failed`; tiến trình đếm thêm
  `interrupted`.
- Màn xếp hạng lưu lô vào `localStorage` sau mỗi thay đổi (chỉ khi đã có hồ sơ rời
  trạng thái chờ, nên mở rồi đóng không tạo cảnh báo rác), và xoá khi mọi hồ sơ đã
  xong. Khi mở lại trang, nếu còn hồ sơ chưa xong thì hiện một dải nhắc:
  “Lô Shortlist lần trước chưa xong: 1/2 hồ sơ đã cập nhật, 1 lỗi, 0 chưa rõ kết quả”
  với **Xem biên bản** (mở lại đúng hộp thoại, đúng lý do chung, đúng chỗ dừng) và
  **Bỏ qua** (xoá bản lưu).
- Dòng bị gián đoạn trong hộp thoại nói rõ “Lô bị gián đoạn khi đang ghi hồ sơ này;
  mở hồ sơ để kiểm tra trạng thái trước khi làm lại” kèm link mở hồ sơ; khi chỉ còn
  dòng chưa rõ thì hộp thoại chỉ có **Đóng**, không có nút thử lại.
- Nút hành động của lô đã dừng đổi thành **Đóng** + **Thử lại {n} hồ sơ lỗi** (chỉ
  hiện khi thật sự có dòng lỗi), và `handleBulkApply` không chạy khi không còn dòng
  chờ — bấm nhầm không sinh thông báo “Đã cập nhật 0 hồ sơ”.

**Phạm vi giữ nguyên.** Vẫn tuần tự từng `PATCH /applications/{id}/status` hiện có,
không endpoint mới, không đổi schema hay ma trận trạng thái. `localStorage` chỉ là
bản lưu phía trình duyệt của chính HR, không gửi đi đâu; bị chặn storage thì lô vẫn
chạy bình thường.

**Kiểm thử.** `frontend/tests/bulk-run.test.cjs` thêm 3 test: dòng đang ghi thành
“chưa rõ” và không bị thử lại, lưu/đọc lại đúng và loại payload sai (sai vị trí, sai
phiên bản, JSON hỏng, dòng vô lý), dòng `running` khi đọc lại thành `interrupted`.
`frontend/tests/bulk-recovery.e2e.cjs` (mới) chạy một lô lỗi thật, **tải lại trang**,
thấy dải nhắc đúng số liệu, mở biên bản, thử lại chỉ đúng hồ sơ lỗi, rồi tải lại lần
nữa để chắc bản lưu đã được xoá; và một cảnh tab chết giữa bước hai: dòng hiện “Chưa
rõ kết quả”, có link mở hồ sơ, không có nút thử lại.

**Chưa kiểm.** Chưa thử trên trình duyệt thật khi mất mạng giữa request (e2e mô phỏng
bằng một PATCH trả 503 và bằng bản lưu viết tay); chưa có backend thật ở VM này.

## 2026-11-19 — Bảng DOCX giữ hàng cột; lọc hồ sơ theo bằng chứng và thời gian chờ

**Vấn đề 1 — CV dạng bảng đọc lệch hàng.** Bộ đọc DOCX duyệt mọi `w:p` trong tài
liệu, kể cả đoạn nằm trong ô bảng, nên bảng bị làm phẳng thành một dòng cho mỗi ô:
“Python”, “2022”, “VinIT” rơi xuống ba dòng và HR đối chiếu nhầm hàng khi so với tiêu
chí. CV sinh viên rất hay dùng bảng, nên đây là lỗi đọc sai chứ không chỉ là xấu.

**Thay đổi 1.** `frontend/src/lib/docxText.ts` giữ nguyên cấu trúc: duyệt con của
`w:body` theo đúng thứ tự, `w:p` thành đoạn, `w:tbl` thành **bảng** (hàng `w:tr`, ô
`w:tc`, text các đoạn trong ô ghép lại). Ô trộn giữ đúng vị trí cột (`w:gridSpan` → ô
trống đệm), hàng tiêu đề chỉ được đánh dấu khi Word đánh dấu (`w:tblHeader`), không
đoán. Nội dung trong content control (`w:sdt`) vẫn được đọc. `extractDocxBlocks()`
trả block cho phần hiển thị; `extractDocxParagraphs()` cũ vẫn còn cho chỗ chỉ cần
text (mỗi hàng bảng thành một dòng tab). `CVDocumentViewer` render block bảng bằng
`Table` của MUI, có tiêu đề khi Word đánh dấu. Vẫn không thêm thư viện, không đổi
backend, không dùng `innerHTML`.

**Vấn đề 2 — ô tìm chỉ lọc tên.** Dòng đếm chỉ nói “Đang lọc theo tên”, trong khi
việc HR làm hằng ngày là “hồ sơ nào thiếu bằng chứng cho tiêu chí X” và “hồ sơ nào
chờ tôi xác minh quá 3 ngày”; hai câu đó trước đây phải mở từng hồ sơ để tự dò.

**Thay đổi 2.** `frontend/src/lib/applicantReview.ts` thêm
`ApplicantCriteriaFilter` (`criterionId`, `outcome`, `verificationWaitingDays`) và
`matchesApplicantCriteriaFilter()`, ghép với bộ lọc hàng đợi và ô tên thay vì thay
thế nhau:

- “Thiếu bằng chứng” gồm kết quả `UNCLEAR`, kết quả còn `requires_verification`, và
  hồ sơ **không có** kết quả cho tiêu chí đó (kể cả hồ sơ chưa đánh giá) — đúng tập
  hồ sơ HR phải xem.
- Kết quả khác (`Chưa đáp ứng`, `Đã đáp ứng`, `Mọi kết quả`) lọc đúng kết quả đó;
  `MATCH` bao gồm `STRONG_MATCH`.
- “Chờ xác minh quá N ngày” đòi cả cờ cần xác minh **và** tuổi hồ sơ; hồ sơ không
  rõ ngày tạo không bị coi là đã chờ đủ N ngày.
- Màn xếp hạng có ba ô chọn (tiêu chí / bằng chứng / thời gian chờ), dòng đếm nói
  đúng đang lọc gì, và “Xoá bộ lọc và tìm kiếm” đặt lại cả ba. Không đổi API, không
  đổi schema; danh sách tiêu chí lấy từ chính `criterion_results` đã có trong xếp hạng.

**Kiểm thử.** `frontend/tests/applicant-criteria-filter.test.cjs` (mới, 5 test) cho
“thiếu bằng chứng”, từng kết quả, thời gian chờ (kể cả ngày tạo không rõ), và việc
ghép với hàng đợi/ô tên. `applicant-criteria-filter.e2e.cjs` (mới) bấm thật ba ô chọn
trên dữ liệu xếp hạng biến thiên và đối chiếu số dòng + tên dòng. `docx-preview.e2e.cjs`
giờ phục vụ một DOCX **có bảng** và kiểm bảng giữ đúng hàng, đúng thứ tự cột, hàng
tiêu đề là `th` thật.

**Chưa kiểm.** Không có backend chạy ở VM này nên dữ liệu xếp hạng thật vẫn qua
mock; DOCX thật của ứng viên (bảng trộn ô phức tạp, ảnh, chữ trong shape) chưa được
thử — bộ đọc vẫn chỉ đọc text, không dựng lại bố cục.

## 2026-11-19 — Hành động hàng loạt có biên bản: tiến trình, chỗ dừng, thử lại phần lỗi

**Vấn đề.** Shortlist/loại hàng loạt chạy lần lượt từng hồ sơ rồi mới báo kết quả,
nên với lô vài chục hồ sơ HR chỉ thấy nút “Đang cập nhật 20 hồ sơ…” không biết đang
ở hồ sơ nào. Khi một hồ sơ lỗi giữa đường, toàn bộ lỗi bị dồn thành một câu trong
Snackbar, kèm một câu cứng “đã ghi nhận bước Mới → Đang xem, chưa tới Shortlist”
hiển thị cho mọi trường hợp — kể cả khi hồ sơ lỗi ngay bước đầu và chưa ghi gì.
Muốn cứu những hồ sơ lỗi, HR phải chạy lại cả lô: hồ sơ đã xong bị gọi lại, và với
hồ sơ dừng giữa đường bước đã ghi lại bị lặp trong lịch sử.

**Thay đổi.**

- `frontend/src/lib/bulkActionRun.ts` (mới): lô được chốt thành danh sách hồ sơ kèm
  **các bước hợp lệ** lấy đúng từ ma trận chuyển trạng thái hiện có (Mới → Đang xem
  → Shortlist; Đang xem → Shortlist; loại một bước). Mỗi dòng nhớ `applied` (số bước
  đã ghi) và `reached_status`, nên biết chính xác chỗ dừng và biết lần sau đi tiếp
  từ đâu. `retryFailed()` chỉ đưa các dòng lỗi về chờ, `remainingSteps()` trả phần
  còn thiếu; `stopPoint()` trả `null` khi hồ sơ lỗi ngay bước đầu (chưa ghi gì thì
  không được nói “đã sang Đang xem”).
- Hộp thoại xác nhận giữ **biên bản tại chỗ**: tiến trình “Đang xử lý 2/5: <tên>”
  kèm thanh tiến độ, và từng hồ sơ có chip trạng thái (Chờ xử lý / Đang xử lý / Xong
  / Lỗi). Hồ sơ lỗi hiện lý do từ máy chủ và **chỗ dừng** (“Đã ghi nhận bước Đang
  xem, chưa tới Shortlist.”).
- Chỉ khi **tất cả** hồ sơ đều lỗi mới không có gì để thử lại; còn lại nút “Thử lại
  {n} hồ sơ lỗi” chạy đúng tập lỗi, không gọi lại hồ sơ đã xong và không lặp bước đã
  ghi. Lựa chọn trên trang được thu về đúng các hồ sơ lỗi, nên thanh hành động không
  mời chạy lại việc đã hoàn tất. Lô thành công toàn bộ vẫn đóng hộp thoại và báo
  bằng thông báo như trước.

**Phạm vi giữ nguyên.** Không thêm endpoint, không đổi schema hay ma trận chuyển
trạng thái: mỗi bước vẫn là một lần gọi `PATCH /applications/{id}/status` hiện có,
 và lý do chung vẫn được gửi cho từng hồ sơ. Lý do dùng cho thử lại là lý do còn
 trong hộp thoại, nên loại hàng loạt thử lại vẫn bắt buộc có lý do.

**Kiểm thử.** `frontend/tests/bulk-run.test.cjs` (mới, 5 test) cho bước hợp lệ, lọc
hồ sơ không có bước, thử lại chỉ phần lỗi và đi tiếp từ bước còn thiếu, chỗ dừng,
và đếm tiến trình. `bulk-actions.e2e.cjs` bổ sung cảnh lỗi thật: một hồ sơ Đang xem
chậm (thấy tiến trình), một hồ sơ Mới lỗi ở bước Shortlist (thấy lý do + chỗ dừng),
rồi thử lại chỉ gọi đúng hồ sơ lỗi và đúng bước còn thiếu.

## 2026-11-19 — Gom quyền màn hồ sơ về một object `capabilities`

**Vấn đề.** Màn hồ sơ tự quyết định hiện gì từ hai cờ rời `can_update_status` và
`can_manage_hr_notes`, trong khi mỗi endpoint có cổng riêng: ghi nhận xác minh bằng
chứng (`POST /assessments/results/{id}/review`) chỉ nhận quyền HR notes, còn
`can_update_status` là quyền đổi trạng thái. Hai quyền này không luôn đi cùng nhau —
ADMIN toàn cục có quyền đổi trạng thái nhưng không có quyền HR notes — nên người đó
vẫn thấy nút “Trích dẫn đúng, đã kiểm” / “Trích dẫn sai”, và bấm vào là **403**. Nút
“Đã xử lý xong hồ sơ này” cũng gửi review cho mọi tiêu chí còn chờ, nên cả vòng hoàn
tất hỏng ngay ở bước đầu.

**Thay đổi.**

- `backend/app/core/permissions.py`: `_application_access_flags` trả **một cờ cho một
  hành động** — `view_cv`, `view_evidence`, `update_status`, `review_evidence`,
  `manage_hr_notes`, `edit_profile`, `view_status_history`, `reprocess_cv` — mỗi cờ
  trùng đúng cổng của endpoint tương ứng. `application_capabilities()` công bố object
  này; `application_access()` cũ vẫn trả ba cờ như trước nhưng tính từ cùng một lần
  đọc, nên các chỗ gọi cũ không phải sửa và hai đường không thể lệch nhau.
- `backend/app/schemas/applications.py`: schema `ApplicationCapabilities`, gắn vào
  `ApplicationWithAssessment`. Ba cờ phẳng giữ nguyên cho client cũ.
- `backend/app/api/applications.py`: `GET /applications/{id}` trả `capabilities`;
  `view_evidence` được thu hẹp theo từng assessment, nên share chỉ tóm tắt vẫn không
  thấy bằng chứng.
- `frontend/src/lib/applicationCapabilities.ts` (mới): đọc object, đổi sang tên
  camelCase, có dự phòng ba cờ rời cho payload cũ; cờ thiếu = `false` (ẩn nút, không
  để lộ 403). `review_evidence` **không** suy ra từ `update_status`.
- Màn hồ sơ dùng một biến `caps` cho mọi nút: xác minh theo `reviewEvidence`, đổi
  trạng thái / lịch sử / xử lý lại CV theo `updateStatus`, ghi chú HR theo
  `manageHrNotes`, sửa hồ sơ theo `editProfile`. Bước hoàn tất chỉ gửi review cho
  người có quyền xác minh, và hộp thoại nói rõ phần việc còn lại vẫn chờ HR thay vì
  đòi xác nhận một việc họ không ghi được.

**Kiểm thử.** `tests/application-capabilities.test.cjs` (4 test: đọc đúng object, quyền
đổi trạng thái không kéo theo quyền xác minh, dự phòng cờ rời, cờ thiếu = false) —
`npm run test:unit` 48/48; `test:i18n` 3/3; `type-check` và `lint` pass; `py_compile`
ba file backend pass. e2e: `capabilities` (mới — người chỉ đổi được trạng thái: không
có nút xác minh, hộp thoại giải thích, không có request review nào), `verify-only`,
`finish-application`, `ux02-review`, `ranking-context` — pass. Fixture chung nay mô tả
đúng một HR phụ trách (đủ cả hai quyền); trước đó nó là “đổi trạng thái nhưng không
có quyền notes”, tức đúng hình dạng gây 403, và mock vẫn trả 201 nên lỗi bị che.

**Chưa kiểm.** Chưa chạy bộ test backend: VM này không cài được dependency Python
(`pytest` không có, không có virtualenv), nên object capabilities mới được kiểm ở
phía frontend với payload mô phỏng và chỉ đảm bảo biên dịch ở backend. Chưa thử với
API thật + DB thật cho các tổ hợp quyền khác (share chỉ tóm tắt, Hiring Manager).

## 2026-11-19 — Test i18n bắt được nhãn trong `src/lib` và lỗi trang ứng tuyển

**Vấn đề.** Test i18n chỉ quét file `.tsx` và chỉ tìm `t('<literal>')`, nên hai loại
chuỗi thoát lưới. (1) Nhãn khai báo trong `src/lib` (bảng nhãn hàng đợi, thông điệp
lỗi trả về nguyên văn): giao diện dịch chúng qua `t(LABELS[x])` nên test không thấy
khoá nào và một nhãn mới có thể lên production mà không có bản dịch. (2) Lỗi của
form ứng tuyển công khai: `careers/page.tsx` render thẳng `{error}`, nên câu tiếng
Việt vẫn hiện nguyên khi người dùng chọn tiếng Anh, dù khoá đã có bản dịch trong
`en.json`.

**Thay đổi.**

- `frontend/tests/i18n.test.cjs`: đọc bằng AST thay vì regex (comment không bị tính
  là nhãn) và mở rộng phạm vi thành đúng hai luật: `t('literal')` ở mọi file
  `.ts`/`.tsx` dưới `src` (trừ `src/i18n`), cộng mọi literal tiếng Việt trong
  `src/lib`. Literal nằm trong phép so sánh (`===`, `==`, `!==`, `!=`) được bỏ qua
  vì đó là hợp đồng với server (`'IN_REVIEW'`, `'application/pdf'`), không phải nhãn.
  Sau khi mở rộng đã rút lại còn hai luật này (bỏ nhánh `PropertyAssignment` /
  `ReturnStatement` thừa) và kiểm chứng âm: test bắt được literal trong
  `src/lib/intake.ts` và `src/lib/workQueueLabels.ts`, và không đòi dịch mã trạng thái.
- `frontend/src/app/careers/page.tsx`: render `{t(error)}`.
- `frontend/src/i18n/en.json`: thêm 6 bản dịch cho các câu lỗi của form ứng tuyển
  (không rõ đã nhận hay chưa, mã yêu cầu đã dùng, yêu cầu hết hạn, dịch vụ chưa
  sẵn sàng, dữ liệu không hợp lệ, lỗi chung).
- `frontend/tests/intake-ui.e2e.cjs`: thêm một lượt chạy giao diện tiếng Anh — gửi
  hồ sơ thử nghiệm với API bị ngắt và khẳng định câu lỗi hiện bằng tiếng Anh, không
  rơi về tiếng Việt.

**Kiểm thử.** `npm run test:i18n` 3/3, `npm run test:unit` 44/44, `npm run lint` và
`npm run build` pass; e2e `intake-ui` pass (gồm kiểm tra "Careers failure message
follows the selected language: OK").

**Chưa kiểm.** Chưa dịch phần còn lại của trang careers (tiêu đề, nút, cảnh báo vẫn
là tiếng Việt ở cả hai ngôn ngữ); mới kiểm đúng câu lỗi mà form trả về.

## 2026-11-19 — Bỏ nốt từ vựng "matching" khỏi bản dịch tiếng Anh

**Vấn đề.** Giao diện đã thay "matching" bằng từ vựng nghiệp vụ ở lượt trước, nhưng
`frontend/src/i18n/en.json` vẫn còn 11 khoá mở đầu bằng "Điểm matching", "Nhóm
matching", "Chạy matching"… Không màn hình nào còn hỏi những khoá này, nên chúng là
bản dịch mồ côi: người đọc file dễ tưởng giao diện vẫn dùng "matching", và lần sau
thêm lại thuật ngữ cũ sẽ không ai thấy mâu thuẫn. Ngược lại, khoá "Tất cả" (nhãn bộ
lọc đầu tiên) đang được dùng thật nhưng thiếu bản dịch, nên ở giao diện tiếng Anh
nhãn đó vẫn là tiếng Việt.

**Thay đổi** (chỉ dữ liệu, `frontend/src/i18n/en.json`):

- Xoá 11 khoá chứa "matching": "Điểm matching tổng hợp", "Lọc theo nhóm matching",
  "Nhóm matching", "Điểm matching", "Điểm matching cao nhất", "Chưa matching",
  "Chạy matching", "Một số hồ sơ đã sẵn sàng nhưng chưa được matching.", "Đã
  matching", "Hồ sơ chưa matching", "Matching & HR rà soát".
- Thêm `"Tất cả": "All"`.

**Kiểm thử.** `npm run test:i18n` 3/3 (test quét đúng các khoá `t('...')` trong
`src`), `npm run build` pass.

**Chưa kiểm.** Chưa mở lại màn hình xếp hạng ở chế độ tiếng Anh để nhìn nhãn bộ lọc
sau khi thêm bản dịch; chỉ khẳng định bằng test và build.

## 2026-11-19 — Thanh hành động nổi dùng được trên điện thoại

**Vấn đề.** Đo trên Chromium 390×844 (và 360×640): thanh hành động nổi
(`position: fixed`, `left: 50%`, không có `width`) co lại còn **195px rộng và
311px cao** — chiếm hơn một phần ba màn hình, nhãn nút gãy dòng, và trang không
chừa chỗ nên **dòng hồ sơ cuối nằm dưới thanh** (card cuối kết thúc ở 752px,
thanh bắt đầu ở 521px). Nút trong thanh chỉ cao 43–45px, nút xác nhận trong hộp
thoại còn thấp hơn mức chạm thoải mái.

**Thay đổi** (`frontend/src/app/positions/[id]/applicants/page.tsx`):

- Thanh trải hết bề ngang trên điện thoại (`left/right: 8px`, bỏ `translateX`),
  giữ kiểu canh giữa trên desktop; nhãn không gãy dòng, cỡ chữ 13px trên mobile
  để ba hành động xếp vừa hai dòng thay vì bốn.
- Mọi nút trong thanh và hai nút của hộp thoại cao **tối thiểu 44px**; hộp thoại
  xếp nút theo cột trên điện thoại để nút xác nhận rộng và nằm cuối tầm tay.
- Trang đo chiều cao thật của thanh (`ResizeObserver`) và tự chừa
  `padding-bottom` tương ứng, nên hồ sơ cuối luôn cuộn lên trên thanh thay vì bị
  che; không dùng con số cứng vì chiều cao thanh phụ thuộc bề ngang.
- Kết quả đo lại: 390×844 → thanh 167px cao, không chồng lấn (card cuối 581px,
  thanh 669px); 360×640 → thanh 167px, card cuối 357px, thanh 465px.

**Kiểm thử.** Bổ sung mục 5 vào `frontend/tests/bulk-actions.e2e.cjs`: chạy lại
luồng ở 390×844 và 360×640, khẳng định thanh trải sát hai mép, cao ≤ 40% màn
hình, đủ 4 nút với chiều cao ≥ 44px và không tràn ngang, card cuối cùng nằm trên
thanh sau khi cuộn hết, nút xác nhận ≥ 44px và nằm trọn trong màn hình, không có
exception phía client.

| Lệnh | Kết quả |
| --- | --- |
| `npm run test:e2e:bulk-actions` (có kiểm tra mobile) | pass |
| `npm run test:e2e:ranking-context`, `ranking-compact`, `duplicate-warning` | pass |
| `npm run type-check` / `npm run lint` / `npm run test:unit` / `npm run build` | pass |

**Chưa kiểm.** Chưa thử trên thiết bị thật hay trình duyệt di động khác
(iOS Safari, thanh địa chỉ động làm `innerHeight` thay đổi); chưa xem ảnh chụp —
chỉ đo hình học qua Chromium headless. Chưa kiểm bàn phím ảo che thanh khi gõ lý do
chung trong hộp thoại.

## 2026-11-19 — Shortlist hàng loạt được cả hồ sơ Mới (hai bước)

**Vấn đề.** Thanh hành động hàng loạt chỉ shortlist hồ sơ Đang xem; hồ sơ Mới bị
bỏ qua và hiện cảnh báo “cần chuyển sang Đang xem trước”. HR vừa lọc ra một lô
ứng viên mới vừa xem xong vẫn phải mở từng hồ sơ bấm hai lần, hoặc bỏ lô đó.

**Thay đổi** (chỉ frontend, không thêm endpoint, không đổi state machine):

- `frontend/src/app/positions/[id]/applicants/page.tsx`: lô shortlist nay gồm cả
  hồ sơ `NEW`. Mỗi hồ sơ Mới được đẩy qua đúng hai bước của ma trận hiện có:
  `NEW → IN_REVIEW → SHORTLIST`, mỗi bước một lần gọi
  `PATCH /applications/{id}/status`; hồ sơ Đang xem vẫn một bước.
- Hộp thoại xác nhận nêu rõ: số hồ sơ Mới sẽ **ghi nhận hai lần chuyển trạng
  thái** (`Mới → Đang xem → Shortlist`), mỗi bước là một lần gọi API trạng thái
  hiện có nên lịch sử hồ sơ có hai mục. Từng dòng trong danh sách được đánh dấu
  “Mới · 2 bước chuyển trạng thái”.
- Cảnh báo “bỏ qua” chỉ còn dành cho hồ sơ không shortlist được từ trạng thái
  hiện tại (đã Shortlist, hoặc ngoài vòng sàng lọc).
- Lỗi giữa hai bước được báo đúng chỗ dừng: hồ sơ Mới đã lưu bước đầu nhưng
  chưa tới Shortlist thì thông báo nói rõ, để HR không tưởng hồ sơ còn nguyên
  trạng thái.
- Thông báo thành công nêu số hồ sơ Mới đã ghi hai lần chuyển trạng thái.

**Kiểm thử.**

| Lệnh | Kết quả |
| --- | --- |
| `npm run type-check` / `npm run lint` / `npm run test:i18n` / `npm run test:unit` | pass |
| `npm run build` | pass |
| `npm run test:e2e:bulk-actions` (cập nhật) | pass |
| `npm run test:e2e:ranking-context`, `ux03-dashboard`, `duplicate-warning`, `vocabulary-locale` | pass |

E2E chọn 3 hồ sơ (Đang xem + đã Shortlist + Mới) và xác nhận: nút ghi
“Shortlist 2 hồ sơ”; hộp thoại có thông báo hai bước và dòng “Mới · 2 bước”;
chỉ bỏ qua 1 hồ sơ; các request đúng thứ tự
`app-0 SHORTLIST`, `app-11 IN_REVIEW`, `app-11 SHORTLIST`; thông báo cuối nêu
“hai lần chuyển trạng thái”.

**Chưa kiểm.** Chưa chạy với backend thật (mock chấp nhận mọi bước, chỉ kiểm
thứ tự request). Nhánh lỗi giữa hai bước chỉ được đọc trong code, chưa có e2e
giả lập PATCH thứ hai thất bại. Chưa xem trực quan hộp thoại — chỉ kiểm qua
Chromium headless.

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
