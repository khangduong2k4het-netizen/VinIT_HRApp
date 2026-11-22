# Kế hoạch phối hợp 4 coding agent — rà soát thực tế và phân công

> Lập ngày 2026-11-30. Branch `arena/ea6e2570-vinit-hrapp`, HEAD `74bbe7b`.
> Mọi trạng thái dưới đây **đọc từ code**, không lấy từ tài liệu kế hoạch (các doc
> đó mô tả mục tiêu, và một số đã lệch thực tế). Chỗ nào doc nói khác code, tôi ghi
> rõ và tin code.

---

## 1. Bảng tiến độ thật, theo bằng chứng trong code

Cột "bằng chứng" là thứ tôi đã mở và đọc, không phải suy từ tên file.

| Mã | Hạng mục | Trạng thái thật | Bằng chứng |
|---|---|---|---|
| F1.01–F1.06 | Vị trí/JD, tiêu chí + duyệt 2 cấp, batch CV, matching 4 mức + dẫn chứng, ranking, shortlist | **Có code, đã test; chưa nghiệm thu production** | 66 file test backend; `doc/PHASE1_REMAINING_EXECUTION_PLAN.md` ghi Phase 1 **chưa đóng** |
| F2.01 | Rubric library theo job family | **Xong phần code** | `api/rubric_library.py`, `/rubrics` |
| F2.02 | Workflow HR–HM có cấu trúc | **Xong phần code** | `api/shortlist.py`, `api/scorecards.py` |
| F2.03 | Dashboard vận hành | **Một phần** — có dashboard vị trí/hàng đợi việc; **không có** báo cáo hiệu năng pilot theo thời gian | `api/dashboard.py` |
| F2.04 | Giám sát chất lượng OCR/matching, lấy mẫu kiểm | **Chưa có** | không có route/service nào |
| F2.05 | Trùng hồ sơ **chéo nhiều vị trí** | **Chỉ trong cùng một vị trí** | `matching.py:385` — docstring: *"within same position"* |
| F2.06 | OCR ảnh rời / ảnh nhúng DOCX | **Chưa có** | không có |
| F2.07 | Tự động retention | **Có code, có kiểm soát; chưa bật production** | `services/retention.py`, `api/retention.py` |
| F2.08 | SSO | **Chưa, và đã được chốt là tạm treo** | — |
| F2.09 | So sánh song song + xuất báo cáo | **Chưa có** | không có |
| F3.01 | Talent Pool / rediscovery | **Có code, có consent**; còn bản `-demo` riêng | `api/talent_pool.py`, `api/talent_pool_demo` |
| F3.02 | Đồng bộ ATS/HRIS | **Chưa có** | — |
| F3.03 | Nhận CV đa kênh | **Một phần**: có intake công khai + Gmail **test** | `careers_intake.py`, `gmail_test.py` |
| F3.04 | Lịch phỏng vấn + scorecard | **Xong phần code** (đợt này vừa hoàn thiện) | `interviews.py`, `scorecards.py`, `00039–00041` |
| F3.05 | Thông báo ứng viên bán tự động | **Chưa** — thông báo hiện có là **nội bộ** | `notifications.py` không có khái niệm ứng viên |
| F3.06 | Đa ngôn ngữ đầy đủ | **Một phần**: UI có i18n vi/en; CV/JD chưa | `i18n/` |
| F3.07 | Tìm kiếm ngữ nghĩa nâng cao | **Chưa** — semantic hiện chỉ trong một CV | không có route tìm kiếm |
| F4.01–F4.06 | Analytics dự báo, DEI/anti-bias, cổng ứng viên, chatbot, tích hợp đánh giá năng lực, video CV | **Chưa có** | — |

### 1.1. Điều quan trọng nhất trong bảng này

**Không hạng mục nào ở trên được gọi là "hoàn thành".** Có code ≠ nghiệm thu.
`doc/PENDING_DEPLOYMENT.md` ghi rõ: Phase 1 tạm dừng chờ Production, DEP-01
`CLOSED_SCOPED`, DEP-02 `PARTIAL`, DEP-03/04/05 `BLOCKED`, DEP-06/07/08 `WAITING`.
App **chưa deploy** lần nào kể cả sau khi 00039–00041 đã áp lên Supabase.

### 1.1.b. Trạng thái CI lúc lập kế hoạch (đã sửa xong)

CI đã **đỏ ở mọi lần push từ 19/11 đến 30/11**. Lần xanh cuối trước đó là `db6efa2`.
Nguyên nhân và việc đã làm:

| Lỗi | Gốc | Xử lý |
|---|---|---|
| Job integration chết ở bước áp migration | `00035_purge_test_cv_jd_data` là migration **xoá dữ liệu một lần**, có chốt chặn đòi schema `app_backup_20261119` không migration nào tạo → luôn `RAISE EXCEPTION` trên DB trắng | Loại đúng file đó khỏi bước dựng schema test (CI, không đụng file đã áp) |
| Job unit chết ở ruff | 8 lỗi F401/F841 tích tụ | Sửa hết |
| **82 test tích hợp + 92 test khác chưa từng chạy 11 ngày** | bị che bởi lỗi migration | Chạy lại → lộ 1 bug thật + 2 test lỗi thời, đã sửa |
| **BUG THẬT:** duyệt bộ tiêu chí thứ hai → 500 | `criteria.py` đọc `cv["version_number"]` nhưng SELECT không có cột đó | Thêm cột + test khoá (đã kiểm ngược) |

Sau khi sửa: **CI xanh cả 3 job** tại `5c939df`. Đây là mốc M0 đã đạt phần CI.

Bài học đưa vào `AGENTS.md`: **một job đỏ thì mọi thứ sau nó là vô nghĩa.** CI đỏ
11 ngày nghĩa là 11 ngày không ai biết code có chạy không, trong khi vẫn có 8 commit
được push.

### 1.2. Ba mâu thuẫn cần người quyết, không phải agent tự quyết

1. **F3.05 chưa có, nhưng người dùng đã chốt "email để sau"** cho lịch phỏng vấn.
   Vậy F3.05 = đúng hướng, chưa làm. Cần chốt: khi làm thì làm cho **ứng viên**
   (F3.05) hay chỉ mở rộng thông báo **nội bộ** sang email? Hai phạm vi rất khác nhau.
2. **F2.05 doc nói "phát hiện trùng chéo vị trí", code chỉ làm trong một vị trí.**
   Đây là thiếu sót thật, và vá nó đụng quyền riêng tư (phải so ứng viên giữa các
   vị trí). Cần Privacy/HR quyết trước khi code.
3. **Deploy chưa từng chạy.** Mọi thứ đã xây (kể cả 4 đợt vừa rồi) chưa từng chạy
   trên môi trường đích. Đây là rủi ro lớn hơn mọi hạng mục chưa code.

---

## 2. Năng lực hiện tại của nhóm

- **1 agent đang làm** (agent A) — đã làm 8 commit gần nhất: audit, lịch phỏng vấn,
  thông báo, purge.
- **Thêm 3 agent** ⇒ tổng 4.
- Hạ tầng sẵn có: CI chạy `pytest backend/tests` + `test:i18n` + `test:unit` +
  `type-check` + `lint` + `build`; 66 file test backend; 164 test FE.

### 2.1. Nút thắt thật khi có 4 agent (không phải thiếu người)

| Nút thắt | Vì sao | Ai chịu |
|---|---|---|
| **Một migration tại một thời điểm** | Số thứ tự `00042` là tài nguyên tuần tự; hai agent cùng tạo ⇒ trùng số, phải sửa tay | Người điều phối (A) |
| **Không có môi trường chạy chung** | Chỉ Supabase test `myrymlqdbyqmpynesiwk`, mọi agent cùng áp migration vào **một** DB | A + DevOps |
| **`backend/app/api/__init__.py`, `types/index.ts`, `en.json` là file nóng** | Ai cũng phải sửa; merge conflict gần như chắc chắn | Quy ước: sửa muộn, commit nhỏ |
| **`pytest` hệ thống không dùng được** | Phải `/tmp/venv/bin/pytest`; agent mới sẽ mất thời gian phát hiện | Ghi vào `AGENTS.md` |
| **Test tích hợp không chạy được trên Supabase** | conftest từ chối + fixture TRUNCATE CASCADE | Mỗi agent dựng PostgreSQL cục bộ (§7.1) |
| **Chưa có `AGENTS.md`** | 3 agent mới sẽ tự đoán quy ước (i18n phải dịch thật, test phải kiểm ngược, không sửa migration đã áp) | A viết trước khi mời |

---

## 3. Phân công: 4 agent, 4 luồng không giẫm chân

Nguyên tắc chia: **chia theo tầng dọc đủ mỏng để một agent làm trọn một tính năng**,
không chia theo tầng ngang (người làm DB, người làm API) — cách đó tạo phụ thuộc
chéo và agent phải chờ nhau.

### Luồng A — Nền tảng & phát hành (agent hiện tại giữ)
- Viết `AGENTS.md` (quy ước, bẫy, cách chạy test) — **làm trước tiên, chặn 3 luồng kia**.
- Giữ cổng migration: cấp số `00042+`, review mọi migration.
- Dọn `-demo` (F3.01/F3.03 còn bản demo song song) — quyết định giữ hay bỏ.
- **Deploy lần đầu** + chạy E2E trên môi trường đích.
- Chủ sở hữu `api/__init__.py`, `types/index.ts`, `en.json`, `Sidebar.tsx`.

### Luồng B — Ứng viên & tiếp nhận
- **F3.05** thông báo cho ứng viên (sau khi người dùng chốt phạm vi — xem §1.2).
- **F3.03** hoàn thiện đa kênh: Gmail test → thật.
- **F2.06** OCR ảnh rời / ảnh nhúng DOCX.
- Chủ sở hữu `careers*`, `gmail*`, `notifications*`, `document_processing*`.

### Luồng C — Đo lường & kiểm soát chất lượng
- **F2.03** báo cáo hiệu năng pilot (thời gian, phễu, tỉ lệ qua từng bước).
- **F2.04** lấy mẫu kiểm chất lượng OCR/matching.
- **F4.01** phần analytics dự báo **chỉ đọc**, không đụng luồng quyết định.
- Chủ sở hữu `dashboard.py`, `audit_events` reports, trang phân tích.

### Luồng D — Đa ngôn ngữ & trải nghiệm
- **F3.06** đa ngôn ngữ thật cho CV/JD (hiện chỉ UI có i18n).
- **F2.09** so sánh song song + xuất báo cáo.
- **F4.03** cổng ứng viên tự phục vụ (mảnh nhỏ đầu tiên: tra cứu trạng thái hồ sơ).
- Chủ sở hữu `frontend/src/i18n`, `components/*` mới, `careers` UI.

### Không giao cho ai (và vì sao)
- **F2.08 SSO** — đã chốt tạm treo, chờ IT.
- **F2.05 chéo vị trí** — chờ Privacy/HR (đụng dữ liệu ứng viên giữa vị trí).
- **F3.02 ATS/HRIS** — chờ VinUni cung cấp API/đặc tả.
- **F3.07 semantic search** — chờ dữ liệu và quyết định về phạm vi tìm.
- **F4.02 DEI/anti-bias, F4.04 chatbot, F4.05, F4.06** — chưa có nền (F4.02 cần dữ liệu
  nhãn; chatbot cần chính sách dữ liệu; F4.05/06 cần đối tác/nội dung).

---

## 4. Thứ tự thực hiện (2 tuần — đã đổi theo quyết định số 4)

> Bản đầu của mục này chia 8 tuần và xếp buffer. Người dùng đã bác: 4 agent năng
> lực cao, không cần ưu tiên luồng nào, sẽ xong trong 2 tuần. Mục này giữ lại
> **thứ tự phụ thuộc** (cái nào phải trước cái nào), bỏ phần chia lịch tuần tự.
> Lịch thật nằm ở §7.3 — 4 mốc đồng bộ trong 14 ngày.

### 4.1. Thứ tự bắt buộc (không phải lịch)

Chỉ có ba ràng buộc thật, phần còn lại chạy song song được:

1. **`AGENTS.md` trước mọi thứ.** Không có nó, 3 agent mới sẽ tự đoán quy ước —
   và làm sai những chỗ đã có luật (i18n phải dịch thật, không `"X": "X"`; không
   thêm cột "đã gửi" khi chưa gửi). Việc này mất nửa ngày, chặn cả 3 luồng.
2. **Số migration cấp sau `AGENTS.md`.** Chỉ người điều phối cấp. Luồng B gần như
   chắc chắn cần `00042` (lưu vết thư đã gửi), nên B xin số sớm.
3. **Deploy lần đầu không chặn code mới nhưng chặn "tính là xong".** Bốn agent có
   thể viết song song ngay từ ngày 2; nhưng nếu hết 14 ngày chưa deploy thì cả
   4 luồng vẫn là code chưa từng chạy trên môi trường đích.

### 4.2. Chạy song song được ngay từ ngày 2

| Luồng | Ngày 2–4 | Ngày 5–7 | Ngày 8–10 | Ngày 11–14 |
|---|---|---|---|---|
| **A** | `AGENTS.md`, cấp số migration, dựng staging | Deploy lần đầu | Sửa lỗi từ deploy | E2E, gate |
| **B** | F3.05: chọn nhà cung cấp + lưu vết gửi | F3.05 gửi thật ở chế độ thử | F3.05 bật + F3.03 Gmail | F2.06 OCR ảnh |
| **C** | F2.03 báo cáo phễu | F2.03 UI | F2.04 lấy mẫu kiểm | F4.01 analytics đọc |
| **D** | F3.06 dò ngôn ngữ CV | F3.06 hiển thị song ngữ | F2.09 so sánh song song | F2.09 xuất báo cáo |

Không luồng nào trong bảng này sửa file của luồng khác — đó là lý do chia theo
tầng dọc ở §3. Hai ngoại lệ duy nhất là `api/__init__.py`, `types/index.ts`,
`en.json`; quy ước: **sửa sau cùng trong ngày, commit riêng, nhỏ**.

## 5. Quy ước làm việc 4 agent (đề xuất đưa vào `AGENTS.md`)

1. **Một migration một lần.** Xin số từ A, không tự đặt.
2. **Không sửa migration đã áp.** Đã có tiền lệ đúng ở `00039`/`00040`.
3. **Test phải kiểm ngược:** gỡ dòng sửa, test phải đỏ. Đã có 3 lần bắt được lỗi thật nhờ vậy.
4. **i18n phải dịch thật**, không `"X": "X"`. Test i18n chỉ kiểm key tồn tại, không kiểm giá trị.
5. **File nóng sửa sau cùng, commit nhỏ:** `api/__init__.py`, `types/index.ts`, `en.json`.
6. **Mỗi agent một nhánh**, PR nhỏ, không push thẳng.
7. **Không thêm cột "đã gửi/đã thông báo" khi chưa có cơ chế gửi** — đã có test khoá.
8. **Đo trước khi tối ưu.** Lần tối ưu scorecard: 8 truy vấn/phiếu đo được trước khi sửa.

---

## 6. Quyết định đã chốt (2026-11-30) — thay thế phần câu hỏi

| # | Đã chốt | Hệ quả lên kế hoạch |
|---|---|---|
| 1 | **F3.05 = gửi email cho ứng viên** | Luồng B có việc thật, và phải xây hạ tầng gửi từ đầu (§7) |
| 2 | Chỉ dùng Supabase test `myrymlqdbyqmpynesiwk`; **chỉ 1 người được áp migration**, ai cần thì hỏi | Cổng migration đã có người giữ. **Nhưng test thì không được chạy trên DB đó** (§7.1) |
| 3 | **Mỗi agent một fork**; người dùng là người chia việc và điều phối | Bỏ mô hình PR chung một repo; đổi sang quy trình fork + cherry-pick (§7.2) |
| 4 | **Không cần ưu tiên** — 4 agent năng lực cao, chắc chắn xong trong 2 tuần | Bỏ bảng 8 tuần. Thay bằng 2 tuần có cổng kiểm (§7.3) |

### 6.1. Điều chỉnh quan trọng nhất, rút ra từ câu trả lời số 4

**Nút thắt không phải năng lực agent, mà là việc kiểm chứng.** Bằng chứng ngay
trong đợt rà soát này: CI đã đỏ từ 19/11 và không ai biết. Khi sửa xong, lộ ra
một lỗi làm **tính năng "một vị trí chỉ một bộ tiêu chí hiệu lực" chưa từng chạy
được** — duyệt bộ thứ hai là 500 — và 82 test tích hợp chưa từng chạy suốt 11
ngày. 4 agent viết nhanh gấp 4 thì lượng code chưa từng chạy thật cũng tăng gấp 4.

Vì vậy kế hoạch 2 tuần **không** chia theo "mỗi ngày xong một tính năng". Nó chia
theo **4 mốc đồng bộ**, mỗi mốc trả lời một câu: *cái vừa viết đã chạy thật chưa?*

---

## 7. Bốn điều chỉnh bắt buộc trước khi mời 3 agent

### 7.1. Test KHÔNG được chạy trên Supabase `myrymlqdbyqmpynesiwk`

Đây là điểm tôi phải nói thẳng: `backend/tests/conftest.py` **từ chối** chạy nếu
`TEST_DATABASE_URL` không phải host cục bộ và tên DB không kết thúc `_test`. Nó
còn ghi rõ trong README: fixture sẽ `TRUNCATE app_private.positions CASCADE` và
`TRUNCATE auth.users CASCADE` — **xoá gần như toàn bộ dữ liệu**.

Nghĩa là 174 test tích hợp **không thể** chạy trên Supabase test. Ai đó trỏ vào
đó sẽ bị conftest chặn; nếu vô hiệu hoá conftest để chạy, họ xoá sạch DB. Hai
kết cục đều xấu.

**Cách đúng, và nó miễn phí:** mỗi agent dựng một PostgreSQL cục bộ dùng một lần
(`pgvector/pgvector:pg17`, port riêng, `*_test`), áp migration từ đầu. CI đã làm
đúng thế từ trước — xem job `backend-integration` trong `.github/workflows/ci.yml`.
Không agent nào cần quyền trên Supabase để chạy test.

| Việc | Chạy ở đâu | Ai |
|---|---|---|
| Test đơn vị + ruff + i18n + build | máy agent / CI | cả 4, thoải mái |
| Test tích hợp | **PostgreSQL cục bộ của từng agent** | cả 4, mỗi người một cụm |
| Áp migration lên Supabase | `myrymlqdbyqmpynesiwk` | **chỉ người điều phối** |

### 7.2. Quy trình fork (thay cho PR chung)

1. Agent làm trên fork của mình, nhánh riêng.
2. **CI trên fork phải xanh trước khi xin gộp** — đây là cổng, không phải thủ tục.
   Fork chạy CI được là điều kiện tiên quyết; nếu fork không chạy được CI thì
   phải nói ngay từ đầu thay vì phát hiện giữa tuần.
3. Người điều phối gộp bằng **cherry-pick một commit**, không merge cả nhánh —
   giữ lịch sử tuyến tính và dễ lùi.
4. Commit phải nêu **lý do**, không chỉ việc đã làm (quy ước đang dùng).
5. Migration: agent **không** tự đặt số. Đề xuất nội dung, người điều phối cấp số
   `00042+` và áp.

### 7.3. Hai tuần, 4 mốc đồng bộ (thay bảng 8 tuần)

Mỗi mốc là một buổi kiểm chung. Không đạt mốc thì **dừng nhận việc mới**, không
chạy tiếp — vì nợ chưa kiểm sẽ cộng dồn và mất dấu.

| Mốc | Thời điểm | Câu hỏi phải trả lời được |
|---|---|---|
| **M0** | trước khi mời agent | `AGENTS.md` có chưa? CI trên nhánh chính xanh chưa? Fork chạy được CI chưa? |
| **M1** | hết ngày 4 | Mỗi agent có **một** thứ chạy được đầu-cuối trên DB cục bộ, không phải khung rỗng? |
| **M2** | hết ngày 7 | Đã có ít nhất một luồng chạy trên **Supabase thật** sau khi áp migration? |
| **M3** | hết ngày 10 | Demo được 4 luồng cạnh nhau, không luồng nào làm hỏng luồng khác? |
| **M4** | hết ngày 14 | Deploy lần đầu + E2E. Nếu chưa deploy được thì **2 tuần đó chưa tính là xong** |

### 7.4. Chia lại việc theo 4 quyết định trên

| Luồng | Việc | Ghi chú sau khi chốt |
|---|---|---|
| **A** (điều phối) | `AGENTS.md`, cổng migration, deploy, E2E, dọn `-demo` | Không kiêm tính năng — điều phối 3 người là đủ việc |
| **B** | **F3.05 gửi email ứng viên** → F3.03 Gmail thật → F2.06 OCR ảnh | F3.05 nay là việc lớn nhất: **chưa có hạ tầng gửi email nào** (§8) |
| **C** | F2.03 báo cáo phễu → F2.04 lấy mẫu kiểm → F4.01 analytics | Giữ nguyên |
| **D** | F3.06 đa ngữ CV/JD → F2.09 so sánh + xuất → F4.03 tra cứu | Giữ nguyên |

---

## 8. F3.05: việc lớn hơn tên gọi của nó

Đã kiểm: **repo không có hạ tầng gửi email nào.** Không SMTP, không SendGrid,
không Resend, không `send_email` — chỉ có:
- `services/email_demo.py`: docstring ghi *"Offline MIME routing demonstration.
  Never contacts a mailbox"* — chỉ phân tích MIME, không gửi.
- `services/gmail_test_client.py`: client Gmail **test**.

Nên F3.05 không phải "thêm một thông báo". Nó là: chọn nhà cung cấp → quản lý
khoá → mẫu thư + bản dịch → xử lý thư trả về/hỏng → **đồng ý nhận thư** → ghi
nhật ký đã gửi. Và có ràng buộc pháp lý: gửi thư cho ứng viên là xử lý dữ liệu
cá nhân, phải có căn cứ và phải rút được.

Ba điều bắt buộc, rút từ lỗi cũ:
1. **Không thêm cột `sent_at`/`delivered` trước khi có cơ chế gửi thật** — đã có
   test khoá điều này.
2. **Không báo "đã gửi" khi chưa gửi** — đúng loại lỗi vừa tìm thấy ở `criteria.py`:
   ghi vào audit một giá trị chưa từng được nạp.
3. **Gửi hỏng phải thấy được**, không im lặng nuốt lỗi.

---

## 9. Điều còn chưa biết (thay cho §6 cũ)

1. **Fork có chạy được CI không?** Nếu không, cả quy trình §7.2 sụp. Cần biết
   trước M0.
2. **Nhà cung cấp email nào?** Chưa chốt thì luồng B bắt đầu bằng một quyết định
   hạ tầng, không phải code.
3. **Ai duyệt nội dung thư gửi ứng viên?** Thư gửi ra ngoài không thể thu hồi.
