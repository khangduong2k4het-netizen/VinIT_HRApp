# Spec P3-1: Talent Pool và Candidate Rediscovery

Thuộc đề xuất Phase 3, mục P3-1.

Đây là **spec đề xuất**, chưa phải quyết định. Chỗ nào là quyết định của HR/Pháp chế được ghi là `D-TP-xx` ở mục 2. Phần "Hiện trạng" là sự thật đã đọc trong code/migration; phần còn lại là thiết kế đề xuất.

## 1. Hiện trạng của hệ thống (cơ sở của thiết kế)

| Điều đã có | Hệ quả cho thiết kế |
| :--- | :--- |
| **Không có bảng candidate dùng chung.** `applications` thuộc đúng một `position_id`; `application_identities` (tên, email, SĐT) gắn 1-1 với application (migration 00001, ghi chú "no global candidate table") | Ứng viên cũ chỉ tồn tại dưới dạng application của vị trí cũ. Rediscovery phải tạo cấu trúc mới, không thể chỉ "tìm trong DB" |
| `assessment_runs` buộc `position_id`, `application_id`, `criteria_version_id`, `profile_version_id` | Chấm một ứng viên cũ theo rubric vị trí mới cần một application mới trong vị trí mới (hoặc bảng kết quả riêng) |
| Retention: `application_retention_cases` sinh khi vị trí đóng, hạn = ngày đóng + 12 tháng; xóa vật lý cần HR xác nhận (+ OTP, F2.07); case còn lại dạng ẩn danh sau khi xóa (migration 00012) | Hồ sơ cũ sẽ bị xóa sau 12 tháng nếu không có gì can thiệp. Talent Pool phải có đường đi rõ ràng với retention |
| F2.07: tạm hoãn (`ON_HOLD`) yêu cầu lý do từ danh sách và số văn bản Pháp chế; scheduler tắt mặc định | Có thể tái dùng cơ chế hold, nhưng ý nghĩa pháp lý khác ("đang khiếu nại" khác "ứng viên đồng ý lưu tiếp") |
| Có `services/mailer.py` (SMTP), `audit_events` append-only có hash chain, `app_private` schema + RLS + `service_role` | Dùng lại cho email consent, audit, và quyền truy cập |
| Hạ tầng matching: rule engine tất định + LLM fallback + (tùy chọn) BGE; `redaction.py` | Rediscovery dùng lại, không cần model mới |
| Nhãn trạng thái application có `INTERVIEW`, `REJECTED_INTERVIEW`, `OFFERED`, `ACCEPTED` | Có thể xác định "đạt chuẩn phỏng vấn nhưng chưa nhận offer" theo PRD |

## 2. Quyết định cần chốt (chặn thiết kế chi tiết)

| Mã | Câu hỏi | Người chốt | Đề xuất mặc định |
| :--- | :--- | :--- | :--- |
| D-TP-01 | Mục đích, nội dung thông báo và thời hạn consent (PRD ví dụ 24 tháng; không mặc định) | Pháp chế + HR Lead | 24 tháng, gia hạn được bằng consent mới |
| D-TP-02 | Hồ sơ Talent Pool tồn tại **bên cạnh** retention 12 tháng như thế nào: (A) giữ hồ sơ gốc bằng hold; (B) pool tự giữ **bản sao tối thiểu**, hồ sơ gốc vẫn bị xóa đúng hạn | Pháp chế + HR Lead | **B**, vì không phá hứa hẹn retention của application gốc và dễ chứng minh xóa khi hết hạn/rút consent |
| D-TP-03 | Ai được gắn nhãn vào pool và ai được quét | HR Lead | HR phụ trách vị trí gắn nhãn; quét: HR được phân công vị trí mới + HR Lead; HM không quét |
| D-TP-04 | Điều kiện vào pool: trạng thái application nào (PRD: đạt chuẩn phỏng vấn, chưa nhận offer) | HR Lead | `INTERVIEW`, `REJECTED_INTERVIEW`, và `SHORTLIST` do HR chọn tay; không tự động |
| D-TP-05 | Gửi consent bằng kênh nào, ngôn ngữ nào, ai ký tên thư | HR + IT | Email Outlook của VinUni, song ngữ Việt–Anh, mẫu do HR duyệt |
| D-TP-06 | Khi consent hết hạn mà ứng viên không phản hồi: xóa tự động hay HR xác nhận | Pháp chế | HR xác nhận như retention hiện tại (dùng lại hàng đợi + OTP của F2.07) |
| D-TP-07 | Có cho phép ứng viên cập nhật CV qua link không (PRD có) | HR Lead | Có, ở bước sau (pha 3), vì đi qua cổng công khai cần P3-3 |

## 3. Phạm vi

**Trong phạm vi:** gắn nhãn pool; consent riêng (có bằng chứng, hạn, rút); quét pool theo rubric đã duyệt của vị trí mới và xếp hạng; HR xem bằng chứng và quyết định liên hệ; audit và retention cho dữ liệu pool.

**Ngoài phạm vi (bản này):** tự liên hệ ứng viên, tự đưa ứng viên vào vị trí mới, nhập hàng loạt hồ sơ cũ vào pool, suy đoán consent từ việc đã nộp CV hoặc gửi email, tự gia hạn retention, semantic search toàn kho (F3.07, làm sau).

## 4. Nguyên tắc bắt buộc (từ PRD và kế hoạch của nhóm)

1. Chỉ quét hồ sơ **có consent còn hạn, chưa rút, chưa quá hạn lưu trữ, không đang chờ xóa**. Kiểm tra ở backend ngay trước mỗi lượt quét và khi hiển thị kết quả, không chỉ ở lúc tạo.
2. Consent là lựa chọn **riêng**: nộp CV hay nhận phỏng vấn không phải consent.
3. Không có consent thật thì chức năng **fail-closed**: chỉ chạy với dữ liệu tổng hợp trong môi trường dev/test.
4. Mọi lượt quét và truy cập đều ghi audit, **không chứa PII** (đếm, ID đã băm, vị trí, người gọi).
5. Không gửi họ tên, SĐT, email cho LLM (giữ `redaction.py`); gửi nội dung CV ra ngoài chỉ khi DEP-05 được duyệt.
6. AI chỉ gợi ý xếp hạng; HR quyết định liên hệ.

## 5. Mô hình dữ liệu đề xuất (migration mới, đánh số tiếp sau migration hiện có)

Chỉ là thiết kế; chưa viết SQL. Theo hướng **B** của D-TP-02. Mọi bảng nằm trong `app_private`, bật RLS, chỉ `service_role` truy cập, giống các bảng retention.

| Bảng | Nội dung chính |
| :--- | :--- |
| `talent_pool_entries` | `entry_id`, `source_position_id`, `source_application_opaque_id` (ID băm, **không** FK để không giữ ràng buộc với application sắp bị xóa), `status` (`PENDING_CONSENT`, `ACTIVE`, `WITHDRAWN`, `EXPIRED`, `DELETED`), `nominated_by`, `nominated_at`, `consent_expires_at`, `retention_expires_at`, `deletion_pending` |
| `talent_pool_profiles` | bản sao **tối thiểu** dùng để chấm: `entry_id`, `profile_snapshot` (JSONB các `profile_facts` đã trích, không kèm email/SĐT), đường dẫn CV đã sao chép sang bucket riêng của pool, `extracted_text_path`, hash nội dung. Danh tính liên hệ nằm ở bảng riêng dưới đây |
| `talent_pool_contacts` | `entry_id`, tên, email, SĐT; tách bảng để dễ xóa/ẩn danh độc lập và hạn chế truy cập |
| `talent_pool_consents` | lịch sử: `consent_id`, `entry_id`, `notice_version` (phiên bản nội dung thông báo), `purpose`, `granted_at`, `expires_at`, `withdrawn_at`, `evidence` (token đã băm, thời điểm bấm, IP đã rút gọn tùy chính sách), `channel` |
| `talent_pool_tokens` | token một lần cho link đồng ý / rút / cập nhật CV: chỉ lưu hash, hạn ngắn, số lần dùng |
| `talent_pool_scans` | mỗi lượt quét: `scan_id`, `position_id` đích, `criteria_version_id` đã duyệt, người gọi, số hồ sơ đủ điều kiện, số bị loại theo từng lý do (chỉ số) |
| `talent_pool_scan_results` | kết quả chấm: `scan_id`, `entry_id`, trạng thái, điểm, độ phủ bằng chứng, các `criterion_results` + trích dẫn bằng chứng (lưu dạng cùng schema `criterion_assessment_results`/`evidence_items` hoặc bảng song song), `hr_decision` (`CONTACT`, `SKIP`, `LATER`), `decided_by`, `decided_at` |

Lý do tách `talent_pool_profiles` khỏi `application`: assessment hiện buộc `application_id` thuộc một vị trí; sao chép sang pool tránh việc application cũ phải sống thêm sau khi retention xóa.

**Tương tác với retention (hướng B):** application gốc vẫn đi đúng quy trình 12 tháng và F2.07. Khi nominate, hệ thống sao chép dữ liệu tối thiểu sang pool **chỉ sau khi consent được ghi nhận** (trạng thái `PENDING_CONSENT` chưa có profile đầy đủ, chỉ có tham chiếu đến application để chờ). Nếu hồ sơ gốc đến hạn xóa trong lúc chưa có consent thì mục `PENDING_CONSENT` chuyển `EXPIRED` và không sao chép. Hạn `consent_expires_at` mới là hạn lưu trữ của bản sao; cần Pháp chế xác nhận không mâu thuẫn với chính sách 12 tháng (D-TP-02).

## 6. Luồng nghiệp vụ

### 6.1 Gắn nhãn và xin consent

1. HR mở application đủ điều kiện (D-TP-04), bấm **"Đề xuất vào Talent Pool"**, hệ thống tạo `talent_pool_entries` ở `PENDING_CONSENT`.
2. HR xem trước email consent (mẫu song ngữ, có tên vị trí cũ, mục đích, thời hạn, quyền rút, liên hệ), bấm gửi. Không gửi tự động.
3. Email có hai link token một lần: **Đồng ý** và **Từ chối/Rút**. Link dẫn tới trang công khai tối giản, không cần đăng nhập, không hiển thị dữ liệu cá nhân ngoài tên vị trí.
4. Đồng ý: ghi `talent_pool_consents` (phiên bản thông báo, thời điểm, hạn), sao chép dữ liệu tối thiểu, entry `ACTIVE`. Từ chối hoặc không trả lời sau N ngày (đề xuất 14): entry `EXPIRED`, không sao chép gì.
5. Rút consent bất cứ lúc nào (link trong email hoặc HR nhập theo yêu cầu bằng văn bản): entry `WITHDRAWN`, **chặn quét ngay**, xếp hàng xóa dữ liệu pool (D-TP-06).

### 6.2 Quét kho (Rediscovery)

1. Điều kiện: vị trí mới `OPEN`, criteria `APPROVED` (HR + HM), người gọi có quyền theo D-TP-03.
2. HR bấm **"Quét Talent Pool"** trên trang vị trí. Backend tạo `talent_pool_scans`, rồi trong **một transaction đọc** chọn các entry thỏa: `ACTIVE`, consent chưa hết hạn, `retention_expires_at` chưa tới, không `deletion_pending`, không `WITHDRAWN`. Khóa nhẹ (hoặc kiểm lại sau khi chấm) để tránh race "rút consent trong lúc đang quét".
3. Chấm bằng pipeline hiện có (rule engine → LLM fallback cho tiêu chí chưa giải được; có thể kèm BGE nếu bật) trên `profile_snapshot`, theo `criteria_version_id` của vị trí mới. Kết quả lưu ở `talent_pool_scan_results`.
4. Trước khi **hiển thị** kết quả cho HR, kiểm tra lại điều kiện hợp lệ của từng entry (phòng trường hợp rút consent trong lúc chấm); entry hết hợp lệ bị loại khỏi danh sách và xóa kết quả của nó.
5. HR xem danh sách xếp hạng: điểm, độ phủ bằng chứng, từng tiêu chí với trích dẫn, mức không chắc chắn. HR chọn `CONTACT / SKIP / LATER`. `CONTACT` chỉ hiện thông tin liên hệ và gợi ý soạn email (qua Outlook, có xem trước); **hệ thống không tự liên hệ và không tự tạo application**. Nếu ứng viên đồng ý ứng tuyển, HR tạo application bình thường qua luồng nhập CV hiện có.

### 6.3 Hết hạn và xóa

Cron/chu kỳ nền (mở rộng chu kỳ retention hiện có, vẫn **không bao giờ xóa tự động**): đánh dấu entry sắp hết hạn consent, nhắc HR 30/15/7 ngày (cùng cơ chế thông báo F2.07), chuyển `EXPIRED` khi quá hạn, đưa vào hàng đợi xóa; xóa vật lý cần HR xác nhận (+ OTP) như F2.07. Sau xóa giữ bản ghi ẩn danh (ID băm, thời điểm, lý do) để chứng minh đã xóa.

## 7. API đề xuất (prefix `/v1/talent-pool`)

| Method | Path | Quyền | Ghi chú |
| :--- | :--- | :--- | :--- |
| POST | `/entries` | HR phụ trách vị trí nguồn / HR Lead | Body: `application_id`; kiểm tra trạng thái hợp lệ (D-TP-04) |
| POST | `/entries/{id}/consent-request` | như trên | Tạo token, trả bản xem trước email; gửi chỉ khi HR xác nhận |
| GET | `/entries` | HR Lead, HR được phân công | Danh sách + trạng thái, lọc theo vị trí nguồn; **không** trả nội dung CV |
| POST | `/entries/{id}/withdraw` | HR Lead/Admin (thay mặt theo văn bản) | Ghi lý do |
| POST | `/positions/{id}/talent-pool/scan` | theo D-TP-03 | Trả `scan_id` và chạy bất đồng bộ qua worker/operation giống assessment |
| GET | `/talent-pool/scans/{scan_id}` | người tạo, HR Lead | Kết quả đã lọc hợp lệ tại thời điểm xem |
| POST | `/talent-pool/scans/{scan_id}/results/{entry_id}/decision` | như trên | `CONTACT/SKIP/LATER` |
| GET/POST | `/public/talent-pool/consent/{token}` | **không đăng nhập** | Xem thông báo, đồng ý hoặc từ chối; rate limit, token một lần; chỉ ra tên vị trí và mục đích |
| POST | `/public/talent-pool/withdraw/{token}` | không đăng nhập | Rút consent |

Endpoint công khai chỉ cần cho consent/rút; chưa gồm form nộp CV (đó là P3-3). Đặt rate limit và giới hạn kích thước ngay từ đầu vì đây là bề mặt công khai đầu tiên của HRApp.

## 8. Giao diện (Việt/Anh, trong Recruitment Workspace hiện có)

- Trang application (HR): nút "Đề xuất vào Talent Pool" và badge trạng thái consent.
- Trang mới **Talent Pool**: danh sách entry, trạng thái consent, hạn, nhắc hạn, hàng đợi xóa (mở rộng trang "Lưu trữ & xóa dữ liệu").
- Trang vị trí: nút "Quét Talent Pool" (chỉ hiện khi vị trí OPEN và criteria APPROVED), màn kết quả có bằng chứng cạnh nhau như màn đối chiếu hiện tại, kèm cột "còn hạn consent đến".
- Trang công khai consent: một trang tối giản, nội dung do Pháp chế duyệt, hiển thị theo ngôn ngữ trong link.

## 9. Kiểm thử và nghiệm thu

Kiểm thử tự động (dữ liệu tổng hợp, PostgreSQL + pgvector như CI hiện tại):

- Điều kiện hợp lệ: chưa consent, consent hết hạn, đã rút, retention đã tới hạn, đang chờ xóa, đang `ON_HOLD`: tất cả **không** xuất hiện trong kết quả quét.
- Race: rút consent trong lúc quét; consent hết hạn giữa lúc chấm và lúc xem kết quả.
- Quyền: HM không quét/không xem pool; HR không phụ trách vị trí nguồn không gắn nhãn; token công khai dùng lại, hết hạn, sai token.
- Retention: application gốc bị xóa không làm mất pool entry đã consent; pool entry hết hạn không bị quét; xóa pool cần xác nhận + OTP; bản ghi ẩn danh còn lại không chứa PII.
- Audit: mọi quét/xem/quyết định có sự kiện, metadata không chứa tên/email/SĐT/CV.
- Chống rò rỉ: kết quả quét vị trí A không lộ cho HR chỉ phụ trách vị trí B ngoài D-TP-03.
- Fail-closed: bảng pool rỗng hoặc cấu hình tắt thì quét trả lỗi rõ, không quét application cũ thay thế.

**Tiêu chí nghiệm thu (đề xuất, một phần theo Cổng 3 của PRD):**
1. Mẫu consent và thời hạn được Pháp chế duyệt bằng văn bản.
2. 100% entry `ACTIVE` có bản ghi consent đầy đủ (phiên bản thông báo, thời điểm, hạn).
3. Không có trường hợp quét nào chạm entry không hợp lệ trong bộ test tổng hợp, kể cả race.
4. Quét một vị trí mới trên pool tổng hợp 200 hồ sơ cho kết quả có bằng chứng; thời gian chấp nhận được (cần đo, chưa có số).
5. Quy trình rút và xóa chạy đầu-cuối trên staging với dữ liệu tổng hợp.

## 10. Thứ tự triển khai đề xuất

| Pha | Nội dung | Phụ thuộc | Độ lớn |
| :--- | :--- | :--- | :-: |
| 0 | Chốt D-TP-01…D-TP-06 với Pháp chế/HR Lead; viết mẫu thông báo consent | Pháp chế | chờ |
| 1 | Migration + mô hình + luật đủ điều kiện (hàm thuần kèm truy vấn DB) + test race/retention | D-TP-02 | M |
| 2 | Gắn nhãn, email consent qua Outlook (cần P3-0: Microsoft Graph/SMTP), trang công khai consent/rút, token | IT cấp quyền gửi mail; D-TP-05 | M |
| 3 | Quét và xếp hạng, màn kết quả có bằng chứng, quyết định HR | P3-0 (pilot Phase 2 ổn); DEP-05 nếu dùng LLM với dữ liệu thật | M |
| 4 | Hết hạn, nhắc 30/15/7, hàng đợi xóa + OTP cho pool, cập nhật CV qua link (D-TP-07) | Pháp chế duyệt hold/OTP (F2.07) | S–M |

Ước lượng tổng: L (khoảng 3–4 tuần làm việc, chưa tính thời gian chờ Pháp chế/IT). Pha 1 làm được ngay mà không cần chờ quyết định cuối nếu giữ hằng số hạn consent cấu hình được.

## 11. Rủi ro

| Rủi ro | Giảm thiểu |
| :--- | :--- |
| Pháp chế không chấp nhận hướng B (bản sao tồn tại sau 12 tháng) | Chuẩn bị phương án A: dùng `ON_HOLD` với lý do mới `TALENT_POOL_CONSENT`; cần mở rộng danh sách lý do và ý nghĩa "số văn bản" |
| Nhân đôi dữ liệu cá nhân, tăng bề mặt rò rỉ | Chỉ sao chép tối thiểu; tách bảng liên hệ; RLS + service_role; xóa có xác nhận; kiểm tra chéo trong test |
| Chấm lại CV cũ tốn chi phí/LLM và cần egress | Rule engine trước; LLM chỉ cho tiêu chí chưa giải được; gate DEP-05 trước khi dùng dữ liệu thật |
| Bề mặt công khai đầu tiên (consent/rút) bị lạm dụng | Rate limit, token băm một lần, không lộ dữ liệu cá nhân, không log nội dung |
| Kết quả cũ "treo" sau khi rút consent | Kiểm tra lại điều kiện lúc hiển thị; xóa kết quả của entry không còn hợp lệ |
| Email consent bị coi là spam hoặc gửi nhầm | HR xem trước, gửi từ hòm thư chính thức, giới hạn tần suất, ghi nhật ký gửi |
| Đồng ý nhưng sau đó đổi CV/hết liên quan | Hạn consent ngắn hơn khi không cập nhật; nhắc làm mới (pha 4) |
