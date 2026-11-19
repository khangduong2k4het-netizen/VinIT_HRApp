# Plan triển khai nâng cấp UI/UX Frontend — Recruitment Workspace

> Ngày lập plan: 2026-11-08  
> Branch: `arena/ea6e2570-vinit-hrapp`  
> Mốc rà soát: `1d03ff4` (sau commit CI `e49c346` được GPT đối chiếu)  
> Trạng thái: **ĐÃ TRIỂN KHAI UX-0…UX-4 Ở CODE — CHỜ STAGING/USABILITY GATE**
> Nguồn đề xuất: Review UI/UX Frontend của GPT ngày 2026-11-08.  
> Phạm vi: tổ chức lại trải nghiệm làm việc của HR/HM trên nền frontend/API hiện tại. Không thay đổi matching engine, BGE, LTR, tiêu chí phê duyệt hoặc quyền quyết định nghiệp vụ.

## 0. Trạng thái triển khai

- **UX-0:** đã khóa contract qua `backend/app/services/workspace.py`, `GET /v1/dashboard/work-queue` và `GET /v1/positions/{position_id}/workspace`; có unit test và integration test theo RBAC/scope.
- **UX-1:** đã triển khai My Work Queue trên `/dashboard`, Position Summary, Workflow Stepper và Next Best Action trên `/positions/[id]`; Sidebar được phân nhóm và Header dùng profile từ AppLayout.
- **UX-2:** đã triển khai Applicant Review queue chips/sort/URL state/sticky table/bulk share bar, Candidate Review sticky bar, prev/next theo hàng đợi, EvidenceCard và CVDocumentViewer.
- **UX-3:** đã triển khai CV Intake Panel trong Position Workspace và OperationProgressPanel dùng chung; không có retry từng file vì backend chưa có contract retry.
- **UX-4:** đã bổ sung PageHeader, EmptyState, StickyActionBar, i18n cho nhãn mới và kiểm tra lint/type-check/build.
- **UX-5:** chưa triển khai Global Search, PDF text highlight, server-side pagination, retry file hoặc overall confidence; các hạng mục này vẫn cần contract/đánh giá riêng.
- **Gate còn lại:** chưa chạy usability test HR/HM trên staging và chưa đóng DEP-01; không dùng dữ liệu thật cho kiểm thử khi chưa có phê duyệt.

## 1. Kết luận tiếp nhận đề xuất

Đề xuất chuyển từ “cải tiến từng màn hình” sang **Recruitment Workspace theo vị trí** là hợp lý và nên thực hiện. Tuy nhiên, không triển khai như một cuộc viết lại frontend. Plan này chọn cách **tái cấu trúc theo lát cắt dọc, tái sử dụng route/API/component hiện có, bổ sung contract dữ liệu ở nơi frontend đang phải tự suy luận**.

### 1.1. Ma trận quyết định

| Hạng mục GPT đề xuất | Quyết định | Mức ưu tiên | Lý do/khả thi |
|---|---|---:|---|
| Position Workspace cho từng vị trí | **Chấp nhận** | P0 | Route `/positions/[id]` đã có JD/criteria/upload/operation; cần thêm summary, stepper và next action thay vì tạo route mới. |
| Workflow Stepper + Next Best Action | **Chấp nhận** | P0 | Giá trị cao nhất; phải có state contract rõ ràng để không lệch logic nghiệp vụ. |
| My Work Queue | **Chấp nhận** | P0 | Dashboard đã có số liệu tổng hợp nhưng chưa có danh sách việc theo position và deep link tới đúng bộ lọc. |
| Applicant Review Center theo hàng đợi | **Chấp nhận** | P0 | Trang applicants đã có search, filter matching, bảng/cards và shortlist; cần chuyển trọng tâm sang nhu cầu rà soát. |
| Candidate Review side-by-side | **Chấp nhận dạng nâng cấp** | P0 | Trang hiện tại đã có evidence bên trái, CV bên phải và click bằng chứng để nhảy trang PDF. Cần sticky action, prev/next và trạng thái bằng chứng tốt hơn, không cần viết lại từ đầu. |
| CV Intake Center | **Chấp nhận một phần** | P1 | Làm Intake Panel trong Position Workspace trước; chưa tạo route riêng và chưa hứa retry từng file khi backend chưa hỗ trợ. |
| Operation Progress Panel dùng chung | **Chấp nhận** | P1 | Operation API đã có progress/invalidated files; position và applicants đang hiển thị tách nhau. |
| Điều hướng/Breadcrumb/PageHeader | **Chấp nhận** | P1 | Sidebar cần phân nhóm nghiệp vụ/quản trị; AppLayout và Header đang cùng gọi profile API. |
| Design System/component dùng chung | **Chấp nhận từng phần** | P1 | Chỉ tạo component khi có nhu cầu dùng thật trong batch; không đại tu toàn bộ `sx` trước. |
| Bulk actions | **Chấp nhận giới hạn** | P1 | Đã có chọn nhiều hồ sơ để share shortlist. Chưa thêm bulk đổi trạng thái cho tới khi có rule nghiệp vụ/an toàn riêng. |
| Sticky table header, sort, lưu bộ lọc | **Chấp nhận** | P1 | Áp dụng cho Applicant Review bằng URL query/session state; chưa chuyển server-side pagination ở vòng đầu. |
| Empty/skeleton/toast/accessibility | **Chấp nhận** | P1/P2 | Làm theo từng màn hình trong các batch, có kiểm thử bàn phím và i18n. |
| Global Search trên Header | **Hoãn** | Backlog | Chưa có backend search xuyên position/candidate, dễ lộ dữ liệu ngoài scope và không thuộc ba hạng mục tác động cao nhất. |
| Highlight trực tiếp đoạn chữ trong PDF | **Hoãn** | Backlog | Iframe PDF hiện tại chỉ nhảy `#page=N`; highlight cần đánh giá `pdf.js`/text layer, bảo mật signed URL và hiệu năng. |
| Hiển thị Confidence tổng thể | **Không đưa vào plan** | Không làm | Backend chưa có định nghĩa/chỉ số confidence tổng thể cho assessment. Không dùng evidence coverage hoặc `evidence_strength` của từng criterion để thay thế. |
| Usability test với HR/HM | **Chấp nhận** | Gate nghiệm thu | Cần staging DEP-01 và dữ liệu tổng hợp; đo baseline trước, không nghiệm thu chỉ bằng cảm nhận “đẹp hơn”. |

## 2. Hiện trạng đã có và khoảng thiếu

### 2.1. Nền tảng nên tái sử dụng

- MUI 5, theme VinUni và `StatusBadge` đã tồn tại tại `frontend/src/lib/theme.ts` và `frontend/src/components/common/StatusBadge.tsx`.
- Dashboard `/dashboard` đã có KPI về vị trí mở, tổng hồ sơ, CV cần HR kiểm tra, shortlist, trạng thái hồ sơ, coverage, duplicate và processing.
- Position detail đã có breadcrumb, header, trạng thái criteria, upload dialog, operation progress, 4 tabs và thống kê hồ sơ.
- Applicants page đã có search tên, lọc nhóm matching, bảng desktop, cards mobile, chọn shortlist, share HM, polling operation và chạy assessment.
- Candidate detail đã là side-by-side: criterion/evidence ở cột trái, CV PDF ở cột phải; evidence đã xác minh có thể click để đổi `selectedPage` và iframe dùng `#page=N`.
- Operation API đã trả `stage`, `status`, `progress.total/processed/failed/percent_complete` và `invalid_files` cho CV processing.
- Candidate detail đã có trạng thái HR qua dialog xác nhận, lý do bắt buộc khi loại, HR notes riêng tư và lịch sử trạng thái.

### 2.2. Khoảng thiếu thật sự

- Chưa có một API “workspace state” duy nhất cho stepper/next action; frontend position detail đang tự kết hợp position, JD, criteria, dashboard counts và operation.
- Dashboard chưa trả danh sách công việc theo từng position; người dùng chưa thể bấm “5 hồ sơ cần xác minh” để tới đúng position + đúng queue.
- Applicants filter hiện là một select “nhóm matching”; file review, duplicate, coverage thấp và matching status chưa thành queue chips có số lượng và deep link.
- Candidate detail chưa có điều hướng ứng viên trước/sau theo cùng hàng đợi; header/action chưa sticky; profile/notes/history vẫn nằm trước phần đối chiếu chính.
- Upload vẫn là dialog, danh sách file chọn chưa có trạng thái kiểm tra từng file và sau upload người dùng phải tự tìm bước tiếp theo.
- Sidebar chưa phân nhóm rõ “công việc tuyển dụng” và “quản trị”; Header tự gọi `authApi.me()` trong khi AppLayout cũng đã lấy profile/roles.
- Chưa có baseline usability: thời gian hoàn thành, số click, số lần quay lại và lỗi thao tác của HR/HM.

## 3. Nguyên tắc bắt buộc

1. **HR/HM quyết định; AI chỉ hỗ trợ.** Không dùng nhãn, màu hoặc CTA gây hiểu nhầm AI đã tuyển/loại ứng viên.
2. **`UNCLEAR` không hiển thị như `NO_MATCH`.** Queue “cần xác minh” phải tách khỏi “có dấu hiệu không đáp ứng bắt buộc”.
3. **Matching score, evidence coverage và evidence strength là các khái niệm riêng.** Không tạo “confidence” tổng thể khi backend chưa định nghĩa.
4. **Không để frontend tự phát minh trạng thái nghiệp vụ.** Stepper/next action và queue counts phải dùng contract backend hoặc hàm domain dùng chung có unit test.
5. **Deep link phải tới đúng ngữ cảnh.** Một work item phải mở đúng position, tab/queue và khi phù hợp đúng ứng viên.
6. **Giữ route hiện tại trong vòng đầu.** Không đổi URL của positions, applicants, candidate detail, shortlist và dashboard để tránh phá vỡ link đã chia sẻ.
7. **Không viết lại frontend hoặc thay MUI.** Chuẩn hóa component theo nhu cầu của từng batch.
8. **RBAC là một phần của UX.** Work queue chỉ chứa dữ liệu người dùng được phép xem; HM không thấy HR private notes hoặc hồ sơ ngoài share.
9. **Mọi trạng thái phải có nhãn chữ**, không chỉ dựa vào màu; hỗ trợ bàn phím, focus rõ ràng và i18n Việt/Anh.
10. **Không dùng dữ liệu thật cho usability test** khi chưa qua các gate Phase 1; dùng staging và dữ liệu tổng hợp.

## 4. Kiến trúc trải nghiệm mục tiêu

### 4.1. Điều hướng

Giữ các route hiện tại nhưng đổi nhãn và phân nhóm:

```text
CÔNG VIỆC TUYỂN DỤNG
- Tổng quan công việc        /dashboard
- Vị trí tuyển dụng          /positions
- Shortlist & phản hồi       /shortlist

QUẢN TRỊ — chỉ hiển thị theo quyền
- Cấu hình AI                /admin
- Người dùng & phân quyền    /admin/users
- Phòng ban                  /admin/departments
```

- Sau đăng nhập, HR/HM vẫn có thể vào `/dashboard`; trang này được tái định vị thành **Tổng quan công việc** thay vì chỉ là báo cáo.
- Không tạo route “Hàng đợi ứng viên” toàn hệ thống ở vòng đầu. Hàng đợi nằm trong từng Position Workspace để giữ scope và quyền dữ liệu.
- Admin thuần quản trị có thể giữ điểm vào `/admin` theo vai trò; không ép mọi vai trò dùng cùng một work queue.

### 4.2. Position Workspace

Route giữ nguyên: `/positions/[id]`.

Bố cục mới theo thứ tự:

1. Breadcrumb + PageHeader: title, position code, department, HM, trạng thái vị trí.
2. `PositionSummary`: tổng CV, đã matching, đang xử lý, cần kiểm tra/xác minh, shortlist.
3. `WorkflowStepper`: JD → Criteria → CV Intake → Matching & HR Review → Shortlist/HM.
4. `NextActionCard`: một hành động chính, lý do bị chặn nếu có và hành động phụ.
5. Nội dung tab hiện tại được giữ trong vòng đầu: Criteria, Applications, Shortlist, JD.

Không loại bỏ tab ngay. Stepper là lớp định hướng phía trên; tab là khu vực thực thi chi tiết.

### 4.3. My Work Queue

Route giữ nguyên: `/dashboard`.

Trang gồm:

- KPI ngắn ở trên.
- Danh sách `WorkQueueItem` theo position/loại việc.
- Mỗi item có: mức ưu tiên, position code/title, mô tả việc, số lượng, CTA và deep link.
- Khu vực phân tích hiện tại được giữ ở dưới với nhãn “Tổng quan” để không mất chức năng dashboard.

Ví dụ deep link:

- `/positions/{id}?tab=criteria`
- `/positions/{id}?tab=applications&intake=1`
- `/positions/{id}/applicants?queue=file_review`
- `/positions/{id}/applicants?queue=needs_verification`
- `/positions/{id}/applicants?queue=duplicate`

### 4.4. Applicant Review Center

Route giữ nguyên: `/positions/[id]/applicants`.

- Queue chips: Tất cả, Cần kiểm tra file, Cần xác minh, Có cảnh báo trùng, Có dấu hiệu không đáp ứng, Chưa matching, Đáp ứng bắt buộc.
- Queue là bộ lọc rà soát, không phải kết luận tuyển dụng.
- Sort mặc định: `REVIEW_PRIORITY`; các lựa chọn khác: ranking, matching score, coverage tăng dần, mới nhất.
- Filter/search/sort được lưu vào URL query để back/forward và chia sẻ nội bộ đúng ngữ cảnh.
- Desktop giữ bảng; mobile giữ cards; hai dạng dùng cùng một filter/sort model.
- Thanh bulk action chỉ xuất hiện khi có lựa chọn và ở vòng đầu chỉ phục vụ share shortlist như hiện tại.

### 4.5. Candidate Review

Route giữ nguyên: `/positions/[id]/applicants/[applicantId]`.

Nâng cấp thay vì viết lại:

- Sticky header rút gọn: tên ứng viên, trạng thái hồ sơ, matching status, nút trước/sau.
- Score/coverage đặt cạnh nhau nhưng nhãn rõ ràng; không thêm confidence.
- Evidence card có trạng thái: đã xác minh, chưa xác minh, không có bằng chứng; click chỉ nhảy trang khi có page hợp lệ.
- Khu vực quyết định HR sticky ở cuối hoặc cột hành động; mở dialog xác nhận hiện tại.
- Profile, HR notes và history chuyển thành panel có thể thu gọn sau phần quyết định chính; vẫn giữ quyền riêng tư.
- Prev/next lấy theo queue + sort hiện tại của Applicant Review; hiển thị “Hồ sơ 3/12 của hàng đợi Cần xác minh”.

### 4.6. CV Intake

Ở vòng đầu, Intake là một panel/section trong Position Workspace, có thể mở từ stepper hoặc CTA `Upload CV`; chưa tạo route riêng.

- Drag & drop + chọn file.
- Trước khi gửi, mỗi file có trạng thái: hợp lệ, sai định dạng, rỗng/vượt dung lượng, trùng tên cần kiểm tra.
- Hiển thị rõ giới hạn hiện tại: PDF/DOCX, tối đa 50 file/lô, 10 MB/file, 250 MB/lô.
- Sau khi gửi: `OperationProgressPanel` tách ba trạng thái: upload request, xử lý file, matching.
- Invalid files từ server được liệt kê; CTA sau hoàn tất dẫn tới `queue=file_review` hoặc nút chạy matching nếu điều kiện cho phép.
- **Không hứa retry từng file** cho tới khi backend có endpoint/retry semantics riêng.

## 5. Contract dữ liệu cần chốt trước khi code

### 5.1. API Work Queue

Đề xuất bổ sung:

```http
GET /v1/dashboard/work-queue
```

Response theo vai trò và scope hiện tại:

```json
{
  "generated_at": "2026-11-08T00:00:00Z",
  "summary": {
    "positions_needing_attention": 3,
    "files_needing_review": 12,
    "applications_needing_verification": 7,
    "duplicate_alerts": 2,
    "criteria_pending_action": 4
  },
  "items": [
    {
      "item_id": "needs_verification:{position_id}",
      "type": "NEEDS_VERIFICATION",
      "priority": "HIGH",
      "position_id": "...",
      "position_code": "REQ-IT-01",
      "position_title": "Software Engineer",
      "count": 5,
      "target": {
        "pathname": "/positions/{position_id}/applicants",
        "search": "queue=needs_verification"
      }
    }
  ]
}
```

Loại item vòng đầu:

| Type | Nguồn dữ liệu | Ghi chú |
|---|---|---|
| `CRITERIA_PENDING_HR` | criteria version mới nhất theo position | Chỉ hiển thị cho người có quyền hành động/xem phù hợp. |
| `CRITERIA_PENDING_HM` | criteria `PENDING_HM_APPROVAL` | HM thấy việc của mình; HR thấy trạng thái chờ, không giả vờ HR có thể duyệt thay. |
| `FILE_REVIEW` | documents `NEEDS_HR_REVIEW`/`ERROR_UNSUPPORTED`/processing error | Deep link queue `file_review`. |
| `PROCESSING` | applications/documents đang xử lý hoặc active operation | Không trộn với matching chưa chạy. |
| `NEEDS_VERIFICATION` | latest assessment `NEEDS_HR_VERIFICATION` hoặc coverage dưới ngưỡng theo rule backend hiện tại | Phải dùng cùng định nghĩa với ranking. |
| `DUPLICATE_PENDING` | duplicate signals `PENDING` | Chỉ trong cùng position như phạm vi hiện tại. |
| `NOT_ASSESSED` | hồ sơ hoàn tất xử lý nhưng chưa có latest assessment phù hợp | CTA chạy matching ở Position Workspace/Applicants. |
| `SHARE_WITHOUT_FEEDBACK` | shortlist share active chưa có feedback | Chỉ là tín hiệu trao đổi, không gọi là quá hạn/chờ duyệt khi chưa có scorecard F2.02. |

Backend phải tự scope theo assignment/share như dashboard hiện tại. Frontend không tự cộng dữ liệu từ nhiều position bằng N+1 request.

### 5.2. API Position Workspace Summary

Đề xuất bổ sung hoặc mở rộng dashboard position:

```http
GET /v1/positions/{position_id}/workspace
```

Response tối thiểu:

```json
{
  "position": { "position_id": "...", "title": "...", "position_code": "...", "status": "OPEN" },
  "jd": { "latest_version_id": "...", "version_number": 3, "is_latest": true },
  "criteria": {
    "current_status": "APPROVED",
    "approved_for_latest_jd": true,
    "is_stale_for_latest_jd": false,
    "version_number": 2
  },
  "counts": {
    "total": 86,
    "processing": 0,
    "file_review": 3,
    "not_assessed": 4,
    "needs_verification": 9,
    "possible_mismatch": 2,
    "meets_mandatory": 61,
    "duplicate_pending": 1,
    "shortlisted": 8
  },
  "active_operation": null,
  "workflow": {
    "current_step": "HR_REVIEW",
    "steps": [
      { "code": "JD", "status": "COMPLETED" },
      { "code": "CRITERIA", "status": "COMPLETED" },
      { "code": "CV_INTAKE", "status": "COMPLETED" },
      { "code": "HR_REVIEW", "status": "IN_PROGRESS" },
      { "code": "SHORTLIST", "status": "NOT_STARTED" }
    ],
    "next_action": {
      "code": "REVIEW_EVIDENCE",
      "blocked_reason_code": null,
      "target": { "pathname": "/positions/{position_id}/applicants", "search": "queue=needs_verification" }
    }
  }
}
```

`next_action.code` vòng đầu:

| Code | Điều kiện | CTA |
|---|---|---|
| `CREATE_JD` | Chưa có JD | Tạo JD |
| `GENERATE_CRITERIA` | Có JD, chưa có criteria cho JD mới nhất | Đề xuất tiêu chí |
| `REVIEW_CRITERIA_HR` | Criteria draft/chờ HR | Tiếp tục duyệt HR |
| `WAIT_HM_APPROVAL` | Chờ HM | Xem trạng thái chờ HM |
| `APPROVE_CRITERIA_HM` | Người dùng hiện tại là HM được giao duyệt | Duyệt tiêu chí |
| `REGENERATE_CRITERIA` | Criteria bị reject hoặc stale với JD mới nhất | Tạo/điều chỉnh phiên bản mới |
| `UPLOAD_CV` | Criteria approved cho JD mới nhất, chưa có CV | Upload CV |
| `VIEW_PROCESSING` | Có operation/file đang xử lý | Theo dõi xử lý |
| `RUN_ASSESSMENT` | Có hồ sơ hoàn tất nhưng chưa matching | Chạy matching |
| `REVIEW_FILES` | Có file cần HR kiểm tra | Kiểm tra file |
| `REVIEW_EVIDENCE` | Có hồ sơ cần xác minh | Tiếp tục xác minh |
| `REVIEW_DUPLICATES` | Có duplicate pending | Kiểm tra cảnh báo trùng |
| `SHARE_SHORTLIST` | Có hồ sơ shortlist chưa được chia sẻ phù hợp | Chia sẻ shortlist |
| `VIEW_RANKING` | Không còn việc ưu tiên | Mở Applicant Review |
| `VIEW_ONLY_CLOSED` | Position đã đóng/paused theo rule hiện tại | Xem thông tin, không mở upload |

Thứ tự ưu tiên khi nhiều điều kiện cùng đúng phải được backend test: file review → duplicate → needs verification → possible mismatch → not assessed/processing theo trạng thái thực tế. Không để mỗi màn hình tự sắp xếp khác nhau.

### 5.3. Applicant queue model dùng chung

Tạo pure model ở frontend và contract test với dữ liệu backend:

| Queue | Điều kiện |
|---|---|
| `file_review` | `file_processing_status = NEEDS_HR_REVIEW` |
| `duplicate` | `has_duplicate_warning = true` |
| `needs_verification` | ranking item `needs_verification = true` |
| `possible_mismatch` | `has_mismatch = true` |
| `not_assessed` | `matching_status = NOT_ASSESSED` |
| `meets_mandatory` | display category hiện tại là `MEETS_MANDATORY` |

Một hồ sơ có thể thuộc nhiều flag; chips hiển thị số theo flag. Khi chọn một queue, danh sách lọc theo flag đó. Sort `REVIEW_PRIORITY` dùng thứ tự: file review, duplicate, needs verification, possible mismatch, not assessed, meets mandatory; trong cùng nhóm giữ ranking/score hiện tại.

### 5.4. Candidate navigation context

- Applicants page ghi ordered application IDs + queue/sort/search vào `sessionStorage` theo `position_id` trước khi điều hướng.
- Candidate page đọc context, hiển thị prev/next và vị trí trong hàng đợi.
- Nếu context không còn hợp lệ hoặc người dùng mở link trực tiếp, prev/next bị ẩn và nút quay lại danh sách vẫn hoạt động.
- Sau khi HR đổi trạng thái, candidate page làm mới dữ liệu; nếu hồ sơ rời khỏi queue, nút “Tiếp theo” đi tới ID kế tiếp đã lưu hoặc quay về queue.

## 6. Lộ trình triển khai theo batch

### UX-0 — Discovery, baseline và khóa contract

**Mục tiêu:** tránh code giao diện dựa trên trạng thái suy đoán.

Công việc:

- Chốt state matrix cho Position Workspace và thứ tự next action.
- Chốt schema `GET /dashboard/work-queue` và `GET /positions/{id}/workspace`.
- Kiểm kê component/`sx` trùng lặp; chỉ chọn component sẽ tạo ở UX-1/UX-2.
- Viết kịch bản usability 5 tình huống của GPT và cách đo baseline.
- Xác nhận vai trò: HR Recruiter, HR Lead, HM, Admin; màn hình mặc định theo vai trò.

Đầu ra:

- Contract/API schema được duyệt.
- Wireframe mức cấu trúc cho Dashboard, Position Workspace, Applicant Review, Candidate Review.
- Baseline usability script; chưa cần số liệu nếu staging chưa sẵn sàng.

**Gate:** Không code UX-1 nếu state matrix chưa được HR/Dev thống nhất.

### UX-1 — Workflow Foundation: My Work Queue + Position Workspace

**Mục tiêu:** HR mở hệ thống là biết việc cần làm và vị trí đang ở bước nào.

Backend:

- Thêm work-queue aggregate có scope theo user.
- Thêm position workspace summary/next action.
- Unit/integration test cho state priority và RBAC scope.

Frontend:

- Đổi `/dashboard` thành Tổng quan công việc: KPI + Work Queue + phần tổng quan cũ.
- Sidebar phân nhóm công việc/quản trị; giữ route.
- AppLayout truyền profile/roles xuống Header, bỏ lần gọi `authApi.me()` trùng.
- Tạo `PageHeader`, `WorkflowStepper`, `NextActionCard`, `WorkQueueList`, `PositionSummary`, `EmptyState`.
- Position detail thêm summary/stepper/next action ở trên tabs; tab hiện tại nhận query `tab` để deep link.

File dự kiến:

- `backend/app/api/dashboard.py`, `backend/app/api/positions.py` hoặc router workspace riêng.
- `backend/tests/test_dashboard_analytics.py`, `backend/tests/test_phase1_integration.py`.
- `frontend/src/components/layout/AppLayout.tsx`, `Header.tsx`, `Sidebar.tsx`.
- `frontend/src/app/dashboard/page.tsx`, `frontend/src/app/positions/[id]/page.tsx`.
- `frontend/src/components/common/PageHeader.tsx`, `WorkflowStepper.tsx`, `NextActionCard.tsx`, `WorkQueueList.tsx`, `EmptyState.tsx`.
- `frontend/src/lib/api.ts`, `frontend/src/types/index.ts`, i18n dictionaries.

Nghiệm thu:

- Work item dẫn đúng position/queue; số lượng khớp API/dashboard.
- HM không thấy việc/hồ sơ ngoài share; HR không thấy position ngoài assignment trừ vai trò toàn cục hiện tại.
- Position ở từng trạng thái mẫu hiển thị đúng step và next action.
- Không thay đổi hành vi duyệt criteria/upload/matching hiện tại.

### UX-2 — Applicant Review + Candidate Review

**Mục tiêu:** giảm thao tác rà soát số lượng lớn và đối chiếu bằng chứng.

Frontend:

- Applicants: queue chips có count, URL query state, search, sort, sticky table header, bulk share bar rõ hơn.
- Dùng chung queue/sort model cho bảng desktop và cards mobile.
- Candidate: sticky summary/action bar, prev/next theo queue context, evidence selected state, panel profile/notes/history có thứ tự hợp lý.
- Tách `EvidenceCard` và `CVDocumentViewer` khỏi page khi việc tách không làm thay đổi hành vi.
- Giữ click evidence → page jump; không cam kết highlight text.

File dự kiến:

- `frontend/src/app/positions/[id]/applicants/page.tsx`.
- `frontend/src/app/positions/[id]/applicants/[applicantId]/page.tsx`.
- `frontend/src/components/candidates/EvidenceCard.tsx`, `CVDocumentViewer.tsx`, `StickyActionBar.tsx`.
- `frontend/src/lib/applicantReview.ts` cho queue/sort/navigation model và test thuần.
- `frontend/tests/` cho model/i18n/E2E synthetic.

Nghiệm thu:

- Từ Work Queue mở `queue=needs_verification` thì Applicants chỉ hiển thị đúng nhóm.
- Prev/next đi đúng thứ tự đang nhìn thấy; back quay lại đúng filter.
- Evidence đã xác minh có page mới nhảy đúng trang; evidence chưa xác minh không tạo cảm giác đã kiểm chứng.
- HR đổi trạng thái vẫn qua dialog xác nhận và lý do bắt buộc khi loại như hiện tại.

### UX-3 — CV Intake + Operation Progress

**Mục tiêu:** upload và theo dõi xử lý không còn là dialog rời rạc.

Công việc:

- Tạo `CVIntakePanel` và `IntakeFileList` trong Position Workspace.
- Pre-validation từng file ở client; cảnh báo trùng tên là cảnh báo kiểm tra, không tự kết luận duplicate candidate.
- Tạo `OperationProgressPanel` dùng chung cho position detail và applicants.
- Hiển thị invalid files, failed count và CTA sau xử lý: kiểm tra file, chạy matching hoặc mở ranking.
- Giữ upload API hiện tại; chỉ bổ sung API nếu operation progress thiếu dữ liệu đã có trong DB.

File dự kiến:

- `frontend/src/app/positions/[id]/page.tsx`.
- `frontend/src/components/positions/CVIntakePanel.tsx`, `OperationProgressPanel.tsx`.
- `frontend/src/lib/api.ts`, types/i18n.
- Backend chỉ khi cần mở rộng `backend/app/api/operations.py` theo contract đã duyệt.

Nghiệm thu:

- File sai định dạng/vượt dung lượng bị chặn trước khi gửi và có lý do theo từng file.
- Đang upload, đang xử lý file và đang matching là ba trạng thái phân biệt.
- Sau khi batch hoàn tất, CTA dẫn tới đúng queue hoặc matching.
- Không có nút retry nếu backend chưa hỗ trợ retry thật.

### UX-4 — Interaction polish và chuẩn hóa design system theo nhu cầu

**Mục tiêu:** nhất quán và dễ dùng hằng ngày sau khi workflow chính đã ổn định.

Công việc:

- Chuẩn hóa tokens còn rời rạc vào `lib/theme.ts`/CSS variables; giảm `sx` trùng lặp ở các màn hình đã chạm.
- Skeleton theo khu vực, empty state có CTA, toast có hành động “Mở kết quả”.
- Kiểm tra keyboard/focus/aria, responsive và text không chỉ dựa vào màu.
- Rà soát i18n cho mọi nhãn mới; không hardcode chuỗi ngoài hệ thống dịch hiện tại.
- Đánh giá lại sidebar collapse trên desktop nếu người dùng cần thêm không gian bảng.

Nghiệm thu:

- Frontend type-check, lint, build và i18n test đạt.
- Các luồng chính dùng được bằng bàn phím; focus visible.
- Màn hình hẹp vẫn truy cập được CTA chính và trạng thái hồ sơ.

### UX-5 — Backlog sau khi có dữ liệu/contract riêng

Chỉ lập plan riêng khi có nhu cầu và điều kiện:

- PDF viewer bằng `pdf.js` với text layer/highlight.
- Global Search có backend search và RBAC theo position/share.
- Server-side pagination/sort/filter cho Applicant Review khi dữ liệu lớn.
- Retry từng file ở CV Intake.
- Overall assessment confidence khi backend định nghĩa được chỉ số.
- HM work items theo scorecard/deadline khi F2.02 Phase 2 được triển khai.

## 7. Kiểm thử và nghiệm thu

### 7.1. Kiểm thử kỹ thuật

- Backend unit test cho workspace state/next-action priority và work-queue aggregation.
- Backend integration test cho RBAC: HR assigned, HR Lead/Admin, HM shared, HM unshared, outsider.
- Frontend pure tests cho queue filter/sort/navigation context.
- Frontend `test:i18n`, `type-check`, lint, build.
- E2E synthetic hiện có và bổ sung kịch bản điều hướng Work Queue → Position → Applicant Queue → Candidate → Next.
- Kiểm tra trực quan desktop/mobile cho các route chính; không để CTA chính bị che bởi sticky bar.

### 7.2. Usability test

Dùng 5 tình huống GPT đề xuất:

1. Tạo vị trí và hoàn tất phê duyệt tiêu chí.
2. Upload 20 CV, xử lý file lỗi.
3. Tìm hồ sơ cần xác minh bằng chứng.
4. Đọc CV, kiểm tra evidence và cập nhật trạng thái.
5. Chọn shortlist và chia sẻ với HM.

Đo trước/sau:

- thời gian hoàn thành;
- số click/chuyển trang;
- số lần quay lại;
- tỷ lệ hoàn thành đúng;
- số lần cần hỏi người hướng dẫn;
- nhận định định tính của HR/HM.

Không đặt mục tiêu phần trăm giảm thời gian trước khi có baseline. Usability test chỉ thực hiện trên staging với dữ liệu tổng hợp sau khi môi trường cho phép.

### 7.3. Tiêu chí Done toàn chương trình

- HR xác định được việc tiếp theo từ Dashboard và Position Workspace mà không phải mở từng tab để đoán.
- Mọi work item có deep link đúng scope/queue.
- Applicant Review giữ ranking nhưng ưu tiên hàng đợi rà soát.
- Candidate Review giữ bằng chứng truy vết được tới CV/trang; không hiển thị confidence giả.
- Không thay đổi kết quả matching, trạng thái nghiệp vụ hoặc quyền dữ liệu.
- CI đạt và có bằng chứng E2E synthetic; usability trên staging là gate riêng.

## 8. Phụ thuộc, rủi ro và điểm dừng

| Rủi ro/phụ thuộc | Cách xử lý trong plan |
|---|---|
| Phase 1 DEP-01 chưa có staging mapping/owner | UX-0 và plan có thể làm; triển khai code diện rộng nên chờ DEP-01 đạt hoặc có risk acceptance rõ ràng theo quyết định quản trị. |
| Frontend tự suy luận workflow | Chốt API workspace/work-queue ở UX-0; có backend tests. |
| Số queue không khớp giữa Dashboard/Position/Applicants | Dùng cùng định nghĩa backend và queue model; contract test. |
| Candidate prev/next dùng danh sách cũ | Context có position/queue/sort; làm mới sau khi đổi trạng thái và fallback về danh sách. |
| PDF signed URL/iframe giới hạn | Vòng đầu chỉ page jump; highlight để backlog với đánh giá pdf.js riêng. |
| Dữ liệu lớn làm client-side list chậm | Vòng đầu giữ cơ chế hiện tại; đo hiệu năng trước khi chuyển server-side pagination. |
| Thay đổi UI làm HR mất thói quen | Giữ route/tab chính, triển khai theo batch và đo usability baseline. |
| F2.02 scorecard chưa triển khai | Work Queue không hiển thị deadline/điểm HM giả; chỉ dùng tín hiệu share/feedback hiện có. |

## 9. Quyết định cần duyệt trước khi triển khai

| ID | Quyết định | Đề xuất |
|---|---|---|
| UX-D01 | Điểm vào mặc định theo vai trò | HR/HM vào Tổng quan công việc; Admin quản trị có thể vào khu quản trị hoặc vẫn xem tổng quan theo quyền. |
| UX-D02 | Backend sở hữu workflow state | Backend trả `workflow.steps` và `next_action`; frontend không tự tính lại. |
| UX-D03 | Thứ tự ưu tiên queue | File review → duplicate → needs verification → possible mismatch → not assessed/meets mandatory. |
| UX-D04 | CV Intake ở đâu | Panel trong Position Workspace ở vòng đầu; chưa tạo route riêng. |
| UX-D05 | PDF highlight | Chưa làm; chỉ page jump cho tới khi có plan pdf.js riêng. |
| UX-D06 | Thời điểm code UX-1 | Sau khi DEP-01 có bằng chứng hoặc có chấp nhận rủi ro bằng văn bản; UX-0 được làm trước. |
| UX-D07 | Người tham gia usability | Ít nhất HR Recruiter và Hiring Manager dùng dữ liệu tổng hợp trên staging. |

## 10. Thứ tự khuyến nghị

1. Duyệt plan và UX-D01…UX-D07.
2. Làm UX-0: contract, state matrix, wireframe cấu trúc và baseline script.
3. Khi gate triển khai cho phép, làm UX-1 Workflow Foundation.
4. Làm UX-2 Applicant/Candidate Review.
5. Làm UX-3 CV Intake/Operation.
6. Làm UX-4 polish/design system theo nhu cầu thực tế.
7. Chỉ mở UX-5 khi có contract/dữ liệu/nhu cầu riêng.

Plan này không thay thế `doc/PHASE2_IMPLEMENTATION_PLAN.md` cho F2.01/F2.02. Hai lộ trình có thể bổ trợ nhau: UI/UX tạo workspace và hàng đợi; Phase 2 bổ sung nghiệp vụ rubric/scorecard vào cùng workspace khi được triển khai.
