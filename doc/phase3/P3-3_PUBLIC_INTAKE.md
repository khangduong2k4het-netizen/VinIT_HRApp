# P3-3 — Tiếp nhận CV qua web

Cập nhật 19/11/2026. Phạm vi đợt này: hoàn thiện và kiểm chứng kênh web trên máy local với dữ liệu tổng hợp. Không triển khai lên VPS/Supabase; email ingestion chưa nằm trong phần đã làm.

## Luồng đang triển khai

1. HR bật nhận hồ sơ công khai trên trang vị trí. Chỉ vị trí `OPEN`, được bật và có criteria `APPROVED` cho JD mới nhất xuất hiện ở `/apply`.
2. Ứng viên chọn vị trí, tải PDF/DOCX/JPG/PNG tối đa 10 MB. Không cần tài khoản; request công khai không dùng axios có token HR.
3. Notice `v4` có **một ô đồng ý bắt buộc**, mặc định không chọn, gồm xử lý hồ sơ cho vị trí này và dùng lại trong Talent Pool, theo yêu cầu mới nhất của chủ dự án ngày 19/11. Tick ô này rồi nộp tạo cả `THIS_POSITION` và `TALENT_POOL`. Không sửa consent đã ghi ở các phiên bản trước.
4. Form gửi `notice_version=v4`. API trả 409 khi thiếu hoặc khác `PUBLIC_INTAKE_NOTICE_VERSION`, không quét/lưu CV hoặc tạo consent. Khi đổi câu chữ, tăng cả `CONSENT_NOTICE_VERSION` ở frontend và cấu hình backend; không tự đổi phiên bản của consent cũ.
5. Backend kiểm tra rate limit theo IP đã băm, honeypot, vị trí, consent, kích thước/định dạng và ClamAV trước khi lưu hồ sơ. Lỗi scanner trả 503; file bị phát hiện trả 400. Chỉ verdict INSTREAM `stream: OK` có ký tự kết thúc NUL mới được coi là sạch.
6. Hồ sơ được tạo với `source_code=PORTAL`, giữ đúng `position_id`. Worker dùng pipeline trích xuất/matching/ranking hiện có. Nếu vị trí đang có CV/assessment/ranking job, hồ sơ mới ở `NEEDS_HR_REVIEW`: HR dùng **Xử lý lại** sau khi job trước xong.
7. File cùng SHA-256 trong cùng vị trí không tạo hồ sơ thứ hai. Response vẫn giống nhận thành công để không tiết lộ hồ sơ đã tồn tại. Lần nộp trùng nhận mã giả, không thay đổi consent/mã của bản gốc; ứng viên giữ mã ở lần nộp đầu tiên.
8. Khi nộp thành công, response trả mã rút consent 64 ký tự, hiển thị một lần; DB chỉ lưu băm SHA-256. Response nộp hồ sơ có `Cache-Control: no-store`. `/apply/withdraw` vẫn hoạt động khi tắt tiếp nhận. Mã sai/đã dùng trả thông báo chung, không xác nhận ai có hồ sơ.

Rút consent Talent Pool chặn tái sử dụng và bỏ đánh dấu pool, không tự xóa hồ sơ ứng tuyển nguồn. Consent `v1`/`v2` có sẵn giữ nguyên; không tự ghi thêm consent cho CV HR upload hoặc CV cũ.

## Retention

- Migration `00022`: chính sách hồ sơ `v2.0-60month`, hạn = ngày đóng vị trí + 60 tháng. Đây là chính sách lưu/xóa application; xóa vật lý vẫn theo xác nhận và OTP hiện có.
- Quyền tái sử dụng Talent Pool: hạn = `application_data_consents.granted_at + 60 tháng`. Hết hạn thì không còn đủ điều kiện pool, dù application có thể vẫn còn lưu theo chính sách vị trí.
- Chu kỳ retention hủy case chưa xóa thuộc chính sách cũ đã bị thay thế; không hủy legal hold `ON_HOLD`. Việc chạy chu kỳ ở môi trường đích cần kiểm tra tác động của `00022` trước.

## Cấu hình triển khai

Áp migration theo thứ tự đến `00023`. Hai file `.env.example` và `backend/.env.example` có đầy đủ biến, mặc định tắt portal.

```dotenv
PUBLIC_INTAKE_ENABLED=true
PUBLIC_INTAKE_NOTICE_VERSION=v4
PUBLIC_INTAKE_IP_SALT=<chuỗi ngẫu nhiên riêng cho môi trường, ít nhất 16 ký tự>
PUBLIC_INTAKE_MAX_PER_IP_HOUR=5
PUBLIC_INTAKE_TRUSTED_PROXY_HOPS=1
MALWARE_SCAN_MODE=clamav
CLAMD_HOST=<địa chỉ clamd từ backend>
CLAMD_PORT=3310
CLAMD_TIMEOUT_SECONDS=10
```

`PUBLIC_INTAKE_TRUSTED_PROXY_HOPS=1` chỉ đúng khi nginx tin cậy nối IP vào `X-Forwarded-For` trước Next.js; Next không tính là hop. Đặt đúng sơ đồ mạng; chỉ cho truy cập qua proxy đó. Backend từ chối cấu hình thiếu scanner/salt/proxy hops khi bật portal ngoài development/testing. Đặt giới hạn body ở reverse proxy, ví dụ nginx `client_max_body_size 11m;`. Chỉ mở cổng clamd trong mạng riêng.

Câu chữ notice `v4` cần được xác nhận trước khi phát hành. Thay đổi cấu hình môi trường đang đặt `v2`/`v3` thành `v4` cùng lần deploy frontend; tab cũ sẽ nhận 409 và cần tải lại.

## Kiểm thử lặp lại

Chỉ dùng PostgreSQL cục bộ **mới, dùng một lần**, không chứa dữ liệu thật. Fixture sẽ `TRUNCATE positions CASCADE`; tên DB phải kết thúc `_test`. Không chạy hai bộ test cùng DB đồng thời. Không dùng `backend/.env` của môi trường phát triển làm đích test.

Ví dụ tạo riêng PostgreSQL với pgvector và ClamAV, không mount dữ liệu dự án:

```bash
docker run -d --rm --name hra-p33-postgres -p 127.0.0.1:55439:5432 \
  -e POSTGRES_HOST_AUTH_METHOD=trust pgvector/pgvector:pg16
docker run -d --rm --platform linux/amd64 --name hra-p33-clamav \
  -p 127.0.0.1:53319:3310 -e CLAMAV_NO_MILTER=true \
  -e CLAMAV_NO_FRESHCLAMD=true clamav/clamav:stable
```

Đợi PostgreSQL sẵn sàng và log ClamAV có `clamd started`. Cấu hình ClamAV trên chỉ dùng test với database chữ ký có sẵn trong image; môi trường triển khai phải cập nhật chữ ký định kỳ. `--platform linux/amd64` dùng khi image không có ARM.

```bash
backend/.venv/bin/python backend/scripts/setup_local_db.py \
  --admin-url postgresql://postgres@127.0.0.1:55439/postgres --database hra_p33_test

TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/hra_p33_test \
HRA_TEST_CLAMD_PORT=53319 \
  backend/.venv/bin/python -m pytest -q \
  backend/tests/test_public_intake_talent_pool.py backend/tests/test_talent_pool_scan.py
```

Browser E2E dùng Chromium tương thích Playwright và dependencies frontend đã cài. Harness tự mở API/Next trên loopback với port tạm, sao chép frontend vào thư mục test riêng, tạo hai DOCX giả, rồi dừng hai server sau test. Không intercept/mock API. PostgreSQL, ClamAV, HTTP, Next proxy, upload và worker thật; Auth nội bộ và phản hồi AI được giả lập. Worker được gọi chủ động để kiểm chứng cả hồ sơ bị giữ lại khi có job.

```bash
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/hra_p33_test \
HRA_TEST_CLAMD_PORT=53319 HRA_TEST_PUBLIC_BROWSER=1 \
HRA_E2E_CHROMIUM_EXECUTABLE='/đường/dẫn/Chromium' \
  backend/.venv/bin/python -m pytest -q backend/tests/test_public_intake_browser.py

cd frontend
npm run test:unit
npm run test:i18n
npm run type-check
```

Để Playwright dùng browser đã cài theo mặc định, bỏ `HRA_E2E_CHROMIUM_EXECUTABLE`. Nếu không đặt `HRA_TEST_CLAMD_PORT`, các test yêu cầu scanner thật bị skip; browser test cũng chỉ giả lập bước quét theo cấu hình fixture.

Dọn hai container do đợt test này tạo sau khi kiểm tra xong: `docker stop hra-p33-clamav hra-p33-postgres`. Không xóa container hoặc volume dùng chung khác.

## Checklist nghiệm thu staging còn lại

Kiểm tra trước khi push ngày 19/11/2026 với notice `v4`: nhóm portal, Talent Pool, browser, AI quality và OCR/retention có **69 passed, 2 skipped** (hai ca cần Tesseract chưa cài). Dùng PostgreSQL thật áp đủ `00001–00023`, ClamAV thật (clean/EICAR/scanner-down) và Chrome thật trên viewport mobile. Browser xác nhận chỉ có một checkbox, nộp ghi hai mục đích consent và rút consent dùng lại thành công. Frontend: **14 unit + 3 i18n passed**, type-check và ESLint các file frontend thay đổi đều qua. Auth/AI vẫn được giả lập; chưa chứng minh chất lượng model hoặc Storage/Supabase/nginx thực tế.

- [ ] Xác nhận câu chữ notice `v4` và chính sách lưu trữ; deploy đồng thời frontend/backend, áp migration đầy đủ, không sửa consent cũ.
- [ ] Kiểm thử HTTPS/nginx/IP thật, chặn backend/Next đi vòng proxy, body limit và rate limit với request song song.
- [ ] ClamAV có cập nhật chữ ký, thử sạch/EICAR/scanner-down; file bị từ chối không sinh application hay object storage.
- [ ] Thử bằng Auth, Storage, OCR và endpoint AI thực tế đã được phép: nộp, xem HR list, xử lý lại, matching/ranking và bằng chứng.
- [ ] Kiểm tra đóng/tạm dừng/bỏ công khai/đổi JD khiến vị trí ngừng nhận; consent một ô/rút consent vẫn đúng.
- [ ] Theo dõi log, hàng đợi, chi phí và orphan storage; điều chỉnh giới hạn IP cho NAT/mạng trường.

Chưa triển khai trong đợt này: CAPTCHA, email ingestion, webhook xác thực cho cổng tuyển dụng bên ngoài. Email cần xác định Microsoft 365/Gmail/IMAP, mailbox, quyền kết nối và quy tắc ánh xạ mã vị trí. Kênh web local được kiểm chứng không có nghĩa toàn bộ P3-3 đa kênh đã hoàn thành.
