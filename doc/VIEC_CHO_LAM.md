# Việc chờ làm — UI/UX tuyển dụng

Danh sách những việc **đã thống nhất là cần làm nhưng chưa làm**, để không phải
dò lại từ đầu mỗi lượt. Mục đã xong nằm trong `doc/NHAT_KY_THAY_DOI.md`; tài liệu
này chỉ giữ phần còn mở.

Cách dùng: thêm mục mới vào bảng, mỗi mục một phần chi tiết bên dưới ghi hiện
trạng trong code, phạm vi dự kiến và cái phải quyết trước khi code. Khi làm
xong: chuyển trạng thái sang **Xong** kèm commit, và ghi mục tương ứng vào nhật
ký.

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
