# Kế hoạch cải tiến workflow và UI/UX HR – Hiring Manager

## 1. Mục tiêu và phạm vi

**Trạng thái:** plan sau rà soát mã nguồn và hai trang JD mẫu; anh đã xác nhận JD bắt buộc và vòng đầu chỉ nhận `.docx`/`.txt`; chưa triển khai và chưa đo usability thực tế. Đây là plan mới bổ sung cho `FRONTEND_UI_UX_UPGRADE_PLAN.md` (UX-0–UX-4 đã có trong code, gate usability còn mở), không coi plan cũ là chưa làm.

**Mục tiêu:** HR/HM hoàn thành công việc theo ngữ cảnh, ít phải mở trang phụ, biết ngay việc cần làm, không phải nhớ quy trình kỹ thuật. Chỉ tự động hóa bước có thể kiểm tra/khôi phục; **HR/HM vẫn duyệt và quyết định**.

**Phạm vi rà soát:** danh sách và tạo vị trí, nhập/chỉnh JD, tiêu chí/rubric, duyệt HR/HM, tiếp nhận CV, danh sách và xếp hạng ứng viên, xem hồ sơ, shortlist/scorecard, dashboard, điều hướng, các điểm nối Careers/Gmail/Talent Pool. Không thay đổi engine chấm, phân quyền, consent/retention hoặc thực hiện demo thật trong lượt lập plan.

**Bằng chứng:** đọc mã frontend/backend, schema, test và plan UX cũ; phản hồi do anh cung cấp; `fetch_page` đọc được hai trang công khai mẫu. Chưa quan sát HR/HM thao tác, chưa có số đo click/thời gian, chưa kiểm thử trình duyệt end-to-end trên VPS, chưa kiểm tra parser JD thực sự trên VPS. Nhận định UX là giả thuyết dựa trên code/feedback, cần xác nhận với người dùng.

## 2. Kết luận nhanh: vấn đề và ưu tiên

| Mức | Vấn đề quan sát trong code/feedback | Tác động và hướng xử lý |
|---|---|---|
| P0 | Tạo vị trí nằm trong popup; HR nhập title, phòng ban, HM và JD nhưng sau đó phải sang trang chi tiết, đặt hạn, tạo và duyệt tiêu chí; form ghi “JD tiếng Anh”. `positions.py` luôn lưu ngôn ngữ `en`, kể cả khi dán tiếng Việt. | Trang tạo riêng, chọn nguồn JD, ngôn ngữ đúng ngay từ đầu, đặt hạn trong cùng luồng; sau lưu chuyển đúng bước rà soát. Không tạo JD version giả chỉ để đổi ngôn ngữ. |
| P0 | Danh sách ưu tiên mặc định `REVIEW_PRIORITY`, không phải thứ tự `rank_number`. Nó đẩy file lỗi/trùng/xác minh lên trước; bảng vẫn hiển thị cột “thứ hạng”, khiến thứ tự 3, 1, 2… có thể xuất hiện và gây hiểu nhầm. | Tách rõ **Xếp hạng** và **Việc cần rà soát**; nhãn, thứ tự mặc định và số thứ hạng phải nhất quán. Không thay đổi chính sách ranking backend trong một thay đổi UI. |
| P0 | `/positions/[id]` chứa stepper/next action nhưng JD, tiêu chí và ứng viên tách tab/trang; xem JD khi duyệt và tìm lại danh sách ứng viên phải chuyển ngữ cảnh. | Workspace theo vị trí: JD cạnh tiêu chí khi duyệt, nút ứng viên luôn nhìn thấy kèm số lượng và trạng thái, liên kết đúng ngữ cảnh. Giữ các route hiện có. |
| P0 | HM xem shortlist qua dialog danh sách `/shortlist`, rồi mở ứng viên/scorecard; thông tin cần quyết định bị chia nhiều vùng. Quyền HM hiện dựa vào share. | Màn duyệt shortlist tập trung, JD/tiêu chí, hồ sơ được chia sẻ và scorecard ở cùng ngữ cảnh; kiểm tra lại quyền ở backend, không nới scope. |
| P1 | Frontend applicant review gọi `applicationsApi.listAll` và gộp với ranking trên client; danh sách chỉ lấy `NEW`, `IN_REVIEW`, `SHORTLIST`, search theo tên. Counts/filter có thể không đại diện toàn bộ vòng đời. | Làm rõ phạm vi “đang sàng lọc”, thêm truy cập hồ sơ ngoài sàng lọc có phân quyền; server-side query/pagination là hạng mục contract riêng, không giả vờ một trang là toàn bộ. |
| P1 | DOCX CV hiện báo phải tải xuống, PDF mới nhảy trang theo bằng chứng; không có highlight chính xác. | Ưu tiên xem được trích xuất và PDF inline; DOCX preview là hạng mục kỹ thuật riêng có giới hạn an toàn, fallback tải xuống theo quyền. |
| P1 | Sidebar trộn mục làm việc, test Gmail, email demo, Talent Pool thật/demo và rubric. | Điều hướng theo nhiệm vụ/role; nhóm test khỏi công việc chính, nhưng không chỉ dựa vào ẩn menu để bảo vệ quyền. |
| P1 | JD upload/link chưa có luồng nhập; parser hiện tại xử lý CV PDF/DOCX, không hỗ trợ JD `.txt` hay Word legacy `.doc`. | Thêm import có preview/edit/nhập lại, kiểm tra an toàn/giới hạn và các định dạng thực sự hỗ trợ; không quảng cáo `.doc` khi chưa có parser. |
| P2 | Work queue/next action đã có nhưng có thể chưa bao phủ tác vụ thực tế, số liệu và tên gọi còn thiên kỹ thuật. | Dùng baseline HR/HM và phân tích hành động; cải thiện hợp đồng `workspace`, không thêm logic nghiệp vụ chỉ ở frontend. |

### Phân biệt ba loại “ưu tiên”

1. **Thứ hạng đánh giá:** `rank_number` do backend tạo theo chính sách và lần chạy; chỉ các hồ sơ đủ điều kiện có số hạng. Ở mặc định backend, thứ tự dựa trên nhóm kết quả bắt buộc → điểm → độ phủ → tie-break ổn định; mode LTR ACTIVE có thể thay đổi trong phạm vi policy cho phép. Không nói đơn giản là điểm cao nhất luôn hạng 1.
2. **Ưu tiên cần HR xử lý:** thứ tự công việc hiện tại `file cần kiểm tra → cảnh báo trùng → cần xác minh → có dấu hiệu mismatch → chưa đánh giá → còn lại`, sau đó mới so hạng/điểm. Đây là ưu tiên giải quyết vấn đề, **không phải mức phù hợp**.
3. **Quyết định tuyển dụng:** do người tuyển dụng đưa ra, không tự động shortlist/loại/chọn theo AI. `UNCLEAR` không phải `NO_MATCH`; điểm, độ phủ và độ mạnh bằng chứng là các đại lượng khác nhau, không gộp thành “độ tin cậy AI”.

## 3. Luồng mục tiêu (giữ quy tắc nghiệp vụ)

### 3.1 HR: tạo vị trí và đưa vào trạng thái sẵn sàng

```text
Vị trí → + Tạo vị trí [trang riêng]
  Thông tin vị trí + HM + hạn + nguồn JD (Dán | Tệp | Link)
  → Trích xuất có xem trước, sửa, chọn ngôn ngữ
  → Tạo vị trí [thao tác có xác nhận]
  → Rà soát JD và bộ tiêu chí đề xuất/mẫu
  → HR duyệt & gửi HM    HOẶC    HR Lead/Admin duyệt trực tiếp theo quyền
  → Tiếp nhận CV / Xem ứng viên / Theo dõi trạng thái
```

- **Một trang, không nhất thiết một màn hình dài:** nhóm thông tin rõ, sections/anchor, CTA cố định, hiển thị lỗi tại trường và giữ nội dung khi lỗi. Nút quay lại cảnh báo dữ liệu chưa lưu. Không phụ thuộc thao tác bằng chuột.
- Trường cần thiết: phòng ban, tên vị trí, HM đang hoạt động khác HR, JD, ngôn ngữ; mã do backend sinh, hiển thị preview là dự kiến; hạn, địa điểm/hình thức là thông tin hữu ích nhưng chính sách bắt buộc phải thống nhất. Có thể đặt hạn khi tạo; xác định múi giờ, hiển thị rõ.
- **Nguồn JD là lựa chọn cách nhập:** mặc định dán; có thể chọn upload/link, mọi nguồn đổ về editor có thể sửa. Chuyển nguồn không tự xóa nội dung đã sửa; hỏi xác nhận trước khi thay thế. Import chỉ là bản nháp ở client/server tạm, **không tự lưu JD/khởi chạy AI**.
- **Quyết định đã chốt — JD bắt buộc:** HR chọn một trong ba cách (dán, upload `.docx`/`.txt`, link được hỗ trợ), xem/sửa nội dung và phải có nội dung JD không rỗng trước khi tạo vị trí. Không triển khai lưu vị trí nháp không JD. Import lỗi hoặc trích xuất rỗng thì không coi là có JD; cho phép HR sửa, dán hoặc thử lại. Backend vẫn kiểm tra độc lập và tạo position/JD/HM atomic, không chỉ dựa vào nút bị khóa ở UI.
- **Ngôn ngữ:** trường `vi/en` rõ ràng, có gợi ý tự nhận diện tùy chọn nhưng HR xác nhận; API nhận `jd_language_code` có default `en` để client cũ vẫn dùng được, lưu ngay phiên bản đầu. Kiểm tra migration/schema thực tế và gọi tương thích; không backfill đoán ngôn ngữ dữ liệu cũ. Sau tạo JD sửa vẫn dùng version/optimistic lock hiện có.
- **Ngày mở tuyển:** lựa chọn minh bạch; hiện Careers hiển thị mọi `OPEN` còn hạn, không đợi rubric duyệt. Thêm cảnh báo xem trước JD công khai và xác nhận khi đặt hạn/mở; không âm thầm đổi quy tắc public. Nếu kỳ vọng “chỉ đăng sau khi duyệt”, phải là thay đổi sản phẩm riêng, không đưa lén vào UX.
- Sau lưu, server trả position ID; chuyển thẳng tới workspace đúng bước. Cung cấp “Tạo tiêu chí từ JD” và “Dùng rubric” cạnh nhau, không ngụ ý một mẫu đã được duyệt cho vị trí. Không tự tạo cùng lúc hai job AI. Giữ phiên bản JD và idempotency/chống double-click.

### 3.2 HR/HM: rà soát và duyệt ngay tại ngữ cảnh

- Màn chính có 2 cột (desktop), xếp dọc (mobile): **JD phiên bản đang duyệt** bên trái; **tiêu chí bắt buộc/ưu tiên và trọng số** bên phải. Có xem toàn văn/thu gọn và diff khi JD hoặc tiêu chí thay đổi; cùng một dữ liệu/version, không copy thủ công.
- Header: vị trí, mã, HR phụ trách, HM, trạng thái hiện tại, phiên bản JD/criteria, ai cần làm tiếp. Các CTA rõ “HR duyệt & gửi HM”, “HM duyệt chuyên môn”, “Yêu cầu chỉnh sửa”; Admin/HR Lead direct approve khi backend cho phép, có nhãn trách nhiệm rõ.
- Nếu thiếu trọng số, JD thay đổi, quyền không đủ, AI lỗi, đang xử lý: nêu **lý do + hành động** cạnh nút, không chỉ disable. Giữ nguyên yêu cầu hai tài khoản khác nhau trong luồng HR→HM, version concurrency, audit; không tự duyệt bằng AI.
- HM vào từ dashboard/work queue/deep link, mở đúng vị trí, đúng phiên bản và phần cần duyệt, thấy JD + tiêu chí trước khi quyết định. Nếu đã thay đổi/đã duyệt ở tab khác, backend trả xung đột, UI tải lại và giải thích.

### 3.3 HR: ứng viên, xếp hạng và xử lý hằng ngày

- Ngay trong header mỗi vị trí: **Ứng viên (N)**, **Cần xử lý (M)**, **Shortlist (K)** — mỗi mục đi thẳng đúng danh sách, giữ `position_id`, tab/filter/sort trong URL. Không coi số liệu chưa tải là số 0.
- Trang ứng viên có hai chế độ rõ ràng:
  - **Xếp hạng:** mặc định `RANK` tăng dần theo `rank_number` do backend trả; các hồ sơ `rank=null` ở nhóm riêng “Chưa đủ điều kiện xếp hạng / chưa đánh giá”, không tự cấp số. Giải thích vì sao không có số, nếu backend cung cấp đủ dữ liệu. Cột số hạng phản ánh lần chạy thực, **không dùng số dòng**. Hiển thị dữ liệu cũ/chưa có assessment một cách trung thực.
  - **Cần rà soát:** giữ `REVIEW_PRIORITY` hiện tại, kèm nhãn lý do/file/trùng/thiếu bằng chứng; nếu hiện số hạng thật, ghi rõ “Thứ hạng lần chạy” và không ngụ ý thứ tự trong hàng là xếp hạng. Với nhiều cảnh báo, cho thấy tất cả, ưu tiên hiển thị chỉ là quy tắc UI.
- Trong Xếp hạng: tên, hạng, trạng thái phù hợp, điểm **một phần**, độ phủ và cảnh báo, phiên bản/thời điểm lần chạy nếu API cung cấp; mở rộng xem bằng chứng và link CV. Không gọi coverage là confidence; không dùng màu đơn thuần. Tên/điểm/stale phải rõ nếu hồ sơ mới, tiêu chí đổi, processing lỗi, assessment thiếu, ranking chưa chạy hoặc chỉ có một phần ứng viên.
- Sort rank/score/review priority phải có tên cụ thể, thể hiện sort hiện hành trong URL; lọc/search/rank không đánh lại số, phân trang ổn định. Không trộn kết quả cũ với mới mà không có nhãn. Backend `get_latest_ranking` hiện lọc theo JD/criteria/profile mới nhất và trạng thái sàng lọc; cần thiết kế API riêng để biểu diễn freshness/chưa đánh giá, không suy đoán từ mảng rỗng.
- Chi tiết ứng viên: tận dụng side-by-side và prev/next hiện có; ưu tiên ngay phần bằng chứng/CV và nút quyết định; mở xem chi tiết trong cùng ngữ cảnh với URL có thể chia sẻ. Lưu filter/scroll, quay lại đúng hàng. Tiếp tục cho HR ghi chú riêng; HM không thấy HR notes, hồ sơ ngoài share hay CV khi share không cho phép.
- DOCX: trước mắt hiển thị phần trích xuất được phép + nút tải xuống nếu được cấp quyền; nếu cần preview DOCX thực, làm conversion/hiển thị riêng, sandbox, giới hạn nội dung và kiểm soát audit. Không hứa highlight PDF chính xác khi hiện chỉ nhảy trang.

### 3.4 HM: duyệt shortlist / phản hồi

- Mở từ work queue → đúng shortlist đang được chia sẻ → **trang làm việc**, không phụ thuộc dialog sâu. Header mô tả vị trí, JD/criteria phiên bản áp dụng, người gửi, hạn phản hồi, trạng thái share.
- Cột trái danh sách được share; cột phải ứng viên đang chọn + CV/bằng chứng được phép + scorecard; nút **Lưu nháp** / **Gửi phản hồi** theo hợp đồng hiện có, hiển thị phần chưa hoàn tất và lỗi từng tiêu chí. Giữ nháp khi chuyển ứng viên/tab, xử lý đồng thời và lỗi mạng rõ ràng.
- Chỉ xem hồ sơ/CV, feedback, đánh giá khi share/role hiện tại cho phép; share bị revoke, retention, JD/version thay đổi hoặc link cũ phải bị backend từ chối và UI ngừng hiển thị tài liệu. Không truyền HR private notes sang HM. Tránh biến “xem danh sách” thành quyền xem toàn bộ ứng viên của vị trí.

### 3.5 Các điểm nối khác

- **Dashboard:** “Việc của tôi” ưu tiên hành động với người chịu trách nhiệm, thông tin đủ ngắn và deep link; tách số liệu báo cáo sang vùng phụ, role HR/HM hiển thị đúng phạm vi. Tận dụng `dashboard/work-queue`/workspace contract đang có.
- **Tiếp nhận CV:** panel trong workspace thể hiện file, tiến độ, lỗi, CTA đi danh sách; không tự tái xử lý từng file nếu API chưa có. Nhắc khi tác vụ vị trí đang chạy. Không hứa xử lý tức thì.
- **Gmail test:** hiển thị trạng thái nhận, lỗi và liên kết hồ sơ trong ngữ cảnh vị trí; đồng bộ thủ công; không suy consent, không coi tên/email giữ chỗ là danh tính thật. Chỉ test synthetic khi đã cấu hình OAuth/scanner.
- **Talent Pool:** giữ opt-in/rút/retention và role gate. Scan hiện là danh sách **đủ điều kiện**, không phải matching/ranking; không gắn nhãn “phù hợp” hay số điểm cho đến khi có matching được thiết kế/duyệt riêng. Luôn cho phép rút theo thiết kế sau khi cấp mã.
- **Careers:** nêu trạng thái công khai ngay nơi HR sửa vị trí; review tất cả `OPEN` còn hạn. Không xóa gate scanner hoặc thay đổi chính sách listing trong đợt UX.

## 4. Nhập JD từ tệp và URL — thiết kế khả thi

### 4.1 Kết quả khảo sát hai URL người dùng đưa

- [Data Engineer](https://careerportalvinuni.talent.vn/job/vinfast-data-engineer-16526) và [Mechanical Design Engineer](https://careerportalvinuni.talent.vn/job/vinfast-mechanical-design-engineer-16525): công cụ đọc trang đã thấy heading **Job Description**, mô tả/nhiệm vụ, **Requirements** và tiếp sau là **Application Tracking Form**. Khối JD cũng bắt đầu bằng hướng dẫn ứng tuyển 2 bước/link ngoài; HR có thể muốn bỏ hướng dẫn đó khỏi JD nội bộ. Trang còn có job liên quan, navigation, captcha và form: không đưa chúng vào nội dung JD.
- Đây là **thử đọc bằng công cụ fetch của agent**, không phải test adapter HTTP/DOM trong HRA, không chứng minh VPS truy cập được trang hay cấu trúc ổn định. Trang có thể đổi, yêu cầu quyền/chặn truy cập hoặc render động. Cần kiểm tra điều khoản/quyền sử dụng nội dung và quyền network thực tế trước deploy.
- Ưu tiên xác định vùng DOM theo heading `Job Description` và khối nội dung của job, kết thúc trước form/related/footer, bao gồm `Requirements`, giữ bullet/thứ tự; **không cắt tại heading `Requirements`**. Tách “hướng dẫn ứng tuyển” thành phần xem lại/tùy chọn, không tự xóa nội dung mơ hồ. Nếu DOM không chắc chắn hoặc thiếu heading/empty/truncated/không tìm được ranh giới, báo không tin cậy và cho HR dán thủ công; không silently lấy toàn trang.
- Output chỉ là plain text đã làm sạch, kèm cảnh báo nguồn và preview có thể sửa. Các nội dung/URL ngoài, markdown hay HTML không được chèn thành HTML tin cậy hoặc thực thi script. Lưu nguồn/thời điểm nếu nghiệp vụ đồng ý; không chứa query chứa token/PII, không làm lộ link riêng. Không tự chạy form, captcha hay theo link tuyển dụng ngoài.

### 4.2 Hỗ trợ tệp

- P0/P1: `.txt` UTF-8 có kiểm tra encoding, `.docx` theo nội dung thực (không chỉ đuôi); ưu tiên dùng lại parser DOCX hiện tại sau khi kiểm tra JD có bảng/heading/bullet. Xác minh khả năng trích xuất bảng vì `document_processor` hiện đọc paragraph và có thể bỏ sót bảng. Giữ thứ tự, hiển thị cảnh báo nếu mất cấu trúc; limit input/output, error states, file rỗng/sai định dạng/ZIP bomb. AV quét trước parse; scanner lỗi thì dừng an toàn. Không gửi file/Nội dung vào log/analytics.
- **Định dạng đã chốt:** vòng đầu nhận `.docx` và `.txt`; không hỗ trợ `.doc` Word binary legacy. UI thông báo rõ khi chọn `.doc`, hướng dẫn lưu thành `.docx` hoặc dán nội dung, không tự đổi đuôi. Converter `.doc` nằm ngoài phạm vi vòng này, chỉ xem xét nếu có yêu cầu mới.
- Xử lý parse trên backend có RBAC HR, quota/giới hạn và không lưu file thô lâu hơn cần thiết; quy định xóa tệp tạm và cleanup lỗi. Không đồng nhất dữ liệu JD với CV hay tự chuyển sang pipeline ứng viên. PDF JD nếu muốn là phần mở rộng sau, không bỏ qua gate an toàn.

### 4.3 URL adapter và các ràng buộc tối thiểu

- Đề xuất API HR-only dạng `POST /v1/jd-import/preview` hoặc tương đương; trả văn bản, warnings, nguồn đã chuẩn hóa, không tạo position/JD, không log nội dung. Endpoint file/URL cụ thể chốt khi thiết kế hợp đồng; xem parser là nguồn untrusted.
- **Demo allowlist hẹp:** chỉ `https://careerportalvinuni.talent.vn/job/<slug-id>` (xác nhận pattern thực tế), không credential, port lạ, IP literal, nội bộ, localhost hay link ngoài. Kiểm tra DNS và mọi địa chỉ khi kết nối; chặn private/loopback/link-local/metadata, DNS rebinding, proxy ngầm; pin/verify điểm kết nối an toàn. Tắt redirect hoặc xác nhận lại từng hop cùng policy, không theo redirect ra ngoài allowlist. Giới hạn thời gian, số byte, content type, số redirect, concurrency và rate; không browser headless tùy ý, không credential/cookie.
- Chặn script/iframes, không thực thi JS; phục vụ error rõ ràng (URL không hỗ trợ, không kết nối, trang đổi cấu trúc, không thấy JD, file quá lớn, scanner lỗi). Có nút dán thủ công và giữ nội dung form. XSS/SSRF/rò nội bộ không được hy sinh để giảm một bước. Trang public không đồng nghĩa được phép scrape mọi domain.
- Kiểm thử fixture HTML tối giản tổng hợp, 2 layout đại diện, HTML malformed, tiếng Việt, heading thiếu, nội dung động, block/challenge, URL gian lận, redirect, DNS private/rebinding, size/timeout, HTML chứa script và dữ liệu form. Test integration từ VPS hoặc staging **sau khi được phép**; xác nhận egress, DNS, consent/trách nhiệm trước khi nói đã hỗ trợ.

## 5. Thiết kế màn hình đề xuất (wireframe chữ)

**A. Tạo vị trí — `/positions/new` (mới, không thay route cũ)**

```text
← Vị trí                         TẠO VỊ TRÍ
Thông tin  [Tên] [Phòng ban] [HM] [Hạn / múi giờ] [các trường tùy chọn]
Nguồn JD   (• Dán) (  Tệp DOCX/TXT) (  Link talent.vn)
            [vùng nhập / chọn tệp / nhập link] [Lấy nội dung]
Nội dung    [Editor: JD, yêu cầu, chỉnh sửa được] [Ngôn ngữ vi/en]
            [Nguồn + cảnh báo trích xuất] [Xem trước phần công khai]
                                     [Hủy] [Tạo vị trí và tiếp tục]
```

**B. Duyệt trong vị trí — dùng route hiện có**

```text
Tên · Mã · HR · HM · JD v2 · Tiêu chí v1        Ứng viên (N)  Shortlist (K)
[Bước cần làm + ai làm + lý do]    [CTA đúng quyền]
┌────────── JD đang xét ──────────┬──────── Tiêu chí bắt buộc/ưu tiên ───────┐
│ Xem JD, nguồn, phiên bản       │ Từng tiêu chí, trọng số, sửa khi được phép │
└─────────────────────────────────┴───────────────────────────────────────────┘
           [Yêu cầu sửa] [HR gửi HM / HM duyệt / duyệt trực tiếp theo quyền]
```

**C. Ứng viên — cùng route `/positions/{id}/applicants`**

```text
Ứng viên / vị trí X                      [Tiếp nhận CV] [Chạy đánh giá]
[ Xếp hạng ] [ Cần rà soát (M) ]       [Tìm tên] [lọc] [sort hiển thị rõ]
Hạng | Ứng viên | Kết quả | Điểm một phần | Độ phủ | Cảnh báo | Hành động
  1  | ...      | ...     | ...            | ...    | ...       | Xem
-- Chưa đủ điều kiện / Chưa đánh giá (không có số hạng) --
```

**D. HM — shortlist**: list ứng viên đã chia sẻ + bảng thông tin/scorecard gắn với ứng viên đang chọn + JD/tiêu chí; trạng thái share và quyền CV luôn nhìn thấy; link có ngữ cảnh, không mở quyền vượt share.

## 6. Thứ tự triển khai đề xuất, phụ thuộc và nghiệm thu

Không ước lượng ngày trước khi đo độ lớn và chốt phạm vi. Mỗi giai đoạn là lát cắt có thể test/rollback; không gộp deploy trong khi đang chạy tác vụ, không tự áp migration hay thay đổi VPS khi chỉ đang lập plan.

| Đợt | Kết quả giao | Phụ thuộc | Điều kiện nghiệm thu |
|---|---|---|---|
| 0 — baseline/đặc tả | 3–5 HR/HM có thể tham gia usability, 5–6 nhiệm vụ synthetic, ghi thời gian, lỗi, số lần chuyển trang; xác nhận thứ tự/scope; chụp baseline, không lộ CV thật. | Tài khoản test/đồng ý ghi nhận; chưa có số đo. | Mô tả bối cảnh, sample size, median/range, lỗi, thiết bị; có chủ nghiệp vụ duyệt. |
| 1 — định hướng + ranking rõ | Nút “Ứng viên” hiển thị bền vững, 2 chế độ Xếp hạng/Cần rà soát, empty/error/stale, deep link, đúng quyền. | Chốt nhãn/default, contract hiện có; metadata freshness nếu muốn hiển thị cần API bổ sung. | Rank `[2,1,null]` hiển thị `[1,2,null]` trong Xếp hạng; queue review khác rank được gắn nhãn; lọc không đổi rank; mới/cũ/thiếu dữ liệu không bị khẳng định quá mức; mobile/a11y/role tests. |
| 2 — trang tạo & JD ngôn ngữ | Trang riêng dán JD, chọn ngôn ngữ ngay đầu, chọn hạn, lưu một lần, điều hướng tiếp. Giữ transaction và API cũ backward compatible. | Backend schema `PositionCreate`, language mặc định, cho phép deadline khi tạo cần contract; RBAC. | Tạo vi/en đúng language ngay version 1, mã do server cấp, double-click/retry không tạo trùng theo contract mới, lỗi giữ form, không tự publish ngoài quy tắc. API client cũ vẫn hoạt động. |
| 3 — import JD | Upload TXT/DOCX + adapter hai trang, preview/edit, fallback; `.doc` nằm ngoài vòng này. | Quét AV, parser/limits, network allowlist/SSRF, quyền trang. | Fixture + integration: đúng JD và Requirements, loại form/job liên quan, không silent lấy toàn trang, timeout/blocked fallback, test file valid/invalid/mã hóa/scanner down/ZIP bomb và từ chối `.doc` rõ ràng. |
| 4 — duyệt HR/HM tại chỗ | Xem JD/criteria cùng nơi, CTA theo quyền, thẻ “ai đang chờ”, stale/version/conflict, deep link. | Workspace/criteria APIs, kiểm thử 2 người và direct-approve. | HM thấy đúng phiên bản; HR→HM tách người; direct đúng role; concurrent thay JD/duyệt trả 409; không tự duyệt, audit còn nguyên. |
| 5 — applicant & shortlist workspace | Cải thiện xem chi tiết, quay lại đúng danh sách, luồng HM, scorecard, DOCX fallback; định nghĩa tìm kiếm/pagination server-side nếu dữ liệu lớn. | API share/scorecard/access, contract và scope dữ liệu. | HM chỉ thấy hồ sơ đã share; deny/revoke/retention xử lý tức thời ở backend; HR notes ẩn; filter/search/prev-next, lỗi/partial-load và bàn phím đều qua test. |
| 6 — đo lại & pilot synthetic | Chạy lại các bài baseline, so sánh định lượng, sửa các vướng; triển khai test từng phần sau review. | Các đợt hoàn tất, môi trường test và người dùng. | Có kết quả và lỗi thực tế, không coi CI/mock là nghiệm thu; không bật thật hay dùng dữ liệu thật trước các gate riêng. |

Thứ tự 1→2→3 có thể điều chỉnh sau baseline; import JD không nên trì hoãn việc sửa nhầm lẫn xếp hạng. Đợt 4/5 không phụ thuộc adapter thành công; `.doc` không thuộc vòng đầu. Các mục global search toàn hệ thống, PDF text highlight, bulk trạng thái, tự động gửi/duyệt, ranking engine mới nằm ngoài MVP; đề xuất lại sau khi đo.

## 7. Kế hoạch đo hiệu quả – có baseline trước khi cam kết

**Nhiệm vụ HR:** (1) tạo 1 vị trí từ JD; (2) xem JD cạnh criteria và gửi duyệt; (3) tìm danh sách ứng viên của vị trí và chọn thứ hạng 1; (4) tìm hồ sơ cần kiểm tra và xem chứng cứ; (5) tạo/chia sẻ shortlist. **Nhiệm vụ HM:** (6) mở việc cần duyệt, so JD/criteria và phản hồi; (7) mở shortlist đã share, xem CV được phép và gửi scorecard.

- Đo theo người/thiết bị: completion rate, thời gian từ bắt đầu đến hoàn tất, số chuyển trang/mở dialog, quay lại do lạc, lỗi nhầm rank/priority, sai lệch quyền, mức dễ dùng 1–5, câu hỏi cần trợ giúp. Ghi thêm thời gian chờ model/network riêng để không quy hết cho UX. Dùng 5 JD/30 CV giả nhưng đảm bảo test có trạng thái phân bổ sẵn.
- Baseline trước → prototype/mock → sau trên cùng bộ task/dữ liệu; sample nhỏ 3–5 là gợi ý định tính, không đủ khẳng định thống kê. **Mục tiêu đề xuất** sau khi đo baseline: 100% người thử tìm đúng “Xếp hạng” vs “Cần rà soát”; giảm ít nhất 30% thời gian trung vị cho tạo vị trí và tìm/xem ứng viên, không tăng lỗi hay bước duyệt; điều chỉnh mục tiêu cùng HR/HM. Đây không phải kết quả đã đạt.
- Thu thập dữ liệu tối thiểu; không log CV, JD nhạy cảm, email, token hay nội dung feedback; đo thử synthetic trước và được đồng ý. Phân biệt lỗi app thật với lỗi cơ sở hạ tầng.

## 8. Test và contract cần bao phủ

- **Frontend unit:** sort rank/nulls/tie, review priority, filter + search + URL state, queue counts/pagination, mobile; vị trí vi/en, import source switching, text không mất khi lỗi, thay thế phải xác nhận; trạng thái loading/error/empty/stale, i18n VI/EN và keyboard/focus.
- **Backend:** tạo position atomic và backward compatibility; JD `vi/en`, deadline/timezone, mã concurrency, duplicate POST/idempotency, invalid JD/version conflict, quyền HR/HM; URL allowlist/SSRF từng hop/DNS pin, response-size/time, content-type/parse boundary/XSS; file thật TXT/DOCX, từ chối `.doc`, macro/zip bomb/scanner down, cleanup.
- **Integration với PostgreSQL/Storage giả lập/DB test riêng:** JD version → criteria → HR/HM/direct approve, application/assessment/rank stale, processing failure, race/retry; consent, retention, Gmail và audit không bị ảnh hưởng; không chạy script xóa dữ liệu remote. Test backend xác nhận quyền, UI không phải security boundary.
- **Browser mock:** HR/HM tạo/duyệt, ranking modes, shortlist, deep links, giữ ngữ cảnh, keyboard và mobile; không tuyên bố mock chứng minh AI/Storage/Gmail. **VPS synthetic sau deploy có kiểm soát:** egress trang mẫu, scanner, worker/Storage, OAuth test sau khi sẵn sàng và 2–3 CV trước khi nhập đủ 30; không kết luận production từ test này.
- **An toàn thay đổi:** feature flag cho luồng import/new UI nếu cần, giữ route/API cũ, release note, kiểm thử API cũ, drain trước restart, không đổi backend ranking algorithm hoặc ngưỡng; rollback UI riêng và forward-fix schema khi có migration. Nếu schema cần migration, review và áp từng cái riêng, không chạy `supabase db push` cả chuỗi.

## 9. Quyết định nghiệp vụ

**Đã xác nhận:** HR chọn một trong ba cách nhập; phải có JD mới tạo vị trí. Vòng đầu upload `.docx`/`.txt`, chưa hỗ trợ `.doc`.

**Các điểm còn cần xác nhận khi thiết kế chi tiết:**

1. **Thứ tự mặc định:** đề xuất tab Xếp hạng theo rank; tab Cần rà soát theo lỗi/thiếu bằng chứng. HR muốn tab nào mở đầu khi vào từ workspace? Deep link tác vụ vẫn mở đúng tab.
2. **Công khai Careers:** giữ quyết định hiện hành `OPEN` + hạn, bất kể rubric. HR có muốn bổ sung bước xác nhận hiển thị riêng trong form? Không thay đổi quy tắc listing nếu chưa quyết định.
3. **HM phản hồi:** màn tập trung trong route shortlist hiện có hay route con mới? Đề xuất giữ link hiện có và thêm route/anchor tương thích nếu cần, không mở rộng quyền HM.
4. **Nguồn JD trang mẫu:** anh xác nhận được phép đưa nội dung vào hệ thống và có thể test kết nối từ VPS/staging; nguồn có thể chứa hướng dẫn ứng tuyển không phù hợp để công khai lại, HR cần review.

## 10. Bản đồ mã nguồn để thực hiện

- Tạo vị trí, modal: `frontend/src/app/positions/page.tsx`; schema/transaction/JD ngôn ngữ: `backend/app/schemas/positions.py`, `backend/app/api/positions.py`.
- Vị trí, JD, criteria, modal edit/approval: `frontend/src/app/positions/[id]/page.tsx`; `frontend/src/components/positions/ApplyRubric.tsx`; `backend/app/api/criteria.py`, `rubric_library.py`.
- Work queue/next action: `frontend/src/app/dashboard/page.tsx`, `frontend/src/components/workflow/*`, `backend/app/services/workspace.py`, `backend/app/api/dashboard.py`.
- Sắp xếp/filters/list: `frontend/src/lib/applicantReview.ts`, `frontend/src/app/positions/[id]/applicants/page.tsx`, `backend/app/api/assessments.py`, `backend/app/services/matching.py`.
- Ứng viên/CV/evidence: `frontend/src/app/positions/[id]/applicants/[applicantId]/page.tsx`, `frontend/src/components/candidates/*`, `backend/app/api/applications.py`, `candidate_details.py`.
- HM/scorecard/share: `frontend/src/app/shortlist/page.tsx`, `frontend/src/components/shortlist/*`, `backend/app/api/shortlist.py` và kiểm thử quyền, retention.
- File adapter/AV: `backend/app/services/document_processor.py`, `malware_scan.py`; chưa có JD import adapter. Gmail/Pool/Careers: tài liệu riêng `VPS_THU_NGHIEM_RUT_GON.md`, `PUBLIC_CAREERS_TALENT_POOL_EMAIL_PLAN.md`.
- Existing unit/E2E: `frontend/tests/workspace-ui.test.cjs`, `synthetic-ui.e2e.cjs`, `intake-ui.e2e.cjs`; `backend/tests/test_workspace.py`, `test_phase2_workflow.py`, `test_phase1_integration.py`, `test_cv_access_audit.py`.

### Kết quả kiểm tra khi lập plan

Chạy `npm run test:unit` tại frontend: **8/8 pass**, bao gồm test xác nhận review priority đặt lỗi file trước thứ hạng. Đây là kiểm thử code hiện tại, không đo usability và không chứng minh behavior VPS hay import JD; chưa có test adapter vì chưa triển khai.

## 11. Trạng thái triển khai trong workspace (chưa deploy)

- **Đã làm:** trang `/positions/new`, bắt buộc JD; dán, tải TXT UTF-8/DOCX hoặc nhập link VinUni Talent theo allowlist; preview sửa được; chọn vi/en từ version đầu, hạn ứng tuyển và cảnh báo Careers. File được quét ClamAV fail-closed; link không theo redirect, hạn chế địa chỉ public và kích thước. Form chặn submit khi kết quả mạng không rõ và hướng dẫn kiểm tra danh sách trước khi thử lại.
- **Đã làm một phần workflow:** JD mới nhất cạnh tiêu chí; danh sách mặc định xếp theo rank thực, có chế độ ưu tiên rà soát và lọc shortlist; các card điều hướng theo ngữ cảnh và phạm vi. Inbox chia sẻ có thể lọc theo vị trí, từ scorecard có thể mở hồ sơ. Chia sẻ/duyệt/consent/RBAC và engine không được bỏ qua; frontend filter không phải hàng rào bảo mật.
- **Kiểm thử tại workspace:** backend unit không có DB **262 pass, 165 skip**, test JD có mô phỏng SQL/scanner/mạng, không kiểm chứng PostgreSQL transaction. Frontend type-check/lint/build, unit **10/10**, i18n **3/3**; browser mock tạo vị trí/tài khoản và lọc shortlist desktop/mobile đều pass, mọi `/v1` bị chặn/mock. Không dùng cụm PostgreSQL/VPS có sẵn. Chưa có kết quả usability/baseline, kiểm thử end-to-end hai vai trò trên DB thật, Storage/ClamAV/VPS hay URL thật từ VPS.
- **Còn việc trước khi coi là hoàn thành:** kiểm thử PostgreSQL disposable với migrations, atomic rollback và vi/en/deadline, race/duplicate request; test duyệt HR/HM, share/revoke/retention và trạng thái stale trên môi trường synthetic thật. Import URL chưa xác minh HTML thực tế trên VPS; DNS và HTTP headers chưa có deadline tổng được bảo đảm, bộ lọc link phụ thuộc HTML nguồn, do đó cần gia cố/giới hạn ở môi trường và kiểm thử trước mở dùng rộng; khi thất bại dán JD thủ công. Chưa có idempotency server-side cho POST tạo vị trí, chưa chặn mọi đường điều hướng nội bộ làm mất form. Chưa chứng minh accessibility/keyboard toàn luồng hay xử lý danh sách lớn. Inbox HM vẫn dựa trên trang/dialog hiện có, chưa hoàn tất toàn bộ workspace và quy trình nghiệm thu đợt 4–6 trong plan.
- Không có migration mới cho lát cắt này; deadline dựa trên cột Careers đã tồn tại sau migration 00027. Chưa commit/push/deploy hay khởi động lại VPS. Các hướng dẫn demo cũ về tạo version vi tiếp theo vẫn áp dụng cho VPS **trước** khi phiên bản mới được triển khai và kiểm thử.

## 12. Tiếp tục thực hiện: workspace shortlist và PostgreSQL disposable

- Thay dialog chi tiết shortlist bằng `/shortlist/[share_id]`: danh sách ứng viên được chia sẻ, chọn ứng viên và scorecard tương ứng; nháp scorecard giữ trong bộ nhớ khi đổi ứng viên, phân biệt quyền CV, trạng thái share, feedback chung và liên kết hồ sơ. Nhắc khi rời trang qua các link chính nếu còn nháp/chưa gửi. Đường dẫn cũ `/shortlist?share=...` chuyển sang workspace; từ hồ sơ có thể quay lại đúng share. JD hiện tại chỉ là link tới phiên bản hiện tại; UI nêu rõ có thể khác snapshot scorecard.
- Mọi đọc/ghi vẫn qua API share/scorecard hiện có và kiểm tra quyền tại backend. Khi API báo 403/404, workspace xóa dữ liệu đang hiển thị; khi quay lại tab, trang kiểm tra lại share. Đây **không phải** cơ chế thông báo revoke tức thời khi tab vẫn mở, không thay thế kiểm tra quyền cho từng request; không thể thu hồi nội dung đã được xem/tải trước đó.
- API preview URL trả 504 sau 20 giây nếu request chưa xong. Worker có thể còn kẹt trong DNS/headers sau khi phản hồi; slot bị giữ đến khi worker kết thúc, tối đa hai fetch đồng thời mỗi process. Đây là giới hạn thời gian *phản hồi*, không phải hủy cưỡng bức hay deadline tổng của worker; nếu nguồn lỗi, HR dán thủ công.
- Chạy **431/431 backend tests** tuần tự trên PostgreSQL 16 mới trong thư mục socket riêng dùng một lần; các migration 00001–00031 được áp **chỉ lên cụm test này**, không áp Supabase. Auth được stub; bộ pgserver đang có extension `uuid-ossp` và `pgcrypto` dạng stub, test bổ sung shim `digest(text,'sha256')` dùng SHA-256 sẵn trong PostgreSQL. Do đó đây là kiểm thử SQL/API cục bộ, **không** chứng minh Auth/pgcrypto thật của Supabase. Kiểm tra thêm JD v1 vi/en, deadline múi giờ, client cũ, rollback sau lỗi insert HM và bốn create đồng thời cấp mã không trùng. Bộ test cũng bao gồm các test backend hiện hữu cho HR/HM, approval/share/scorecard/revoke/retention; bên ngoài DB vẫn có mock.
- Frontend type-check/lint/build, unit 10/10, i18n 3/3; browser mock tạo vị trí, tài khoản, lọc shortlist và workspace HM trên desktop/mobile pass (giữ nháp khi đổi ứng viên, link cũ, thu hồi khi kiểm tra lại). Browser test chặn tất cả `/v1`, không chứng minh API thật hay usability người dùng.
- **Còn trước nghiệm thu/deploy:** chưa kiểm thử browser + backend + Supabase/Storage thật, ClamAV hay nguồn link thực từ VPS; chưa có idempotency POST vị trí, chưa bảo vệ tất cả điều hướng nội bộ khỏi mất nháp, chưa tích hợp CV/evidence trong cùng panel scorecard, chưa đo usability/a11y toàn luồng. Chưa commit/push/deploy/restart VPS hoặc áp migration remote trong đợt này.

## 13. Tiếp tục đợt 5: chống trùng, bảo toàn nháp, bằng chứng cạnh scorecard

- **Chống tạo trùng:** migration mới `00032_position_create_idempotency.sql` thêm `app_private.position_create_requests` (RLS bật, chỉ `service_role` đọc/ghi, không lưu JD hay nội dung form, chỉ hash SHA-256 của payload). `POST /v1/positions` nhận `request_id` tùy chọn; khóa `pg_advisory_xact_lock` theo cặp (người dùng, mã yêu cầu) giữ tới commit, nên hai lần gửi song song không cấp hai mã vị trí. Lần gửi lại cùng nội dung trả 200 kèm header `Idempotent-Replay: true` và đúng vị trí cũ; cùng mã nhưng nội dung khác trả **409**; vị trí đã bị xóa hoặc người gọi mất quyền trả **410/403**. Không đổi hành vi với client cũ không gửi `request_id`.
- **UI tạo vị trí:** sinh `crypto.randomUUID()` (chỉ khi có secure context), giữ nguyên payload khi kết quả mạng không rõ, khóa fieldset, hiện “Thử lại cùng yêu cầu” và “Kiểm tra danh sách”; thử lại dùng **đúng** mã và nội dung đã lưu, không gửi bản đã sửa. Không có `randomUUID` (ví dụ HTTP không secure context) thì bỏ `request_id` — khi đó không có bảo vệ chống trùng phía server, chỉ còn cảnh báo kiểm tra danh sách.
- **Bảo toàn nháp:** hook dùng chung `useUnsavedChangesGuard` chặn `beforeunload` **và** click link nội bộ (kể cả link trong menu/stepper) khi còn dữ liệu chưa lưu; áp cho form tạo vị trí, dialog tạo phiên bản JD và workspace shortlist (scorecard + phản hồi). Nút Back/Forward của trình duyệt vẫn không chặn được qua App Router; nháp scorecard vẫn chỉ ở bộ nhớ nên tải lại trang là mất.
- **Bằng chứng cạnh scorecard:** workspace `/shortlist/[id]` có khối “CV và bằng chứng đánh giá” ngay dưới scorecard, gọi đúng `GET /applications/{id}` và `GET /applications/{id}/cv-file` nên backend vẫn quyết định `allow_cv_view`, snapshot assessment và ẩn contact/tài liệu với share chỉ tóm tắt. Bấm một trích dẫn nhảy trang PDF trong khung xem; DOCX chỉ tải xuống. Không tự suy ra điểm khi thiếu bằng chứng.
- **URL JD:** thêm ngân sách tổng `FETCH_BUDGET = 15s` cho DNS → TCP → TLS → headers → body (dưới timeout phản hồi 20s). DNS vẫn là lệnh gọi hệ thống không hủy được, nhưng sau khi resolve, mọi pha đều dùng thời gian còn lại và slot được trả trong `finally`; test mới mô phỏng body chậm để xác nhận timeout và trả đủ hai slot. Chưa thử mạng/egress VPS.
- **Kiểm thử:** backend chạy trên cụm PostgreSQL 16 disposable mới (cổng 55492, migrations 00001–00032 áp **chỉ cục bộ**; auth stub, shim `digest` test-only vì bundled pgcrypto là stub): **434 passed** khi chạy trọn bộ. Lần chạy đầu của cả bộ fail `test_superseded_worker_cannot_commit_after_database_connection_loss` (test cũ, timeout/đua tài nguyên); chạy riêng pass, chạy lại cả `test_phase1_integration.py` 90 passed và cả bộ 434 passed — chưa kết luận nguyên nhân, cần theo dõi khi CI. Frontend type-check/lint/build, unit 10/10, i18n 3/3; browser mock desktop/mobile cho tạo vị trí (503 rồi thử lại dùng cùng `request_id`), tài khoản, workspace shortlist (cổng quyền CV, giữ nháp, deep link, revoke khi tab hiển thị) và lọc shortlist đều pass.
- **Còn lại:** chưa kiểm thử thật với Supabase/Storage/ClamAV/egress VPS, chưa áp migration 00032 lên remote, chưa có browser E2E với backend thật, chưa đo usability/a11y và danh sách lớn, chưa bảo vệ Back/Forward hay lưu nháp scorecard phía server. Chưa commit/push/deploy trong đợt này.

## 14. Đợt 6: danh sách lớn, trạng thái cũ, migration 00032 trên Supabase

- **Migration 00032 đã áp lên Supabase `myrymlqdbyqmpynesiwk`** qua cổng migration (tên `position_create_idempotency_00032`). Kiểm tra sau áp: bảng `app_private.position_create_requests` tồn tại, 0 policy (RLS bật, không policy nên chỉ vai trò đặc quyền dùng được), `service_role` có INSERT, `authenticated` **không** có SELECT. Snapshot sau áp: 0 biên nhận, 6 vị trí, 0 vị trí OPEN còn hạn, 0 share ACTIVE, 0 scorecard. Không có dữ liệu sản phẩm nào bị sửa; chưa gọi API tạo vị trí trên Supabase.
- **Danh sách lớn:** trang xếp hạng tải ứng viên theo trang qua `listAllApplications` (dừng khi gặp trang ngắn, báo tiến độ `{n} hồ sơ`, chặn vòng lặp vô hạn ở 100 trang) và chỉ mount **50 dòng đầu**, nút “Hiện thêm 50 hồ sơ” mở rộng theo bước 50 qua helper `windowApplicantItems`. Đổi hàng đợi/bộ lọc/tìm kiếm đưa cửa sổ về 50. Cửa sổ chỉ ảnh hưởng hiển thị: thứ hạng, bộ lọc và tập chọn chia sẻ vẫn tính trên toàn bộ danh sách; ô “chọn tất cả” vẫn dùng toàn bộ danh sách đã lọc.
- **Trạng thái cũ/xung đột:** workspace share chỉ refetch khi tab đã ẩn ≥30 giây (tránh gọi API mỗi lần liếc sang tab khác), hiện banner “Dữ liệu có thể đã cũ…” với nút tải lại; 403/404 vẫn xóa dữ liệu ngay. Lỗi 409 của scorecard (revision/share đã đổi) hiển thị nguyên văn từ server, người dùng phải tải lại trước khi ghi tiếp; không tự ghi đè.
- **Nháp:** đóng dialog JD bằng nút Hủy hoặc backdrop cũng hỏi xác nhận nếu nội dung đã đổi, không chỉ khi rời trang. Back/Forward vẫn chưa chặn được.
- **Accessibility:** danh sách ứng viên được chia sẻ có nhãn phụ (nhóm matching + % scorecard đã quyết), vùng `aria-live` thông báo khi đổi ứng viên, trạng thái tải có `role="status"`; ô chọn ứng viên vẫn là button có `aria-pressed`. Đã kiểm tra bằng bàn phím ở mức cơ bản (focus/Tab trên bảng), **chưa** audit screen reader đầy đủ.
- **Kiểm thử:** thêm `frontend/tests/applicants-large-list-mock.e2e.cjs` (123 hồ sơ: tải 2 trang, 50 → 100 → 123 dòng, không đổi thứ hạng, đổi hàng đợi reset cửa sổ) và unit test `windowApplicantItems`; tổng unit **11/11**, i18n 3/3, type-check/lint/build pass; 5 bộ browser mock desktop/mobile pass. Backend unit không DB: **264 passed, 170 skipped**; ruff `--select F` các file mới pass. Kết quả 434 pass trên PostgreSQL disposable của đợt 5 vẫn là tham chiếu gần nhất cho DB, không chạy lại ở đợt này.
- **Chưa làm:** chưa chạy backend/browser E2E với Supabase + Storage + ClamAV thật, chưa thử URL JD từ VPS, chưa đo usability với HR/HM, chưa audit accessibility đầy đủ, chưa chặn Back/Forward, chưa lưu nháp scorecard phía server. Chưa commit/push/deploy hay restart VPS.

## 15. Đợt 7: chốt mã nguồn, CI và trạng thái triển khai

- **Đã commit và push** lên nhánh `arena/ea6e2570-vinit-hrapp` thành các commit theo nhóm: `de655ed` (backend replay-safe create + ngân sách URL), `a158e90` (UX tạo vị trí, workspace HM, danh sách lớn), `170b492` (tài liệu trạng thái), `aff5c86` (script test), `7f7f2d7` + `94fad03` (bộ demo 5 JD/30 CV). Không dùng force-push, không đổi nhánh.
- **CI GitHub Actions run `44441175204`: success** cả ba job — Backend unit tests, Frontend checks (i18n, type-check, lint, build) và **Backend integration trên PostgreSQL 17 + pgvector disposable**, job này áp **toàn bộ 32 migration** trong `supabase/migrations/` gồm `00032_position_create_idempotency.sql` rồi chạy `pytest backend/tests` với `TEST_DATABASE_URL`. Đây là lần đầu migration 00032 được kiểm chứng trên PostgreSQL thật có pgvector, nhưng vẫn là DB dùng một lần, không phải Supabase/VPS. Số test trong log không đọc được qua cổng hiện tại (tải log bị chặn egress); kết quả cục bộ tương ứng là 434 passed.
- **Supabase `myrymlqdbyqmpynesiwk`:** migration 00032 đã áp (tên `position_create_idempotency_00032`); bảng `app_private.position_create_requests` tồn tại, RLS bật với 0 policy, `service_role` có INSERT, `authenticated` không có SELECT/INSERT và cũng không có grant nào trên 7 bảng nhạy cảm được kiểm tra. Dữ liệu sản phẩm không đổi: 6 vị trí, 0 OPEN còn hạn, 0 share ACTIVE, 0 scorecard, 0 biên nhận.
- **Chưa triển khai VPS:** phiên này không có SSH tới máy chủ, nên code mới **chưa** lên HRA đang chạy; VPS vẫn là bản `a218217`. Người vận hành cần pull `94fad03`, chạy migration (đã áp sẵn trên Supabase nên chỉ cần pull code), build lại frontend/backend và kiểm tra readiness.
- **Còn lại trước khi coi là nghiệm thu:** E2E hai vai trò HR/HM trên VPS với Supabase Auth/Storage/ClamAV thật, thử URL JD thật từ VPS, usability và audit accessibility đầy đủ, danh sách rất lớn trên dữ liệu thật, chặn Back/Forward, lưu nháp scorecard phía server. Không có mục nào trong số này đã được chứng minh.

## 16. Đợt 8: kiểm tra accessibility bằng bàn phím, sửa lỗi tràn ngang

- **Lỗi tìm thấy và đã sửa:** vùng `aria-live` thông báo ứng viên đang đánh giá dùng `position: absolute` nhưng thiếu `left/top` nên rộng đúng bằng container và bị đẩy sang phải, làm workspace share rộng **1905px** trên màn 1280px. Đã ghim `left/top: 0`, thêm `clipPath: inset(50%)` và padding/border 0; test mới xác nhận không còn tràn ngang ở cả desktop và mobile.
- **Test mới `frontend/tests/a11y-mock.e2e.cjs`** (mock toàn bộ `/v1`, chạy desktop 1280 và mobile 390):
  - mọi phần tử hiển thị và nhận focus trên trang tạo vị trí và workspace share đều có tên dễ đọc (aria-label, aria-labelledby, `<label for>`, label bao ngoài, text hoặc title);
  - chỉ dùng Tab vẫn tới được ô “Tên vị trí”, gõ được, và nút tạo vẫn disabled khi chưa có JD;
  - danh sách ứng viên là button có `aria-pressed` đúng, chọn ứng viên thứ hai bằng phím Enter, mở accordion “CV và bằng chứng đánh giá” bằng Enter;
  - không tràn ngang ở cả hai kích thước.
- Đây là **smoke test**, không phải audit screen reader (NVDA/VoiceOver), không kiểm tra tương phản màu, thứ tự đọc thực tế hay zoom 200%/400%. Chưa kiểm thử với dữ liệu thật.
- **Kết quả sau sửa:** type-check/lint/build pass; **6 bộ browser mock** desktop/mobile pass (a11y, tạo vị trí, danh sách 123 hồ sơ, workspace share, lọc share, tài khoản); unit **11/11**, i18n **3/3**; backend unit không DB **264 passed/170 skipped**. Commit `8ba1160` đã push.
- **Còn lại:** E2E thật trên VPS với Supabase/Storage/ClamAV, thử URL JD từ VPS, usability test với HR/HM, screen reader/contrast/zoom, chặn Back/Forward, lưu nháp scorecard phía server. VPS vẫn chưa cập nhật.
