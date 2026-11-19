# KỊCH BẢN DEMO — ĐỢT CHỈNH UI/UX (what-if "trước và sau")

**Mục đích:** cho người xem thấy **cái gì đã đổi và vì sao nó đáng đổi**, không phải
khoe danh sách tính năng. Mỗi mục dưới đây có: hiện tượng *trước*, thao tác *sau*,
và **con số đo được** để nói thành câu.

**Trạng thái code:** `d6e3ca3` trên `arena/ea6e2570-vinit-hrapp`, đã deploy VPS.
**DB:** migration `00033`/`00034` đã áp (`20261119093753`, `20261119093801`).
**Dữ liệu:** 100% tổng hợp. Không CV/tài khoản thật.

---

## 0. Chuẩn bị trước khi mở màn hình (15 phút)

### 0.1. Kiểm hệ thống sống

```bash
curl --fail http://127.0.0.1:8005/health/ready      # database: connected
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3005   # 200
pm2 list | grep hra                                  # cả hai online
cd /home/ubuntu/hra && git rev-parse --short HEAD     # d6e3ca3
```

### 0.2. Chuẩn bị dữ liệu demo — **quan trọng, đừng bỏ**

Truy vấn dưới đây cho biết **hồ sơ nào dùng để demo cái gì**. Chạy trên Supabase
SQL Editor và ghi ra giấy **mã ứng viên thật** ứng với từng vai (đừng đọc UUID
trên màn hình chiếu — quá dài, người xem không theo được).

```sql
-- Vai A: hồ sơ "nhiều tiêu chí cần xác minh" — dùng cho màn Review (UX-02).
SELECT p.position_code, a.application_id, count(car.result_id) AS results,
       count(car.result_id) FILTER (WHERE car.requires_hr_verification) AS flagged
FROM app_private.positions p
JOIN app_private.applications a ON a.position_id = p.position_id
JOIN app_private.assessment_runs ar ON ar.application_id = a.application_id
JOIN app_private.criterion_assessment_results car ON car.assessment_id = ar.assessment_id
GROUP BY 1,2 ORDER BY flagged DESC;
```

> **Kết quả trên DB hiện tại (đã kiểm ngày 2026-11-19):** `IT-0004`
> "Synthetic Backend Engineer" có 6 hồ sơ. Hồ sơ **flagged 12/12** là vai
> "nặng nhất" — dùng để demo U5 và U1. Hồ sơ **flagged 2/12** dùng để demo
> "hàng đợi đóng được sau vài lần bấm".

**Điều phải biết trước, kẻo demo sai kỳ vọng:**

| Dữ liệu test hiện có | Hệ quả khi demo |
|---|---|
| `evidence_items.page_number` **toàn NULL** | Câu U5 sẽ **không** hiện "trang N". Nói thẳng: *"với CV có số trang, câu này nói rõ trang để mở — bộ dữ liệu test không có số trang."* |
| `verification_status` **100% `VERIFIED`**, `is_hallucinated` = 0 | Không có câu `MISMATCH_CHECK` / "Máy tìm không thấy trích dẫn". Không dựng cảnh này. |
| `hr_reviews` = **0** trên mọi hồ sơ | Đây là **trạng thái đầu đẹp nhất**: hàng đợi còn nguyên, chứng minh được "trước khi HR làm gì". |

Nếu muốn có trang số + trích dẫn lỗi để demo đủ 7 nhánh, phải nạp một CV mới qua
luồng upload thật — **không** sửa DB bằng tay (sẽ làm sai lệch chứng cứ).
Xem mục 7.

### 0.3. Ba tab trình duyệt mở sẵn

1. `/dashboard`
2. `/positions/IT-0004` (mã vị trí lấy từ truy vấn trên) — tab "Danh sách ứng viên"
3. `/admin` → tab "Cài đặt HR"

Đăng nhập **ADMIN** trước. Mở sẵn **DevTools → Network**, lọc `cv-file` — sẽ dùng
ở mục 3.

---

## 1. Mở đầu (2 phút) — nói cái đã hỏng, không nói cái đã thêm

> "Đợt này không thêm tính năng mới. Nó sửa **bốn chỗ HR bị chặn hoặc bị lừa**, và
> tôi có số đo trước/sau cho từng chỗ."

Đừng đọc danh sách 9 hạng mục. Chỉ cần 4 câu này, mỗi câu một mục dưới.

---

## 2. Dashboard — "bấm vào việc là ra đúng việc" (3 phút)

**Trước:** tài liệu ghi mọi deep link đã đúng — **sai**. Backend phát
`?queue=file_review`, trang xếp hạng chỉ nhận `FILE_REVIEW` ⇒ mọi nút mở danh
sách **không lọc**.

**Demo:**

1. `/dashboard` → chỉ vào khối "Việc cần làm". Nói: *"đây là toàn bộ việc còn
   lại, không phải số liệu trang trí."*
2. Bấm **"Xác minh hồ sơ"** → nhìn thanh URL: `?queue=NEEDS_VERIFICATION`.
3. Bấm **"Kiểm tra file"** → `?queue=FILE_REVIEW`.
4. Quay lại `/dashboard`, chỉ dòng **"Đã xác minh xong N hồ sơ"** nếu có.

**Số để nói:** khối "Việc cần làm" từ **428px → 360px** (đẩy lên 68px); trang
1877 → 1832px. Việc đã kiểm xong giờ **hiện thành số** thay vì chỉ làm con số
"cần xác minh" nhỏ đi mà không ai biết vì sao.

**Chốt:** *"Nếu nút này mở danh sách không lọc, HR phải tự tìm lại hồ sơ trong
12 dòng — mỗi ngày, mỗi lần. Đó là lý do nó là lỗi ưu tiên 1."*

---

## 3. Review hồ sơ — trái tim của đợt này (10 phút)

### 3.1. Mỗi tiêu chí tự nói nó đòi gì (U5)

Mở hồ sơ vai A. Chỉ vào từng thẻ tiêu chí, đọc **dòng ngay dưới tên tiêu chí**:

- Thẻ "Đáp ứng tốt" → *"Đã đủ bằng chứng và máy đã xác minh — không cần làm gì"*
  (im lặng, màu xanh — **không** chiếm dòng của thẻ khác).
- Thẻ "Chưa rõ" có trích dẫn → *"Đối chiếu trích dẫn với CV rồi xác nhận"*.
- Thẻ "Chưa rõ" **không** có trích dẫn → *"CV không nêu tiêu chí này — cần hỏi
  thêm khi phỏng vấn"*.

**Nói rõ đây không phải AI đoán:** *"Câu này suy từ dữ liệu đã có — kết quả chấm,
trạng thái trích dẫn, quyết định HR đã ghi. Không gọi model lần hai, không bịa
việc. Có 10 unit test, trong đó một test chống nhánh chết."*

### 3.2. CV gốc không trôi khỏi màn hình (UX-04)

1. Cuộn xuống **tiêu chí thứ 3–4**. Chỉ vào cột phải: **"CV gốc" vẫn ở đó**.
2. **Số để nói:** trước khi sửa, cuộn tới tiêu chí cuối thì khung CV nằm
   **−637px** (trên màn hình) trong khi cột phải còn **900px trống**. Sau: tiêu
   đề CV ở **151px**, dưới thanh điều hướng (kết thúc 143px).
3. Mở DevTools Network: **0 request `cv-file`** kể cả khi đã cuộn hết trang.
4. Bấm **"Xem CV gốc"** → đúng **1 request**, và đó là lúc có audit.

**Nói thêm cái bẫy kỹ thuật** (nếu có người kỹ thuật trong phòng): *"`sticky`
không chạy vì toàn app bị `overflow-x: hidden` ở body — nó biến body thành scroll
container. Đổi sang `clip` là xong. Lỗi này ẩn suốt vì test nào cũng chỉ kiểm
`top > 0`, mà phần tử bị che thì vẫn `top > 0`."*

### 3.3. Khép vòng hàng đợi — đây là giá trị lớn nhất (U1)

Đây là phần **thuyết phục nhất**, dành nhiều thời gian nhất.

**Trước:** cách duy nhất để một hồ sơ rời hàng đợi "Cần xác minh" là **ra quyết
định tuyển dụng** (loại, hoặc chuyển phỏng vấn) — vì `SHORTLIST` vẫn là trạng
thái sàng lọc. Nghĩa là HR bị **ép đưa ra quyết định tuyển người chỉ để dọn một
danh sách việc kỹ thuật**.

**Demo:**

1. Trên thẻ tiêu chí "Chưa rõ", bấm **"Trích dẫn đúng, đã kiểm"**.
2. Chỉ vào dải tiến độ trên đầu, đọc **nguyên văn**: *"Đã xác minh k/N tiêu chí
   cần kiểm"* — con số tăng, **chưa** rời hàng đợi (đúng quyết định Q2: chỉ rời
   khi kiểm **hết**, khi đó câu đổi thành *"Đã xác minh đủ N/N tiêu chí cần
   kiểm"*).
3. **Chỉ vào ô "Cập nhật trạng thái"** — vẫn nguyên. Nói: *"Quyết định tuyển
   dụng không bị đụng tới. Ghi nhận kỹ thuật không phải quyết định tuyển người."*
4. **Tải lại trang (F5)** → quyết định **vẫn còn**.
5. Quay lại hàng đợi → hồ sơ vẫn ở đó cho tới khi kiểm hết.

**Nếu bấm thử "Trích dẫn sai"**: ô lý do **bắt buộc** (API trả 422 nếu thiếu) —
*"một dòng không lý do không phải là review, chỉ là một cú bấm."*

**Bảng chỉ hiện trên trang xác minh**: *"bảng review là **append-only** — xem lại
lần hai là một dòng mới, không ghi đè. Nhờ vậy trả lời được 'ai đổi ý, khi nào'."*

---

## 4. Phản hồi khi thao tác — chỗ từng im lặng (3 phút)

1. Mở một hồ sơ, đổi **trạng thái** → hiện thông báo thành công ở đáy.
2. Vào **Shortlist** → "Lưu nháp scorecard" → **giờ có câu xác nhận**.
   **Trước:** chỉ nút hết quay, không nói gì. HR không phân biệt được "đã lưu"
   với "bấm hụt".
3. Bật **screen reader** (hoặc chỉ DevTools → Accessibility) và chỉ vào vùng
   `role="status" aria-live="polite"`: *"vùng thông báo **tồn tại từ đầu**, rỗng
   khi chưa có gì. Không dùng `<Snackbar>` của MUI vì nó chỉ mount khi `open` —
   vùng live sinh ra cùng lúc với thông báo thì screen reader đăng ký quá muộn
   và bỏ lỡ câu đầu."*

**Số để nói:** trước đợt này toàn app có **35 file dùng `Alert`**, **3 file dùng
`Snackbar`**, chỉ **5 chỗ** có `aria-live`. Giờ có một component chung cho cả
5 luồng chính.

**Bonus nếu bị hỏi "sao biết có lỗi":** *"E2E mới lộ ra trang `/shortlist` crash
'Application error' — API trả object thay vì mảng nên `.length` là `undefined`
(khác `0`) rồi rơi vào `.map`. Lỗi có sẵn từ lâu, không ai thấy vì mọi test chỉ
đi qua trang chi tiết."* → đây là câu trả lời tốt cho "làm sao tin được là đã
kiểm".

---

## 5. Cài đặt ngưỡng — cái vừa mở khoá hôm nay (2 phút)

`/admin` → tab **"Cài đặt HR"**.

1. Chỉ hai ngưỡng: `deadline_soon_days = 7`, `waiting_attention_days = 7`.
2. Nói: *"Đây từng là số **hard-code trong code**. Giờ HR đổi được, có audit ghi
   giá trị cũ/mới và ai đổi."*
3. Đổi thử một giá trị → lưu → xác nhận → **đổi lại 7**.
4. Thử nhập **0** hoặc **999** → API từ chối kèm câu nêu khoảng cho phép.

**Nói thẳng giới hạn:** *"Chỉ ADMIN đổi được. Đây là ngưỡng ảnh hưởng **quyết
định nghiệp vụ**, không phải sở thích giao diện."*

---

## 6. Câu chốt (1 phút)

> "Bốn chỗ trong đợt này đều cùng một dạng: **hệ thống biết điều gì đó mà không
> nói ra**. Biết trích dẫn ở trang mấy, biết tiêu chí nào đã kiểm, biết đã lưu
> hay chưa, biết nút này dẫn tới đâu. Không thêm năng lực mới — chỉ **nói ra
> cái đã biết**, đúng lúc, đúng chỗ."

---

## 7. Nếu muốn demo đủ 7 nhánh câu hành động (chuẩn bị trước 1 ngày)

Bộ dữ liệu test hiện thiếu **số trang** và **trích dẫn lỗi**, nên chỉ demo được
5/7 nhánh. Muốn đủ, nạp **một CV mới thật qua luồng upload** (không sửa DB):

1. Vào `IT-0004` → tải lên một CV PDF **có số trang rõ** và **có một tiêu chí
   cố tình không nêu**.
2. Chờ worker chạy xong (`COMPLETED`).
3. Hồ sơ mới sẽ có `page_number` khác NULL → câu U5 hiện *"…CV trang N…"*.
4. Nếu muốn nhánh `MISMATCH_CHECK`, cần một trích dẫn mà máy **tìm không thấy**
   trong text — cách sạch nhất là để model tạo ra rồi kiểm tra; **không** sửa
   `evidence_items` bằng tay.

Kiểm nhanh sau khi nạp:

```sql
SELECT count(*) FILTER (WHERE page_number IS NOT NULL) AS with_page,
       count(*) FILTER (WHERE verification_status = 'FAILED') AS failed
FROM app_private.evidence_items;
```

Cả hai > 0 thì demo được đủ nhánh.

---

## 8. Ba câu **không** nói trong buổi demo

1. **"Đã nghiệm thu xong."** Chưa có HR thật nào dùng. Nói: *"đã kiểm bằng máy
   và bằng số đo; chưa có vòng người dùng thật."*
2. **"Chạy được trên mọi trình duyệt."** **Safari/iOS chưa ai thử** — mà đợt này
   dùng `position: sticky` + `overflow: clip`, đúng hai chỗ dễ khác biệt nhất.
3. **"An toàn cho production."** VPS đang chạy HTTP qua IP, không mã hoá. Chỉ
   dữ liệu giả, và đây không phải cấu hình production.

---

## 9. Nếu có sự cố giữa buổi

| Hiện tượng | Xử lý ngay |
|---|---|
| Trang trắng "Application error" | F5. Nếu vẫn lỗi: `pm2 logs hra-frontend --lines 30`. Không debug trước mặt người xem. |
| Nút review trả 500 | Kiểm migration: `SELECT to_regclass('app_private.hr_criterion_reviews');` — nếu NULL, migration chưa áp. |
| Dashboard không có việc | Kiểm `SELECT count(*) FROM app_private.operations WHERE status IN ('PENDING','PROCESSING');` |
| Bấm "Xem CV gốc" không mở | Kiểm `can_view_cv` của hồ sơ đó; tài khoản demo phải là HR của **đúng vị trí**. |
| Quên mất mình đã bấm review thử | `SELECT count(*) FROM app_private.hr_criterion_reviews;` rồi `DELETE` đúng dòng của buổi thử — **chỉ khi** đó là dữ liệu test và đã ghi lại ID. |
