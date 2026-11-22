# Lịch phỏng vấn & scorecard — đề xuất triển khai

Ngày: 2026-11-21. HEAD lúc viết: `3c8583c`. Mục nguồn: `VIEC_CHO_LAM.md` §1.

Tài liệu này **không** tự phê duyệt nghiệp vụ. Bốn câu hỏi ở §1 (dưới) là của
anh/HR; phần còn lại là phương án kỹ thuật để trả lời xong là code được ngay.

---

## 0. Hiện trạng đã kiểm trong code (để không dò lại)

| Điều | Bằng chứng |
|---|---|
| **Không có** bảng/endpoint lịch phỏng vấn | `grep -rn "CREATE TABLE.*interview" supabase/migrations/` = 0; không file nào trong `backend/app/api/` tên interview |
| Trạng thái có sẵn | `SHORTLIST → INTERVIEW → OFFERED / REJECTED_INTERVIEW` (`schemas/applications.py`, ma trận ở `api/applications.py:40`) |
| Scorecard **đã có** nhưng gắn shortlist share | `shortlist_scorecards.share_item_id` **UNIQUE NOT NULL** (`00023:49`); tạo tự động khi share (`shortlist.py:158`) |
| Scorecard có đủ thứ cần cho vòng phỏng vấn | `criteria_version_id`, `due_at`, `overall_recommendation` (4 mức), `strengths`, `concerns`, `status`, `revision` |
| Tiêu chí chấm dùng lại `criteria_items` | `shortlist_scorecard_criteria(criterion_id)` + ràng buộc `NOT insufficient_evidence OR rating IS NULL` |
| Quyền theo assignment | `core/permissions.py:253` `application_capabilities()` → `view_cv`, `update_status`, `manage_hr_notes`, `review_evidence` |
| Hàng đợi việc đã có khung | `api/dashboard.py:393` `/work-queue`; `services/workspace.py` có `_needs_verification`, `_WORK_TYPE_QUEUES` |

**Kết luận quan trọng:** khoảng trống **không** phải "chưa có scorecard". Đã có
scorecard chấm theo tiêu chí của đúng bản rubric. Khoảng trống là:

1. **Không có buổi phỏng vấn** — không ai/giờ/địa điểm/vòng.
2. Scorecard bị **khoá cứng vào `share_item_id`**, nên không dùng được cho một
   buổi phỏng vấn (một hồ sơ có thể có 2–3 buổi, nhiều người chấm).

Vì vậy phương án rẻ nhất là **mở khoá scorecard hiện có**, không viết scorecard thứ hai.

---

## 1. Bốn câu phải trả lời trước khi code

Đây là chặn thật, không phải thủ tục. Mỗi câu đổi schema hoặc đổi phạm vi.

### Q1. Ai được tạo/sửa lịch?

- **Đề xuất:** HR phụ trách vị trí (`hr_access` trong `application_capabilities`)
  và HR_LEAD. Hiring Manager **chỉ xem** lịch của mình, trừ khi được cấp quyền
  riêng sau.
- **Vì sao:** HM hiện chỉ thấy hồ sơ đã share. Cho HM tạo lịch nghĩa là cho HM
  đặt lịch cho ứng viên họ chưa được xem — mở một đường vòng qua shortlist.
- **Ảnh hưởng:** một capability mới `manage_interviews` trong `permissions.py`.

### Q2. Một buổi có nhiều người phỏng vấn không?

- **Đề xuất:** **có**. Bảng `interview_participants` (buổi × người × vai trò
  `INTERVIEWER`/`OBSERVER`), mỗi người một scorecard.
- **Vì sao:** phỏng vấn hội đồng là chuẩn ở trường đại học; mô hình một-người
  buộc phải tạo 3 buổi giả cho cùng một giờ, và báo cáo "ai đã chấm" sẽ sai.
- **Ảnh hưởng:** scorecard cần khoá `(interview_id, reviewer_user_id)`, không
  phải `interview_id` đơn.

### Q3. Có bắt buộc gắn vòng (round) không?

- **Đề xuất:** `round_number smallint NOT NULL DEFAULT 1`, cho phép 1..10.
- **Vì sao:** "vòng mấy" là câu HR hỏi đầu tiên khi xem lịch; để NULL rồi suy ra
  từ thứ tự thời gian là suy diễn, và sai khi có buổi bị huỷ rồi xếp lại.

### Q4. Ứng viên có nhận thông báo không?

- **Đề xuất cho vòng này: KHÔNG.** Chỉ hiện lịch trong app.
- **Vì sao:** gửi email cho ứng viên là thay đổi phạm vi lớn — cần mẫu thư, cần
  xử lý gửi lỗi, cần chống gửi trùng, cần nói rõ đây là dữ liệu thật (hiện
  `PUBLIC_CAREERS_TEST_INTAKE_ENABLED` vẫn chỉ nhận `@example.test`). Nếu thêm
  bây giờ thì đó là dự án thứ hai, không phải phần mở rộng của việc này.
- **Hệ quả phải chấp nhận:** HR vẫn phải gửi thư mời bên ngoài ở vòng này. Nếu
  anh thấy điều đó làm tính năng vô dụng thì phải mở Q4 thành phạm vi riêng —
  nói thẳng: **tính năng này chỉ có giá trị nếu HR chấp nhận gửi thư tay**, hoặc
  ta làm luôn phần thư.

> Ba câu Q1–Q3 tôi có đề xuất và có thể tự quyết theo hướng đó nếu anh không
> phản đối. **Q4 thì không** — nó đổi bản chất dự án.

---

## 2. Phương án schema

Hai bảng mới, **không** sửa bảng cũ theo hướng phá vỡ.

```sql
-- 00039_interviews.sql
CREATE TABLE app_private.interviews (
    interview_id     uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id   uuid NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    round_number     smallint NOT NULL DEFAULT 1 CHECK (round_number BETWEEN 1 AND 10),
    status           text NOT NULL DEFAULT 'SCHEDULED'
                     CHECK (status IN ('SCHEDULED','DONE','CANCELLED','NO_SHOW')),
    starts_at        timestamptz NOT NULL,          -- LUÔN UTC
    ends_at          timestamptz NOT NULL,
    location_kind    text NOT NULL CHECK (location_kind IN ('ONSITE','ONLINE','PHONE')),
    location_text    text,                           -- phòng họp / link / số điện thoại
    created_by       uuid REFERENCES auth.users(id),
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_at > starts_at),
    CHECK (location_kind = 'ONSITE' OR location_text IS NOT NULL)  -- online/phone phải có link/số
);
-- Một hồ sơ không thể có hai buổi cùng vòng còn hiệu lực.
CREATE UNIQUE INDEX uq_interviews_active_round
    ON app_private.interviews(application_id, round_number)
    WHERE status IN ('SCHEDULED','DONE');

CREATE TABLE app_private.interview_participants (
    interview_id     uuid NOT NULL REFERENCES app_private.interviews(interview_id) ON DELETE CASCADE,
    user_id          uuid NOT NULL REFERENCES auth.users(id),
    participant_role text NOT NULL DEFAULT 'INTERVIEWER'
                     CHECK (participant_role IN ('INTERVIEWER','OBSERVER')),
    added_by         uuid REFERENCES auth.users(id),
    created_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (interview_id, user_id)
);
```

**Mở khoá scorecard** — migration này là phần rủi ro nhất nên phải làm đúng:

```sql
-- scorecard gắn hoặc với share (đường cũ) hoặc với buổi phỏng vấn (đường mới)
ALTER TABLE app_private.shortlist_scorecards
    ALTER COLUMN share_item_id DROP NOT NULL,
    ADD COLUMN interview_id uuid REFERENCES app_private.interviews(interview_id) ON DELETE CASCADE;

-- Đúng một trong hai phải có mặt.
ALTER TABLE app_private.shortlist_scorecards
    ADD CONSTRAINT scorecard_has_exactly_one_source
    CHECK ((share_item_id IS NOT NULL)::int + (interview_id IS NOT NULL)::int = 1);

-- Một người chấm một buổi đúng một lần.
CREATE UNIQUE INDEX uq_scorecard_interview_reviewer
    ON app_private.shortlist_scorecards(interview_id, reviewer_user_id)
    WHERE interview_id IS NOT NULL;
```

### Vì sao mở khoá thay vì bảng `interview_scorecards` riêng

| | Mở khoá (đề xuất) | Bảng riêng |
|---|---|---|
| Code API | Dùng lại `scorecards.py` (8 route đã có, có reopen + history) | Viết lại 8 route, hoặc nhân đôi |
| Sửa lỗi | Sửa một chỗ | Phải sửa hai chỗ, và chúng sẽ lệch nhau |
| Báo cáo "điểm theo tiêu chí" | Một nguồn | Phải hợp hai nguồn, sai lệch kiểu gì cũng xảy ra |
| Rủi ro | `DROP NOT NULL` trên bảng đang có dữ liệu — nhưng chỉ nới ràng buộc, không mất dòng nào | Không đụng bảng cũ |
| Ràng buộc mới | Cần `CHECK` đúng-một-nguồn, nếu quên thì scorecard mồ côi | Không có |

Đánh đổi thật: `DROP NOT NULL` là thao tác **nới**, nên không thể làm hỏng dòng
cũ; dòng cũ vẫn có `share_item_id` nên vẫn thoả `CHECK`. Rủi ro thấp hơn hẳn
việc nhân đôi 8 route.

---

## 3. Phương án API

Router mới `api/interviews.py`, theo đúng khuôn `scorecards.py`.

| Method | Đường | Quyền | Ghi chú |
|---|---|---|---|
| `POST` | `/interviews` | `manage_interviews` | Tạo buổi + participants trong **một** transaction |
| `GET` | `/interviews?from&to&position_id&mine=true` | xem lịch của mình, hoặc HR của vị trí | `mine=true` cho màn "Lịch của tôi" |
| `GET` | `/interviews/{id}` | người tham gia, HR của vị trí, HR_LEAD | |
| `PATCH` | `/interviews/{id}` | `manage_interviews` | Đổi giờ/địa điểm/vòng; **không** đổi `application_id` |
| `POST` | `/interviews/{id}/status` | `manage_interviews` | `SCHEDULED → DONE / CANCELLED / NO_SHOW`; chuyển ngược bị chặn trừ `CANCELLED → SCHEDULED` (dời lịch) |
| `POST` | `/interviews/{id}/scorecards` | `manage_interviews` | Sinh scorecard cho từng `INTERVIEWER` từ rubric đã duyệt **của đúng JD hiện tại** |
| `GET` | `/interviews/mine?week=` | mọi người | Tuần hiện tại/tuần chỉ định |

**Ba chốt chặn cố ý:**

1. **Không tạo được buổi nếu hồ sơ chưa `SHORTLIST`.** Phỏng vấn trước khi
   shortlist là bỏ qua bước sàng lọc — nếu HR muốn nhảy, họ đổi trạng thái
   trước, và việc đó có ghi vết.
2. **Không chấm được buổi chưa `DONE`.** Chấm trước là chấm dự đoán.
3. **Scorecard dùng `criteria_version_id` đã duyệt cho đúng `jd_version_id` hiện
   tại.** Nếu rubric đổi giữa lúc đặt lịch và lúc chấm, buổi đó phải được đánh
   dấu để HR quyết định chấm lại — không tự đổi tiêu chí dưới chân người chấm.

**Múi giờ.** Lưu UTC (`timestamptz`), API nhận và trả ISO-8601 có offset, giao
diện hiển thị `Asia/Ho_Chi_Minh` và **luôn ghi kèm múi giờ** khi đặt lịch
("14:00 (GMT+7)"). Ràng buộc đã có sẵn khuôn: `positions.py:507` chặn
`application_deadline_at` không có offset — dùng lại đúng câu đó.

---

## 4. Phương án giao diện

Ba chỗ, xếp theo giá trị:

1. **Khối "Lịch phỏng vấn" trong hồ sơ** (`applicants/[applicantId]`): danh sách
   buổi theo vòng, trạng thái, người phỏng vấn, nút Đặt lịch. Đây là nơi HR đang
   đứng khi cần đặt lịch.
2. **`/interviews` — "Lịch của tôi" theo tuần.** Một cột ngày, không cần
   calendar phức tạp. Dùng lại `week` helper nếu có; nếu không thì 7 dòng.
3. **Hàng đợi:** thêm hai loại việc vào `workspace.py`:
   - `INTERVIEW_TODAY` — buổi hôm nay chưa `DONE`.
   - `SCORECARD_OVERDUE` — scorecard `due_at < now()` và chưa `SUBMITTED`.
   Cùng kiểu "quá N ngày" đang có, để lịch không nằm ngoài luồng việc.

**Không làm ở vòng này:** kéo-thả lịch, đồng bộ Google Calendar, nhắc qua email,
đặt lịch nhiều ứng viên một lượt.

---

## 5. Chia bước — mỗi bước tự dùng được

Xếp để bước 1 đã có giá trị, không phải chờ đủ bộ.

| Bước | Nội dung | Tự dùng được khi xong? | Ước lượng |
|---|---|---|---|
| **B1** | Migration `00039` (2 bảng + mở khoá scorecard) + `interviews.py` CRUD + quyền + test | Có — đặt/xem lịch được, dù chưa chấm | 1–1,5 ngày |
| **B2** | Sinh scorecard theo buổi + `POST /status` + nối `scorecards.py` nhận `interview_id` | Có — chấm được theo buổi | 1 ngày |
| **B3** | Khối lịch trong hồ sơ + `/interviews` theo tuần | Có — dùng được không cần biết API | 1–1,5 ngày |
| **B4** | Hai loại việc trong work-queue + dashboard | Có — lịch vào luồng việc | 0,5 ngày |

Tổng 3,5–4,5 ngày. Nếu chỉ làm được một bước: **B1**, vì sau B1 đã trả lời được
"tuần này ai phỏng vấn ai" — câu HR hỏi hằng ngày.

### Đã làm (2026-11-29)

| Bước | Commit | Kết quả |
|---|---|---|
| B1 | `a7d619e` | Migration `00039` đã áp (`interviews_00039`); 5 route CRUD; 32 test |
| B2 | `f835e5a` | Migration `00040` đã áp (`interview_scorecards_00040`); sinh scorecard theo buổi; 12 test; 2 test chống hồi quy cho đường share |
| B3 | `d699b09` | `InterviewPanel` trong hồ sơ + `/interviews` theo tuần; logic tuần tách ra `lib/interviewWeek.ts`, 10 test |
| B4 | `f5b5e8f` | `INTERVIEW_TODAY` + `SCORECARD_OVERDUE` trong work-queue; 12 test |
| Purge | sau B4 | `interviews`/`interview_participants` vào phạm vi `CV` của `test_data_purge.py`, 3 test |

Ba chỗ khác với bản đề xuất, đều vì kiểm lại code/DB thấy khác:

1. **B2 tách thành migration `00040`.** `00039` đã áp rồi thì không được sửa file
   nữa — PostgreSQL sẽ không chạy lại nó. Việc mở khoá scorecard nằm ở `00040`.
2. **Số bảng "CASCADE cả hai" ở §6 chưa đúng.** `interviews → applications` là
   CASCADE (`interviews_application_id_fkey`, `confdeltype='c'`), nhưng
   `interview_participants` không trỏ tới `applications`; nó CASCADE vào
   `interviews`. Hệ quả cho purge: hai bảng **không** được nằm trong
   `PROTECTED_TABLES`. Nếu nằm đó, chọn xoá `CV` vẫn xoá sạch chúng qua CASCADE và
   preview sẽ nói dối rằng chúng được bảo vệ. Đã kiểm `pg_constraint` trên DB thật
   và thêm 5 cạnh vào `tests/fixtures/app_private_foreign_keys.json`.
3. **Retention thật chưa đụng tới.** Đề xuất ghi "và vào luồng retention thật";
   luồng đó đang dựa trên hồ sơ nên xoá hồ sơ đã kéo lịch theo qua CASCADE. Không
   thêm bảng vào retention là chủ ý, không phải bỏ sót.

---

## 6. Rủi ro và cách chặn

| Rủi ro | Cách chặn |
|---|---|
| Đổi scorecard làm hỏng đường share đang chạy | `CHECK` đúng-một-nguồn + test cho **cả hai** đường; dữ liệu cũ vẫn thoả vì có `share_item_id` |
| Hai người đặt lịch cùng lúc cho cùng vòng | `uq_interviews_active_round` là unique index bộ phận → DB chặn, không phải code |
| Múi giờ sai lệch | Bắt buộc offset ở API (khuôn đã có), lưu UTC, hiện kèm GMT+7 |
| Rubric đổi giữa lúc đặt lịch và lúc chấm | Lưu `criteria_version_id` lúc sinh scorecard; nếu khác bản APPROVED hiện tại thì đánh dấu "rubric đã đổi" thay vì tự đổi |
| Xoá hồ sơ kéo theo lịch | `ON DELETE CASCADE` cả hai bảng — đúng, vì lịch của hồ sơ đã xoá là dữ liệu chết |
| Retention không biết bảng mới | Thêm `interviews`/`interview_participants` vào phạm vi purge của `test_data_purge.py` **và** vào luồng retention thật |

**Việc cuối cùng trong bảng là chỗ dễ bỏ sót nhất.** `PROTECTED_TABLES` trong
`test_data_purge.py` hiện có `job_families`; bảng mới phải được phân loại rõ:
xoá được khi xoá hồ sơ (cascade), và **không** nằm trong protected.

---

## 7. Điều tôi sẽ không tự làm

- Không tự đặt lịch mẫu hay seed dữ liệu phỏng vấn vào DB thật.
- Không gửi thư cho ứng viên ở vòng này (Q4).
- Không đổi ma trận trạng thái hồ sơ: lịch phỏng vấn là **dữ liệu bổ sung**,
  không phải điều kiện mới để chuyển `SHORTLIST → INTERVIEW`. Nếu biến nó thành
  điều kiện, mọi hồ sơ đang ở `INTERVIEW` sẽ thành dữ liệu không hợp lệ.
