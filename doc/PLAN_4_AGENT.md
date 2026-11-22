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
| **`pytest` hệ thống không dùng được** | Phải `/tmp/venv/bin/pytest`; agent mới sẽ mất thời gian phát hiện | Ghi vào `README`/AGENTS |
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

## 4. Thứ tự thực hiện (8 tuần, 4 agent)

Giả định mỗi agent ~1 tính năng vừa / 3–5 ngày. **Tuần 1 là bắt buộc tuần tự.**

| Tuần | A (nền tảng) | B (ứng viên) | C (đo lường) | D (ngôn ngữ/UX) |
|---|---|---|---|---|
| 1 | `AGENTS.md`, cổng migration, deploy thử | chờ (đọc AGENTS, làm F3.05 khảo sát) | chờ | chờ |
| 2 | Deploy + E2E | F3.05 backend (thông báo ứng viên) | F2.03 báo cáo phễu | F3.06 khảo sát CV/JD đa ngữ |
| 3 | Sửa lỗi từ E2E | F3.05 UI + chính sách | F2.03 UI | F2.09 so sánh song song |
| 4 | Dọn `-demo` | F3.03 Gmail thật | F2.04 lấy mẫu kiểm | F2.09 xuất báo cáo |
| 5 | Hỗ trợ + review | F2.06 OCR ảnh | F2.04 UI | F3.06 CV/JD đa ngữ |
| 6 | Review + gate | F2.06 hoàn thiện | F4.01 analytics đọc | F4.03 tra cứu trạng thái |
| 7 | Gate nghiệm thu | Buffer | Buffer | Buffer |
| 8 | Deploy cuối | — | — | — |

Tuần 7 là buffer **cố ý**, không phải thời gian rảnh: với 4 agent sửa cùng repo,
một tuần buffer là mức tối thiểu để hấp thụ conflict và lỗi tích hợp.

---

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

## 6. Điều tôi chưa biết, cần người dùng trả lời

1. **F3.05 phạm vi**: thông báo cho ứng viên, hay mở rộng thông báo nội bộ sang email?
2. **Deploy**: có môi trường staging thật ngoài Supabase test không? Nếu không, 4 agent
   cùng áp migration vào một DB là rủi ro.
3. **3 agent mới là ai**: có cùng quyền commit vào repo này không, hay mỗi agent một
   fork? Điều này quyết định cách chia nhánh.
4. **Ưu tiên**: nếu chỉ làm được 2 luồng trong 8 tuần, chọn luồng nào?
