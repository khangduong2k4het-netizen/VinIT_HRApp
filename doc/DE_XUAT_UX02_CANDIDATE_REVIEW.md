# Đề xuất UX-02 — Candidate Review: HR đọc, xác minh và ra quyết định

- Ngày lập: 2026-11-19. Nhánh `arena/ea6e2570-vinit-hrapp`, sau commit `a1642d9`.
- Trạng thái: **chờ anh duyệt. Chưa sửa một dòng code nào.**
- Phạm vi đọc: chỉ màn hồ sơ ứng viên và những gì nó gọi tới. Không đổi màn Ranking, Dashboard.

---

## 0. Vì sao phải nói rõ "UX-02" là việc gì

Trong hội thoại GPT (đã đúc kết ở `doc/DE_XUAT_UI_UX_TU_GPT.md`), **UX-02 = "bộ lọc nhanh + số lượng"** — hạng mục đó **đã xong từ lâu** và đã đóng. Nhưng trong chỉ đạo mới nhất của anh, **UX-02 = Candidate Review** (đọc, xác minh bằng chứng, đối chiếu tiêu chí, xem CV), và UX-03/UX-04 cũng mang nghĩa anh đặt lại: Dashboard, rồi Visual polish.

Em theo **cách đánh số của anh**, và ghi lại đây để sau này không ai đọc `DE_XUAT_UI_UX_TU_GPT.md` rồi tưởng việc đã làm rồi. Từ mục 1 trở đi, "UX-02" chỉ có một nghĩa: màn Candidate Review.

---

## 1. Hiện trạng: những gì đã tốt, và cái gì thật sự chặn HR

### 1.1 Đã tốt, không nên đụng

Màn này không phải "chưa tối ưu" theo nghĩa xấu. Nó đã có nhiều thứ đúng mà màn khác phải mất công mới có:

| Đã có | Ghi nhận |
| --- | --- |
| Ba số quyết định ở dải đầu (điểm / độ phủ / số tiêu chí) | Đọc được ngay trong màn đầu, không phải cuộn |
| Mỗi tiêu chí một thẻ, có trích dẫn nguyên văn + số trang | Đúng yêu cầu "không được bịa"; trích dẫn là thứ kiểm chứng được |
| Trích dẫn ghi rõ "Đã xác minh" / "Trích dẫn chưa xác minh" | Trung thực. Không giả vờ chắc chắn |
| Tiêu chí `UNCLEAR` có câu "Không tìm thấy bằng chứng rõ ràng. Vui lòng kiểm tra CV" | Đúng hướng dẫn HR |
| CV **không** tải khi mở trang, chỉ tải khi HR bấm "Xem CV gốc" | Đo được: 0 request `cv-file` khi mở, 1 request sau khi bấm. Việc này đã xong (mục 3.4 trong đề xuất cũ) |
| Prev/Next mang theo `queue/sort/q` | Điều hướng liên tiếp không mất ngữ cảnh |
| Bố cục 2 cột: bằng chứng trái, CV phải | Đúng cách HR đối chiếu |

Ghi chú này quan trọng: **ba màn Ranking → Dashboard → Candidate Review không cùng mức trưởng thành.** Ranking vừa được R6 làm gọn. Candidate Review đã có "xương sống" nghiệp vụ đúng. Vấn đề của nó **không phải bố cục**, mà là **vòng làm việc chưa khép kín**.

### 1.2 Số đo trên app thật (production build, fixture cố định)

Đo bằng `frontend/tests/review-metrics.cjs` (mới, chạy được, chưa gắn CI):

| Chỉ số | 1440×900 | 820×1180 | 390×844 |
| --- | --- | --- | --- |
| Thẻ tiêu chí đầu tiên bắt đầu ở | **511px** | 519px | **873px** |
| Số thẻ tiêu chí **trọn vẹn** trong màn đầu | **1** | 2 | **0** |
| Chiều cao trang | 1777px | 2719px | 3116px |
| Bảng CV bắt đầu ở | 477px | 1580px | 2321px |
| Cuộn ngang | không | không | không |

Ở desktop 900px, HR thấy **một** thẻ tiêu chí trọn vẹn. Ở mobile, thẻ đầu nằm **dưới** màn hình và bảng CV nằm sau **2.321px** nội dung khác. Nhưng đây chỉ là triệu chứng — nguyên nhân ở mục 1.3.

### 1.3 Phát hiện làm thay đổi đề xuất: HR **không có chỗ nào để ghi lại kết quả xác minh**

Em kiểm tra cả ba tầng, không suy đoán:

**a) Không có API nào ghi quyết định xác minh.**
Toàn bộ endpoint của `applications.py` và `assessments.py` chỉ có: upload, reprocess, **đổi `application_status`**, chạy đánh giá, chạy xếp hạng. **Không** endpoint nào cập nhật `evidence_items.verification_status`, **không** endpoint nào cập nhật `criterion_assessment_results.requires_hr_verification`.

**b) Không có chỗ chứa quyết định đó trong schema.**
`evidence_items.verification_status` có 4 giá trị `PENDING | VERIFIED | FAILED | MANUAL_FIX`, nhưng **chỉ worker ghi** (`processor.py:1533`) — tức chỉ hệ thống tự đặt `VERIFIED`/`FAILED`. Không có bảng nào cho quyết định của HR trên từng tiêu chí.

**c) Trên màn hình cũng không có nút nào.** Liệt kê toàn bộ điều khiển của trang chi tiết: `Tải CV gốc`, `Xem CV gốc`, `Trang trước/sau`, `Hồ sơ trước/tiếp theo`, `Cập nhật trạng thái`, `Chỉnh sửa profile`, `VI/EN`. Không một nút nào ghi "tôi đã kiểm và trích dẫn này đúng/sai".

**Hệ quả nghiệp vụ — đây là phần quan trọng nhất của tài liệu này:**

- Hàng đợi **"Cần xác minh"** được tính từ `matching_status` và `evidence_coverage`, tức từ **kết quả máy**. HR kiểm xong, đọc xong, quyết xong — nhưng **hàng đợi không đổi**. Hồ sơ vẫn nằm đó ở lần tải lại sau.
- **Shortlist cũng không làm nó rời hàng đợi.** Em đã kiểm cả hai tầng: `SCREENING_APPLICATION_STATUSES = ("NEW", "IN_REVIEW", "SHORTLIST")` ở `workspace.py:30`, và `needsVerification()` bên frontend yêu cầu `inScreening(status)` — mà `SHORTLIST` nằm trong danh sách đang sàng lọc. Nên một hồ sơ đã shortlist **vẫn hiện trong "Cần xác minh"** và vẫn còn trong bảng xếp hạng (`WHERE application_status IN ('NEW','IN_REVIEW','SHORTLIST')`).
- Vậy **đường duy nhất** để một hồ sơ rời hàng đợi Cần xác minh là **loại hồ sơ** (`REJECTED_SCREENING`) hoặc **đẩy sang phỏng vấn** (`INTERVIEW`). Nói thẳng: **để dọn một hàng đợi kỹ thuật, HR buộc phải ra một quyết định tuyển dụng.** Đây không phải bất tiện nhỏ — nó **bóp méo dữ liệu tuyển dụng**, vì trạng thái hồ sơ sẽ phản ánh "cái gì dọn được hàng đợi" chứ không phải "ứng viên này thực sự thế nào".
- Kết quả thực tế chỉ có hai lối, cả hai đều xấu: HR để hàng đợi phình mãi rồi **mất niềm tin vào con số trên Dashboard**, hoặc HR loại/đẩy hồ sơ cho xong cho sạch màn hình.

Nói cách khác: màn này hiện là **màn đọc**. Nó chưa phải **màn làm việc**. Đó là lý do nếu chỉ sửa bố cục, HR sẽ thấy đẹp hơn nhưng **không nhanh hơn và không ít nhầm hơn** — tức là không đạt đúng mục tiêu anh đặt.

### 1.4 Ba lỗi cụ thể, tái hiện được, không cần suy luận

**(1) Trích dẫn "Đã xác minh" bấm không được cho tới khi HR tải CV — mà không ai nói vậy.**
`EvidenceCard` chỉ cho trích dẫn thành nút bấm khi `verified && page && isPdf && hasCv`. Nhưng CV lại tải lười (đúng, nên giữ). Kết quả: **thẻ ghi "Trang 2 · Đã xác minh" nhưng bấm vào không có phản ứng gì.** Đo được: bấm trích dẫn khi chưa tải CV → **0** request, không có `role="button"`; sau khi bấm "Xem CV gốc" thì cùng trích dẫn đó mới thành nút. Con số trang vẫn hiện, nên HR hiểu là "bấm được". Đây là **lời hứa suông trên UI** đúng nghĩa.

**(2) Màn Review không hiển thị yêu cầu gốc của tiêu chí.**
Đo được: trang chi tiết **không** gọi endpoint criteria nào (chỉ `auth/me`, `applications/app-2`, `ranking/latest`, `applications`, `status-events`, `profile`). API `GET /v1/assessments/{id}` trả `criterion_name`, `category`, `outcome`, `score`, `reasoning`, `evidence` — **không** trả `description`, `evidence_guidance`, `jd_reference_text`, dù `criteria_items` và `CriteriaVersion` đều có ba trường này (và `GET /criteria/position/{id}/approved` trả được).

Hệ quả: HR được yêu cầu "đối chiếu tiêu chí", nhưng chỉ thấy **tên tiêu chí** ("Kinh nghiệm dẫn nhóm kỹ thuật nhỏ") và **kết luận của máy**. Muốn biết tiêu chí này thực sự đòi gì — bao nhiêu năm, quy mô nhóm nào, bằng chứng nào được tính — HR phải **rời màn hình** sang trang rubric. Và khi quay lại thì mất chỗ đang đọc. Đây là lỗ hổng lớn nhất về mặt "đối chiếu tiêu chí" mà anh nêu.

**(3) Không phân biệt "máy chưa chắc" với "máy chắc nhưng sai".**
Trích dẫn `FAILED` (không tìm thấy trong văn bản gốc) và `PENDING` (chưa kiểm) đang được **gộp chung** thành một nhãn "Trích dẫn chưa xác minh" màu cam. Hai chuyện rất khác nhau về mức độ tin cậy. Đo trên fixture: 4 thẻ có **2** trích dẫn chưa xác minh, không phân biệt được loại nào.

### 1.5 Hai điểm về khả năng tiếp cận, đo bằng bàn phím

- **Thứ tự tab đi qua 11 điểm dừng trang trí trước khi tới nội dung.** Tab 1→11: `Tổng quan công việc`, `Vị trí tuyển dụng`, `Gmail thử nghiệm`, `Email offline`, `Talent Pool`, `Talent Pool (demo)`, `Thư viện rubric`, `Shortlist & phản hồi`, `VI`, `EN`, `N` — rồi mới tới `Quay lại danh sách`. Người dùng bàn phím phải bấm 11 lần mỗi lần mở hồ sơ. (Đây là khung chung của app, không riêng màn này, nhưng màn này là nơi tốn nhất vì HR mở hàng chục hồ sơ một ngày.)
- **Nhãn "Điểm trên tiêu chí đã có bằng chứng"** dễ bị đọc thành "điểm chỉ tính trên tiêu chí đã có bằng chứng" — trong khi nó là điểm tổng hợp của cả lần đánh giá. Nhãn này không sai về kỹ thuật nhưng dễ gây hiểu nhầm về bản chất con số.

---

## 2. Bảng đề xuất — xếp theo giá trị/công sức, và cái gì **không** làm

Đây là bảng để anh duyệt từng dòng. Cột "Đổi API?" quyết định phạm vi: **U1–U4 thuần frontend**, **U5–U6 chạm backend**.

| Mã | Việc | Vấn đề nó giải | Đổi API? | Công sức | Giá trị | Rủi ro |
| --- | --- | --- | --- | --- | --- | --- |
| **U1** | **"Đã kiểm trích dẫn này"** — nút ngay trong từng thẻ tiêu chí, ghi nhận HR đã đối chiếu, kèm ghi chú tuỳ chọn | Hàng đợi Cần xác minh không bao giờ đóng được (1.3) | **Có** — 1 bảng + 1 endpoint | **L** | **Rất cao** | Trung bình: đụng migration, cần audit |
| **U2** | **Hiện yêu cầu gốc của tiêu chí** ngay trên thẻ (mô tả + hướng dẫn bằng chứng), thu gọn 1 dòng, bấm mới mở | HR phải rời màn hình sang rubric (1.4-2) | Không (endpoint criteria đã có) | **M** | **Rất cao** | Thấp |
| **U3** | **Bấm trích dẫn là tải CV và nhảy đúng trang**, kèm chữ "Bấm để mở trang N trong CV" | Lời hứa suông "Đã xác minh" (1.4-1) | Không | **S** | **Cao** | Thấp |
| **U4** | **Tách "chưa kiểm" khỏi "kiểm không thấy"**; đổi nhãn điểm thành "Điểm tổng hợp (…)"; bỏ 11 điểm dừng tab trang trí khỏi luồng bàn phím | Gộp hai mức tin cậy; hiểu nhầm con số; phí 11 lần Tab (1.4-3, 1.5) | Không | **S** | **Trung bình–cao** | Thấp |
| **U5** | **Dải "việc tiếp theo" trên đầu mỗi thẻ**: tiêu chí này cần gì để đóng — "cần HR xác minh" / "CV không có bằng chứng" / "đã đủ" | HR phải tự suy từ 3 nhãn chip | Không (dữ liệu đã có) | **M** | **Cao** | Thấp |
| **U6** | **Danh sách tiêu chí thu gọn bên trái + thẻ chi tiết**: nhìn được cả 6 tiêu chí trong 1 màn, bấm để nhảy | Chỉ thấy 1 thẻ trọn vẹn (1.2) | Không | **L** | Trung bình | **Cao**: đụng CV viewer, ghi chú, lịch sử |

**Đề xuất thứ tự làm:** **U2 → U3 → U4 → U1 → U5**, và **hoãn U6**.

Lý do thứ tự này, không theo bảng giá trị:

1. **U2 và U3 trước** vì thuần frontend, không migration, và sửa đúng hai lỗi "HR đang bị lừa / đang bị bắt đi vòng". Làm xong hai việc này là HR đã **đối chiếu được tiêu chí và kiểm được bằng chứng ngay trong một màn** — đúng câu anh nói, mà không cần đổi nghiệp vụ.
2. **U4 ngay sau** vì rẻ và làm cho U2/U3 dễ đọc hơn (tách nhãn trước khi thêm nút).
3. **U1 sau cùng trong nhóm bắt buộc** vì nó là việc **duy nhất đổi backend**. Em muốn anh duyệt riêng nó, có bảng dữ liệu và câu chuyện audit rõ ràng, chứ không lẫn vào một đợt UI.
4. **U6 hoãn** — không phải vì khó, mà vì nó là **bố cục lại**, và nếu U2/U3/U5 làm đúng thì nhu cầu "thấy cả 6 tiêu chí một lúc" giảm hẳn. Làm U6 trước là tối ưu cái chưa đo được.

**Những việc em đề nghị KHÔNG làm trong UX-02:**

| Không làm | Vì sao |
| --- | --- |
| **Drawer / split view** (UX-04 cũ của GPT) | Ảnh hưởng CV viewer, ghi chú HR, lịch sử, phân quyền — đúng như GPT tự kết luận. Và nó **không** giải quyết vấn đề thật (1.3) |
| **Đổi màu / làm lại thẻ cho đẹp** | Không làm HR nhanh hơn hay ít nhầm hơn. Để dành cho UX-04 (visual polish) |
| **Tự động duyệt / tự đóng hàng đợi** | Sẽ là máy quyết thay HR. Trái nguyên tắc "không suy diễn nghiệp vụ từ dữ liệu thiếu" |
| **Đưa điểm số lên đầu to hơn** | Điểm đã ở dải đầu. Vấn đề là HR cần biết **vì sao**, không phải thấy số to hơn |
| **Sửa ngưỡng `WAITING_ATTENTION_DAYS = 7` trong UX-02** | Đây là nợ kỹ thuật đã biết (ngưỡng đã cấu hình được trong Settings nhưng màn Ranking còn hard-code). Việc nhỏ, nhưng **khác màn** — nên làm ở UX-03 hoặc một đợt riêng, không trộn vào đây |

---

## 3. Chi tiết U1 — việc duy nhất đổi backend, cần anh duyệt riêng

Em đưa lên đây vì nó là **quyết định nghiệp vụ**, không phải kỹ thuật.

### 3.1 Câu hỏi cần anh trả lời trước

> Khi HR đã kiểm một trích dẫn và thấy nó đúng, hồ sơ có nên **rời** hàng đợi "Cần xác minh" không?
>
> (a) **Rời ngay** — hàng đợi là "việc chưa làm", làm xong thì biến mất.
> (b) **Ở lại nhưng đổi dấu** — hiện "đã kiểm 2/4 tiêu chí", chỉ rời khi HR xác nhận toàn bộ.
> (c) **Rời khi mọi tiêu chí `requires_hr_verification` đã được kiểm** — kết hợp hai cái trên.

Em nghiêng **(c)**: nó trung thực nhất với dữ liệu (một hồ sơ có 4 tiêu chí thì kiểm 1 cái chưa phải xong), và vẫn cho HR thấy tiến độ. Nhưng đây là **anh quyết**, vì nó đổi ý nghĩa con số trên Dashboard.

### 3.2 Dữ liệu đề xuất (tối thiểu)

```sql
-- 00034_hr_evidence_reviews.sql
CREATE TABLE app_private.hr_evidence_reviews (
    review_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    criterion_result_id UUID NOT NULL REFERENCES app_private.criterion_assessment_results(result_id) ON DELETE CASCADE,
    reviewer_user_id UUID NOT NULL REFERENCES app_private.user_profiles(user_id),
    decision TEXT NOT NULL CHECK (decision IN ('CONFIRMED', 'REJECTED')),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (criterion_result_id, reviewer_user_id, created_at)  -- giữ lịch sử, không ghi đè
);
```

Không sửa `evidence_items.verification_status` — đó là **kết quả của máy**, không được để HR ghi đè. Quyết định của HR là **một lớp riêng**, có người, có giờ, có lý do. Đây là điểm quan trọng: nếu ghi đè `verification_status`, sau này không ai phân biệt được "máy xác minh" và "HR xác nhận", và audit mất giá trị.

### 3.3 API

- `POST /v1/assessments/results/{result_id}/review` — body `{decision: 'CONFIRMED'|'REJECTED', comment?}`. Ghi `audit_events` với `action_type='HR_EVIDENCE_REVIEW'`, kèm `criterion_result_id` và `assessment_id`.
- `GET /v1/assessments/{id}` trả thêm `hr_reviews[]` cho từng `criterion_result` (đã có sẵn chỗ trong response).
- **Chỉ người có quyền HR trên vị trí đó** (dùng lại `_require_hr_locked` sẵn có ở `candidate_details.py`), không phải ADMIN-only.

### 3.4 Nghiệm thu U1

- Kiểm 1 trong 4 tiêu chí → hồ sơ hiện "đã kiểm 1/4"; kiểm đủ 4 → **rời hàng đợi** và **vẫn giữ nguyên `application_status`** (đây là điểm mấu chốt: xác minh bằng chứng **không được** là lý do đổi trạng thái tuyển dụng).
- Kiểm lại lần hai → **có ghi thứ hai**, không ghi đè, không lỗi.
- Người không có quyền HR trên vị trí → **403**, không lộ dữ liệu.
- Audit có `HR_EVIDENCE_REVIEW` kèm người + giờ + quyết định; `verification_status` của máy **không đổi**.

### 3.5 Rủi ro và cách giảm

| Rủi ro | Giảm thế nào |
| --- | --- |
| HR bấm "đã kiểm" cho xong, không đọc | Bắt buộc comment khi chọn `REJECTED`; không cho bấm khi chưa từng mở trích dẫn (đếm `evidence_viewed` ở client — yếu, nhưng có) |
| Con số Dashboard đổi nghĩa | Ghi rõ trong README của metric: "Cần xác minh = việc **chưa kiểm**, không phải 'máy chưa chắc'" |
| Migration trên VPS | `00033` còn chưa chạy ở VPS. Nếu duyệt U1, sẽ gộp `00033`+`00034` vào một lần deploy, không deploy hai lần |

---

## 4. Chi tiết ba việc thuần frontend (U2, U3, U4)

### U2 — Hiện yêu cầu gốc của tiêu chí (làm đầu tiên)

**Thay đổi.** Mỗi thẻ tiêu chí thêm một dòng gập được ngay dưới tên tiêu chí:

```
Kinh nghiệm dẫn nhóm kỹ thuật nhỏ                    Chưa rõ · Ưu tiên
▸ Yêu cầu gốc của tiêu chí
  (mở ra) Tối thiểu 1 năm dẫn dắt nhóm từ 3 người; có ví dụ cụ thể về
  phân công và review code. Bằng chứng cần: tên nhóm, quy mô, thời gian.
  Trích JD: "Experience leading a small engineering team"
```

**Dữ liệu lấy từ đâu.** Gọi `GET /v1/criteria/position/{position_id}/approved` **một lần** cho cả trang (không phải mỗi thẻ một lần), map theo `criterion_id`. Endpoint đã có, đã trả `description`, `evidence_guidance`, `jd_reference_text`, `specific_requirement_spec`. **Không đổi backend.**

**Vì sao gập mặc định.** Mở sẵn cả 6 thẻ sẽ làm trang dài thêm ~120px và đẩy CV xuống — đúng lỗi R6 vừa sửa. Gập mặc định giữ nguyên chiều cao, ai cần thì mở. Nhưng **phải nhìn thấy là có** (dòng `▸` có nhãn rõ), không giấu trong tooltip — theo đúng quyết định Q2 của anh.

**Nghiệm thu.** Mở hồ sơ → 6 thẻ đều có dòng "Yêu cầu gốc của tiêu chí"; mở ra thấy đúng mô tả của tiêu chí đó (không lẫn tiêu chí khác); chiều cao trang **không tăng** khi tất cả đang đóng; bàn phím mở/đóng được; chỉ **1** request criteria cho cả trang.

### U3 — Bấm trích dẫn là tải CV và nhảy đúng trang

**Thay đổi.** Trích dẫn trong thẻ **luôn là nút bấm** (khi CV tồn tại), kể cả lúc CV chưa tải. Nhãn nói đúng việc sẽ xảy ra:

- CV chưa tải: `Trang 2 · Đã xác minh — bấm để mở trong CV`
- CV đã tải: `Trang 2 · Đã xác minh` (như hiện nay)

Bấm → gọi `loadCv()` rồi `jumpToPage(page)` sau khi CV sẵn sàng. Nếu CV không xem được (không có quyền), giữ nguyên trạng thái không bấm và nói rõ "Bạn không có quyền xem CV gốc".

**Vì sao đây là lỗi chứ không phải tính năng.** Hiện tại thẻ nói "Trang 2 · Đã xác minh" nhưng bấm **không có gì xảy ra**. Người dùng không thể biết là do chưa tải CV hay do trích dẫn hỏng. Sửa lỗi này đồng thời làm CV tải **đúng lúc HR thật sự cần** — giữ nguyên nguyên tắc tải lười.

**Nghiệm thu.** Mở hồ sơ, **0** request `cv-file`; bấm trích dẫn → **1** request, CV mở đúng trang, thẻ đó được highlight; bấm trích dẫn của thẻ khác → không tải lại file, chỉ nhảy trang; e2e kiểm cả hai trạng thái nhãn.

### U4 — Ba chỉnh nhỏ, cùng một chủ đề "nói đúng mức tin cậy"

1. **Tách nhãn trích dẫn:** `FAILED` → "Không tìm thấy trong CV" (đỏ, nặng); `PENDING` → "Chưa đối chiếu" (xám, nhẹ); `VERIFIED`/`MANUAL_FIX` → giữ "Đã xác minh". Ba màu, ba nghĩa.
2. **Đổi nhãn điểm** thành "Điểm tổng hợp" + caption "trên 4 tiêu chí, 2 có trích dẫn đã xác minh" — để con số 69% không bị hiểu là "chỉ tính tiêu chí có bằng chứng".
3. **Bỏ 11 điểm dừng tab trang trí**: sidebar và switcher ngôn ngữ dùng `tabIndex={-1}` + skip-link "Tới nội dung chính" ở đầu trang. Đây là sửa ở layout dùng chung nên **ảnh hưởng mọi màn** (theo hướng tốt), và cần chạy lại `a11y-mock` cho toàn bộ.

**Nghiệm thu.** Mỗi loại trích dẫn có nhãn và màu riêng, có e2e; Tab từ đầu trang tới nội dung chính trong **≤ 2** lần bấm; skip-link hiện khi focus; `a11y-mock` vẫn xanh.

---

## 5. U5 — "việc tiếp theo" trên mỗi thẻ (sau U1)

Mỗi thẻ có **một câu hành động**, không phải ba nhãn chip để HR tự ghép:

| Tình huống dữ liệu | Câu trên thẻ |
| --- | --- |
| `requires_hr_verification = true`, có trích dẫn `VERIFIED` | "Đối chiếu trích dẫn với CV trang 2, rồi xác nhận" |
| `UNCLEAR`, không có trích dẫn | "CV không nêu tiêu chí này — cần hỏi thêm khi phỏng vấn" |
| `NO_MATCH`, trích dẫn `FAILED` | "Máy tìm không thấy trong CV — kiểm tra thủ công trước khi kết luận" |
| `STRONG_MATCH`/`MATCH`, trích dẫn `VERIFIED` | "Đã đủ bằng chứng — không cần làm gì" |

Đây là chỗ **không được** để AI tự đoán: câu này suy ra từ **dữ liệu có thật** (outcome + verification_status + có trích dẫn hay không), theo bảng cố định, không gọi thêm LLM. Nếu dữ liệu rơi vào tổ hợp chưa có trong bảng, hiện câu trung tính "Xem trích dẫn và CV để kết luận", **không bịa**.

---

## 6. Kế hoạch kiểm và bằng chứng

| Việc | Cách kiểm | Hiện có chưa |
| --- | --- | --- |
| Số đo trước/sau | `frontend/tests/review-metrics.cjs` (đã viết, đã chạy được) | **Có**, chưa gắn npm script |
| U2 không làm trang dài thêm | đo `pageHeight` + `firstCardTop` trước/sau, yêu cầu **không tăng quá 8px** | sẽ thêm vào script trên |
| U3 tải đúng lúc | đếm request `cv-file`: 0 khi mở, 1 khi bấm trích dẫn | sẽ thêm |
| U4 nhãn ba loại | e2e mở hồ sơ có đủ 3 loại trích dẫn, kiểm nhãn + màu | sẽ thêm fixture |
| U1 hàng đợi giảm | integration test Postgres: kiểm 1 tiêu chí → đếm lại work queue | sẽ thêm |
| Không hồi quy | chạy đủ **11/11** bộ e2e + unit + i18n + tsc/lint + backend | quy trình đã có |

Ảnh before/after cho từng mục, cùng `review-metrics.json`, đóng gói như `doc/ui-review/r6-review-for-gpt.zip` để anh và GPT xem.

---

## 7. Câu hỏi cần anh trả lời để em bắt đầu

**Q1 (quan trọng nhất — quyết định phạm vi).** Anh có duyệt **U1** (thêm chỗ ghi nhận HR đã xác minh) không? Nếu **không**, UX-02 chỉ còn U2–U5: HR đọc và đối chiếu tốt hơn, nhưng **hàng đợi Cần xác minh vẫn không đóng được**, và đường duy nhất để đóng vẫn là **loại hồ sơ hoặc đẩy sang phỏng vấn**. Em phải nói thẳng: khi đó màn Review đẹp hơn nhưng **vẫn ép HR ra quyết định tuyển dụng để dọn hàng đợi** — đúng thứ anh dặn phải tránh.

**Q2.** Nếu duyệt U1: chọn **(a) rời hàng đợi ngay**, **(b) ở lại kèm tiến độ**, hay **(c) rời khi đã kiểm hết tiêu chí cần xác minh**? Em nghiêng (c).

**Q3.** Thứ tự em đề xuất là **U2 → U3 → U4 → U1 → U5**, hoãn U6. Anh muốn đổi không? (Nếu anh muốn thấy kết quả nhanh, U2+U3+U4 gọn trong một đợt; U1 cần thêm một đợt vì có migration.)

---

## 8. Nếu anh duyệt ngay, em làm gì trong đợt đầu

1. **U2** — gọi criteria 1 lần/trang, thêm khối "Yêu cầu gốc của tiêu chí" gập được, đúng phong cách "Cách đọc danh sách" vừa làm ở R6. Test: chiều cao không tăng, 1 request, bàn phím.
2. **U3** — trích dẫn luôn bấm được, nhãn nói đúng việc sẽ xảy ra, tải CV rồi nhảy trang. Test: đếm request, nhãn hai trạng thái.
3. **U4** — ba nhãn trích dẫn, đổi nhãn điểm, skip-link + bỏ tab trang trí. Test: a11y toàn bộ.
4. Chụp before/after, đo lại, chạy **11/11** bộ e2e, rồi báo anh trước khi sang **U1**.
