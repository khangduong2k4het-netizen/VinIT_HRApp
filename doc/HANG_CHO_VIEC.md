# Hàng chờ việc — HRA

Danh sách việc **đã quyết định nhưng cố ý chưa làm**, kèm đủ bối cảnh để lần sau
làm tiếp mà không phải dựng lại. Mỗi mục ghi rõ: vì sao chưa làm, đã kiểm chứng
được gì, còn thiếu gì, và định hướng đã thống nhất.

Thứ tự trong tài liệu **không** phải thứ tự ưu tiên. Mục nào có "Quyết định" thì
đó là hướng đã chốt, không cần bàn lại.

---

## HANG-01 — ClamAV không nên chặn toàn bộ form tuyển dụng

**Trạng thái:** treo (2026-11-19). Ưu tiên sau khi thử xong các tính năng khác.

### Vấn đề

Form tuyển dụng `/careers` phụ thuộc tuyệt đối vào ClamAV. Nếu scanner không sẵn
sàng, **toàn bộ form tắt** — mọi vị trí hiện "Chưa mở nhận hồ sơ thử nghiệm"
(`can_apply_test = False`), và route trả 503 ngay từ dòng đầu.

Điều này trộn hai quyết định khác nhau:

1. *Luồng tiếp nhận CV phải chạy được* — yêu cầu nghiệp vụ.
2. *Máy chủ này đã đủ điều kiện an toàn để mở internet chưa* — quyết định vận hành.

### Vì sao quan trọng

Scanner chết không gây lỗi rõ ràng. `clamav-daemon.socket` (systemd socket
activation) tự khởi động lại service, nên "chết" thực tế là **treo im lặng rồi
timeout 10 giây** cho mỗi lượt nộp (`malware_scan.py`, `timeout_seconds=10.0`).
Ứng viên chờ rồi bỏ đi, không ai biết vì sao.

Thêm nữa `/health/ready` **không kiểm ClamAV**, nên health check vẫn báo `ready`
trong khi scanner đã hỏng — không có cảnh báo nào.

### Đã kiểm chứng trên VPS (2026-11-19)

- `check_test_scanners.py`: `clamav_clean=CLEAN`, `clamav_eicar=INFECTED`, `pass=true`
  → adapter, socket, quyền của user backend đều đúng.
- `StreamMaxLength 25M`, `MaxFileSize 25M`, `MaxScanSize 100M` → dư cho CV 10 MB.
- `AlertEncrypted yes`, `AlertExceedsMax yes`.
- Chữ ký `28188` cập nhật cùng ngày; `clamav-freshclam` active 1 ngày 11 giờ.

**Chưa kiểm chứng:** nhánh scanner chết. Lần thử đầu dừng nhầm
(`systemctl stop clamav-daemon` trong khi `.socket` vẫn active → systemd bật lại
ngay). Cần dừng **cả hai** unit rồi mới thử.

### Định hướng đã thống nhất

Bắt chước đúng mô hình luồng Gmail đã có: khi không quét được, nó đưa thư vào
`REVIEW / ANTIVIRUS_UNAVAILABLE` cho HR xử lý, **không chặn người gửi**.

Cụ thể cho form tuyển dụng:

- Có `CLAMAV_UNIX_SOCKET` → quét như hiện tại, fail-closed với tệp nghi vấn.
  Đây là mặc định khi chạy thật.
- Không có → **vẫn nhận hồ sơ**, gắn cờ "chưa quét virus", đẩy vào hàng chờ HR xem.
  Chỉ cho phép ở chế độ test có bật cờ rõ ràng; production vẫn fail-closed.

### Việc phải làm khi bắt tay vào

- [ ] Đổi `careers.py:42` (`can_apply_test`) và `careers_intake.py:39` để không
      chặn cứng khi thiếu scanner, có cờ riêng kiểm soát.
- [ ] Thêm trường/cờ đánh dấu hồ sơ "chưa quét virus", hiển thị cho HR.
- [ ] Quyết định chỗ lưu cờ: cột mới trên `application_documents` hay bảng riêng.
      Cần migration mới nếu thêm cột.
- [ ] Test: scanner chết → hồ sơ vẫn vào, cờ bật; scanner sống + tệp bẩn → chặn.
- [ ] Cân nhắc thêm trạng thái ClamAV vào `/health/ready` (hoặc endpoint riêng) để
      có cảnh báo thay vì phát hiện muộn.

### Lưu ý

EICAR PASS **không** chứng minh mọi mã độc đều bị phát hiện, không chứng minh
signature luôn được cập nhật, và không chứng minh giới hạn archive/nested hoạt
động đúng. Đừng dùng kết quả đó để kết luận "an toàn".

---

## HANG-02 — Kiểm chứng nhánh scanner chết trên VPS

**Trạng thái:** treo cùng HANG-01. Đây là bước đo lường, không phải sửa code.

Chạy đúng thứ tự (lần trước dừng thiếu unit `.socket`):

```bash
sudo systemctl stop clamav-daemon.socket clamav-daemon.service
systemctl is-active clamav-daemon clamav-daemon.socket   # phải inactive cả hai
# nộp một CV qua form -> kỳ vọng 503, không có hồ sơ nào được tạo
sudo systemctl start clamav-daemon.socket clamav-daemon.service
# nộp lại cùng request_id -> phải thành công, không tạo hồ sơ trùng
```

Ghi lại thời gian thực tế từ lúc bấm nộp tới khi nhận lỗi. Nếu xấp xỉ 10 giây thì
đúng là đang đi qua timeout, không phải fail nhanh.

Kiểm tra không có hồ sơ mồ côi:

```sql
SELECT count(*) FROM app_private.careers_intake_receipts
WHERE state NOT IN ('COMMITTED');
```

---

## HANG-03 — Giám sát ClamAV định kỳ

**Trạng thái:** treo. Nhỏ nhưng đáng làm trước buổi demo thật.

`/health/ready` không kiểm scanner, nên không có cảnh báo nào khi nó hỏng. Cách
đơn giản: cho `check_test_scanners.py` chạy định kỳ (cron 15 phút), báo khi
`pass` khác `true`. EICAR tạo trong RAM, không ghi đĩa, an toàn chạy lặp lại.

```bash
sudo -u ubuntu backend/.venv/bin/python backend/scripts/check_test_scanners.py \
  --clam-socket /run/clamav/clamd.ctl --confirm-synthetic
```

---

## Ghi chú chung

- ClamAV trên VPS đã cài và cấu hình đúng; **không cần cài lại hay chỉnh cấu hình**.
  Vấn đề ở HANG-01 là thiết kế luồng, không phải hạ tầng.
- HANG-01 không được làm giảm an toàn khi chạy thật: mọi thay đổi phải giữ
  fail-closed cho môi trường production, chỉ mở đường "nhận vào hàng chờ" khi có
  cờ test bật rõ ràng.

---

## HANG-04 — Sinh tiêu chí chạy đồng bộ trong request (A và B)

**Trạng thái:** hoãn có điều kiện (2026-11-19), sau khi luồng tạo vị trí chạy
thành công trên VPS. **Không phải việc gấp.**

### Vấn đề

`POST /criteria/generate/{position_id}` khai báo `202 ACCEPTED` nhưng chạy LLM
ngay trong request. Cấu hình hiện tại có thể khiến một request kéo rất dài:

- `timeout=120s` mỗi lần gọi (`llm_client.py:530`)
- retry 3 lần (`stop_after_attempt(3)`, `llm_client.py:413`)
- tối đa 4 route (primary + 3 fallback, `llm_client.py:380`)

Trường hợp xấu nhất là hàng chục phút cho một request. Đây là gốc của nhóm lỗi
"không biết kết quả" đã gặp.

### Vì sao hoãn

Sau khi sửa hai lỗi serialize (`88c13cc`) và trang chịu lỗi từng phần
(`6395669`), luồng đã chạy được trên VPS. Ở quy mô hiện tại (1 người tạo vị trí,
1 request mỗi lần) rủi ro còn lại chỉ là **thời gian chờ**, không phải mất dữ
liệu: vị trí luôn được lưu trước, tiêu chí hoặc có hoặc sinh lại được.

### Bước A — không làm

Gồm: hạ timeout 120s → ~45s, hoặc giảm retry 3 → 2, hoặc đặt `LLM_SEED` cố định.

**Lý do bỏ:** đây là cấu hình dùng chung cho **mọi tác vụ AI** (trích CV, chấm
điểm, sinh tiêu chí). Hạ ngưỡng để chữa một luồng có thể làm CV dài hỏng ở luồng
khác — đánh đổi không tương xứng, và không sửa được nguyên nhân.

### Bước B — điều kiện để bắt tay vào

Chỉ làm khi gặp **một trong hai** dấu hiệu sau, vì đó là lúc lợi ích thật:

1. HR thực sự gặp request bị cắt/504 khi sinh tiêu chí (không phải chỉ chậm).
2. Cần sinh tiêu chí **hàng loạt** — nhập nhiều vị trí một lúc, hoặc sinh lại
   cho toàn bộ vị trí sau khi đổi JD.

Nếu chỉ chậm mà vẫn ra kết quả thì **không cần làm gì**.

### Hướng đã thống nhất khi làm

Thêm capability `CRITERIA_GENERATION` vào worker có sẵn:

- Endpoint trả `operation_id` ngay, không chờ LLM.
- Dùng lại `OperationProgressPanel` đã có cho CV processing.
- Popup của trang tạo vị trí giữ nguyên, chỉ đổi nguồn dữ liệu sang theo dõi
  operation thay vì chờ một request dài.

**Quy mô thật:** `app/workers/processor.py` là **1.761 dòng**, 23 hàm, dùng
advisory lock + `FencedSession` + heartbeat + phân trang queue. Nó được thiết kế
cho CV processing (nhiều tệp, chạy hàng phút), không phải một job ~20 giây. Phải
sửa: claim query, dispatch, `_load_operations`, và có thể cần migration.

### Rủi ro cần xử lý khi làm

`LLM_SEED` mặc định `None` → retry không tất định, 3 lần thử có thể cho 3 kết quả
khác nhau. Với luồng đồng bộ đây chỉ là "thử lại chậm"; với luồng nền thì khó tái
hiện lỗi hơn nhiều. Nên đặt seed cố định **trong phạm vi capability này**, không
đổi toàn cục.

### Bài học giữ lại

Khi một endpoint dài bị cắt, response **không có `detail`** — giao diện phải hỏi
lại server thay vì đoán. Đã làm ở `frontend/src/lib/criteriaGeneration.ts`.
Chi tiết chẩn đoán: `doc/CHAN_DOAN_TAO_TIEU_CHI.md`.
