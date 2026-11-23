# Phiếu giao việc cho 4 coding agent

> Lập 2026-11-30. Branch `arena/ea6e2570-vinit-hrapp`. CI xanh tại `47cef64`.
> Đọc `AGENTS.md` trước, rồi `doc/PLAN_4_AGENT.md`. File này là **việc cụ thể**,
> không phải chiến lược.
>
> Mỗi phiếu viết đủ để người nhận làm mà **không phải hỏi lại**: biết file nào,
> biết xong nghĩa là gì, biết cái gì sẽ kiểm nó.

---

## Cách đọc phiếu

| Trường | Nghĩa |
|---|---|
| **Xong khi** | Điều kiện nghiệm thu. Không đạt thì chưa xong, dù code đã viết |
| **Kiểm bằng** | Thứ sẽ chứng minh. Nếu không kiểm được thì chưa xong |
| **Không được** | Ranh giới. Vượt qua là làm hỏng việc người khác |
| **Phụ thuộc** | Phải có gì trước khi bắt đầu |

**Quy tắc chung cho cả 4 người:**

1. Đọc `AGENTS.md`. Đặc biệt mục 3 (test phải kiểm ngược) và mục 7 (file nóng).
2. Trước khi bắt đầu một phiếu: `git pull` nhánh chính, cập nhật fork.
3. Xong một phiếu: CI trên fork xanh → báo người điều phối → **dừng, chờ gộp**.
   Không ôm hai phiếu cùng lúc, trừ khi phiếu ghi rõ là được.
4. **Không tự đặt số migration.** Xin người điều phối.
5. Test viết xong phải **kiểm ngược**: gỡ dòng sửa, test phải đỏ. Ghi lại việc đã
   kiểm ngược vào commit message.

---

# TUẦN 1 — làm nền, chưa ra tính năng

Tuần 1 cố ý **không có tính năng nào**. Bốn người cùng dựng được môi trường chạy
thật (DB cục bộ) và cùng thống nhất một khuôn thì tuần 2 mới chạy song song được.
Tuần 1 mà mỗi người lao vào làm tính năng là tuần 3 phải gỡ ra làm lại.

## A0 — Chủ repo: chốt 3 câu hỏi chặn

**Người làm:** A (điều phối) · **Ưu tiên:** ngay, chặn B1 và B2

Đây không phải việc code, nhưng **chặn** việc code. Ba câu:

| # | Câu | Chặn ai | Nếu chưa có câu trả lời thì |
|---|---|---|---|
| 1 | Fork của agent có chạy được CI không? | cả 3 | Quy trình fork sụp — thử ngay bằng một PR giả |
| 2 | Dùng nhà cung cấp email nào? (SMTP nội bộ / Resend / SendGrid) | B1, B2 | B không viết được dòng nào |
| 3 | Ai duyệt nội dung thư gửi ứng viên? | B2 | Không được bật gửi thật |

**Xong khi:** ba câu có câu trả lời ghi vào chính file này (mục "Quyết định đã
chốt" ở cuối), và A đã báo cho người bị chặn.

---

## A1 — Dựng khuôn test tích hợp cho agent

**Người làm:** A · **Ưu tiên:** ngày 1 · **Phụ thuộc:** không

**Vì sao:** cả 3 agent sẽ cần chạy 174 test tích hợp. Hiện cách dựng DB cục bộ nằm
rải rác trong `backend/tests/README.md` và `doc/HUONG_DAN_DEMO_TUYEN_DUNG.md`, và
phải nhớ **bỏ qua `00035`**. Ba người tự mò là ba người mất nửa ngày, ba kiểu sai.

**Làm gì:**
- Thêm script `scripts/test-db.sh` làm đúng chuỗi việc: tạo DB `*_test`, tạo role
  stub (`anon`, `authenticated`, `service_role`), áp migration **theo thứ tự tên,
  bỏ `00035`**, in ra `TEST_DATABASE_URL`.
- Hỗ trợ tham số để chạy trên cổng khác nhau (4 agent cùng máy thì không đụng cổng).
- Không tự chạy test. Chỉ dựng DB.

**Xong khi:** trên máy sạch, chạy `bash scripts/test-db.sh --port 55433` rồi
`TEST_DATABASE_URL=... pytest backend/tests -q` cho ra **671+ passed, 0 skipped**.

**Kiểm bằng:** chính lệnh trên. Số `0 skipped` là bằng chứng DB đã dựng đúng.

**Không được:** script này không được trỏ tới Supabase, không được chứa mật khẩu
thật, không được `DROP DATABASE` gì ngoài DB mà nó vừa tạo.

---

## A2 — Deploy lần đầu lên môi trường đích

**Người làm:** A · **Ưu tiên:** ngày 2–3 · **Phụ thuộc:** câu hỏi 1 của A0

**Vì sao:** app **chưa từng chạy** trên môi trường đích. Mọi thứ đã xây, kể cả 8
commit của đợt trước, chỉ mới chạy trên máy và trên CI.

**Làm gì:** áp `00039`–`00041` (nếu chưa), rồi chạy deploy theo `scripts/deploy.sh`.
Script **không tự áp migration** — nó chỉ phát hiện thay đổi và đòi cờ
`--migrations-verified`, nên phải áp migration trước bằng tay.

**Xong khi:** app chạy được trên môi trường đích; đăng nhập được; một vị trí mở
được; **duyệt bộ tiêu chí thứ hai cho cùng một vị trí không còn 500** (bug vừa sửa
ở `5c939df` chỉ được xác nhận là hết khi chạy thật).

**Kiểm bằng:** biên bản deploy + ảnh chụp màn hình duyệt bộ tiêu chí thứ hai.

**Không được:** không seed dữ liệu mẫu, không gửi thư cho ứng viên thật.

---

## A3 — Quyết định số phận các màn `-demo`

**Người làm:** A · **Ưu tiên:** ngày 4 · **Phụ thuộc:** A2 (cần biết bản thật chạy được)

**Vì sao:** repo có hai bộ song song: `careers_demo.py` + `/careers-demo`,
`email-demo`, `gmail-test`, `talent-pool-demo` + `/talent-pool-demo`. Người mới
(3 agent) sẽ không biết cái nào là thật. Đây là nợ **đang gây nhầm lẫn ngay bây giờ**,
không phải nợ thẩm mỹ.

**Làm gì:** với từng màn, chọn một: **giữ** (và ghi trong README là màn demo, chỉ
dùng để kiểm), hoặc **bỏ** (xoá route + trang + test). Không để trạng thái lửng lơ.

**Xong khi:** mỗi màn demo có quyết định ghi trong `doc/PLAN_4_AGENT.md`, và nếu bỏ
thì đã xoá sạch (không còn route mồ côi trong `api/__init__.py`).

---

# TUẦN 1–2, song song: 3 luồng tính năng

## B1 — Lưu vết thư đã gửi (không gửi thật)

**Người làm:** B · **Ưu tiên:** ngày 2–4 · **Phụ thuộc:** A0 câu 2
**Cần:** migration `00042` (xin A cấp số)

**Vì sao làm cái này trước "gửi thư":** chưa có nhà cung cấp thì vẫn làm được phần
khó nhất — mô hình dữ liệu và đường đi. Và nó buộc phải trả lời câu hỏi đúng:
*thư đang ở trạng thái nào?* Nếu làm gửi trước, sẽ có một bảng chỉ ghi "đã gửi"
mà không ai biết gửi được hay không.

**Làm gì:**
- Bảng lưu vết thư **theo từng lần thử**, không phải một cột trên hồ sơ:
  `id`, `application_id`, `template_key`, `recipient_email`, `status`,
  `attempt_count`, `last_error`, `created_at`, `sent_at` (NULL được).
- Trạng thái tối thiểu: `QUEUED` → `SENDING` → `SENT` / `FAILED`. **`SENT` chỉ được
  ghi khi nhà cung cấp xác nhận**, không phải khi ta gọi hàm.
- `recipient_email` che bớt khi đọc qua API (không trả nguyên email ra ngoài).
- **Chưa gửi gì cả.** Chưa có nhà cung cấp thì chỉ ghi `QUEUED`.

**Xong khi:** có bảng, có API đọc trạng thái, có test. Gửi thư **vẫn chưa xảy ra**.

**Kiểm bằng:**
- Test: một bản ghi `QUEUED` **không** được đọc ra như "đã gửi".
- Test: ghi `SENT` mà không có xác nhận của nhà cung cấp thì phải lỗi.
- Test khoá: **không** có cột nào tên `notified`/`delivered` trên bảng hồ sơ.
- Kiểm ngược: sửa cho `SENT` được ghi ngay khi gọi hàm → test phải đỏ.

**Không được:** không bật gửi thật. Không thêm cột vào `applications`. Không dùng
lại bảng `interview_notifications` (đó là thông báo **nội bộ**, khác đối tượng).

---

## B2 — Gửi thư thật cho ứng viên, sau một cờ tắt mặc định

**Người làm:** B · **Ưu tiên:** ngày 5–7 · **Phụ thuộc:** B1 xong, A0 câu 2 và 3

**Làm gì:**
- Adapter gửi thư, **một interface, một cài đặt** theo nhà cung cấp đã chốt.
- Cờ `CANDIDATE_EMAIL_ENABLED`, **mặc định `False`** — giống cách
  `GMAIL_TEST_INGEST_ENABLED` đang làm.
- Chế độ thử: gửi tới hộp thư của chính người bấm, không gửi tới ứng viên.
- Mẫu thư có bản Việt và Anh; chọn theo ngôn ngữ của **tin tuyển dụng**, không theo
  ngôn ngữ trình duyệt của HR.
- Ghi vết vào bảng của B1: gọi xong, đọc lại trạng thái từ nhà cung cấp rồi mới
  ghi `SENT`.

**Xong khi:** với cờ tắt, không có thư nào ra ngoài (chứng minh bằng test). Với cờ
bật ở chế độ thử, thư tới hộp thư người bấm và bảng vết ghi đúng.

**Kiểm bằng:**
- Test: cờ tắt → adapter **không được gọi** (dùng đối tượng giả đếm số lần gọi).
- Test: nhà cung cấp trả lỗi → trạng thái `FAILED`, có `last_error`, **không** `SENT`.
- Kiểm ngược: bỏ kiểm tra cờ → test phải đỏ.
- Một lần gửi thật do **người** bấm, không phải test tự bấm.

**Không được:** không gửi cho ứng viên thật khi chưa có người duyệt nội dung
(A0 câu 3). Không ghi `SENT` trước khi nhà cung cấp xác nhận. Không nuốt lỗi.

---

## C1 — Báo cáo phễu tuyển dụng

**Người làm:** C · **Ưu tiên:** ngày 2–5 · **Phụ thuộc:** không
**Cần:** migration `00043` (nếu cần bảng tổng hợp; **ưu tiên đọc thẳng, không tạo bảng**)

**Vì sao:** `dashboard.py` hiện có 3 route — `work-queue`, `summary`,
`position/{id}` — đều là *ảnh chụp hiện tại*. Không có gì trả lời được *vị trí này
chậm ở bước nào*. Đó chính là F2.03 và cũng là thứ cần để biết pilot có hiệu quả.

**Làm gì:**
- Route mới `GET /dashboard/funnel` (và bản theo vị trí).
- Số liệu: số hồ sơ vào từng bước, **thời gian trung vị** ở từng bước, số hồ sơ
  đang kẹt quá N ngày. Lấy từ `application_status_events` (đã có) — **không tạo
  bảng tổng hợp mới** nếu đọc thẳng được.
- Tôn trọng đúng phạm vi quyền như `summary` đang làm: HR chỉ thấy vị trí mình.

**Xong khi:** có route + test + một trang xem được; số liệu khớp với một ca tự
dựng tay (biết trước đáp án).

**Kiểm bằng:**
- Test: dựng 3 hồ sơ với mốc thời gian biết trước → trung vị tính ra đúng số đã
  tính tay. **Đừng chỉ kiểm "trả về 200".**
- Test: HR của vị trí khác **không** thấy số của vị trí này.

**Không được:** không tính trung bình khi có ít hơn 5 hồ sơ mà không ghi rõ "mẫu
nhỏ" — một con số trung bình từ 2 hồ sơ bị đọc như sự thật. Không đụng bảng khác.

---

## C2 — Lấy mẫu kiểm chất lượng OCR/matching

**Người làm:** C · **Ưu tiên:** ngày 6–8 · **Phụ thuộc:** C1 (dùng chung quyền đọc)
**Cần:** migration `00044`

**Vì sao:** hiện không có cách nào biết matching có đang sai không. Đây là F2.04 và
là điều kiện để tin các con số của C1.

**Làm gì:**
- Bảng lưu **lần kiểm**: ai kiểm, hồ sơ nào, kết luận (`ĐÚNG` / `SAI` / `KHÔNG RÕ`),
  lý do.
- Lấy mẫu ngẫu nhiên **có hạt** (seed) để cùng một đợt kiểm chạy lại ra cùng mẫu —
  nếu không, không ai đối chiếu được.
- Màn hình: hiện hồ sơ + điểm + dẫn chứng, người kiểm chọn kết luận.

**Xong khi:** kiểm được 10 hồ sơ, có báo cáo tỉ lệ đúng, và chạy lại cùng seed ra
cùng danh sách mẫu.

**Kiểm bằng:** test với seed cố định → danh sách mẫu **giống hệt** ở hai lần chạy.

---

## D1 — Dò ngôn ngữ CV (chỉ dò, chưa đổi hành vi)

**Người làm:** D · **Ưu tiên:** ngày 2–4 · **Phụ thuộc:** không

**Vì sao làm bản nhỏ trước:** `language_detect.py` đã dò được JD. Dò CV là cùng
bài toán, nhưng **chưa được dùng để đổi cách chấm điểm**. Làm bước dò trước, đo
xem đúng bao nhiêu phần trăm, rồi mới quyết định có dùng hay không.

**Làm gì:**
- Dùng lại `detect_language_code`. Lưu kết quả vào trường có sẵn của hồ sơ nếu có;
  nếu không có thì **chưa thêm cột** — chỉ tính lúc đọc.
- Ghi rõ giới hạn đã biết: tiếng Việt **không dấu** bị đoán là tiếng Anh.

**Xong khi:** có số đo trên CV thật trong DB test: bao nhiêu phần trăm dò đúng, và
bao nhiêu phần trăm là "không dấu nên đoán sai".

**Kiểm bằng:** báo cáo số đo, không phải "đã thêm hàm".

**Không được:** không đổi cách chấm điểm, không đổi prompt, không thêm cột. Bước
này chỉ đo.

---

## D2 — Hiển thị song ngữ cho CV/JD

**Người làm:** D · **Ưu tiên:** ngày 5–8 · **Phụ thuộc:** D1
**Cần:** migration `00045` (nếu phải lưu bản dịch)

**Làm gì:** hiển thị bản dịch **bên cạnh** bản gốc, không thay thế. Người đọc phải
luôn biết mình đang đọc bản dịch hay bản gốc — đây là dữ liệu ứng viên tự viết,
dịch sai mà không đánh dấu là làm sai hồ sơ của người ta.

**Xong khi:** một CV tiếng Việt xem được ở giao diện tiếng Anh, có nhãn rõ "bản
dịch", và bản gốc vẫn xem được.

**Kiểm bằng:** test giao diện: nhãn "bản dịch" **phải có**; nếu bỏ nhãn → test đỏ.

**Không được:** không ghi đè `content_text` gốc. Không dịch tự động rồi lưu như
thể ứng viên viết bằng tiếng Anh.

---

# TUẦN 2 — gộp, kiểm, deploy

| Việc | Ai | Xong khi |
|---|---|---|
| Gộp từng phiếu, cherry-pick một commit | A | Nhánh chính vẫn xanh sau **mỗi** lần gộp |
| Chạy lại toàn bộ test trên nhánh chính | A | 671+ backend, 163+ FE, 0 skipped khi có DB |
| Demo 4 luồng cạnh nhau | cả 4 | Không luồng nào làm hỏng luồng khác |
| Deploy lần cuối + E2E | A | E2E chạy trên môi trường đích, không phải trên máy |

**Cổng gộp — không đạt thì không gộp:**

1. CI trên fork xanh.
2. Commit message nêu lý do, không chỉ việc đã làm.
3. Test mới đã kiểm ngược, và **đã ghi lại việc kiểm ngược đó**.
4. Không sửa file của luồng khác (trừ 3 file nóng, sửa riêng một commit).

---

# Quyết định đã chốt

| # | Quyết định | Ngày | Ai chốt |
|---|---|---|---|
| 1 | F3.05 = email cho ứng viên | 2026-11-30 | người dùng |
| 2 | Chỉ một Supabase; chỉ người điều phối áp migration | 2026-11-30 | người dùng |
| 3 | Mỗi agent một fork; người dùng điều phối | 2026-11-30 | người dùng |
| 4 | Không ưu tiên luồng; 2 tuần | 2026-11-30 | người dùng |
| 5 | Nhà cung cấp email: **chưa chốt** | — | chặn B2 |
| 6 | Fork có chạy được CI: **chưa thử** | — | chặn cả 3 |
| 7 | Ai duyệt nội dung thư: **chưa chốt** | — | chặn B2 |

Bốn dòng cuối là việc của A, xong trước ngày 2.
