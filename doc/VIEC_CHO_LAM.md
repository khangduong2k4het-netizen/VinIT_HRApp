# Việc chờ làm — UI/UX tuyển dụng

Danh sách những việc **đã thống nhất là cần làm nhưng chưa làm**, để không phải
dò lại từ đầu mỗi lượt. Mục đã xong nằm trong `doc/NHAT_KY_THAY_DOI.md`; tài liệu
này chỉ giữ phần còn mở.

Cách dùng: thêm mục mới vào bảng, mỗi mục một phần chi tiết bên dưới ghi hiện
trạng trong code, phạm vi dự kiến và cái phải quyết trước khi code. Khi làm
xong: chuyển trạng thái sang **Xong** kèm commit, và ghi mục tương ứng vào nhật
ký.

> **Bàn giao 2026-11-19.** File này đã gộp nội dung `doc/HANG_CHO_VIEC.md` (các
> mục hoãn kỹ thuật: ClamAV, sinh tiêu chí đồng bộ). Hai danh sách backlog tên
> gần giống nhau đã từng gây nhầm, nên chỉ còn **một** chỗ: phần A ở trên và
> phần B ở cuối file.

| # | Việc | Trạng thái | Vì sao / nguồn |
| --- | --- | --- | --- |
| 1 | Lịch phỏng vấn & scorecard | **Chờ làm** — khoảng trống nghiệp vụ lớn nhất | Mục 3 trong danh sách ưu tiên của anh; chi tiết ở §1 |
| 2 | Backend tổng hợp số đo UX (bảng event + endpoint theo tuần/vị trí/HR) | Chờ làm | Số đo hiện chỉ cục bộ trên một trình duyệt — `doc/NHAT_KY_THAY_DOI.md` mục 2026-11-19 “Đo tác động…” |
| 3 | Retention `execute` / `recover` (UI + xác nhận hai bước) | Chờ làm — cố ý chưa làm | Xoá dữ liệu thật, cần quy trình vận hành riêng — `doc/NHAT_KY_THAY_DOI.md` mục “Dữ liệu & lưu trữ” |
| 4 | 3.8 sửa tiêu chí tại chỗ | Chờ làm — chờ dữ liệu usability | `doc/TONG_HOP_DONG_PHASE_UIUX.md` §6.1 (khuyến nghị cách B) |
| 5 | Usability test staging + Safari/iOS + deploy `00033`/`00034` | Chờ làm — gate nghiệm thu | `doc/E2E_STAGING_EXECUTION_CHECKLIST.md`, `doc/TONG_HOP_DONG_PHASE_UIUX.md` §5 |

## 1. Lịch phỏng vấn & scorecard (chờ làm)

**Vì sao là khoảng trống lớn nhất.** Hệ thống dừng ở sàng lọc: hồ sơ đi
`SHORTLIST → INTERVIEW → OFFERED/REJECTED_INTERVIEW`, nhưng **không có nơi nào
ghi một buổi phỏng vấn** — ai phỏng vấn, khi nào, ở đâu, vòng mấy, kết quả. HR
vẫn phải giữ lịch ở ngoài (email/Excel) rồi quay lại đổi trạng thái bằng tay,
nên “hồ sơ đang ở vòng phỏng vấn” chỉ là một nhãn, không phải một kế hoạch.

**Đã kiểm trong code (để lần sau không dò lại):**

- **Không có bảng/endpoint lịch phỏng vấn.** Không có `interview` trong
  `backend/app/api`; `supabase/migrations` không có bảng lịch. Chỉ có trạng thái
  `INTERVIEW`, `REJECTED_INTERVIEW`, `OFFERED`, `ACCEPTED`
  (`backend/app/schemas/applications.py`, ma trận chuyển trạng thái ở
  `backend/app/api/applications.py:40`).
- **Scorecard đã có, nhưng chỉ gắn với shortlist share.** Bảng
  `app_private.shortlist_scorecards` + `shortlist_scorecard_criteria`
  (`backend/app/api/scorecards.py`, tạo tự động khi share shortlist với hạn 3
  ngày làm việc, có `scorecard_reopen_events`, có `/scorecards/reminders`).
  Nghĩa là HM **đã** chấm theo tiêu chí cho ứng viên shortlist; thứ còn thiếu là
  vòng phỏng vấn có scorecard riêng và buổi phỏng vấn có người/giờ.
- Frontend hiện chỉ có `ScorecardReminders` trên dashboard; không có màn lịch.

**Phạm vi dự kiến (chia nhỏ, mỗi bước tự dùng được):**

1. **B1 — Lịch phỏng vấn tối thiểu:** bảng `interviews` (application_id,
   vòng, thời gian bắt đầu/kết thúc, người phỏng vấn, địa điểm/loại, trạng thái
   `SCHEDULED/DONE/CANCELLED/NO_SHOW`), endpoint tạo/sửa/huỷ/liệt kê theo hồ sơ
   và theo người phỏng vấn, quyền theo assignment như retention/work-queue.
   UI: khối “Lịch phỏng vấn” trong hồ sơ + danh sách “Lịch của tôi” theo tuần.
2. **B2 — Scorecard theo buổi:** tái dùng đúng mô hình scorecard hiện có
   (tiêu chí của version đã duyệt, rating + thiếu bằng chứng + nhận xét, append-only,
   mở lại có event) nhưng gắn `interview_id` thay vì `share_item_id`. Một buổi
   chưa `DONE` thì chưa chấm được; chấm xong mới gợi ý bước trạng thái tiếp theo.
3. **B3 — Nối vào hàng đợi:** buổi sắp tới và scorecard quá hạn thành item trong
   work-queue/dashboard, cùng kiểu “quá N ngày” đang có, để lịch không nằm ngoài
   luồng việc.

**Phải quyết trước khi code (chặn B1):**

- Ai được tạo lịch: HR phụ trách, HR_LEAD, hay cả HM được share? (đề xuất: HR
  phụ trách + HR_LEAD tạo/sửa; người phỏng vấn chỉ xem lịch của mình).
- Buổi phỏng vấn có bắt buộc gắn vòng số mấy, và có cho nhiều người phỏng vấn
  cùng buổi không (ảnh hưởng schema và scorecard: một scorecard/người/buổi).
- Múi giờ: lưu UTC, hiển thị theo `Asia/Ho_Chi_Minh` — cần chốt trước khi viết
  API để không phải migrate.
- Ứng viên có nhận thông báo không; nếu có thì dùng email hiện có hay chỉ hiện
  lịch trong app (quyết định này đổi phạm vi đáng kể).

**Rủi ro.** Chạm schema + quyền + state machine nhiều hơn bốn lượt UI vừa rồi;
vì vậy cần migration riêng, test backend thật (VM hiện không chạy được pytest),
và không đổi luồng trạng thái đang có — lịch phỏng vấn là dữ liệu bổ sung, không
phải điều kiện mới để chuyển trạng thái.

**Chưa làm gì.** Chưa sửa code, chưa tạo migration, chưa đổi API — mục này chỉ
ghi lại để lượt sau bắt đầu từ đây.

---

# Phần B — Các mục hoãn kỹ thuật (từ `doc/HANG_CHO_VIEC.md`)

Gộp hai danh sách backlog vào đúng một chỗ: phần A ở trên là việc UI/UX còn mở,
phần B dưới đây là các mục hoãn vì lý do kỹ thuật, đã điều tra và chốt hướng.

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
