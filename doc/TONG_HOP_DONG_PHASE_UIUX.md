# Tổng hợp đợt chỉnh UI/UX — có tạm dừng được chưa?

Ngày rà: 2026-11-19. Nhánh `arena/ea6e2570-vinit-hrapp`, HEAD `ae18992`
(sau khi làm 3.9/UX-08).
Rà bằng cách **đọc code và đo lại từng hạng mục**, không dựa vào tài liệu cũ —
bốn hạng mục tài liệu vẫn ghi "chưa có" nhưng thực tế đã xong từ trước.

## 1. Trả lời ngắn

**Tạm dừng được**, với hai điều kiện phải làm **trước khi** báo xong cho người
dùng thật:

1. ~~**Chạy migration `00033` + `00034`**~~ — **✅ XONG 2026-11-19** (version
   `20261119093753`, `20261119093801`). Còn lại: **deploy code lên VPS**. Lưu ý
   `scripts/deploy.sh` sẽ `exit 2` vì `supabase/migrations` thay đổi — chạy lại
   với `--migrations-verified`. Xem `HUONG_DAN_MIGRATION_00033_00034.md`.
2. **Một vòng usability trên staging** với 2–3 HR thật, vì mọi nghiệm thu tới giờ
   đều là máy đo (pixel, e2e, pytest), chưa có người dùng thật nào.

**3.9/UX-08 đã làm xong** trong đợt này (xem mục 6). Chỉ còn **3.8** (sửa tiêu
chí inline) là P2 thật sự chưa làm — và nên chờ dữ liệu sử dụng trước khi làm.

## 2. Bảng trạng thái 9 hạng mục (8 xong, 1 để sau)

| Mục | Nội dung | Trạng thái | Bằng chứng |
| --- | --- | --- | --- |
| 3.1 / UX-01 | Giữ ngữ cảnh khi mở hồ sơ rồi quay lại | **Xong** | `keepContext` mang `queue/sort/q`; `restore=scroll`; `scrollY` trong `applicantReview.ts`. Đo: vào `/applicants?queue=NEEDS_VERIFICATION&sort=COVERAGE_ASC&q=le` → Prev/Next và nút quay lại giữ nguyên cả 3 tham số. |
| 3.2 / UX-02 | Nghĩa số đếm + xoá bộ lọc | **Xong** | `clear-applicant-filters` ở danh sách hồ sơ, `clearPositionFilters` ở `/positions`; testid `clear-applicant-filters`. |
| 3.3 / UX-03 | Deep link hàng đợi | **Xong** (đã sửa từ trước, đợt này **đóng khe hở test**) | `queue.upper()` ở backend; `normalizeApplicantQueue` nhận cả hai kiểu; test backend đọc thẳng `APPLICANT_QUEUES` của FE, test FE đọc thẳng mã backend phát. Phá thử cả hai chiều đều đỏ. |
| 3.4 | Lazy-load CV | **Xong** (có từ trước) | Đo: mở hồ sơ → **0 request** `cv-file`; bấm "Xem CV gốc" → đúng **1**. Khoá bằng `ux04-sticky-viewer`. |
| 3.5 / UX-05 | Tìm/lọc vị trí | **Xong** (có từ trước) | `?q=` + `?status=` đọc/ghi URL; empty state phân biệt "chưa có vị trí" và "không khớp tìm kiếm". |
| 3.6 / UX-06 | Validate tại chỗ khi tạo vị trí | **Xong phần UI** | `Còn thiếu: {0}.` ngay trên nút. **"Lưu nháp" là việc backend** (cần `DRAFT` + migration), không làm. |
| 3.7 / UX-07 | Từ file lỗi tới đúng hồ sơ | **Xong đợt này** | Backend trả `application_id` + `error_code`; `invalidFileReason.ts` dịch cả mã máy lẫn câu exception; `InvalidFileList` link thẳng hồ sơ hoặc nói rõ "không tạo hồ sơ". |
| 3.8 | Sửa tiêu chí inline | **Chưa — P2 duy nhất còn lại** | Vẫn mở dialog. API **đã có sẵn**, xem mục 6. |
| 3.9 / UX-08 | Phản hồi async nhất quán | **Xong (đợt này)** | `ActionFeedback` với 2 vùng `aria-live` **luôn tồn tại**; áp cho 5 luồng. Kèm sửa crash `/shortlist` khi API trả object thay vì mảng. |
| UX-04 | Drawer/split view | **Không làm, có lý do** | Trang chi tiết đã là hai cột. Vấn đề thật là CV trôi khỏi màn hình — đã sửa bằng sticky (−637px → heading 151px). Drawer sẽ nhân đôi đường đi, không giải quyết thêm. |

## 3. Rủi ro và nợ kỹ thuật đã kiểm

| Kiểm | Kết quả |
| --- | --- |
| `TODO` / `FIXME` / `HACK` trong `frontend/src` + `backend/app` | **0** |
| Test bị skip (`@pytest.mark.skip`, `test.skip`, `it.skip`) | **0** |
| Xung đột với `main` | **0** (main có 1 commit dọn `.md` vào `audit/`, không đụng file nào của đợt này) |
| Nhánh so với `main` | đi trước **177** commit, không có commit lạc |
| PR đang mở | **không có** — cần mở PR để review trước khi merge |
| Migration chưa áp lên VPS | **`00033`, `00034`** — xem mục 1 |
| Quyền của tính năng mới | `GET/PATCH /v1/admin/settings` đều `require_admin_role`; ghi review cần `can_manage_hr_notes` |

## 4. Kiểm chứng tự động tại HEAD `f0f015b`

| Bộ | Kết quả |
| --- | --- |
| Backend pytest | 292 passed / 174 skipped (integration cần Postgres thật, tự skip ở sandbox) |
| FE unit (node --test) | 43 / 43 |
| i18n | 3 / 3 |
| E2E Playwright (mock) | 15 / 15 |
| tsc / lint / build | sạch |
| CI | `44486476247`, `44486915413`, `44490889045` — **success cả 3 job** |

## 5. Nếu muốn đóng hẳn, thứ tự đề xuất

1. **Deploy**: chạy `00033`, `00034` → deploy → bật tab "Cài đặt HR" và U1 trên staging.
2. **Usability 1 vòng** (kịch bản 6 bước trong `doc/E2E_STAGING_EXECUTION_CHECKLIST.md`),
   thêm bước 7: mở link hồ sơ ở tab mới để kiểm 3.1.
3. **Safari/iOS** — chưa ai thử; `position: sticky` và `overflow: clip` là chỗ dễ
   khác biệt giữa trình duyệt nhất trong đợt này.
4. Chỉ sau đó mới cân nhắc **3.8** (P2 duy nhất còn lại).

## 6. Mục P2 — chi tiết

Có **ba** mục từng được xếp P2. Trạng thái hiện tại:

| Mục | Trạng thái |
| --- | --- |
| 3.9 / UX-08 phản hồi async | **Xong** (`ae18992`) |
| U6 danh sách tiêu chí thu gọn | **Hoãn có chủ đích** — anh đã quyết ở UX-02, không mở lại |
| 3.8 sửa tiêu chí inline | **Chưa làm** — mục duy nhất còn lại |

### 6.1. 3.8 — Sửa tiêu chí tại chỗ (chưa làm)

**Hiện trạng.** Sửa một tiêu chí = mở `Dialog` (`editingCriterion`), sửa, lưu,
đóng. Với 8–12 tiêu chí mỗi vị trí, đó là 8–12 vòng mở/đóng.

**Điều đã kiểm được (để lần sau không phải dò lại):** tài liệu cũ lo "có thể
phải thêm endpoint patch một tiêu chí" — **không cần**:

- Backend đã có `PATCH /criteria/{version_id}/items/{criterion_id}`
  (`backend/app/api/criteria.py:566`), chỉ cho phép sửa khi version **chưa
  duyệt** (`_lock_editable_criteria_version`) — đúng quy tắc hiện tại.
- Frontend đã nối sẵn `criteriaApi.updateItem` (`src/lib/api.ts:100`).

⇒ Đây **thuần là việc frontend**.

**Cái bẫy phải quyết trước khi code.** Dialog hiện gửi **6 trường**: `name`,
`description`, `category`, `weight_in_group`, `expected_evidence_keywords`,
`requirement_spec`. Nếu chỉ inline được `name` + `description` thì HR vẫn phải
mở dialog cho phần còn lại — **tệ hơn hiện tại** vì có hai kiểu sửa khác nhau.
Ba lựa chọn:

| Cách | Được | Mất |
| --- | --- | --- |
| A. Inline đủ 6 trường | Không còn dialog cho sửa nhẹ | Ô sửa `requirement_spec` (cấu trúc JSON) rất dễ vỡ; công sức L |
| B. Inline `name`/`description`, dialog cho phần còn lại | Rẻ, an toàn | Hai kiểu sửa — phải nói rõ trên UI cái nào sửa được tại chỗ |
| C. Giữ nguyên | Không rủi ro | Ma sát còn đó |

**Khuyến nghị: B**, và chỉ làm sau khi có dữ liệu cho câu hỏi *"HR có thật sự
sửa nhiều tiêu chí liên tiếp không?"* — chính là thứ một vòng usability sẽ trả
lời. Nếu HR sửa 1–2 tiêu chí mỗi lần thì 3.8 gần như vô giá trị.

**Nghiệm thu nếu làm:** sửa 5 tiêu chí liên tiếp không mở dialog; tổng trọng số
vẫn validate; trạng thái phê duyệt vẫn reset như cũ; **không** đổi quy tắc hai
người phê duyệt.

### 6.2. U6 — Danh sách tiêu chí thu gọn (hoãn)

Nhìn được cả 6 tiêu chí trong một màn, bấm để nhảy. Tài liệu ghi rủi ro **Cao**
vì đụng CV viewer, ghi chú HR, lịch sử, phân quyền — đúng những chỗ vừa ổn định
xong ở UX-02 và UX-04. **Không mở lại** trừ khi có yêu cầu mới.

### 6.3. 3.9 / UX-08 — đã xong, ghi lại để không làm lại

`src/components/common/ActionFeedback.tsx`:

- Hai vùng `role="status"` (`polite`) và `role="alert"` (`assertive`) **luôn có
  trong DOM**, rỗng khi không có gì. Đây là điểm quan trọng: **không** dùng
  `<Snackbar>` của MUI vì nó chỉ mount nội dung khi `open` — vùng thông báo sinh
  ra cùng lúc với thông báo thì screen reader đăng ký quá muộn và bỏ lỡ câu đầu.
- Thành công tự tắt (5s); **lỗi không tự tắt**.
- Đã áp cho 5 luồng: đổi trạng thái hồ sơ, xử lý lại CV, lưu scorecard, nộp
  scorecard, đánh giá/xếp hạng, chia sẻ shortlist, thu hồi shortlist.
- Kèm sửa một **crash có sẵn** ở `/shortlist`: API trả object thay vì mảng ⇒
  `visibleShares.length` là `undefined` ⇒ `.map` nổ ⇒ màn hình trắng "Application
  error". Nay chỉ nhận mảng, còn lại coi như rỗng và hiện lỗi có nút Thử lại.

**Còn lại của UX-08 (không bắt buộc):** các `Alert` tại chỗ trong form (lỗi
validate) vẫn giữ nguyên — đó là đúng chỗ, không cần chuyển sang Snackbar.
