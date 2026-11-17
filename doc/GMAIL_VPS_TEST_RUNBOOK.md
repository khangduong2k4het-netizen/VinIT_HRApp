# Vòng thử nghiệm VPS — careers, Talent Pool và Gmail (chỉ dữ liệu tổng hợp)

## Trạng thái và phạm vi

- Người dùng đồng ý dùng VPS/Supabase test và dữ liệu tổng hợp; không bật HTTPS ứng dụng ở vòng này. Supabase test `myrymlqdbyqmpynesiwk`: migration kết hợp local 00027–00030 đã áp dưới remote `20261117043801 careers_talent_pool_real_00027_00030`; local 00031 đã áp dưới remote `20261117044409 gmail_test_intake_00031`. **Không** chạy `supabase db push` tự động: 00024–00026 là demo, chưa áp remote; remote history dùng timestamp và migration kết hợp. 6 positions/7 applications không đổi ở hai snapshot; không có backup trước hai migration. Chưa seed/xóa dữ liệu, chưa deploy code.
- Luồng Gmail trong code là **đồng bộ thủ công** của HR Lead/Admin, tối đa 5 mail mỗi trang, không thay đổi Gmail; chỉ `label:HRA_TEST` và subject bắt đầu `[HRA-TEST] `, chỉ mailbox test riêng không chứa thư thật. Sau antivirus cả email → spamd → parse MIME → antivirus attachment → validate, mỗi mail được dedupe theo mailbox + message ID và có trạng thái review/spam/malware/accepted. ACCEPTED tạo application `EMAIL_TEST` với tên/email tổng hợp cố định, không lấy danh tính From, không tự opt-in Talent Pool. Tiêu đề phải chứa duy nhất mã vị trí, vị trí OPEN còn hạn với rubric JD hiện tại APPROVED. REVIEW được kiểm tra lại khi sync lại trang; spam/malware/accepted không tự nhập lại. Link Gmail để HR kiểm tra thủ công; chưa có chỉnh sửa/duyệt lại mail ngay trong app hay bộ lập lịch.
- Marker và nhãn **không chứng minh** email/CV là giả, `@example.test` không chứng minh form/CV là giả. Không đưa dữ liệu cá nhân thật vào vòng này. Notice/retention 7 ngày trong code chỉ là fixture, không phải policy thực tế. Không bỏ guard demo hay chạy demo fake-auth trên VPS. Consent recovery và matching/ranking pool chưa hoàn thiện.

## Chuẩn bị hạ tầng — cần operator trên VPS

1. Đối chiếu DB VPS đang dùng đúng project test đã áp migration, vị trí commit đang chạy, các PM2 `hra-backend`/`hra-frontend`, worker, current jobs và Storage bucket. Không đụng hai process khác. Snapshot trước đây frontend `0.0.0.0:3005`, backend `127.0.0.1:8005`; không suy firewall chặn public. Cần giới hạn `3005`/`8005` chỉ localhost hoặc chặn ở firewall và xác minh, bảo đảm các truy cập test chỉ qua SSH tunnel. Không truy cập public qua HTTP: mật khẩu/token và CV sẽ đi không mã hóa. Backend còn báo `APP_ENV=production`; không đổi nhãn chỉ để vượt guard. HTTPS app không bật trong vòng này.
2. Trên **máy anh**, tạo SSH tunnel với quy trình SSH sẵn có: chuyển cổng máy anh `127.0.0.1:13005` tới VPS `127.0.0.1:3005` và `127.0.0.1:8765` tới VPS `127.0.0.1:8765`. Dùng trình duyệt máy anh tại `http://localhost:13005`; localhost là secure context cho Web Crypto, trong khi đường mạng giữa máy anh và VPS được SSH mã hóa. Không public callback OAuth. Nếu có người test từ máy khác, mỗi người cần tunnel riêng và tài khoản phù hợp.
3. Cài/cấu hình `clamd` + signature update và SpamAssassin `spamd` trên VPS theo OS, socket Unix riêng có quyền cho user backend và không lắng nghe public; đặt `CLAMAV_UNIX_SOCKET` và `SPAMD_UNIX_SOCKET` đúng socket thật. ClamAV INSTREAM limit phải đủ **15 MB email + 10 MB CV**, bật cảnh báo file mã hóa/giới hạn archive và từ chối khi không thể quét; kiểm tra fresh database. Kiểm thử EICAR, GTUBE, email/CV sạch tổng hợp, scanner tắt/timeout và tệp quá lớn; antivirus/spam phải fail-closed. Không bật intake nếu chưa test thực tế. Chưa có kết quả clamd/spamd thật.
4. Trước deploy, đối chiếu script PM2, môi trường, commit, migration, tránh mixed-version worker và xác định forward-fix/rollback; user đã nêu DB chưa backup và dữ liệu test không ưu tiên bảo toàn, điều đó không cho phép tự reset/purge. Cài dependency optional `gmail-smoke` cho backend venv theo quy trình deploy được phê duyệt (bao gồm google-auth-oauthlib), build frontend, khởi động lại **chỉ HRA** sau drain và kiểm tra readiness. Các cờ mặc định false; không bật trước khi network, scanner và OAuth sẵn sàng. Không tự động chạy migration demo.
5. Bảo vệ kích thước body/rate limit tại edge hoặc chỉ cho phép các tester tin cậy qua tunnel: FastAPI/Next có thể spool multipart trước khi handler kiểm tra dung lượng. Hiện chưa có distributed rate limit/anti-bot; không công khai luồng nhận hồ sơ.

## Gmail OAuth — chủ hộp thư thực hiện, không gửi secret

1. Dùng Gmail chuyên biệt **chỉ email thử nghiệm**, tạo nhãn `HRA_TEST`. Ở Google Cloud do anh quản lý: bật Gmail API, cấu hình consent screen/test user, tạo OAuth client **Desktop**; Google có thể yêu cầu verification cho scope restricted nếu mở rộng sử dụng. Scope `gmail.readonly` cho phép đọc cả mailbox chứ không bị giới hạn bởi nhãn; code chỉ query nhãn test. Đừng dùng mailbox đang có dữ liệu thật.
2. Trên VPS, lưu client JSON ngoài repo, owner `ubuntu`/service user và mode 0600, thư mục token ngoài repo owner giống backend và mode 0700. Không đưa JSON, token, URL cấp quyền hoặc authorization code vào chat/Git/log. Sau khi code và optional dependency có trên VPS, với tunnel cổng 8765 đã mở, operator chạy từ `/home/ubuntu/hra`:

   ```bash
   backend/.venv/bin/python backend/scripts/gmail_authorize_test.py \
     --client-file "$HOME/.config/hra-gmail/client.json" \
     --token-file "$HOME/.config/hra-gmail/token.json" --confirm-test-mailbox
   ```

   Mở URL in **trong terminal** trên trình duyệt máy anh, chọn mailbox test; callback đi qua tunnel. Script không ghi đè token cũ, lưu mode 0600 và không in token. Cần cấu hình `GMAIL_TEST_TOKEN_FILE` là đường dẫn đó trong môi trường backend, không chép nội dung tệp. OAuth consent mode test của Google có thể hết hạn token; cần quy trình cấp lại an toàn. Không khẳng định đã kết nối khi chưa chạy thật.
3. Sau khi kiểm tra các điều kiện trên, operator cấu hình trên HRA backend: `PUBLIC_CAREERS_ENABLED=true`, `PUBLIC_CAREERS_TEST_INTAKE_ENABLED=true`, `TALENT_POOL_STORAGE_READY=true`, `TALENT_POOL_REDISCOVERY_ENABLED=true`, `GMAIL_TEST_INGEST_ENABLED=true`, hai socket và token path; lưu secrets ngoài Git và restart có kiểm soát. Các flag liên quan không bao hàm nhau. Sau khi đã cấp withdrawal token, giữ đường rút consent hoạt động kể cả khi tắt rediscovery.

## Kiểm thử thủ công sau deploy

- HR tạo/chọn vị trí dữ liệu tổng hợp OPEN, hạn tương lai, JD công khai, rubric JD hiện tại APPROVED. `/careers` hiển thị vị trí, gửi CV/tên/email `@example.test`, chọn opt-in riêng và lưu mã rút; HR thấy hồ sơ, chờ worker hoàn tất; `/talent-pool` quét bằng HR có quyền hai vị trí, rút mã qua `/pool-withdraw`, quét lại không còn kết quả.
- Gửi email **giả** vào Gmail test, gắn nhãn `HRA_TEST`; tiêu đề ví dụ `[HRA-TEST] <mã-vị-trí-giả>` (đúng duy nhất một mã), một DOCX/PDF tổng hợp. Đăng nhập HR Lead/Admin, `/gmail-test` → Kiểm tra Gmail. Xem trạng thái ACCEPTED và ứng viên nguồn `EMAIL_TEST`; click lại không tạo ứng viên trùng. Gửi mail thiếu mã hoặc sai số lượng tệp: phải REVIEW và HR mở Gmail kiểm tra; không tự nhập. Mail gắn nhãn spam/thùng rác thường không nằm trong kết quả tìm kiếm Gmail và có thể không xuất hiện hàng đợi.
- Test fail-closed khi clamd/spamd dừng, tệp có mã thử EICAR, mail thử GTUBE, file lớn và Storage lỗi; không trích xuất hay nhập khi scanner không đạt. Không dùng EICAR/GTUBE để kết luận mọi malware/spam đều bị phát hiện. Đối soát receipt và Storage chỉ sau drain và phê duyệt operator; script mặc định chỉ đếm, `--execute` là xóa và không được chạy tùy tiện.

## Điều chưa được nghiệm thu

Không có SSH trực tiếp từ agent; chưa cài scanner, deploy, cấp OAuth hoặc chạy Gmail/Storage/scanner thật và browser E2E trên VPS. Gmail restricted-scope, phân loại spam, bảo vệ abuse, retention và consent production vẫn là gate riêng. Nếu cần ứng viên thật hoặc công khai Internet, phải làm HTTPS, privacy/retention, token recovery, anti-bot/rate limit, AV quarantine, reconciliation và nghiệm thu tương ứng; không dùng vòng test để tuyên bố production-ready.

## Tiền kiểm scanner do operator gửi

- Operator xác nhận `clamd`, `clamscan`, `spamd`, `spamc` chưa có trong PATH; `pm2 pid hra-backend` = `902622` khớp PID Python nghe `127.0.0.1:8005`, `pm2 pid hra-frontend` = `898038` khớp Next nghe `0.0.0.0:3005` tại snapshot. PID có thể đổi sau restart. Không tác động `fastapi-backend`/`nextjs-dashboard`.
- Có script `backend/scripts/check_test_scanners.py` kiểm tra clamd với EICAR và spamd với GTUBE **trong bộ nhớ**, kèm mẫu sạch. Chỉ in verdict, không đọc hộp thư hay ghi tệp. Script phải chạy bằng user backend sau khi hai dịch vụ đã được cài/cấu hình (socket path thực tế) và code có mặt trên VPS:

  ```bash
  backend/.venv/bin/python backend/scripts/check_test_scanners.py \
    --clam-socket /đường/dẫn/socket-clamd \
    --spamd-socket /đường/dẫn/socket-spamd --confirm-synthetic
  ```

  Đường dẫn trên là ví dụ mô tả, không chạy nguyên văn. PASS đòi CLEAN/INFECTED/HAM/SPAM đúng; script có thể mất hơn một phút khi scanner không đáp ứng. PASS không xác nhận signature cập nhật, giới hạn archive, mọi malware/spam, cách ly mạng, quyền hoặc an toàn production. Hãy kiểm tra các điều kiện đó riêng và không bật flag khi FAIL. Script chưa chạy trên VPS.
