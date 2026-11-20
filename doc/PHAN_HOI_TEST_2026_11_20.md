# PHẢN HỒI SAU LƯỢT TEST ĐẦU (2026-11-20)

Ghi lại bốn điểm người dùng nêu sau khi test trên VPS, và cách xử lý từng điểm.
Mục đích: lần sau đọc lại biết **vì sao** làm thế, không chỉ biết đã làm gì.

---

## 1. "Chọn ngôn ngữ JD có vẻ không còn cần nữa vì hệ thống đã hỗ trợ cả 2 ngôn ngữ?"

**Giữ lại bộ chọn, mặc định English.** Người dùng từng chốt: *"tiếng Anh là ưu
tiên tuyệt đối cho JD và CV; tiếng Việt vẫn tuỳ chọn"*, nên không xoá.

Nhưng câu hỏi này đúng một phần, và phần đúng đó mới là chỗ đáng sửa:

- Hệ thống **không** tự dò ngôn ngữ. Prompt sinh tiêu chí dặn LLM tự nhận biết
  ("nếu JD là tiếng Việt thì đọc như tiếng Việt, đừng dịch trước"), tức là nó
  đoán từ nội dung.
- `jd_versions.language_code` được lưu nhưng **không nơi nào đọc lại** khi sinh
  tiêu chí hay chấm điểm. Nó chỉ hiện lại ở API đọc JD. Nói cách khác, bộ chọn
  này hiện **không ảnh hưởng gì tới kết quả** — nó chỉ ghi lại ý định của HR.
- Rủi ro thật: khi HR chọn "Tiếng Việt" cho một JD viết bằng tiếng Anh (hoặc
  ngược lại), hệ thống không phát hiện và không cảnh báo. Nhãn nói một đằng, nội
  dung một nẻo, và về sau không ai biết cái nào đúng.

**Đề xuất (chưa làm, chờ quyết):** hoặc (a) bỏ bộ chọn và suy ra ngôn ngữ từ
nội dung, hoặc (b) giữ bộ chọn nhưng **đối chiếu với nội dung** và cảnh báo khi
lệch. (a) đơn giản hơn nhưng mất khả năng ghi đè khi LLM đoán sai.

---

## 2. "Tải tệp JD txt lên báo lỗi Máy quét chưa sẵn sàng"

**Đã sửa.** Đây là lỗi thật, không phải người dùng làm sai.

Nguyên nhân: `POST /v1/jd-import/file` gọi ClamAV trước khi trích xuất, và **từ
chối cứng** khi `CLAMAV_UNIX_SOCKET` rỗng hoặc clamd không trả lời.

Vì sao chặn cứng ở đây là sai: đường nhập JD **chỉ trích xuất nội dung ra cho HR
đọc và sửa**. Tệp gốc không được lưu, không được xử lý tiếp, không bao giờ chạy.
Chặn ở đây làm hỏng đúng thao tác người dùng cần mà không thêm an toàn nào.

Ngược lại, đường **CV thì vẫn fail-closed**: ở `careers_intake.py`, tệp được lưu
lại và đẩy vào hàng xử lý, nên không quét được thì không nhận. Hai đường khác
nhau về bản chất rủi ro, nên xử lý khác nhau — và điều này được ghi thẳng trong
code để không ai "sửa cho đồng bộ" rồi mở lại lỗ hổng.

Cách sửa:

| Trường hợp | Trước | Sau |
|---|---|---|
| Cờ `PUBLIC_CAREERS_UNSCANNED_FILES_ENABLED` tắt (mặc định) | 503 | **503** (không đổi) |
| Cờ bật, máy quét chết | 503 | **200**, kèm `scanned: false` + cảnh báo + audit `JD_PREVIEW_UNSCANNED` |
| Cờ bật, tệp **bẩn** | 400 | **400** (không đổi — bẩn thì luôn chặn) |
| Máy quét sống | 200 | **200**, `scanned: true` |

Giao diện hiện cảnh báo màu vàng thay vì màu thông tin khi tệp chưa quét.

**Việc anh cần làm trên VPS:** thêm vào `backend/.env` rồi restart backend:

```
PUBLIC_CAREERS_UNSCANNED_FILES_ENABLED=true
```

Hoặc cấu hình `CLAMAV_UNIX_SOCKET` cho đúng (xem mục HANG-01 trong
`VIEC_CHO_LAM.md`) — khi đó không cần bật cờ này.

---

## 3. "Mục đích của Nhóm vị trí (tuỳ chọn) là để làm gì?"

Nó là **khoá nối vị trí với thư viện rubric**, không phải thuộc tính trang trí.

- Mỗi rubric mẫu (bảng `rubric_templates`) bắt buộc thuộc một nhóm
  (`job_family_id`). Dữ liệu hiện có hai nhóm: `IT & Digital` và
  `Vận hành & Hành chính`.
- Màn `/rubrics` tạo rubric **theo nhóm**, vì bộ tiêu chí của hai nhóm khác hẳn
  nhau.
- Nút "Dùng rubric đã xuất bản" ở trang vị trí lấy rubric từ thư viện để sinh
  bộ tiêu chí nháp cho vị trí đó.

**Lỗi đã sửa:** hộp chọn rubric đó liệt kê **toàn bộ** rubric của mọi nhóm,
không lọc theo nhóm của vị trí. HR rất dễ áp bộ tiêu chí vận hành cho một vị trí
kỹ thuật — sai từ gốc và không ai phát hiện cho tới lúc chấm điểm.

Nay rubric **cùng nhóm được xếp lên đầu**, rubric khác nhóm vẫn chọn được nhưng
bị gắn nhãn đỏ "(khác nhóm vị trí)" để đó là lựa chọn có chủ ý.

**Trả lời ngắn:** chọn nhóm vị trí để hệ thống biết lấy bộ tiêu chí nào từ thư
viện. Bỏ trống thì vẫn tạo vị trí được, nhưng lúc dùng rubric sẽ phải tự chọn
tay và dễ nhầm.

---

## 4. Trang Careers — hiển thị danh sách, chỉ tin nhận được hồ sơ

Tham khảo giao diện: `https://careerportalvinuni.talent.vn/`

Đã làm lại theo mẫu:

- **Danh sách dòng** thay vì thẻ to: `Tên vị trí · địa điểm · hạn · [Xem chi tiết]`.
- **Cột lọc trái**: "Loại việc làm" và "Ngành / Lĩnh vực", kèm số lượng. Chỉ
  hiện giá trị đang có tin thật, để không có bộ lọc bấm vào ra rỗng.
- **Bấm vào tin mới ra form ứng tuyển**, và form nằm ngay dưới tiêu đề tin đã
  chọn. Bấm cả dòng (không chỉ nút) để vùng bấm rộng hơn.
- **Tin không nhận được hồ sơ thì không hiện.**

### Điều kiện để một tin được hiện

Kiểm ở **máy chủ** (`GET /v1/careers/jobs`), không phải ẩn ở giao diện:

1. `status = OPEN` và còn hạn nộp.
2. Có JD thật (không rỗng).
3. Có `criteria_versions` ở trạng thái `APPROVED` cho **đúng phiên bản JD đang
   hiển thị**. Không có rubric thì HR nhận hồ sơ cũng không chấm được.
4. Intake đã mở (`PUBLIC_CAREERS_TEST_INTAKE_ENABLED`) **và** quét được tệp
   (có ClamAV, hoặc đã bật cờ nhận tệp chưa quét).

Điều kiện 4 mà không đạt thì trả **danh sách rỗng kèm lý do**
`INTAKE_NOT_OPEN`, và giao diện hiện "Hiện chưa mở nhận hồ sơ". Lý do: một trang
tuyển dụng liệt kê việc mà bấm vào không nộp được là trang hỏng, không phải
trang "đang cập nhật" — ứng viên không đọc thông báo, họ chỉ thấy nút chết.

Tầng ghi (`careers_intake.py`) **độc lập** kiểm lại điều kiện 1–3, nên gọi
thẳng API cũng không nộp lậu được cho tin chưa đủ điều kiện.

### Hệ quả cho dữ liệu hiện tại

Vừa purge sạch, nên **trang Careers đang rỗng** — đúng như thiết kế. Muốn thấy
tin xuất hiện, cần lần lượt:

1. Tạo vị trí có JD.
2. Duyệt rubric cho vị trí đó (`APPROVED`).
3. Bật `PUBLIC_CAREERS_ENABLED=true`.
4. Bật `PUBLIC_CAREERS_TEST_INTAKE_ENABLED=true`.
5. Có ClamAV, hoặc bật `PUBLIC_CAREERS_UNSCANNED_FILES_ENABLED=true`.

Thiếu bất kỳ bước nào trong 3–5 thì trang rỗng, và API nói rõ thiếu cái gì qua
trường `reason`.
