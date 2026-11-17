# Preflight — đấu nối thật trên VPS để thử nghiệm

## Yêu cầu mới và trạng thái

Người dùng yêu cầu đấu nối thật vào hệ thống hiện tại trên VPS để test ba hạng mục: cổng việc làm/ứng tuyển, Talent Pool/rediscovery và email Gmail. Đây là yêu cầu chuyển từ preview synthetic sang **tích hợp hạ tầng thật**; chưa xác định được phép dùng CV thật, chưa xác minh VPS/project đang chạy, chưa deploy hoặc thay đổi remote. Tài liệu cũ về địa chỉ/commit là snapshot, không phải kết quả kiểm tra hiện tại. Phiên agent hiện không có đường SSH trực tiếp tới VPS; operator có thể thực hiện lệnh được hướng dẫn, không gửi mật khẩu/token/key/URL DB chứa mật khẩu vào chat.

## Điều quan trọng: bản demo chưa phải bản deploy

- `careers-demo`, `talent-pool-demo`, `email-demo` và server `careers_demo_server.py` chỉ chạy với DB local `_test`, local Storage, giả lập HR/AI; **không deploy wrapper giả lập hay bỏ các guard lên VPS hiện tại**. Migration `00024`–`00026` là cấu trúc demo, chưa áp remote; không giả định có thể dùng nguyên chúng như schema chính thức.
- Cổng thực chưa có các kiểm soát cần cho public intake: hạn, nội dung JD phù hợp công khai, upload quarantine/AV, anti-abuse, retry/giới hạn, nhận hồ sơ không mạo danh HR, Storage/DB reconciliation, privacy notice. Hiện intake cũ yêu cầu rubric duyệt, lock, worker và user HR; cần xây và thử luồng thật chứ không bật flag demo.
- Talent Pool mới chỉ là prototype; chưa có policy consent/retention được duyệt, danh tính và quy trình rút/lưu bằng chứng phù hợp, quyền/tìm kiếm xuyên vị trí và matching thật. Chỉ test synthetic cho đến khi các phê duyệt và kiểm soát cần thiết hoàn tất.
- Email `.eml` hiện là tải tay offline; **chưa kết nối Gmail, OAuth, polling/ack, dedupe bền vững, quarantine/AV hoặc hàng review**. Gmail thật phải là mailbox thử nghiệm riêng được chủ sở hữu ủy quyền, dùng dữ liệu giả khi chưa được duyệt dữ liệu thật. Không yêu cầu người dùng gửi password, app password, access/refresh token hoặc client secret vào chat/Git.
- Migration `00023` từng được xác nhận áp trên Supabase test `myrymlqdbyqmpynesiwk`; không suy hiện VPS trỏ project đó, code đã deploy tương ứng hoặc project không có dữ liệu thật. Cần xác nhận thực tế trước khi áp bất kỳ migration nào. Không lặp thao tác purge dữ liệu.

## Tiền kiểm chỉ đọc trên VPS

Chạy trên VPS bởi operator có quyền; các lệnh dưới không đọc/in nội dung `.env`, không dump DB và không thay đổi service. Nếu thư mục cài đặt khác `/home/ubuntu/hra`, dùng thư mục thực tế. Chỉ gửi **output không chứa secrets**, che hostname/IP nội bộ nếu cần.

```bash
cd /home/ubuntu/hra
printf 'commit: '; git rev-parse --short HEAD
printf 'branch: '; git branch --show-current
printf '\ntracked status:\n'; git status --short --untracked-files=no
printf '\nprocesses:\n'; pm2 list
printf '\nbackend health:\n'; curl --max-time 5 -fsS http://127.0.0.1:8005/health || echo 'health unavailable'
printf '\nbackend readiness:\n'; curl --max-time 5 -fsS http://127.0.0.1:8005/health/ready || echo 'readiness unavailable'
printf '\nfrontend HTTP status: '; curl --max-time 5 -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3005/ || true
```

Không chạy `cat .env`, `pm2 env`, `pm2 jlist`, `printenv`, `set -x`, log thô hoặc `git remote -v` trong output gửi lên vì có thể lộ cấu hình/credentials. Nếu cổng khác, báo các cổng nội bộ không chứa secret. Không yêu cầu đăng nhập lại hoặc chia sẻ quyền SSH trong chat.

## Cần chốt trước khi thao tác thay đổi

1. Xác định VPS/process, domain HTTPS, project Supabase đích và tính chất test/production; xem data/active jobs và version migration qua phương thức được ủy quyền, chỉ báo aggregate, không lộ CV. Nếu stack dùng chung production, cần môi trường cách ly/cửa sổ bảo trì và phương án ngăn ảnh hưởng người dùng.
2. Chốt dữ liệu thử nghiệm: **khuyến nghị email và CV synthetic** qua Gmail/Storage/DB thật trước. Chỉ dùng dữ liệu thật khi HR/Privacy/Legal phê duyệt mục đích, notice, thời hạn, phân quyền, xử lý quyền ứng viên và egress LLM/AI. Dữ liệu test vẫn cần cơ chế thu gom/xóa theo quy trình, không tự purge.
3. Gmail test: chủ mailbox chuẩn bị Google Cloud project/OAuth consent screen, tài khoản test và quyền cần thiết; scope tối thiểu, token lưu an toàn phía server, tách môi trường. Không yêu cầu credential trong chat. Chưa có kết nối OAuth; việc biết địa chỉ Gmail không cho phép đọc mailbox.
4. DevOps/DBA xác nhận backup **DB và Storage**, khả năng restore, kế hoạch rollback/forward-fix khi migration không đảo được, topology worker/queue, TLS, firewall và log/monitoring. Không chạy migration, restart, deploy hoặc gửi email trước preflight và phê duyệt thao tác phù hợp.
5. Cổng ứng viên: trước Internet phải có bảo vệ abuse, giới hạn request/body ở edge, kiểm tra định dạng và quét malware fail-closed, quarantine/cleanup/reconciliation, notice và thiết lập hạn/điều kiện mở. Thử nghiệm riêng bằng synthetic, không coi CI/local E2E là nghiệm thu thực tế.
6. Rediscovery: cần lưu và kiểm tra consent độc lập/expiry/withdrawal/retention/quyền; không dùng hồ sơ cũ nếu chưa chứng minh có quyền tái sử dụng. Phân quyền HR và ngăn rò rỉ CV xuyên vị trí; kiểm tra race rút/xóa và audit.
7. Gmail: dùng OAuth, key bảo mật, polling idempotent theo mailbox/message/attachment, ack sau commit, quarantine và review có trạng thái cho sai mã/nhiều tệp; không suy consent pool từ email. Kiểm tra duplicate/retry và từ chối mã độc bằng dữ liệu giả.

## Thứ tự thực thi dự kiến

1. Người dùng xác nhận môi trường, mailbox thử nghiệm và phạm vi dữ liệu; operator gửi kết quả preflight chỉ đọc.
2. Thiết kế/triển khai các luồng thực với feature flags mặc định tắt, migration riêng, permission/retention rõ ràng; local integration/synthetic E2E và review; xây runbook rollback.
3. Xác nhận backup và cửa sổ; sau sự đồng ý deploy cho môi trường cụ thể: apply migration được review, deploy phiên bản đã chọn, smoke, đối soát và giữ chức năng tắt cho đến khi gate đạt.
4. Kết nối Gmail test với OAuth do operator thực hiện trên kênh/công cụ an toàn; thử dữ liệu tổng hợp qua từng kênh, ghi kết quả và cleanup theo quy trình được phê duyệt. Không báo đã chạy khi chưa có bằng chứng.

## Quyết định đã nhận và kiểm tra chỉ đọc

- Người dùng chọn VPS đã dùng và Supabase test `myrymlqdbyqmpynesiwk`; kết nối VPS/DB/Gmail thật nhưng chỉ dùng email/CV tổng hợp. Đã có Gmail test riêng và có thể cấp OAuth. Đây **không phải** phê duyệt dữ liệu thật hay xác nhận backup.
- Kiểm tra connector chỉ đọc: project `ACTIVE_HEALTHY`; DB/Auth/Storage/REST báo healthy; migration cuối được liệt kê `phase2_workflow_core` version `20261116081146` (tương ứng local 00023). Aggregate: 6 positions, 7 applications, 0 operation `PENDING`/`PROCESSING`, 0 deletion `PROCESSING`; chưa có cột deadline demo. Số liệu là snapshot, không chứng minh VPS đang trỏ project/commit đó, dữ liệu hiện hữu là synthetic, backup, runtime hay production readiness. Không thay đổi project.

## Gmail OAuth smoke chỉ đọc — đã chuẩn bị, chưa chạy thực tế

`backend/scripts/gmail_readonly_smoke.py` là bước kiểm tra kết nối **độc lập**, không phải Gmail ingestion. Chỉ thực hiện sau khi operator xác nhận mailbox test chuyên dụng, không chứa email thật, và đã đọc quyền cấp:

1. Trong Google Cloud do anh quản lý, bật Gmail API, cấu hình OAuth consent screen và đưa Gmail thử nghiệm vào test users khi cần; tạo OAuth client loại **Desktop app**. Chuẩn bị nhãn Gmail `HRA_TEST` và gửi một email **giả** vào nhãn đó. Scope `gmail.readonly` cho phép đọc cả mailbox, không chỉ nhãn: query nhãn chỉ giới hạn request của script, không giới hạn quyền OAuth. Đây là scope restricted theo [Google Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes); việc kiểm duyệt/verification Google khi mở rộng là bước riêng.
2. Lưu JSON OAuth client an toàn trên VPS, **ngoài repo**, owner là user chạy app và mode 0600. Không dán nội dung JSON, URL cấp quyền, token hay authorization code vào chat/log/Git. Script từ chối file trong repo, symlink và file có quyền quá rộng; không lưu access/refresh token. Script chỉ lấy tối đa 5 message IDs theo label rồi chỉ in **số lượng**, không in ID/nội dung; không tạo hồ sơ, không sửa/xóa email.
3. Sau khi có code được operator đưa lên VPS và đã xác định/đồng ý cách cài gói, cài optional dependency `gmail-smoke` vào venv test; tránh cài hoặc restart app đang chạy khi chưa chốt cửa sổ. Từ **máy anh**, mở SSH tunnel nội bộ tới VPS (`localhost:8765` của máy anh → `127.0.0.1:8765` trên VPS) theo quy trình SSH sẵn có; không mở cổng callback ra Internet. Trên VPS, chạy trong terminal tương tác từ gốc repo:

   ```bash
   backend/.venv/bin/python backend/scripts/gmail_readonly_smoke.py \
     --client-file "$HOME/.config/hra-gmail/client.json" --confirm-test-mailbox
   ```

   Mở URL chỉ được in trong terminal trên trình duyệt **máy anh**, chọn đúng Gmail test và cấp quyền; callback localhost đi qua tunnel. Chỉ gửi lại trạng thái thành công/thất bại và số đếm, không gửi URL/log lỗi/token. Script timeout sau 5 phút; sau khi kết thúc không có token được lưu bởi script. Nếu có lỗi, gửi loại lỗi đã được script rút gọn; không gửi traceback/config.
4. Đã test với flow/HTTP mock **2 passed**, không kết nối Google thật trong sandbox. Chưa chạy script trên VPS, chưa tạo application và chưa có Gmail ingestion/OAuth refresh token bền vững. Kết nối thật, xác nhận kết quả và triển khai luồng ingestion là các bước tiếp theo.

Tham khảo: [Gmail messages.list](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list), [OAuth Desktop](https://developers.google.com/identity/protocols/oauth2/native-app).

## Kết quả operator báo từ VPS — preflight vòng 1

- Tại `~/hra`, `git rev-parse --short HEAD` = `94e38d9` (trong lịch sử branch hiện tại, trước code ba hạng mục); tracked working tree sạch. Đây là commit checkout, **không tự chứng minh** commit backend/frontend thực tế đã khởi động, hay code build frontend.
- PM2 có `hra-backend`, `hra-frontend`, `fastapi-backend`, `nextjs-dashboard` đều online; tên process sau cùng theo tài liệu cũ có thể thuộc NarrativeHealth nhưng chưa xác minh hiện trạng, không đụng tới. Chưa map cổng/PID/cwd runtime.
- `127.0.0.1:8005/health` healthy, `/health/ready` ready/database connected và cả hai báo `environment=production`. Readiness không chứng minh DB là project test đã chọn. Chưa có HTTP frontend, TLS, backup/restore hay worker drain evidence trong vòng này.
- Không deploy/restart/purge/apply migration hoặc thay đổi cấu hình từ các kết quả này. Giữ nguyên demo guards; không thay `APP_ENV` hoặc cho rằng đây là production-ready. Cần xác nhận người dùng/ảnh hưởng stack, backup và đối chiếu cấu hình DB đích an toàn, cũng như runtime/cổng trước bất kỳ thay đổi nào.

## Kết quả operator báo từ VPS — preflight vòng 2

- Frontend `127.0.0.1:3005/` HTTP 200; `ss` báo Next.js PID 898038 lắng nghe `0.0.0.0:3005`, Python PID 902622 lắng nghe `127.0.0.1:8005` (PID là snapshot, có thể đổi). Lắng nghe `0.0.0.0` có nghĩa mọi interface local, **không đủ** để kết luận firewall/NAT cho phép truy cập Internet. Chưa xác minh TLS, firewall hoặc port-to-PM2 mapping. Không thay network hoặc restart các process.
- Operator xác nhận stack hiện là thử nghiệm, chưa có backup DB và không coi bảo toàn dữ liệu test là ưu tiên. Cần vẫn thỏa thuận rõ phạm vi ảnh hưởng/rollback, bảo vệ tài khoản, cấu hình và dữ liệu hiện hữu; không suy ra được phép xóa hoặc reset. Storage backup chưa xác nhận. Với thay đổi schema có rủi ro hoặc không đảo được, cần backup/restore được xác minh hoặc quyết định chấp nhận rủi ro và cách rollback/forward-fix cụ thể trước khi thao tác. Chưa chốt thao tác migration/deploy cụ thể.

## Chuẩn bị adapter quét mã độc (chưa tích hợp)

`backend/app/services/malware_scan.py` là adapter ClamAV INSTREAM qua Unix socket; chỉ trả CLEAN/INFECTED/UNAVAILABLE và không log CV hay signature. Chỉ CLEAN được phép đi tiếp; lỗi socket, timeout, kích cỡ, scanner error hay trả lời không đúng đều UNAVAILABLE (fail-closed). Test fake socket nội bộ, không có ClamAV thực và **chưa kết nối endpoint intake**. Không có API nào được bảo vệ nhờ adapter này cho tới khi tích hợp đúng thứ tự trước mọi bước parse/extract/promote và test end-to-end.

Trước khi dùng: cấu hình clamd socket chỉ ứng dụng được phép truy cập, signature updates/giám sát freshness, giới hạn INSTREAM và archive/unpack/recursion phù hợp, bật cảnh báo giới hạn/encrypted files, giới hạn request tại edge, kiểm tra thực tế với fixture thử nghiệm an toàn (ví dụ EICAR) và lỗi/quá hạn; đánh giá chính sách file không thể quét và quarantine. CLEAN không chứng minh tệp an toàn tuyệt đối; kiểm soát loại file, spam, quarantine, xử lý lỗi và abuse vẫn bắt buộc. Không tự cài hoặc thay đổi ClamAV trên VPS.

## Cổng việc làm thật: lát cắt danh sách (đã code, chưa deploy)

- DB: `00027_careers_real_listing.sql` là migration độc lập trên schema tới 00023: thêm deadline nếu chưa có và index; deadline NULL không hiển thị, không tự tạo/cập nhật vị trí. Có thể dùng lại cột nếu đã tồn tại trong DB test demo. **00024–00026 là migration demo và chưa được duyệt áp remote**; không chạy tự động toàn bộ chuỗi hay `supabase db push` lên project test vì có thể áp các migration demo ngoài ý muốn. Trước khi thực thi 00027 cần review migration history, target, rollback/forward-fix và plan riêng được đồng ý; bản local không chứng minh remote đã thay đổi.
- BE `GET /v1/careers/jobs`: feature flag `PUBLIC_CAREERS_ENABLED=false` theo mặc định; khi bật trả những vị trí OPEN có deadline tương lai, JD mới nhất (hoặc null), không phụ thuộc rubric; phân trang keyset UUID (mặc định 25, tối đa 100/trang), no-store, chỉ trả trường công khai dự kiến. Các vị trí có deadline NULL không hiển thị. HR cần xác minh *toàn bộ* OPEN/deadline/JD trước khi bật vì sẽ đưa nội dung ra không cần đăng nhập. Khi dữ liệu thay đổi trong lúc phân trang, người xem có thể refresh để nhận danh sách mới; không cam kết snapshot cố định.
- FE `/careers`: không yêu cầu đăng nhập, hiển thị danh sách và nút tải tiếp; có cảnh báo thử nghiệm, **không có form nộp hồ sơ**. HR sửa deadline ở chi tiết vị trí. Flag chỉ điều khiển API; trang có thể vẫn hiện thông báo không tải được khi flag tắt.
- Kiểm thử: PostgreSQL disposable local `hra_careers_real_test` dựa trên schema đến 00023, chỉ áp 00027, test endpoint (bao gồm 105 vị trí, thiếu JD, hạn, trạng thái, phân trang và flag); FE type-check/lint/i18n/unit/build. Không kết nối Supabase/VPS, không kiểm thử browser/edge/anti-abuse thực tế.
- Còn thiếu: public application/AV quarantine & anti-abuse, Talent Pool consent/withdrawal/rediscovery thật, Gmail OAuth ingestion/spam/AV/dedupe/review, kiểm tra Storage thật, full FE/BE/DB integrated E2E. Chưa có lý do để bật flag hoặc xem đây là ba luồng hoàn thiện.

## Talent Pool thật: schema, rút consent và rediscovery (chưa nối intake)

- `00028_talent_pool_real.sql` độc lập với migration demo, tạo bảng consent có notice version, hash token 256-bit, thời gian đồng ý, hạn consent, hạn retention và rút; RLS, không cấp `anon`/`authenticated`. Không mặc định opt-in hồ sơ cũ. Xóa application cascade consent; audit không lưu token. Migration chưa áp remote; không tự áp chuỗi 00024–00026.
- `create_consent` là primitive server-only trong transaction do caller quản lý, chỉ dự kiến gọi sau opt-in riêng, với policy và thời hạn từ server, trả token 1 lần sau commit. **Chưa có caller intake thật**, chưa có notice/retention được phê duyệt hay quy trình khôi phục mã. Không cấp token thử cho ứng viên thật; không có endpoint nào cho HR tùy tiện cấp consent thay ứng viên.
- `POST /v1/talent-pool/withdraw`: token trong body (không URL/log); phản hồi đồng nhất cho mã hợp lệ/không tìm thấy, rút không tự xóa application. Tách cờ `TALENT_POOL_STORAGE_READY` khỏi `TALENT_POOL_REDISCOVERY_ENABLED`: sau khi đã phát mã, phải giữ đường withdrawal khả dụng ngay cả khi tắt rediscovery; các cờ mặc định false. Cần TLS, giới hạn abuse, quy trình mất mã và giám sát trước khi dùng thật.
- `GET /v1/talent-pool/scan`: phải có HR scope cả nguồn/đích và tài khoản active; đích OPEN + rubric JD mới nhất đã duyệt; nguồn OPEN/PAUSED; chỉ consent còn hạn, retention còn hạn, chưa rút/chưa có case xóa, có CV đã xử lý; phân trang, ghi audit, không trả contact, không xếp hạng/liên hệ. Khóa position/role/consent/app để serialize withdrawal/retention/revoke; không đảm bảo ảnh chụp cố định sau khi response đã phát về browser, nên phải kiểm tra lại consent/quyền tại mọi thao tác sử dụng sau này. Chưa có workflow tương tác/copy/contact hồ sơ.
- FE `/talent-pool` cho HR tra cứu; `/pool-withdraw` cho token trong form, không gắn token URL. Không có link cấp token hay form opt-in vì intake thực chưa hoàn thành. Tests trên DB local disposable (quyền, token hash, rút lặp và khi scan tắt, thời hạn, retention/CV, source/target, concurrent withdrawal với lock thực). Không kiểm thử browser, Supabase Storage, token recovery, API edge/ratelimit hoặc luồng thực tế.
- **Không bật cho dữ liệu thật** trước khi hoàn thành intake, kiểm thử AV/abuse, thông báo và thời hạn được duyệt, token recovery, xử lý quyền ứng viên/retention và smoke tổng thể. Nếu storage flag tắt sau khi cấp mã thì ứng viên không rút được: không dùng cờ này như kill switch vận hành thông thường.
