# KỊCH BẢN DEMO HRA — CAREERS, TALENT POOL VÀ GMAIL

**Phạm vi:** dữ liệu tổng hợp, môi trường test; không phải nghiệm thu production.  
**Thời lượng trình bày đề xuất:** 20–30 phút, sau khi đã chuẩn bị và chạy thử. Thời gian xử lý CV/Gmail phụ thuộc hạ tầng; đây không phải cam kết SLA.  
**Thông điệp:** “Một vị trí được hiển thị theo trạng thái/hạn; ứng viên tự chọn Talent Pool; HR chỉ tìm lại hồ sơ còn đủ điều kiện; Gmail được kiểm tra trước khi nhập.”

## Đọc nhanh — bộ 5 JD / 30 CV

Bộ đã mở rộng thành 5 JD (Backend Python, Tích hợp dữ liệu, Frontend React, QA Automation, DevOps Cloud) và 30 CV giả. Xem **[Bảng phân bổ 30 CV](BANG_PHAN_BO_30_CV.md)** để biết vị trí nguồn, lựa chọn consent dự kiến và các cặp vị trí thử Talent Pool. Kịch bản bên dưới là **demo ngắn** với hai JD và ba CV tiêu biểu; muốn nạp toàn bộ 30 CV, làm tiếp theo bảng phân bổ, thời gian sẽ dài hơn nhiều.

Anh đang truy cập `http://IP:3005`, không thay đổi cấu hình firewall trong bộ này. HTTP công khai không mã hóa mật khẩu, token và dữ liệu; chỉ dùng tài khoản, mailbox và dữ liệu giả, không dùng dữ liệu thật và không xem đây là cấu hình production. Lưu ý kỹ thuật: nút ứng tuyển cần Web Crypto (`crypto.randomUUID`); nhiều trình duyệt không cho phép trên HTTP qua IP, kể cả hồ sơ không opt-in. Nếu gặp thông báo yêu cầu HTTPS, cách đơn giản không đổi cấu hình VPS là chạy trên **máy anh** `ssh -L 13005:127.0.0.1:3005 <tai-khoan-ssh>@<IP-VPS>` rồi mở `http://localhost:13005/careers`. Giữ cửa sổ SSH mở; localhost được trình duyệt coi là secure context. Tunnel này không đóng cổng 3005 công khai. OAuth Desktop có thể cần thêm tunnel callback theo runbook.

## 1. Bộ dữ liệu đã chuẩn bị

| Tệp | Mục đích | Thao tác trong demo |
|---|---|---|
| `01_JD/JD_01_Backend_Python.txt` | JD vị trí nguồn | Tạo vị trí Backend Python demo |
| `01_JD/JD_02_Tich_hop_Du_lieu.txt` | JD vị trí đích | Tạo vị trí Tích hợp dữ liệu demo |
| `02_CV/CV_01_An_Careers_Dong_y.docx` | An có Python, API, SQL và dự án dữ liệu giả | Nộp qua Careers và **chọn** Talent Pool |
| `02_CV/CV_02_Binh_Careers_Khong_dong_y.pdf` | Bình có Python/Flask/SQL, kinh nghiệm khác An | Nộp qua Careers và **không chọn** Talent Pool |
| `02_CV/CV_03_Chi_Gmail.docx` | Chi có Backend Python giả | Gửi qua Gmail thử nghiệm |
| `03_GMAIL/MAU_EMAIL.txt` | Tiêu đề, nội dung thư hợp lệ và thư thiếu tệp | Thay mã vị trí thật do HRA tạo trước khi gửi |

Tất cả tên, tổ chức, kinh nghiệm và email `@example.test` trong tài liệu là **hư cấu**; không có số điện thoại thật. Các kỹ năng chỉ giúp câu chuyện dễ hiểu, không đảm bảo AI chấm điểm/xếp hạng hay kết luận ai phù hợp.

## 2. Điều kiện bắt buộc trước khi demo

### Lưu ý khi demo HTTP công khai

- [ ] Chỉ dùng project Supabase test `myrymlqdbyqmpynesiwk` và dữ liệu giả. Không upload CV thật, tài khoản Gmail cá nhân hoặc dữ liệu ứng viên thật.
- [ ] HRA đang mở Internet qua HTTP: nội dung và thông tin đăng nhập có thể bị lộ trên đường truyền. Khuyến nghị dùng tunnel localhost khi demo; không đưa dữ liệu thật hoặc token vào chat/video. Không coi cấu hình này an toàn cho production; anh lựa chọn không thay firewall trong vòng demo.
- [ ] Trình duyệt cần secure context để tạo mã rút an toàn: dùng `http://localhost` qua SSH tunnel hoặc HTTPS phù hợp; HTTP qua IP/VPN thông thường có thể không hỗ trợ. Xác nhận trên trình duyệt thực tế.
- [ ] HR rà soát **tất cả** vị trí `OPEN` còn hạn và JD mới nhất có thể hiển thị khi bật Careers, không chỉ hai vị trí demo. Với listing đang bật, rubric chưa duyệt không ngăn vị trí xuất hiện, nhưng có thể ngăn nộp. Không công bố JD/nội dung thật ngoài phạm vi test.
- [ ] Có quy trình dừng và hỗ trợ khi mất mã rút; mã hiện chưa có cơ chế tự khôi phục. Không quay/chụp/đưa mã rút hoặc mật khẩu/token thật lên màn hình chia sẻ công khai.

### Hệ thống

- [ ] Bản HRA đã triển khai, DB test có migration 00023, 00027–00031; 00024–00026 là demo-only, không tự chạy. Bản `a218217` đã được operator báo marker deploy, backend ready, frontend/proxy HTTP 200; cần xác nhận lại ngay trước buổi demo. Không dùng `supabase db push`.
- [ ] `clamav-daemon`, socket và `freshclam` hoạt động; backend truy cập được `/run/clamav/clamd.ctl`. Operator đã báo EICAR `INFECTED`, mẫu sạch `CLEAN`, PDF mã hóa bị chặn. Đây chỉ là smoke test, không chứng minh phát hiện mọi mã độc hoặc mọi giới hạn. Cần kiểm tra freshness, lỗi scanner/timeout và chính sách giới hạn trước sử dụng.
- [ ] RAM/CPU ổn định; VPS 3,8 GiB RAM chạy nhiều dịch vụ. Không build/restart các ứng dụng khác hoặc gây tải nặng trong buổi demo.
- [ ] Tài khoản HR Lead/Admin hoạt động; có một Hiring Manager **khác tài khoản HR** để tạo vị trí. HR có quyền với cả vị trí nguồn và đích. Chuẩn bị một đơn vị/phòng ban hoạt động hoặc được phép tạo đơn vị test.
- [ ] Chọn 2 vị trí demo `OPEN`, hạn ở tương lai; rubric của **JD mới nhất** đã `APPROVED` cho cả hai. Cần ít nhất vị trí nguồn được duyệt để nộp, và vị trí đích được duyệt để scan. Đừng tự nhập mã vị trí: lấy mã thực tế trên HRA sau khi tạo.
- [ ] Backend/worker và Storage test được xác minh là cùng cấu hình, có khả năng lưu CV; worker thực sự xử lý CV hoàn tất. Worker có phụ thuộc AI/runtime phù hợp; chưa chứng minh model thật/AI matching. Không giả lập hoặc đổi cấu hình AI trên VPS chỉ để che lỗi.
- [ ] Kiểm tra đủ cờ test và đường dẫn scanner bằng operator theo `../VPS_THU_NGHIEM_RUT_GON.md`. Các cờ mặc định tắt. Chỉ bật sau khi kiểm tra scanner/Storage, hiểu rủi ro HTTP và chuẩn bị dữ liệu giả. `PUBLIC_CAREERS_ENABLED`, `PUBLIC_CAREERS_TEST_INTAKE_ENABLED`, `TALENT_POOL_STORAGE_READY`, `TALENT_POOL_REDISCOVERY_ENABLED` phục vụ hai luồng đầu; `GMAIL_TEST_INGEST_ENABLED`, `GMAIL_TEST_GMAIL_SPAM_ONLY`, `GMAIL_TEST_TOKEN_FILE`, `CLAMAV_UNIX_SOCKET` cho Gmail test. Không đưa file `.env` hay token vào chat/Git.
- [ ] Gmail: hộp riêng chỉ chứa dữ liệu giả, có nhãn `HRA_TEST`; Gmail API + OAuth Desktop và test user được cấu hình; cấp OAuth qua tunnel, token ngoài repo mode 0600. Chưa xác nhận OAuth thật ở thời điểm soạn tài liệu. `gmail.readonly` có thể đọc **toàn bộ mailbox**, không chỉ nhãn test. Chế độ rút gọn dùng nhãn Spam/Trash của Gmail, **không có SpamAssassin độc lập**.
- [ ] Có sẵn phương án tạm dừng nếu hạ tầng lỗi. Không giả vờ pass, không xóa/reset database hoặc tự chạy reconciler `--execute`.

### Bảng điều phối trước khi mở màn hình

| Mục | Người demo điền trên giấy riêng | Đã sẵn sàng? |
|---|---|---|
| URL nội bộ qua tunnel/VPN | `http://localhost:13005` nếu tunnel được cấu hình đúng | ☐ |
| Mã vị trí Backend nguồn do HRA sinh | __________________ | ☐ |
| Mã vị trí Tích hợp đích do HRA sinh | __________________ | ☐ |
| HR Lead/Admin + HM riêng | Đã thử đăng nhập qua kênh an toàn | ☐ |
| JD và rubric hai vị trí | JD mới nhất / rubric APPROVED / OPEN / chưa hết hạn | ☐ |
| Gmail test, OAuth, nhãn | Hộp chỉ dữ liệu giả | ☐ |
| Scanner và Storage | Đã có smoke test; kiểm tra lại trước demo | ☐ |
| Worker xử lý CV giả | Một hồ sơ thử trước đã `COMPLETED` | ☐ |

Không ghi mật khẩu, token OAuth hay mã rút vào bảng này.

## 3. Chuẩn bị dữ liệu trên ứng dụng

1. HR đăng nhập qua kênh riêng an toàn. Trong **Vị trí tuyển dụng**, tạo vị trí nguồn với tên `DEMO — Backend Python` và dán `JD_01_Backend_Python.txt`. Chọn đơn vị hoạt động và HM hoạt động là tài khoản khác HR. Mã vị trí do hệ thống cấp; ghi lại làm **MÃ NGUỒN**.
2. Tạo vị trí đích `DEMO — Tích hợp dữ liệu`, dán `JD_02_Tich_hop_Du_lieu.txt`, chọn đơn vị/HM và ghi **MÃ ĐÍCH**. Hai vị trí phải khác nhau.
3. Giao diện tạo vị trí ghi JD phiên bản đầu là `en`, dù dữ liệu mẫu trong gói là tiếng Việt. Để gắn đúng ngôn ngữ, ở từng vị trí mở tab **Mô tả công việc (JD)** → **Tạo phiên bản JD mới**, chọn **Tiếng Việt**, thêm một câu có nghĩa như “Đây là vị trí demo sử dụng dữ liệu giả.” vào nội dung rồi lưu. Chỉ đổi ngôn ngữ mà không đổi nội dung sẽ bị hệ thống từ chối. Làm bước này **trước** khi tạo/duyệt tiêu chí vì tiêu chí phải gắn JD mới nhất.
4. Tại từng vị trí, chọn **Chỉnh sửa vị trí**, đặt trạng thái `OPEN` và hạn sau buổi demo. HR kiểm tra JD mới nhất. Hạn có thể nhập theo giờ trình duyệt; xác nhận lại múi giờ và thời gian hiển thị.
5. Chuẩn bị tiêu chí: dùng rubric **đã xuất bản** phù hợp qua nút “Dùng rubric đã xuất bản” hoặc tạo tiêu chí theo quy trình hiện có. HR kiểm tra và duyệt; HM phê duyệt theo luồng, hoặc HR Lead/Admin dùng duyệt trực tiếp nếu phù hợp. Sau cùng phải thấy `APPROVED` cho JD mới nhất của **cả hai**. Không cam kết model sẽ tự tạo rubric hoặc điểm số.
6. Cho chạy thử một CV giả ngoài buổi trình bày, kiểm tra trạng thái worker và Storage. Đừng tái sử dụng cùng email giả để ngụ ý kiểm tra trùng theo danh tính: idempotency chỉ đảm bảo retry **cùng yêu cầu và nội dung**. Ghi nhận nguồn và đích cho lần trình bày chính; nếu chạy thử đã tạo An/Bình, tạo lại vị trí demo riêng hoặc đặt tên khác để tránh nhầm, không tự xóa dữ liệu cũ.
7. Sau khi scanner, Storage, worker và OAuth sẵn sàng, operator cấu hình các cờ test theo runbook; lưu ý rủi ro Internet/HTTP nêu trên. Khi Careers được bật, mọi vị trí `OPEN` còn hạn có thể được hiển thị — không chỉ bộ dữ liệu này.

### Gợi ý rubric để HR rà soát (không phải bộ tiêu chí đã duyệt)

| Nhóm | Backend Python | Tích hợp dữ liệu |
|---|---|---|
| Bắt buộc | Python; API REST; SQL; kiểm thử/phối hợp | Python; SQL; chất lượng dữ liệu; API/phối hợp |
| Ưu tiên | FastAPI; PostgreSQL; pytest; Docker | PostgreSQL; pipeline theo lô; retry; kiểm thử |

HR cần cấu hình trọng số phù hợp và hoàn thành quy trình phê duyệt. Các CV được xây dựng có một số bằng chứng liên quan, **không phải kết quả đánh giá đã tính sẵn**.

## 4. Kịch bản trình bày trực tiếp

> Nên dùng một màn hình ứng viên qua tunnel và một màn hình HR. Không chia sẻ thông tin đăng nhập, token OAuth hay mã rút trên livestream.

### Cảnh 1 — Careers: vị trí đang tuyển (3 phút)

**Lời dẫn:** “HR quản lý JD; Careers hiển thị những vị trí đang OPEN và còn hạn.”

1. Trên màn HR, giới thiệu hai vị trí tiêu biểu và trạng thái OPEN, hạn, rubric APPROVED. Nếu đã tạo đủ, có thể giới thiệu cả năm JD.
2. Mở `/careers` qua kết nối riêng. Tìm hai vị trí demo, mở JD. Có thể xuất hiện các vị trí OPEN khác; đây là hành vi hiện tại, không phải màn hình chỉ dành cho demo.
3. Nêu rõ: listing không yêu cầu rubric duyệt để hiển thị; intake thử nghiệm yêu cầu cấu hình phù hợp và rubric JD hiện tại đã duyệt.

**Đạt khi:** hai vị trí demo còn hạn hiển thị, nút ứng tuyển thử nghiệm có thể dùng cho vị trí nguồn. Nếu không thấy nút/vị trí, dừng kiểm tra điều kiện thay vì đổi dữ liệu thật.

### Cảnh 2 — Nộp có và không có consent (5–8 phút)

**Lời dẫn:** “Đồng ý vào Talent Pool là lựa chọn riêng, không phải điều kiện nộp hồ sơ.”

1. Chọn vị trí **nguồn**. Điền tên `Ứng viên giả An`, email `an@example.test`, để trống điện thoại; chọn `CV_01_An_Careers_Dong_y.docx`.
2. Tích chọn Talent Pool thử nghiệm **7 ngày**, sao chép/lưu an toàn mã rút của An ở nơi chỉ người demo biết, rồi nộp. Hiển thị “đã tiếp nhận yêu cầu”; lưu ý chưa đồng nghĩa worker đã hoàn tất.
3. Trên màn HR, chờ tác vụ An hoàn tất rồi mở hồ sơ thử nghiệm để kiểm tra CV. Nếu có lỗi/mất kết nối, giữ nguyên form, tệp và mã rút để thử lại cùng yêu cầu; nội dung thay đổi hoặc yêu cầu mới có thể tạo bản ghi khác.
4. Nộp Bình tại cùng vị trí: tên `Ứng viên giả Bình`, email `binh@example.test`, tệp `CV_02_Binh_Careers_Khong_dong_y.pdf`; **không tích** Talent Pool. Chờ xử lý hoàn tất. Nộp tuần tự để tránh xung đột khi vị trí đang có tác vụ.

**Đạt khi:** có hai hồ sơ giả riêng; An có consent riêng, Bình không có; không suy consent từ việc nộp. Nếu worker chưa COMPLETED thì chưa dùng kết quả đó để kết luận Talent Pool.

### Cảnh 3 — Talent Pool và rút lựa chọn (4–6 phút)

**Lời dẫn:** “HR chỉ thấy hồ sơ đã đồng ý riêng, còn hạn và đủ điều kiện; kết quả không phải xếp hạng.”

1. Mở `/talent-pool`; chọn **nguồn = Backend**, **đích = Tích hợp dữ liệu**; bấm tìm.
2. Xác nhận **An xuất hiện** sau khi CV đã COMPLETED; **Bình không xuất hiện** vì không opt-in. Không khẳng định tổng số bằng 1 nếu còn dữ liệu đủ điều kiện khác ở nguồn.
3. Mở `/pool-withdraw`; nhập mã của An ngoài vùng chia sẻ công khai, bấm gửi. Phản hồi được thiết kế giống nhau cho mã hợp lệ/không hợp lệ; không dùng phản hồi để chứng minh mã đã tồn tại.
4. Quay lại HR, bấm **Tìm hồ sơ đủ điều kiện** lại; An không còn trong kết quả. Rút consent không tự xóa hồ sơ ứng tuyển.

**Đạt khi:** trước khi rút thấy An, sau khi rút/tìm lại không thấy An; Bình không xuất hiện. Kết quả scan chỉ là snapshot — cần kiểm tra lại trước khi sử dụng.

### Cảnh 4 — Gmail: an toàn trước nhập, HR xử lý ngoại lệ (5–8 phút)

**Lời dẫn:** “HR chủ động kiểm tra một hộp Gmail test; email và tệp được quét trước khi bóc tách. Gmail không tự cấp consent Talent Pool.”

1. Trong Gmail riêng, gửi/nhận thư giả theo `03_GMAIL/MAU_EMAIL.txt`: thay placeholder bằng **MÃ NGUỒN thực tế**, tiêu đề bắt đầu `[HRA-TEST] `, đúng một tệp `CV_03_Chi_Gmail.docx`, sau đó gắn nhãn `HRA_TEST`.
2. Đảm bảo vị trí nguồn không còn tác vụ đang chạy. HR Lead/Admin mở `/gmail-test`, bấm **Kiểm tra Gmail**, xem kết quả. Gmail chỉ xử lý tối đa 5 email mỗi trang; nếu cần bấm kiểm tra trang tiếp. `ACCEPTED` là đã tiếp nhận, không đồng nghĩa worker xong.
3. Sau khi worker hoàn tất, mở **Xác nhận thông tin giả**, nhập tên `Ứng viên giả Chi`, email `chi@example.test`, tích xác nhận giả và lưu. Mặc định hồ sơ giữ tên/email giả cố định; không coi dữ liệu người gửi hoặc thông tin HR nhập là xác minh danh tính thật. Không tạo consent Pool từ Gmail.
4. Bấm đồng bộ lại: thư đã ACCEPTED không tự tạo application mới. Gửi một **thư giả mới thiếu tệp** theo mẫu, gắn nhãn rồi kiểm tra; kỳ vọng `Cần HR kiểm tra` / số tệp không hợp lệ. Nút **Thử lại** chỉ phù hợp khi nguyên nhân dịch vụ đã được khắc phục; không sửa nội dung email đã gửi.

**Đạt khi:** thư hợp lệ được nhập một lần; thư thiếu tệp vào REVIEW; không có consent Pool tự phát. Gmail spam/trash có thể không xuất hiện trong danh sách. Nếu OAuth/scanner/Storage lỗi, dừng và báo chưa nghiệm thu; không tắt ClamAV hay tạo bản ghi giả để trình bày thay.

### Kết thúc (1 phút)

**Lời dẫn:** “Đây là vòng test dữ liệu giả. Cần nghiệm thu vận hành, chính sách consent/retention, chống abuse và bảo vệ truy cập trước khi dùng thật.”

Điền bảng kết quả:

| Kiểm tra | Kết quả thực tế | Ghi chú / thời điểm |
|---|---|---|
| Careers: 2 vị trí còn hạn | PASS / FAIL / CHƯA CHẠY | |
| An nộp + opt-in; Bình không opt-in | PASS / FAIL / CHƯA CHẠY | |
| Scan trước/sau withdrawal | PASS / FAIL / CHƯA CHẠY | |
| Gmail ACCEPTED + không trùng + REVIEW | PASS / FAIL / CHƯA CHẠY | |
| ClamAV/Storage/worker/OAuth thực tế | PASS / FAIL / CHƯA CHẠY | Ghi nhận riêng từng dịch vụ |

## 5. Xử lý tình huống và giới hạn

- **Không thấy việc làm:** kiểm tra cờ listing, OPEN, deadline, trang tiếp và quyền truy cập kênh test. HR phải xem mọi JD có thể xuất hiện.
- **Nút nộp bị khóa:** cờ intake, đường dẫn ClamAV và rubric APPROVED cho JD mới nhất. Nút khả dụng chưa chứng minh scanner đang hoạt động; backend vẫn quét khi nộp.
- **CV bị từ chối/scanner không sẵn sàng:** xác minh socket, signature, EICAR và PDF mã hóa bằng runbook; không bypass scanner. Nếu CV bị chặn, ghi kết quả FAIL và kiểm tra trước buổi demo khác.
- **Không thấy An trong pool:** kiểm tra opt-in, worker CV COMPLETED, nguồn/đích khác nhau, hạn consent/retention, quyền HR, trạng thái vị trí và retention case. Đừng nhập consent trực tiếp vào DB.
- **Không rút được/không nhớ mã:** phản hồi không tiết lộ tính hợp lệ; chưa có khôi phục tự động. Chỉ trình diễn bằng mã đã lưu an toàn.
- **Gmail không ra ACCEPTED:** kiểm tra OAuth/test user/nhãn/subject, mã vị trí do hệ thống sinh, file và trang tiếp; HR review lý do. Không có daemon SpamAssassin trong chế độ rút gọn; Gmail label không bảo đảm thư an toàn.
- **Model/worker lỗi hoặc lâu:** dừng phần phụ thuộc kết quả xử lý; ghi FAIL/CHƯA CHẠY. Không coi test cục bộ hay giao diện mô phỏng là thành công trên VPS; không hứa có điểm/xếp hạng AI.
- **Sau demo:** tắt ingestion/listing/rediscovery theo quy trình vận hành nếu không tiếp tục test. Nếu đã cấp mã rút, phải giữ `TALENT_POOL_STORAGE_READY` và đường rút khả dụng theo thiết kế; thống nhất với operator trước khi đóng mạng. Không tự xóa dữ liệu, object Storage, token hay chạy tác vụ retention khi chưa được phê duyệt.
