# Tổng hợp đợt chỉnh UI/UX — có tạm dừng được chưa?

Ngày rà: 2026-11-19. Nhánh `arena/ea6e2570-vinit-hrapp`, HEAD `f0f015b`.
Rà bằng cách **đọc code và đo lại từng hạng mục**, không dựa vào tài liệu cũ —
bốn hạng mục tài liệu vẫn ghi "chưa có" nhưng thực tế đã xong từ trước.

## 1. Trả lời ngắn

**Tạm dừng được**, với hai điều kiện phải làm **trước khi** báo xong cho người
dùng thật:

1. **Chạy migration `00033` + `00034` trên VPS** — code đã tham chiếu
   `app_private.app_settings` và `hr_criterion_reviews` ở 10 chỗ. Thiếu migration
   thì tab "Cài đặt HR" và toàn bộ U1 (ghi nhận xét duyệt) **sẽ lỗi 500**.
2. **Một vòng usability trên staging** với 2–3 HR thật, vì mọi nghiệm thu tới giờ
   đều là máy đo (pixel, e2e, pytest), chưa có người dùng thật nào.

Hai việc P2 còn lại (**3.8** sửa tiêu chí inline, **3.9/UX-08** phản hồi async
nhất quán) **không nên làm trong đợt này** — chúng là đánh bóng, và 3.8 còn có
thể phải sửa API trước.

## 2. Bảng trạng thái 9 hạng mục

| Mục | Nội dung | Trạng thái | Bằng chứng |
| --- | --- | --- | --- |
| 3.1 / UX-01 | Giữ ngữ cảnh khi mở hồ sơ rồi quay lại | **Xong** | `keepContext` mang `queue/sort/q`; `restore=scroll`; `scrollY` trong `applicantReview.ts`. Đo: vào `/applicants?queue=NEEDS_VERIFICATION&sort=COVERAGE_ASC&q=le` → Prev/Next và nút quay lại giữ nguyên cả 3 tham số. |
| 3.2 / UX-02 | Nghĩa số đếm + xoá bộ lọc | **Xong** | `clear-applicant-filters` ở danh sách hồ sơ, `clearPositionFilters` ở `/positions`; testid `clear-applicant-filters`. |
| 3.3 / UX-03 | Deep link hàng đợi | **Xong** (đã sửa từ trước, đợt này **đóng khe hở test**) | `queue.upper()` ở backend; `normalizeApplicantQueue` nhận cả hai kiểu; test backend đọc thẳng `APPLICANT_QUEUES` của FE, test FE đọc thẳng mã backend phát. Phá thử cả hai chiều đều đỏ. |
| 3.4 | Lazy-load CV | **Xong** (có từ trước) | Đo: mở hồ sơ → **0 request** `cv-file`; bấm "Xem CV gốc" → đúng **1**. Khoá bằng `ux04-sticky-viewer`. |
| 3.5 / UX-05 | Tìm/lọc vị trí | **Xong** (có từ trước) | `?q=` + `?status=` đọc/ghi URL; empty state phân biệt "chưa có vị trí" và "không khớp tìm kiếm". |
| 3.6 / UX-06 | Validate tại chỗ khi tạo vị trí | **Xong phần UI** | `Còn thiếu: {0}.` ngay trên nút. **"Lưu nháp" là việc backend** (cần `DRAFT` + migration), không làm. |
| 3.7 / UX-07 | Từ file lỗi tới đúng hồ sơ | **Xong đợt này** | Backend trả `application_id` + `error_code`; `invalidFileReason.ts` dịch cả mã máy lẫn câu exception; `InvalidFileList` link thẳng hồ sơ hoặc nói rõ "không tạo hồ sơ". |
| 3.8 / UX-04 | Sửa tiêu chí inline | **Chưa — P2, để sau** | Vẫn mở dialog (`editingCriterion` xuất hiện 40 lần). Đúng như tài liệu xếp P2. |
| 3.9 / UX-08 | Phản hồi async nhất quán | **Chưa — P2, để sau** | Chưa có `useActionFeedback`; hiện mỗi chỗ tự dùng Snackbar/Alert. |
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
| E2E Playwright (mock) | 14 / 14 |
| tsc / lint / build | sạch |
| CI | `44486476247`, `44486915413`, `44490889045` — **success cả 3 job** |

## 5. Nếu muốn đóng hẳn, thứ tự đề xuất

1. **Deploy**: chạy `00033`, `00034` → deploy → bật tab "Cài đặt HR" và U1 trên staging.
2. **Usability 1 vòng** (kịch bản 6 bước trong `doc/E2E_STAGING_EXECUTION_CHECKLIST.md`),
   thêm bước 7: mở link hồ sơ ở tab mới để kiểm 3.1.
3. **Safari/iOS** — chưa ai thử; `position: sticky` và `overflow: clip` là chỗ dễ
   khác biệt giữa trình duyệt nhất trong đợt này.
4. Chỉ sau đó mới cân nhắc 3.9 (UX-08) rồi 3.8.

Lý do xếp 3.9 trước 3.8: 3.9 chỉ đụng frontend và làm các thông báo hiện có
nhất quán; 3.8 có thể phải thêm endpoint "patch một tiêu chí" — cần kiểm API
trước khi hứa, đúng như tài liệu đã ghi.
