# Spec P3-2: Dashboard chất lượng AI

Thuộc gói lõi Phase 3 (`PHASE3_PROPOSAL.md`, mục P3-2). Dựa trên báo cáo vận hành F2.03 và kiểm định QA F2.04 đã có. Phần "Hiện trạng" là điều đã đọc trong code; phần còn lại là thiết kế đề xuất. Các điểm cần HR Lead/Admin chốt ghi là `D-QD-xx`.

## 1. Mục tiêu

Trả lời được ba câu hỏi mà hiện nay phải suy luận thủ công:
1. AI có đang tốt dần lên không (theo tuần, theo tháng)?
2. Lỗi tập trung ở đâu: khối ngành nào, loại tiêu chí nào, loại tệp nào, phiên bản quy tắc nào?
3. Dữ liệu HR override và cờ QA có đủ và đủ sạch để làm tập nhãn thật cho đánh giá và cho việc quyết định bật reranker hoặc xếp hạng học máy?

Không phải mục tiêu: đánh giá cá nhân HR, thay thế kiểm định từng ca, hay tự động thay đổi rubric/từ điển.

## 2. Hiện trạng (cơ sở thiết kế)

| Đã có | Chi tiết quan trọng cho thiết kế |
| :--- | :--- |
| Báo cáo vận hành (`GET /analytics/operations`) | Khối lượng hồ sơ, phễu theo giai đoạn, thời gian đến shortlist, thời gian xử lý CV, tỷ lệ HR override, **lý do override** (7 mã), danh sách ca override (tối đa 200), lỗi kỹ thuật theo loại tệp và mã lỗi xử lý, xu hướng **theo tuần** (hồ sơ và override). Khoảng thời gian tối đa 366 ngày, mặc định 90 ngày |
| Quy tắc đã chốt cho báo cáo này | Chỉ HR Lead/Admin xem toàn bộ vị trí, HR xem vị trí của mình, **Hiring Manager không xem**, **không thống kê theo từng recruiter** (không dùng làm KPI cá nhân). Các quyết định trước khi bắt đầu theo dõi override không có ảnh chụp kết luận AI nên **bị loại, không đoán** |
| QA sampling (F2.04) | Mỗi đợt lấy ngẫu nhiên 10% assessment hoàn tất **cộng** 100% nhóm rủi ro (một tiêu chí bắt buộc không khớp, hoặc độ phủ bằng chứng sát ngưỡng ±0,05). HR Lead đối soát và kết luận `CORRECT` hoặc `ISSUES_FOUND`; ca có lỗi bắt buộc có cờ: bằng chứng sai, thiếu nội dung, dữ kiện sai, lỗi OCR, kết luận so khớp sai. Mỗi ca giữ ảnh chụp assessment tại thời điểm kiểm định. Chỉ lấy mẫu từ assessment mới nhất của mỗi hồ sơ |
| Phiên bản ghi cùng kết quả | Mỗi assessment gắn phiên bản quy tắc, chính sách chấm điểm, cấu hình AI; mỗi lần xử lý tài liệu gắn phiên bản bộ xử lý |
| Đánh giá offline và Langfuse | Có script đánh giá so khớp và cầu nối gửi điểm tổng hợp lên Langfuse (chỉ khi chủ động bật) |
| Chưa có | Xu hướng chất lượng theo thời gian cho QA; phân rã theo khối ngành/job family; đối chiếu trước–sau khi đổi quy tắc/rubric/mô hình; xuất tập nhãn; cảnh báo khi chất lượng xấu đi |

## 3. Từ điển chỉ số

Mọi chỉ số kèm **mẫu số** và hiển thị cả số lượng, không chỉ phần trăm. Ô có mẫu số dưới ngưỡng tối thiểu (đề xuất 20) hiển thị "chưa đủ dữ liệu" thay vì tỷ lệ.

| Nhóm | Chỉ số | Định nghĩa | Lưu ý đọc đúng |
| :--- | :--- | :--- | :--- |
| Mức đồng thuận của HR | Tỷ lệ override | Quyết định sàng lọc (vào shortlist hoặc loại ở bước sàng lọc) trái với kết luận AI ÷ quyết định có kết luận AI | Đo **sự bất đồng của HR với AI**, không phải độ đúng. HR có thể sai, và AI có thể sai mà HR không override |
| | Cơ cấu lý do override | Số ca theo từng mã lý do ÷ tổng override | Lý do như "từ đồng nghĩa", "chứng chỉ tương đương", "bằng chứng ngầm định" chỉ thẳng vào lỗ hổng từ điển/rubric; lý do "khác" cần ghi chú |
| | Hướng override | AI không đạt nhưng HR cho qua / AI đạt nhưng HR loại | Hướng thứ nhất gần với "bỏ sót nhân tài" (nhạy cảm nhất với mục tiêu của hệ thống) |
| Chất lượng theo kiểm định | Tỷ lệ phát hiện lỗi trên **mẫu ngẫu nhiên** | Ca `ISSUES_FOUND` ÷ ca đã kiểm định, **chỉ tính nhóm RANDOM_SAMPLE** | Đây là ước lượng không chệch của tỷ lệ lỗi chung. **Không trộn** nhóm rủi ro vì nhóm này được chọn vì nghi ngờ nên tỷ lệ lỗi cao hơn tự nhiên |
| | Tỷ lệ lỗi trên **nhóm rủi ro** | Như trên, tách riêng cho nhóm rủi ro | Cho biết quy tắc rủi ro có bắt đúng chỗ không; tỷ lệ cao là mong đợi |
| | Cơ cấu loại cờ | Số cờ theo loại ÷ tổng cờ | Cờ OCR chỉ về tài liệu; cờ so khớp chỉ về rubric/quy tắc |
| | Tồn đọng kiểm định | Số ca chưa kiểm định, tuổi ca cũ nhất | Chất lượng mẫu giảm nếu hàng đợi dồn |
| Hành vi của hệ thống | Tỷ lệ tiêu chí chưa rõ (UNCLEAR) | Kết quả tiêu chí UNCLEAR ÷ tổng kết quả tiêu chí | Cao có thể do CV thiếu thông tin, hoặc quy tắc quá chặt; so với override để phân biệt |
| | Độ phủ bằng chứng trung bình | Trung bình độ phủ bằng chứng của assessment hoàn tất | Theo dõi trôi; không phải điểm đúng |
| | Tỷ lệ cần HR xác minh | Assessment ở trạng thái cần xác minh ÷ tổng | Tải công việc của HR |
| | Lỗi xử lý tài liệu theo loại tệp | Tệp cần HR xem lại ÷ tệp tải lên, theo định dạng và mã lỗi | Đã có ở báo cáo vận hành; đưa vào xu hướng |

**Các chỉ số tính từ kiểm định cần được đọc với cỡ mẫu.** Mức mặc định 10% là quy ước vận hành; chưa có phân tích thống kê về độ rộng khoảng tin cậy với số hồ sơ thực tế. Dashboard hiển thị khoảng tin cậy (ví dụ Wilson) cho tỷ lệ chính, và không kết luận xu hướng khi hai khoảng chồng nhau rõ rệt.

## 4. Phân rã và nhãn phiên bản

**Phân rã (lọc và nhóm):** khối ngành/job family, phòng ban, vị trí, loại tệp, khoảng thời gian. Không phân rã theo từng recruiter.

**Dấu mốc thay đổi trên biểu đồ:** hiển thị các thay đổi làm đổi hành vi AI để đọc đúng nguyên nhân xu hướng:
- đổi phiên bản bộ quy tắc xác định, chính sách chấm điểm, cấu hình/mô hình AI, phiên bản bộ xử lý tài liệu;
- áp dụng hoặc cập nhật rubric mẫu, từ điển đồng nghĩa;
- bật/tắt BGE, xếp hạng học máy, reranker.

Mỗi assessment đã ghi các phiên bản này nên dashboard có thể **so sánh trước–sau theo phiên bản** thay vì chỉ theo ngày. Mốc thay đổi do Admin ghi chú tay (không tự suy diễn) nếu không có sẵn trong dữ liệu (ví dụ cập nhật từ điển).

## 5. Tập nhãn thật (golden set)

Mục tiêu phụ quan trọng: biến dữ liệu override và kiểm định thành tập nhãn dùng cho đánh giá offline và cho quyết định bật tính năng mới.

| Nguồn nhãn | Độ tin cậy | Cách dùng |
| :--- | :--- | :--- |
| Ca QA kết luận `ISSUES_FOUND` có cờ và mô tả | Cao (HR Lead đối soát cạnh CV gốc) | Ca hồi quy: cùng hồ sơ/tiêu chí, kỳ vọng sau khi sửa |
| Ca QA `CORRECT` thuộc **mẫu ngẫu nhiên** | Cao, dùng làm mẫu âm tính không chệch | Nền để đo tỷ lệ lỗi và độ chính xác |
| Override có lý do rõ (từ đồng nghĩa, chứng chỉ tương đương…) | Trung bình (ý kiến HR, chưa phải đối soát độc lập) | Gợi ý bổ sung từ điển/rubric; gắn nhãn "ý kiến HR" |
| Override lý do "khác" | Thấp | Không đưa vào nhãn cho đến khi có ghi chú rõ |

**Ràng buộc xuất tập nhãn:** không chứa họ tên, email, số điện thoại; dùng ID đã băm; chỉ chứa đoạn bằng chứng tối thiểu cần để tái hiện; mỗi lần xuất ghi audit (người xuất, số dòng, bộ lọc). Quyền xuất: HR Lead/Admin. Tập nhãn chỉ dùng cho môi trường đã được duyệt xử lý dữ liệu thật.

## 6. Quyền và quyền riêng tư

- Xem dashboard: HR Lead và Admin (toàn bộ), HR chỉ xem vị trí của mình, Hiring Manager không xem. Giữ quy tắc "không theo từng recruiter" (**D-QD-01**: xác nhận lại với HR Lead).
- Hàng đợi QA hiện chỉ HR Lead kiểm định; ADMIN không tự có quyền QA nếu không có vai trò HR Lead. Dashboard **chỉ đọc số liệu tổng hợp**, không mở ca QA cho người không có quyền.
- Danh sách ca override hiện hiển thị tên ứng viên cho người có quyền; dashboard xu hướng chỉ dùng số liệu tổng hợp, và xuất nhãn phải ẩn danh như mục 5.
- Ô nhỏ (ít hơn ngưỡng tối thiểu) bị che để tránh suy ra một cá nhân từ số liệu rất nhỏ.

## 7. Thiết kế kỹ thuật đề xuất

**API (prefix `/v1/analytics`, mở rộng báo cáo vận hành hiện có):**

| Method | Path | Ghi chú |
| :--- | :--- | :--- |
| GET | `/quality/trends` | Tham số: khoảng ngày, hạt thời gian (tuần/tháng), khối ngành/phòng ban/vị trí. Trả chuỗi thời gian cho các chỉ số mục 3, kèm mẫu số và khoảng tin cậy |
| GET | `/quality/breakdown` | Phân rã theo job family, loại tiêu chí, loại tệp, mã lý do, phiên bản quy tắc/chính sách/cấu hình |
| GET | `/quality/markers` | Danh sách mốc thay đổi (tự động từ phiên bản + ghi chú tay) |
| POST | `/quality/markers` | Admin ghi chú mốc thay đổi (ví dụ cập nhật từ điển); ghi audit |
| GET | `/quality/golden-set/export` | HR Lead/Admin; xuất JSON/CSV ẩn danh theo mục 5; ghi audit |

**Dữ liệu:** phần lớn tính trực tiếp từ bảng có sẵn (sự kiện trạng thái hồ sơ, ca kiểm định và cờ, assessment, kết quả tiêu chí, lần xử lý tài liệu), tương tự cách báo cáo vận hành đang làm. Cần thêm: bảng mốc thay đổi và chỉ mục theo thời gian/vị trí nếu truy vấn chậm. Nếu 366 ngày quá chậm ở quy mô thật thì thêm bảng tổng hợp theo tuần được cập nhật theo lịch; quyết định dựa trên đo thực tế, không làm trước.

**Giao diện:** trang mới "Chất lượng AI" trong nhóm báo cáo: thẻ tóm tắt (tỷ lệ override, tỷ lệ lỗi mẫu ngẫu nhiên, tồn đọng QA), biểu đồ xu hướng có dấu mốc thay đổi và khoảng tin cậy, bảng phân rã có lọc, danh sách lý do override, nút xuất tập nhãn. Việt/Anh. Mọi biểu đồ ghi rõ mẫu số và "chưa đủ dữ liệu" khi nhỏ.

## 8. Phạm vi

**Trong phạm vi:** xu hướng và phân rã các chỉ số mục 3, mốc thay đổi, xuất tập nhãn ẩn danh, quyền và audit.
**Ngoài phạm vi:** cảnh báo tự động/email khi chất lượng xấu đi (có thể thêm sau khi có dữ liệu để chọn ngưỡng), tự động sửa từ điển/rubric, so sánh giữa các recruiter, đánh giá độ công bằng nhân khẩu học (thuộc giai đoạn sau), chi phí và độ trễ LLM (đã có trang riêng).

## 9. Kiểm thử và nghiệm thu

Kiểm thử tự động (dữ liệu tổng hợp):
- Tính đúng từng chỉ số với bộ dữ liệu có đáp án biết trước, **đặc biệt** tách đúng mẫu ngẫu nhiên khỏi nhóm rủi ro.
- Loại đúng các quyết định không có ảnh chụp kết luận AI; không đoán nhãn.
- Phân quyền: HR chỉ thấy vị trí của mình, HM bị từ chối, Admin xem toàn bộ, không có số liệu theo recruiter.
- Che ô nhỏ; mẫu số bằng 0 không chia cho 0.
- Xuất tập nhãn không chứa thông tin cá nhân; mỗi lần xuất có audit.
- Assessment cũ bị thay thế không làm sai chỉ số (chỉ dùng assessment mới nhất cho phần QA).

**Tiêu chí nghiệm thu (đề xuất):**
1. Mỗi chỉ số có định nghĩa, mẫu số và khoảng tin cậy hiển thị; HR Lead xác nhận định nghĩa trước khi phát hành.
2. Xu hướng và mốc thay đổi hiển thị đúng trên dữ liệu pilot (khi có).
3. Tập nhãn xuất được, ẩn danh, và chạy được qua script đánh giá offline hiện có.
4. Không rò rỉ: kiểm tra người không có quyền không lấy được số liệu hay ca của vị trí khác.

## 10. Thứ tự triển khai

| Pha | Nội dung | Phụ thuộc | Độ lớn |
| :--- | :--- | :--- | :-: |
| 1 | Chốt từ điển chỉ số và ngưỡng mẫu số với HR Lead; trục dữ liệu và truy vấn xu hướng cho override | D-QD-01…03 | S |
| 2 | Chỉ số kiểm định (tách mẫu ngẫu nhiên/rủi ro), khoảng tin cậy, phân rã theo khối ngành và phiên bản | Dữ liệu QA đã có | S–M |
| 3 | Giao diện trang "Chất lượng AI", mốc thay đổi | Pha 1–2 | S–M |
| 4 | Xuất tập nhãn ẩn danh + nối với script đánh giá | Duyệt xử lý dữ liệu thật | S |

Tổng ước lượng S–M (khoảng 1–2 tuần). **Giá trị thật chỉ xuất hiện khi có dữ liệu pilot**: nếu pilot chưa chạy thì chỉ kiểm thử được bằng dữ liệu tổng hợp và biểu đồ không phản ánh chất lượng thật.

## 11. Quyết định cần chốt

| Mã | Câu hỏi | Người chốt | Đề xuất |
| :--- | :--- | :--- | :--- |
| D-QD-01 | Ai xem dashboard và có cho HR xem vị trí của mình không | HR Lead | HR Lead/Admin toàn bộ; HR chỉ vị trí của mình; HM không xem |
| D-QD-02 | Ngưỡng mẫu số tối thiểu để hiển thị tỷ lệ | HR Lead | 20 |
| D-QD-03 | Định nghĩa "lỗi" cho tỷ lệ chính: mọi ca `ISSUES_FOUND`, hay chỉ cờ nghiêm trọng (bằng chứng sai, kết luận sai) | HR Lead | Hiển thị cả hai; chỉ số chính là mọi ca có cờ |
| D-QD-04 | Có đặt mục tiêu định lượng (ví dụ tỷ lệ lỗi mẫu ngẫu nhiên tối đa) để dashboard tô màu đạt/chưa đạt | HR Lead + Hoang | Chưa đặt cho đến khi có dữ liệu pilot, tránh mục tiêu tùy ý |
| D-QD-05 | Ai ghi mốc thay đổi và quy ước ghi | Admin | Admin; mốc phiên bản tự động, mốc từ điển/rubric ghi tay |

## 12. Rủi ro

| Rủi ro | Giảm thiểu |
| :--- | :--- |
| Đọc override tăng thành "AI kém đi" | Luôn hiển thị mẫu số, tách theo khối ngành và phiên bản, ghi nhãn "đo sự bất đồng của HR" |
| Trộn nhóm rủi ro vào tỷ lệ lỗi chung làm số liệu sai lệch | Chỉ số chính chỉ dùng mẫu ngẫu nhiên; nhóm rủi ro báo riêng |
| Mẫu nhỏ cho kết luận sai | Ngưỡng tối thiểu, khoảng tin cậy, không kết luận khi khoảng chồng nhau |
| Bị dùng làm KPI cá nhân | Không phân rã theo recruiter; che ô nhỏ |
| Tập nhãn lọt thông tin cá nhân | Ẩn danh, ID băm, audit mỗi lần xuất, chỉ dùng ở môi trường đã duyệt |
| Truy vấn chậm trên 366 ngày | Đo trước; chỉ thêm bảng tổng hợp theo tuần khi cần |
