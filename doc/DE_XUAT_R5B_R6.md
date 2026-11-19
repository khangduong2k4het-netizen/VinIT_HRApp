# Đề xuất UX-R5 mức B và UX-R6 — cần anh duyệt trước khi làm

Tài liệu này trả lời đúng câu hỏi: *"cụ thể là gì, đề xuất như thế nào"*. Mọi con số dưới đây đo trên production build, viewport 1440×900, fixture mock cố định (`frontend/tests/fixtures/hr-screens.cjs`).

Trạng thái hiện tại: nhánh `arena/ea6e2570-vinit-hrapp`, HEAD `331478e`. R1–R5 (mức A) đã xong, CI **44457927230** xanh.

---

## Phần 1 — R5 mức B: "áp lực thời gian" trên Dashboard

### 1.1 Mức A đang làm được gì, và chưa được gì

Mức A (đã làm) đọc `created_at` mà API **trang xếp hạng** đã trả về, nên chỉ hiện được tuổi hồ sơ **trong danh sách ứng viên**:

```
Nguyễn Minh Anh   [Đang xem] [Cần HR xác minh]  Chờ 34 ngày
```

Điều đó **không** giải quyết được yêu cầu gốc của GPT ("Dashboard nổi bật việc quá hạn/sắp hạn"), vì hai lý do kỹ thuật đã kiểm:

1. `_APPLICATIONS_QUERY` (`backend/app/api/dashboard.py:42-84`) **không select `a.created_at`** — đã grep tách riêng để chắc chắn: chuỗi `created_at` duy nhất trong câu query là `ar.created_at` trong subquery chọn lần đánh giá mới nhất, không phải ngày nhận hồ sơ. Payload của `/dashboard/work-queue` **không có** dấu thời gian nào của hồ sơ.
2. `WorkQueueItem` (`frontend/src/types/index.ts:62-72`) chỉ có `priority`, `count`, `target` — không có `due_at`, không có `age_days`.

Nên "mức A cho Dashboard" **không tồn tại**: muốn có, buộc phải đổi payload. Đó chính là mức B.

### 1.2 Phát hiện làm thay đổi đề xuất: "quá hạn" chỉ có một nghĩa thật

Em đã kiểm ba nguồn thời gian:

| Nguồn | Có dữ liệu? | Đang được dùng? |
| --- | --- | --- |
| `scorecards.due_at` | Có | **Rồi** — khối "Nhắc hạn scorecard" trên Dashboard, có cả `overdue_count` / `due_soon_count` |
| `positions.application_deadline_at` | Có, đã validate | Chỉ dùng ở Careers (ẩn vị trí hết hạn) và form tạo/sửa vị trí |
| Tuổi hồ sơ (`applications.created_at`) | Có | Chưa lên Dashboard |

Và **hạn ứng tuyển đã qua là điều kiện chặn nộp hồ sơ**, không phải gợi ý:

- `backend/app/api/careers_intake.py:104` → `status != 'OPEN' or not eligible` ⇒ `404 "Vị trí không còn nhận hồ sơ"`
- `backend/app/api/careers_demo.py:98` → cùng luật

Nghĩa là: vị trí `OPEN` mà `application_deadline_at < now()` **vẫn tính là "vị trí đang mở"** trên KPI card, vẫn chiếm chỗ trong quy trình, nhưng **không nhận thêm được hồ sơ nào**. Không có màn nào của HR nói cho họ biết điều đó.

Đây là lý do em **đổi thứ tự ưu tiên**: hạn ứng tuyển (mục B1) quan trọng hơn tuổi hồ sơ (mục B2), dù ban đầu em xếp ngược.

### 1.3 B1 — Cảnh báo hạn ứng tuyển (khuyến nghị làm trước)

**Vấn đề người dùng gặp.** HR đang chạy vị trí, tưởng vẫn tuyển, nhưng cổng nộp đã đóng từ tuần trước. Ứng viên bấm nộp thì nhận lỗi. HR không có tín hiệu nào trên Dashboard.

**Đề xuất (thay đổi tối thiểu):**

- Thêm một loại item vào work queue: `POSITION_DEADLINE_SOON`.
- Không đụng bảng nào. `application_deadline_at` **đã có** trong `app_private.positions`; chỉ cần thêm 1 cột vào `_WORK_QUEUE_POSITIONS_QUERY` (đã `JOIN app_private.positions p` sẵn):

```sql
-- thêm vào SELECT của _WORK_QUEUE_POSITIONS_QUERY
p.application_deadline_at,
```

- Thêm 1 tham số có default vào `build_work_queue_items(...)`:

```python
def build_work_queue_items(
    *,
    position: Mapping[str, Any],
    counts: Mapping[str, int],
    workflow: Mapping[str, Any],
    criteria_status: str | None,
    criteria_stale: bool,
    jd_exists: bool,
    is_hr: bool,
    is_hm: bool,
    share_without_feedback: int = 0,
    criteria_approved: bool = False,
    deadline_at: datetime | None = None,      # NEW, default None
    now: datetime | None = None,             # NEW, default None → test bơm giờ
) -> list[dict[str, Any]]:
```

- Luật sinh item (dùng lại đúng cơ chế `add()` đang có, không viết engine mới):

| Điều kiện | Item | Priority | Nhãn |
| --- | --- | --- | --- |
| `status == 'OPEN'` và `deadline_at < now` | `POSITION_DEADLINE_PASSED` | `HIGH` | "Đã quá hạn nhận hồ sơ — cổng nộp đang đóng" |
| `status == 'OPEN'` và `0 <= now→deadline <= 7 ngày` | `POSITION_DEADLINE_SOON` | `MEDIUM` | "Còn N ngày nhận hồ sơ" |
| `deadline_at is None` | không sinh item | — | (không bịa "0 ngày") |

- `target`: `/positions/{id}?tab=overview` để HR sửa hạn hoặc đóng vị trí.

**Payload đổi những gì** (chỉ thêm, không sửa, không xoá):

```jsonc
// GET /v1/dashboard/work-queue  →  items[] thêm 1 loại và 2 field tuỳ chọn
{
  "item_id": "POSITION_DEADLINE_SOON:pos-1",
  "type": "POSITION_DEADLINE_SOON",       // mở rộng union
  "priority": "MEDIUM",
  "count": 1,
  "due_at": "2026-11-24T00:00:00Z",       // NEW, ISO hoặc null
  "days_left": 5,                          // NEW, số nguyên hoặc null
  "target": { "pathname": "/positions/pos-1", "search": "tab=overview" }
}
```

`summary` thêm một khoá:

```jsonc
"positions_deadline_passed": 2,
"positions_deadline_soon": 3
```

**Rủi ro và cách chặn:**

| Rủi ro | Cách chặn |
| --- | --- |
| Client cũ không biết `type` mới → hiện chuỗi thô | `WorkQueueList` map nhãn theo `Record<type, string>`; thêm nhánh fallback trả `t("Việc cần xử lý")` thay vì key thô. Thêm cùng lúc, không để sau |
| Thêm `summary` key làm vỡ test đang so sánh nguyên khối | Grep: chỉ `test_phase1_integration.py` đọc từng khoá cụ thể (`files_needing_review`), không so cả dict → an toàn |
| Đếm trùng với `POSITION_SETUP` khi vị trí còn thiếu tiêu chí | Chỉ sinh deadline item khi vị trí **đã qua** bước thiết lập (`criteria_approved`), tránh một vị trí hiện 2 dòng cùng lúc |
| Múi giờ | Backend đã chuẩn hoá naive → UTC ở `positions.py:105`; trả ISO có `Z`, FE format bằng `dateLocale` |

**Test kèm theo (bắt buộc):**
1. Unit `build_work_queue_items`: deadline quá khứ → `POSITION_DEADLINE_PASSED` priority `HIGH`; deadline +3 ngày → `SOON`/`MEDIUM`; deadline +30 ngày → không item; `deadline_at=None` → không item (chống bịa số).
2. Unit: vị trí `CLOSED` hoặc chưa `criteria_approved` → không sinh deadline item (chống đếm trùng).
3. Integration `test_phase1_integration.py`: seed 1 vị trí OPEN quá hạn → `work-queue` có item, và `summary.positions_deadline_passed == 1`.
4. Browser mock: item quá hạn đứng trước item sắp hạn; nhãn tiếng Việt/Anh đúng; item có `due_at: null` không hiện "còn 0 ngày".

**Chi phí:** ~1 buổi. File chạm: `backend/app/api/dashboard.py` (1 dòng SQL + 1 tham số), `backend/app/services/workspace.py` (+~25 dòng), `backend/tests/test_workspace.py`, `frontend/src/types/index.ts`, `frontend/src/components/workflow/WorkQueueList.tsx` (2 nhãn + fallback), i18n.

### 1.4 B2 — Tuổi hồ sơ chờ trên Dashboard (nên làm, nhưng sau B1)

**Vấn đề.** Dòng "5 hồ sơ cần xác minh" chỉ nói khối lượng. Nếu 3 trong 5 đã chờ 9 ngày, thứ tự xử lý nên khác — nhưng màn hình không nói.

**Đề xuất:**

- Thêm `a.created_at` vào `_APPLICATIONS_QUERY` (nó **đang thiếu**, đã kiểm).
- `summarize_applications` trả thêm 3 khoá (đều là số, không suy diễn nghiệp vụ):

```python
"waiting_over_7d": 3,        # hồ sơ đang sàng lọc, chờ > 7 ngày
"oldest_waiting_days": 12,   # null nếu không có hồ sơ nào
"median_waiting_days": 4,    # null nếu rỗng
```

- Dashboard hiện dưới dòng "Việc cần làm": *"3 hồ sơ chờ quá 7 ngày · lâu nhất 12 ngày"*, bấm vào mở danh sách sắp theo **cũ nhất trước**.
- Thêm `WAITING` vào `WorkQueueItemType` (item tổng hợp theo vị trí, không phải theo hồ sơ).

**Điểm phải giữ:** tuổi hồ sơ **không được đổi thứ hạng**. `rank_number` đến từ lần chạy ranking; sắp "cũ nhất trước" chỉ là một `sort` của danh sách, và UI phải nói rõ điều đó (đã có câu "Danh sách ưu tiên vấn đề cần xử lý, không phải thứ tự xếp hạng").

**Rủi ro:** ngưỡng 7 ngày là con số nghiệp vụ, không phải kỹ thuật. Em đề nghị để thành hằng số có tên (`WAITING_ATTENTION_DAYS`, FE đã có) và **không** đưa vào `settings` cho tới khi HR xác nhận con số. Nếu anh muốn khác 7, đổi một chỗ.

**Chi phí:** ~1 buổi. **Không** đổi schema, chỉ đổi payload của endpoint Dashboard (vốn không thuộc `frontend/src/app/v1` contract với bên ngoài).

### 1.5 Đề xuất chốt cho R5-B

Làm **B1 trước, B2 sau**, và cả hai đều **chỉ thêm field** vào payload (additive). Nếu anh chỉ muốn duyệt một thứ: chọn **B1**, vì nó sửa một trạng thái *sai sự thật* (Dashboard nói "đang mở" trong khi cổng đã đóng), còn B2 chỉ là *thiếu thông tin phụ*.

---

## Phần 2 — R6: thu gọn phần đầu màn Applicant Ranking

### 2.1 Vấn đề, đo chính xác

`firstRowOffsetPx` = **896px** trên viewport **900px**: dòng ứng viên đầu tiên nằm dưới mép màn hình. Chi tiết từng khối:

| # | Khối | Bắt đầu | Cao |
| --- | --- | --- | --- |
| 1 | Nút "Quay lại vị trí" | 96 | 45 |
| 2 | Tiêu đề + 3 nút (Làm mới / Chia sẻ / Chạy đánh giá) | 149 | 52 |
| 3 | 4 KPI card | 287 | 89 |
| 4 | 2 nút chế độ xem (Xếp hạng / Cần rà soát) | 400 | 47 |
| 5 | Alert giải thích "ưu tiên vấn đề" | 463 | 48 |
| 6 | 8 chip hàng đợi | 527 | 72 |
| 7 | Ô tìm + select sắp xếp | 615 | 37 |
| 8 | Dòng đếm "Hiển thị N/M" | 677 | 16 |
| 9 | Alert "Cách đọc danh sách" (3 dòng) | 723 | 68 |
| 10 | `thead` bảng | 815 | 81 |

Tổng phần "trước dữ liệu": 896px. Ngân sách hợp lý: ≤ 640px (giữ được header + chip + tìm + 2 dòng đầu trong màn hình 900).

### 2.2 Ba thay đổi đề xuất, xếp theo tỉ lệ giá trị/rủi ro

**R6-a · Gộp 3 nút hành động vào một menu (tiết kiệm ~0px chiều cao, nhưng giảm 2 đích nhấn).**
Hiện "Chạy đánh giá & xếp hạng" là hành động chính (đúng), còn "Làm mới" và "Chia sẻ Shortlist" là phụ. Đề xuất: giữ "Chạy đánh giá" làm nút, hai nút kia vào menu `⋮`. **Rủi ro thấp.** Lưu ý: "Chia sẻ Shortlist" là luồng được test trong `shortlist-*` nên phải cập nhật locator — em sẽ chạy lại toàn bộ 8 bộ.

**R6-b · Thu alert "Cách đọc danh sách" thành một dòng có nút "Xem cách đọc" (tiết kiệm ~40px, và nó đang lặp).**
Nội dung alert này (điểm một phần / ô chọn / mở rộng dòng) đã xuất hiện lại dưới dạng tooltip và caption ngay trong bảng. Đề xuất: mặc định thu thành 1 dòng `ⓘ Cách đọc danh sách`, bấm mới mở. **Rủi ro trung bình**: đây là câu giải thích nghiệp vụ quan trọng (điểm một phần ≠ điểm cuối), nên **không được xoá** — chỉ thu gọn. Nếu HR trong usability test không mở ra, đó là tín hiệu *nội dung đang sai chỗ*, không phải "bỏ đi".

**R6-c · Gộp 4 KPI card vào dải chip hàng đợi (tiết kiệm ~89px + 16px).**
"Tổng hồ sơ / Có trong xếp hạng / Cần HR xác minh / Cảnh báo trùng lặp" và 8 chip hàng đợi đang đếm **cùng những thứ đó ở hai nơi**. Đề xuất: bỏ dải card, thêm chip "Có trong xếp hạng (N)" vào dải chip vốn đã có, giữ "Cảnh báo trùng lặp" (đã là chip). **Rủi ro cao nhất trong ba** — đây là phần vừa được nghiệm thu ở đợt P0/P1 và có test đếm chip; em sẽ phải sửa `ranking-context-mock` phần 3–4.

### 2.3 Kết quả kỳ vọng nếu làm cả ba

| | Hiện | Sau R6-a/b | Sau cả ba |
| --- | --- | --- | --- |
| Dòng dữ liệu đầu tiên | 896px | ~800px | **~640px** |
| Điều khiển trước dữ liệu (`filterControlsAboveTable`) | 12 | 12 | ~8 |
| Số đích nhấn ở header | 3 nút | 1 nút + menu | 1 nút + menu |

### 2.4 Đề xuất chốt cho R6

Làm **R6-a + R6-b** (rủi ro thấp–trung bình, tiết kiệm ~40px và giảm 2 đích nhấn). **R6-c để sau usability test**: nếu HR nói "tôi không dùng 4 ô số đó", xoá là quyết định có bằng chứng; nếu không, giữ nguyên vì nó là phần vừa nghiệm thu.

Nói thẳng: **R6 một mình không đưa dòng đầu lên trên màn hình** (896 → ~800px). Muốn đạt thì buộc phải làm R6-c, mà R6-c là thay đổi bố cục lớn nhất. Vì vậy em vẫn giữ nguyên khuyến nghị **hoãn R6 tới sau usability test**, và nếu anh muốn làm ngay thì nên chọn cả ba cùng lúc chứ đừng làm nửa vời.

---

## Phần 3 — Nếu anh duyệt, thứ tự em sẽ làm

| Bước | Việc | Vì sao thứ tự này |
| --- | --- | --- |
| 1 | R5-B1 (hạn ứng tuyển) | Sửa trạng thái sai sự thật; phụ thuộc thấp; test được ngay bằng unit + integration |
| 2 | Chạy lại toàn bộ test + CI | Vì bước 1 chạm payload |
| 3 | R5-B2 (tuổi hồ sơ) | Cùng file, cùng kiểu thay đổi additive |
| 4 | R6-a + R6-b | Thuần frontend, rủi ro thấp |
| 5 | *(Chờ usability test)* | R6-c chỉ quyết định sau khi có phản hồi HR |

Mỗi bước một commit riêng để revert độc lập được.

## Phần 4 — Câu hỏi cần anh trả lời

1. **R5-B1**: duyệt? (em khuyến nghị **có**)
2. **R5-B2**: duyệt? Ngưỡng cảnh báo để **7 ngày** hay con số khác?
3. **R6**: làm **a+b** ngay, hay **hoãn hết** tới sau usability test? (em khuyến nghị hoãn hết)
4. Có cần em **ẩn vị trí quá hạn khỏi KPI "Vị trí đang mở"** không? Đây là thay đổi *định nghĩa* một con số đang hiển thị — em **không** đề xuất làm, vì nó đổi nghĩa "đang mở" mà anh chưa chốt.
