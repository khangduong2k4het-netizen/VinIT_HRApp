# PHẢN HỒI SAU LƯỢT TEST ĐẦU (2026-11-20)

Ghi lại bốn điểm người dùng nêu sau khi test trên VPS, và cách xử lý từng điểm.
Mục đích: lần sau đọc lại biết **vì sao** làm thế, không chỉ biết đã làm gì.

---

## 1. Bộ chọn ngôn ngữ JD — ĐÃ BỎ

Người dùng chốt: *"nếu không ảnh hưởng thì nên bỏ nó đi"*. Đã bỏ, và thay bằng
dò ngôn ngữ từ nội dung ở máy chủ (`app/services/language_detect.py`).

### Vì sao bỏ

`jd_versions.language_code` được **ghi** ở hai chỗ nhưng **không nơi nào đọc
lại** để quyết định gì: `criteria.py`, `llm_client.py`, `processor.py`,
`jd_import.py` đều không tham chiếu tới nó. Prompt sinh tiêu chí vốn đã dặn LLM
tự nhận biết ngôn ngữ từ nội dung.

Nghĩa là ô chọn đó là **một ô điều khiển giả**: trông như đang cấu hình hệ
thống, thực ra không điều khiển gì. Loại này tệ hơn không có ô nào, vì HR tin
nhầm là mình đã kiểm soát được kết quả.

### "Mất khả năng ghi đè" là gì, và vì sao không mất gì thật

"Ghi đè" nghĩa là: LLM tự đoán ngôn ngữ; nếu đoán sai (JD song ngữ, JD tiếng
Anh có đoạn tiếng Việt dài), HR bấm chọn lại để ép kết quả.

Nhưng **cơ chế đó chưa từng tồn tại** — giá trị chưa từng được truyền tới prompt
hay tới bất kỳ chỗ nào ra quyết định. Nên bỏ đi không làm mất một khả năng đang
có; chỉ bỏ một thứ tưởng là có.

### Rủi ro thật của hướng mới

1. **JD song ngữ, tiếng Việt chiếm đa số** → tiêu chí sinh ra bằng tiếng Việt dù
   HR muốn tiếng Anh. Không còn cách ép. Cách xử lý: sửa tay tiêu chí, hoặc
   viết lại JD cho thuần một thứ tiếng. Hiếm nhưng không phải bằng không.
2. **Mất dấu vết ý định.** Trước đây còn một chỗ ghi lại HR *định* ngôn ngữ là
   gì; nay không còn. Đổi lại, không còn nhãn sai.
3. **JD tiếng Việt không dấu** ("Tuyen dung ky su phan mem") → đoán là tiếng Anh.
   Chấp nhận: JD thật gần như luôn có dấu, và nhãn này chỉ để lưu, không ảnh
   hưởng nội dung tiêu chí — LLM vẫn đọc nguyên văn JD.

### Cách dò và vì sao không dùng thư viện

Chỉ đếm tỉ lệ chữ cái có dấu tiếng Việt. Ngưỡng 8%, lấy từ đo thật:

| Loại văn bản | Tỉ lệ chữ có dấu |
|---|---|
| JD tiếng Việt thật (3 mẫu) | 17% – 29% |
| JD tiếng Anh có "Đại học Bách khoa Hà Nội" | 2,4% |
| JD tiếng Anh thuần | 0% |

Ngưỡng cũ thử nghiệm 0,5% từng làm JD tiếng Anh bị gắn nhãn tiếng Việt chỉ vì
một tên trường — đúng ca dễ sai nhất ở môi trường Việt Nam.

Không dùng thư viện nhận dạng ngôn ngữ: chỉ cần phân biệt Việt với phần còn
lại, và thêm một phụ thuộc ngoài cho bài toán đếm dấu là cái giá không đáng.

### Thay đổi kỹ thuật

- `jud_language_code` trong `PositionCreate` và `language_code` trong
  `JDVersionCreate` **vẫn giữ** trong schema để client cũ không bị 422, nhưng
  **giá trị bị bỏ qua**. Không xoá hẳn vì như vậy là phá vỡ hợp đồng API mà
  không có lợi ích gì.
- Giao diện: bỏ ô chọn ở cả màn tạo vị trí và dialog tạo phiên bản JD; không gửi
  trường này lên nữa.
- 14 test mới cho hàm dò, gồm ca "JD tiếng Anh có tên trường tiếng Việt".

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
