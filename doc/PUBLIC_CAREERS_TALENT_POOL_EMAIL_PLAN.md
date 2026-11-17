# Ưu tiên mới — Cổng ứng viên, Talent Pool và Gmail demo

## Trạng thái và phạm vi

Người dùng yêu cầu tạm treo các việc hiện tại để ưu tiên: (1) trang công khai việc làm còn hạn và đang hoạt động, form ứng tuyển và tải CV vào hệ thống; (2) một phần F3.01 Talent Pool/Rediscovery; (3) một phần F3.03 Email Gateway, demo với một Gmail thử nghiệm. Đây là **ưu tiên triển khai mới**, không phải xác nhận các gate Phase 1/2 đã hoàn tất hay chấp thuận xử lý dữ liệu thật. Đã có lát cắt demo bằng dữ liệu tổng hợp trong code như mục 4; chưa deploy hoặc nghiệm thu. Không dùng demo cho dữ liệu thật.

Chi tiết bên dưới là đề xuất kỹ thuật ban đầu, không tự coi là chính sách được duyệt. Người dùng chọn hiển thị mọi vị trí OPEN còn hạn (HR cần bảo đảm JD phù hợp công khai), thiết kế opt-in riêng và demo email offline trước. Nội dung consent, thời hạn, quyền và xử lý dữ liệu thật vẫn cần HR/Privacy/Legal xác nhận.

## Khảo sát code hiện tại

- `positions.status` có `OPEN`, `PAUSED`, `CLOSED`; chưa có hạn ứng tuyển hoặc cờ công khai. JD phiên bản hiện là nội dung nội bộ, không thể mặc nhiên công khai chỉ vì `OPEN`. `AppLayout` hiện yêu cầu đăng nhập với các route nghiệp vụ.
- Batch upload hiện chỉ HR có quyền trên vị trí được gọi; yêu cầu vị trí `OPEN`, criteria `APPROVED` cho JD mới nhất, không có operation xử lý xung đột; tạo batch, application, document và operation để worker xử lý. `applications.created_by`, `cv_batches.uploaded_by`, `operations.requested_by` ràng buộc user; không thể giả mạo HR khi ứng viên/email nộp.
- Worker hiện cập nhật `application_identities` từ thông tin trích xuất, có thể ghi đè dữ liệu form nếu nối trực tiếp mà không thiết kế provenance/ưu tiên. Storage và DB không chung transaction; hiện upload có best-effort cleanup. Cần xử lý lỗi và đối soát file mồ côi.
- Chưa có Candidate/Talent Pool dùng chung; tìm kiếm vector hiện chỉ trong CV của cùng application. Retention hiện hành và xóa/cascade phải được bảo toàn. Gmail hay consent từ ứng viên không tự tạo quyền tái sử dụng xuyên vị trí.
- F3.03 trong roadmap yêu cầu lọc spam và quét mã độc trước bóc tách tệp; validate MIME/đuôi/size không thay thế antivirus. Môi trường sandbox không chứng minh Gmail, Storage, antivirus hay cấu hình production.

## 1. Cổng ứng viên — thiết kế đề xuất

1. HR được phân quyền chủ động xuất bản và đặt hạn cho từng vị trí. Đề xuất mặc định không công khai, hạn bắt buộc; chỉ trả về trường được phép công bố, không tự phơi JD nội bộ. Hạn dùng timestamp rõ múi giờ; phải thống nhất quy ước ngày hết hạn với HR. Danh sách và endpoint nộp phải cùng kiểm tra trạng thái và hạn trên server; kiểm tra lại trong transaction khi nhận hồ sơ để tránh nộp vào vị trí vừa đóng/hết hạn.
2. Trang public độc lập khỏi shell đăng nhập HR: danh sách, chi tiết đã duyệt, form họ tên/email/điện thoại tùy chính sách, CV PDF/DOCX theo giới hạn hiện hành, thông báo xử lý dữ liệu và xác nhận phù hợp. Không suy ra consent Talent Pool từ việc nộp đơn: đó là lựa chọn riêng, không bắt buộc để ứng tuyển.
3. Xây đường tiếp nhận thống nhất, nguồn `CAREERS` và actor loại hệ thống/candidate có provenance đúng, không mạo danh HR. Làm rõ cơ chế xác thực actor, sửa schema/worker có kiểm thử; form metadata không bị worker ghi đè âm thầm. Đơn được HR nhìn thấy trong đúng vị trí và đi vào hàng đợi sau các kiểm tra cần thiết. Nếu rubric chưa được duyệt, cần quyết định tiếp nhận vào hàng chờ hay chưa cho nộp; không bí mật bỏ qua điều kiện duyệt hiện hữu.
4. Bảo vệ endpoint không đăng nhập: giới hạn request/upload ở reverse proxy trước khi body được buffer, rate limiting thực sự hoạt động đa instance, chống spam/bot, xác thực loại file/nội dung/kích thước, quét malware cách ly và fail-closed khi dịch vụ quét không sẵn sàng; không lộ CV, PII, stack trace hoặc ID nội bộ quá mức, không log nội dung và không cache dữ liệu cá nhân. Cần cơ chế chống gửi trùng/idempotency và dọn rác có đối soát.
5. Kiểm thử synthetic danh sách OPEN/công khai/còn hạn, trạng thái biên và đồng thời đóng, route ẩn, upload không hợp lệ/quá lớn/malware, rate limit, rollback/storage lỗi, duplicate/retry, provenance/worker, truy cập HR/HM và retention. Browser E2E + security/privacy review cần riêng trước khi mở Internet.

## 2. F3.01 — Talent Pool và rediscovery

- Roadmap yêu cầu consent **độc lập**, có bằng chứng, hết hạn và quyền rút lại; chỉ quét hồ sơ có quyền tái sử dụng và còn hạn hợp pháp, không quét hồ sơ hết retention đang chờ xóa. Cần HR/Privacy/Legal quyết định mục đích, thời hạn, nội dung thông báo, phạm vi truy cập, cơ sở xử lý, quy trình xóa và contact để thực hiện quyền ứng viên. 24 tháng trong roadmap chỉ là ví dụ, không mặc định áp dụng.
- Không nhập toàn bộ hồ sơ cũ, không suy đoán consent từ gửi CV/email, không gia hạn retention tự động. Trạng thái opt-in/out cần gắn chính xác hồ sơ, version notice, thời điểm, phạm vi, expiry và lịch sử; rút consent phải ngăn quét ngay và xử lý dữ liệu phát sinh theo policy được duyệt. Tránh leak dữ liệu giữa vị trí: chỉ người có quyền theo chính sách được duyệt, audit truy cập/scan không chứa PII.
- Đề xuất chia bước: (a) mô hình/policy và dữ liệu synthetic; (b) cơ chế ghi nhận & rút consent thực sự có thể dùng, đối soát retention; (c) HR quét pool đủ điều kiện theo rubric đã duyệt, hiển thị bằng chứng và độ không chắc chắn, không tự loại/ứng tuyển hay liên hệ. Chỉ khi guardrails hoạt động mới mở dữ liệu thật. Thiếu consent policy thì phần rediscovery chỉ thử với fixture tổng hợp, fail-closed với hồ sơ thật.
- Test quyền xuyên vị trí, consent chưa có/hết hạn/rút, hồ sơ chờ xóa hoặc đang purge, race withdrawal-vs-scan, truy xuất/tài liệu sau revoke, status và toàn bộ hậu quả retention. Gắn với các gate vận hành/xóa còn mở, không coi logic kiểm tra consent đơn lẻ là đủ.

## 3. F3.03 — Gmail demo

- Gmail thử nghiệm riêng, chỉ CV và email tổng hợp; không dùng hộp thư chính thức/dữ liệu thật trong demo. Xác thực OAuth an toàn qua cấu hình phía server, quyền tối thiểu, không đưa mật khẩu/token vào chat, Git, log hoặc trình duyệt; kiểm tra phạm vi Google OAuth và khả năng vận hành thực tế khi có tài khoản được cấp quyền. Chưa kết nối Gmail, chưa có credentials.
- Quy tắc đề xuất: phân tích mã vị trí chính xác trong tiêu đề; chỉ vị trí đủ điều kiện nhận; thư sai mã/nhiều mã/không có CV/nhiều tệp hoặc spam đi hàng HR review, không tự gán nhầm. Không tin địa chỉ From là danh tính đã xác minh. Email tự nó không phải consent Talent Pool.
- Thiết kế polling hoặc gateway có UID/message-id và mailbox identity bền vững; xử lý idempotent từng attachment, chống trùng/retry khi crash, phân biệt thành công với chờ review, không đánh dấu/di chuyển/xóa thư khi chưa commit; ngăn hai worker xử lý cùng thư. Giới hạn số lượng/kích thước, quét malware fail-closed trước parsing, không fetch link ngoài trong email, không log body/CV/tokens. Có test lỗi Gmail, rate limit, dữ liệu MIME độc hại, retry/đồng thời, sai mã, hết hạn và lưu trữ lỗi.
- Tái sử dụng đường intake có kiểm soát như cổng ứng viên, giữ nguồn EMAIL và audit/provenance, không tự tạo user HR. Gmail demo chỉ được chạy sau khi có mailbox thử nghiệm, môi trường và chấp thuận thao tác phù hợp; không tự thay đổi dữ liệu Supabase hay nội dung hộp thư.

## Các bước tiếp theo và gate

1. Chốt câu hỏi về hiển thị công khai/nhận hồ sơ khi chưa duyệt rubric, phạm vi demo và policy Talent Pool; ghi nhận ai phê duyệt trước khi dùng dữ liệu thật.
2. Chốt đặc tả state machine, schema/RLS/actor, retention và thiết kế xử lý retry/quarantine; sau đó triển khai từng lát end-to-end với migration mới chỉ trong repository và DB disposable.
3. Test synthetic bảo mật/permission/worker, cập nhật tài liệu và báo rõ phần đã làm so với roadmap. Chưa áp migration remote/deploy/kết nối Gmail thật nếu chưa có điều kiện và ủy quyền thích hợp.
4. Trước public hoặc xử lý CV thật: HR/Privacy/Legal phê duyệt notice/consent/retention/quyền; DevOps phê duyệt edge chống abuse, malware scanning, secrets, monitoring, backup/restore, retention và incident response; test tích hợp staging/E2E trên môi trường được phép. Các gate đang treo vẫn chưa đạt chỉ vì có code.

## 4. Tiến độ lát cắt demo đã triển khai

### Cổng tuyển dụng demo

- Migration `00024_careers_demo.sql` thêm hạn UTC `application_deadline_at` (mặc định NULL, không tự hiển thị vị trí cũ), phân biệt nguồn `CAREERS_DEMO`, cho phép actor NULL chỉ với nguồn demo thay vì mạo danh HR. Tệp migration **mới chỉ áp lên PostgreSQL disposable cục bộ**, chưa áp Supabase; code mới cần migration tương ứng trước deploy.
- HR được quyền sửa hạn tại dialog chỉnh sửa vị trí; nhập theo giờ trình duyệt, API yêu cầu timestamp có múi giờ. Không có hạn, trạng thái khác OPEN hoặc hạn đã tới thì không hiển thị. Demo hiển thị tối đa 100 vị trí có JD phiên bản mới nhất, theo hạn; chưa có phân trang. Việc đặt hạn không ngụ ý nội dung JD đã được duyệt công khai.
- `/careers-demo` là trang không cần login, hiển thị JD mới nhất của vị trí OPEN còn hạn. Người dùng đã chọn tự hiển thị, không thêm cờ publish; HR chịu trách nhiệm rà soát JD trước khi công khai về sau. Đây chỉ là demo synthetic vì cổng thực chưa đủ gate. Job vẫn hiển thị nếu rubric chưa duyệt, nhưng **chưa nhận đơn** cho đến khi rubric của JD mới nhất đã `APPROVED`; đây là giới hạn tạm bảo toàn workflow hiện hữu, không tự duyệt rubric. Nếu vị trí có operation đang chạy, form trả thông báo thử lại.
- Form tạo application, batch và CV_PROCESSING trong một transaction; có request ID để thử lại idempotent cùng vị trí, giữ thông tin form khi worker cập nhật danh tính, có audit nguồn và dọn file best-effort khi rollback. Integration test synthetic kiểm tra đơn có trong danh sách HR và worker hiện hành đọc/hoàn tất CV với model mock. Không phải xác nhận email hay danh tính thực. Lưu file và DB vẫn không atomic; nếu cleanup lỗi hoặc process chết cần đối soát file mồ côi.
- **Khóa mặc định**: `CAREERS_DEMO_ENABLED=false`; chỉ hoạt động nếu bật rõ và `APP_ENV` là `testing`/`development`, DSN trỏ cục bộ tường minh tới database tên kết thúc `_test`, Storage local và không có biến môi trường libpq nguy hiểm. Các khóa này giảm nguy cơ dùng nhầm, không chứng minh môi trường thực sự biệt lập, không thay thế kiểm soát mạng. Không được mở demo ra Internet hay đưa dữ liệu thật vào demo. Không có AV, rate limit đa instance, CAPTCHA/spam, retention notice đã duyệt, email xác nhận, pagination hay E2E trình duyệt; file checks hiện tại không phải kiểm tra mã độc.
- Talent Pool: đề xuất opt-in là checkbox **không bắt buộc**, tách biệt với ứng tuyển, kèm mục đích/phiên bản nội dung/thời hạn và quyền rút. Chưa có wording/retention được Legal duyệt nên form demo **không thu consent**, không lưu pool, không tạo link rút consent. Module `talent_pool_demo.py` chỉ kiểm thử quy tắc thuần trên fixture synthetic, không đọc DB, không quét CV thật hay xếp hạng. Không áp dụng thời hạn mẫu 24 tháng như chính sách.

### F3.03 — demo offline

- Chạy `backend/.venv/bin/python backend/scripts/demo_email_offline.py` từ gốc repository sau khi cài dependencies. Script tự tạo email và attachment giả; phân tích mã vị trí chính xác trong subject từ danh sách được cấp, kiểm tra số lượng/đuôi/kích thước, trả metadata hoặc lý do review. Không xuất sender, body, CV; không mở Gmail, không kết nối mạng, không tạo application.
- Đây **chưa phải** ingestion Gmail: chưa có OAuth, polling, idempotency mailbox/attachment, UI hàng review, content validation, antivirus/spam hoặc mapping DB. Kết quả `CANDIDATE` chỉ có nghĩa phù hợp quy tắc demo, không phải hợp lệ/an toàn để xử lý.

### Kiểm thử và việc còn lại

- Backend disposable PostgreSQL + synthetic: toàn bộ suite **356 pass, 10 warnings** trước khi bổ sung test tranh chấp; sau đó riêng `test_careers_demo.py` **3 pass**, gồm hạn hết khi đang đợi lock. Frontend type-check/lint/i18n/unit/build pass; không có browser E2E. Ruff F cho các file mới/được chọn pass. Không chứng minh Supabase Storage hay vận hành thực tế.
- Bước tiếp theo: thiết kế tiếp nhận có hàng chờ nếu HR muốn nhận hồ sơ trước khi duyệt rubric; tích hợp kiểm soát anti-abuse/AV/retention và xử lý rollback/idempotency/scan an toàn, phân trang, E2E và privacy/security review; quyết định notice, thời hạn và opt-out, xây consent/pool/search thực sự. Email cần nối vào cùng intake sau quarantine, xây hàng review và test Gmail riêng có ủy quyền. Không tự áp `00024`, deploy, kết nối Gmail hoặc mở dữ liệu thật.
