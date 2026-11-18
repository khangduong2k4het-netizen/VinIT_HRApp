# Thử nghiệm gọn: Gmail + ClamAV, chỉ dữ liệu giả

## Mục tiêu

Chỉ cần ClamAV và Gmail test riêng; chưa cài SpamAssassin. Gmail tự loại thư mang nhãn Spam/Trash, nhưng thư còn lại **không được bộ lọc độc lập quét spam**. Đây không phải xác nhận thư an toàn và không dùng dữ liệu thật. Nhãn `HRA_TEST`, tiêu đề `[HRA-TEST] `, `@example.test` chỉ là guard, không chứng minh dữ liệu giả. Scope OAuth đọc toàn hộp thư, không chỉ nhãn. ClamAV vẫn bắt buộc, quét email và attachment trước xử lý; mất kết nối/lỗi thì không nhập. Tính năng mặc định tắt, chỉ HR Lead/Admin đồng bộ thủ công.

## Bước 1 — Kiểm tra máy, không thay đổi gì

Operator chạy:

```bash
. /etc/os-release && echo "$PRETTY_NAME"
free -h
df -h /
apt-cache policy clamav-daemon clamav-freshclam
```

Gửi kết quả cho agent để xem phiên bản, RAM/đĩa và gói trước khi cài. ClamAV tốn RAM/CPU, ảnh hưởng các dịch vụ khác nếu máy thiếu tài nguyên. Kết quả `command -v` trước đó chưa có scanner; PID HRA trước đây backend 902622, frontend 898038. Chưa chứng minh firewall.

## Bước 2 — Cài ClamAV (chỉ sau khi đã kiểm tra tài nguyên)

Trên Ubuntu/Debian dùng apt, operator chạy:

```bash
sudo apt-get update && sudo apt-get install -y clamav clamav-daemon clamav-freshclam
```

Gói có thể tự tạo/chạy dịch vụ systemd và tải chữ ký; ảnh hưởng RAM/CPU/đĩa và cần mạng ra ngoài. Lệnh không đổi code hay DB và không cố ý restart PM2; không chạy nếu không đủ tài nguyên hoặc nếu cài đặt báo lỗi. Chờ xong rồi gửi **chỉ** output các lệnh sau để kiểm tra socket, signature và trạng thái (không gửi config môi trường/secrets):

```bash
systemctl is-active clamav-daemon clamav-freshclam
sudo grep -E '^(LocalSocket|LocalSocketGroup|LocalSocketMode|StreamMaxLength|MaxScanSize|MaxFileSize|AlertEncrypted|AlertExceedsMax)' /etc/clamav/clamd.conf
sudo ls -lh /var/lib/clamav/*.cvd /var/lib/clamav/*.cld 2>/dev/null
id
```

Không tùy ý thay quyền socket công khai hay thêm user vào group trước khi biết cấu hình. Kiểm tra cấu hình bao gồm giới hạn INSTREAM >= 15 MB, file/scan limits, cảnh báo file mã hóa/vượt giới hạn, signature mới, không mở cổng TCP công khai; adapter phải thực sự nhận verdict lỗi hoặc FOUND cho các trường hợp vượt giới hạn/mã hóa. Dừng nếu không xác minh được. Đường dẫn socket và quyền phụ thuộc gói/OS. App user cần quyền kết nối, và PM2 có thể cần restart sau khi thay group; quyết định sau khi kiểm tra và chỉ restart HRA có kiểm soát.

Khi code mới đã được triển khai vào VPS, kiểm thử trực tiếp **bằng user chạy backend**:

```bash
backend/.venv/bin/python backend/scripts/check_test_scanners.py \
  --clam-socket /duong-dan/socket-thuc-te --confirm-synthetic
```

Thay đường dẫn ví dụ bằng socket xác định ở trên. Kết quả cần `clamav_clean: CLEAN`, `clamav_eicar: INFECTED`, `pass: true`; dữ liệu kiểm tra EICAR được tạo trong RAM. Nếu FAIL không bật intake. Chạy thêm test fail-closed khi scanner dừng/timeout, tệp quá lớn và định dạng mã hóa/giới hạn; EICAR PASS không chứng minh các điều kiện đó hay mọi mã độc.

## Bước 3 — Deploy và OAuth, sau khi kiểm tra hạ tầng

- Xác minh VPS dùng project test `myrymlqdbyqmpynesiwk`, phiên bản tiến trình, worker, Storage, không có việc đang xử lý; migration 00027–00031 đã áp project đó, không tự chạy tất cả migrations (00024–00026 chỉ demo). Triển khai commit mới theo quy trình an toàn; không đụng PM2 `fastapi-backend`/`nextjs-dashboard`. Cài thêm backend optional `[gmail-smoke]`; build frontend và restart HRA theo kế hoạch sau drain. Chưa deploy.
- Không công khai HTTP: giới hạn frontend/backend, kiểm tra firewall; dùng SSH tunnel trên máy người thử (xem `GMAIL_VPS_TEST_RUNBOOK.md`) cho `localhost:13005` và callback OAuth `localhost:8765`. Máy trước đó frontend bind `0.0.0.0:3005`, không chứng minh firewall an toàn.
- Tạo Gmail riêng chỉ có thư giả; Google Cloud bật Gmail API, OAuth client Desktop và test user. Chạy `backend/scripts/gmail_authorize_test.py` như runbook chi tiết, bằng user backend, token ngoài repo mode 0600 trong thư mục 0700. Không gửi token/client JSON/URL/code qua chat. Chưa cấp OAuth.
- Trên backend của VPS, chỉ sau các kiểm tra trên: cấu hình `GMAIL_TEST_INGEST_ENABLED=true`, `GMAIL_TEST_GMAIL_SPAM_ONLY=true`, đường dẫn token và socket `CLAMAV_UNIX_SOCKET`. Flag chỉ áp dụng cho route Gmail **test**; mặc định `false` thì vẫn cần spamd. Khi bypass, `/gmail-test` hiện cảnh báo và audit ghi `GMAIL_LABELS_ONLY_TEST`; trạng thái này không phải spamd. Với form thử nghiệm cần cả `PUBLIC_CAREERS_ENABLED=true` và `PUBLIC_CAREERS_TEST_INTAKE_ENABLED=true`. Talent Pool dùng cờ riêng; giữ withdrawal khả dụng nếu đã phát token. Không sửa config/flag trước deploy và network, scanner, OAuth sẵn sàng.

## Bước 4 — Test giả

Qua tunnel, HR thử một CV giả vào Careers (có và không opt-in), xem worker và thử rút consent; gửi một email giả có nhãn `HRA_TEST`, tiêu đề `[HRA-TEST] <mã vị trí>`, đúng một CV giả, HR Lead/Admin bấm đồng bộ. Kiểm tra retry từng email REVIEW (sửa nguyên nhân hoặc gửi thư mới nếu nội dung sai), dedupe, xác nhận tên/email giả của hồ sơ ACCEPTED sau khi worker dừng, không tự consent pool, ClamAV bị dừng không nhận hồ sơ. Khi mất kết nối lúc nộp form, giữ nguyên form/file/mã rút và thử lại cùng yêu cầu; một yêu cầu mới vẫn có thể tạo hồ sơ trùng. Thư Spam/Trash có thể bị Gmail loại khỏi danh sách và không xuất hiện trong review. Chưa chạy những test này trên hạ tầng thật.

**Chưa sẵn sàng cho production**: cần xét lọc spam độc lập, HTTPS, chống abuse, privacy/retention/withdrawal, backup và các gate vận hành trong runbook chi tiết. Không có bước ở đây cho phép nhận dữ liệu thật.

## Kết quả kiểm tra VPS do operator gửi

Snapshot: repo Ubuntu noble (24.04) arm64, candidate ClamAV `1.5.4+dfsg-0ubuntu0.24.04.1`; 3.8 GiB RAM, 2.5 GiB available, swap 4 GiB trong đó 1.5 GiB used; root filesystem 45 GB, còn 13 GB (73% used). Có thể thử cài nhưng RAM không dư dả và swap đã dùng: cần theo dõi sau khi daemon nạp signatures, tránh làm khi VPS đang tải nặng, dừng và đánh giá nếu RAM/swap tăng nhiều hoặc dịch vụ khác chậm. Không khẳng định thông số này bảo đảm đủ tài nguyên. Tại snapshot scanner chưa được cài; agent không có SSH.

## Ghi chú vòng cải thiện trải nghiệm (chưa deploy)

- Gmail `POST /review/{receipt_id}/retry` chỉ xử lý receipt REVIEW trong đúng mailbox, có lock/dedupe/audit; spam/malware/accepted không retry. Danh sách chỉ 100 receipt mới nhất, không phải inbox đầy đủ. Thư sai nội dung không thể chỉnh trong app; cần gửi thư giả mới.
- Gmail `GET/PUT /review/{receipt_id}/identity`: chỉ HR Lead/Admin active, khi flag Gmail test bật, chỉ receipt ACCEPTED có application nguồn EMAIL_TEST không có retention case; chỉ cho tên giả và email `@example.test` cùng xác nhận tường minh. Chặn khi vị trí có tác vụ đang chạy, dùng `updated_at` chống ghi đè đồng thời và audit actor không ghi thông tin vào metadata. Đây không xác thực danh tính thật, không xác minh dữ liệu giả, không tạo consent hay khôi phục mã rút. Khi email đổi, các duplicate signal PENDING cũ bị dismiss; tín hiệu mới được tính khi chạy ranking sau.
- UI Careers phân biệt lỗi CV rỗng/quá lớn, lỗi dịch vụ và kết quả không rõ; request ID chỉ bảo vệ retry có nội dung giống nhau, không phát hiện mọi ứng viên trùng. UI rút consent luôn phản hồi đồng nhất, không xác nhận mã tồn tại; HR scan là snapshot, cần tìm lại trước khi dùng.
- Không có migration bổ sung; code và test local không chứng minh Gmail, Storage, ClamAV, OAuth hay E2E trên VPS. Không bật tính năng hoặc nhập hồ sơ thật.
