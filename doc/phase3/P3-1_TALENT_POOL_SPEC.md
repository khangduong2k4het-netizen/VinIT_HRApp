# Spec P3-1: Talent Pool và Candidate Rediscovery

Thuộc đề xuất Phase 3, mục P3-1.

**Cập nhật theo thông tin từ chủ dự án:** dự án có quyền lưu CV **5 năm**, và ứng viên phải **tick đồng ý cho phép sử dụng dữ liệu** khi nộp hồ sơ. Vì vậy bản này bỏ phương án "bản sao tối thiểu" và bỏ bước xin consent bằng email cho hồ sơ mới; consent lấy ngay lúc nộp và gắn thẳng vào application. Những điểm vẫn cần xác nhận được ghi ở mục 2.

**Cập nhật triển khai 19/11/2026:** đánh dấu, danh sách, quét/xếp hạng và giao diện đã có đến migration `00023`. Consent `v4` gộp xử lý vị trí và Talent Pool thành một ô bắt buộc theo yêu cầu mới nhất của chủ dự án; `v3` trước đó dùng hai ô. Retention application đã đổi thành 60 tháng sau ngày đóng vị trí (`00022`), còn hạn dùng lại pool vẫn là 60 tháng từ consent. Chưa có quyết định `CONTACT/SKIP/LATER`, cập nhật CV hoặc nghiệm thu môi trường đích. Xem [trạng thái Phase 3](../PHASE3_P3-1_P3-2_P3-3.md) và [hướng dẫn P3-3](P3-3_PUBLIC_INTAKE.md).

Các phần thiết kế đề xuất dưới đây mô tả cả phạm vi chưa triển khai; không coi toàn bộ spec là đã hoàn thành. Chỗ nào là quyết định của HR/Pháp chế được ghi là `D-TP-xx` ở mục 2. Phần "Hiện trạng" là sự thật đã đọc trong code/migration; phần còn lại là thiết kế đề xuất.

## 1. Hiện trạng của hệ thống (cơ sở của thiết kế)

| Điều đã có | Hệ quả cho thiết kế |
| :--- | :--- |
| **Không có bảng candidate dùng chung.** `applications` thuộc đúng một `position_id`; `application_identities` (tên, email, SĐT) gắn 1-1 với application (migration 00001, ghi chú "no global candidate table") | Ứng viên cũ chỉ tồn tại dưới dạng application của vị trí cũ. Rediscovery phải tạo cấu trúc mới, không thể chỉ "tìm trong DB" |
| `assessment_runs` buộc `position_id`, `application_id`, `criteria_version_id`, `profile_version_id` | Chấm một ứng viên cũ theo rubric vị trí mới cần một application mới trong vị trí mới (hoặc bảng kết quả riêng) |
| Retention: `application_retention_cases` sinh khi vị trí đóng, hạn = ngày đóng + 60 tháng (`00022`); xóa vật lý cần HR xác nhận (+ OTP, F2.07); case còn lại dạng ẩn danh sau khi xóa | Hạn lưu application và hạn dùng lại pool là hai mốc khác nhau. Pool vẫn loại hồ sơ đang chờ xóa/hold |
| F2.07: tạm hoãn (`ON_HOLD`) yêu cầu lý do từ danh sách và số văn bản Pháp chế; scheduler tắt mặc định | Có thể tái dùng cơ chế hold, nhưng ý nghĩa pháp lý khác ("đang khiếu nại" khác "ứng viên đồng ý lưu tiếp") |
| Có `services/mailer.py` (SMTP), `audit_events` append-only có hash chain, `app_private` schema + RLS + `service_role` | Dùng lại cho email consent, audit, và quyền truy cập |
| Hạ tầng matching: rule engine tất định + LLM fallback + (tùy chọn) BGE; `redaction.py` | Rediscovery dùng lại, không cần model mới |
| Nhãn trạng thái application có `INTERVIEW`, `REJECTED_INTERVIEW`, `OFFERED`, `ACCEPTED` | Có thể xác định "đạt chuẩn phỏng vấn nhưng chưa nhận offer" theo PRD |

## 2. Quyết định cần chốt (chặn thiết kế chi tiết)

| Mã | Câu hỏi | Người chốt | Đề xuất mặc định |
| :--- | :--- | :--- | :--- |
| D-TP-01 | Câu chữ ô tick lúc nộp có nêu rõ mục đích **dùng lại hồ sơ cho các vị trí khác của trường** không, và có áp dụng cho cả CV nhận qua email/HR nhập tay không. Nếu ô tick chỉ nói "xử lý hồ sơ cho vị trí này" thì chưa đủ cho Talent Pool | HR Lead (đối chiếu văn bản đang dùng) | Dùng câu chữ có nêu mục đích tái sử dụng; lưu `notice_version` |
| D-TP-02 | Hạn dùng lại pool = thời điểm tick consent + 60 tháng, theo quyết định 17/11. Hạn lưu application = ngày đóng vị trí + 60 tháng (`00022`) | HR Lead | Đã triển khai hai mốc riêng. Pool không tự gia hạn retention; case đang chờ xóa/hold luôn bị loại khỏi pool |
| D-TP-03 | Ai được gắn nhãn vào pool và ai được quét | HR Lead | HR phụ trách vị trí gắn nhãn; quét: HR được phân công vị trí mới + HR Lead; HM không quét |
| D-TP-04 | Điều kiện vào pool: trạng thái application nào (PRD: đạt chuẩn phỏng vấn, chưa nhận offer) | HR Lead | `INTERVIEW`, `REJECTED_INTERVIEW`, và `SHORTLIST` do HR chọn tay; không tự động |
| D-TP-05 | Hồ sơ **đã có trong hệ thống trước khi có ô tick** (HR nhập tay, nhận qua email) xử lý thế nào | HR Lead | Không coi là có consent; không vào pool. Chỉ gửi email xin consent riêng khi HR muốn, theo mẫu HR duyệt (làm sau) |
| D-TP-06 | Khi hết 5 năm hoặc ứng viên rút đồng ý: xóa tự động hay HR xác nhận | HR Lead | HR xác nhận như retention hiện tại (hàng đợi + OTP của F2.07); riêng rút đồng ý thì chặn quét ngay |
| D-TP-07 | Có cho phép ứng viên cập nhật CV qua link không (PRD có) | HR Lead | Có, ở bước sau, cần cổng công khai của P3-3 |

Lưu ý: tôi không phải luật sư. Phần "ô tick đã đủ chưa" chỉ cần đối chiếu câu chữ với mục đích thực tế; nếu đã đúng thì không còn việc nào phải chờ Pháp chế.

## 3. Phạm vi

**Trong phạm vi:** đánh dấu hồ sơ đủ điều kiện vào pool; kiểm tra consent đã ghi lúc nộp (có bằng chứng, rút được); quét pool theo rubric đã duyệt của vị trí mới và xếp hạng; HR xem bằng chứng và quyết định liên hệ; audit và retention cho dữ liệu pool.

**Ngoài phạm vi (bản này):** tự liên hệ ứng viên, tự đưa ứng viên vào vị trí mới, nhập hàng loạt hồ sơ cũ vào pool, suy đoán consent cho hồ sơ không có bản ghi tick, tự gia hạn retention, semantic search toàn kho (F3.07, làm sau).

## 4. Nguyên tắc bắt buộc (từ PRD và kế hoạch của nhóm)

1. Chỉ quét hồ sơ **có bản ghi consent lúc nộp (đúng mục đích tái sử dụng), chưa rút, chưa quá hạn 5 năm, không đang chờ xóa**. Kiểm tra ở backend ngay trước mỗi lượt quét và khi hiển thị kết quả, không chỉ ở lúc tạo.
2. Theo yêu cầu mới nhất, notice `v4` dùng **một ô đồng ý bắt buộc** bao gồm xử lý vị trí nguồn và tái sử dụng trong Talent Pool. Lưu hai mục đích consent riêng trong DB; không có bản ghi đúng mục đích thì không được dùng lại. Không diễn giải lại consent của các phiên bản cũ.
3. Không có consent thật thì chức năng **fail-closed**: chỉ chạy với dữ liệu tổng hợp trong môi trường dev/test.
4. Mọi lượt quét và truy cập đều ghi audit, **không chứa PII** (đếm, ID đã băm, vị trí, người gọi).
5. Không gửi họ tên, SĐT, email cho LLM (giữ `redaction.py`); gửi nội dung CV ra ngoài chỉ khi DEP-05 được duyệt.
6. AI chỉ gợi ý xếp hạng; HR quyết định liên hệ.

## 5. Mô hình dữ liệu đề xuất (migration mới, đánh số tiếp sau migration hiện có)

Các bảng consent, đánh dấu và quét đã triển khai qua migration `00020`, `00021`, `00023`; trường quyết định HR và các mở rộng dưới đây vẫn là đề xuất. Vì được giữ 5 năm và consent nằm ngay trên application, **không cần sao chép hồ sơ sang bảng riêng**: pool là một **tập con có điều kiện** của application hiện có. Mọi bảng nằm trong `app_private`, bật RLS, chỉ `service_role` truy cập.

| Bảng / cột | Nội dung chính |
| :--- | :--- |
| `application_data_consents` | `consent_id`, `application_id`, `purpose` (`THIS_POSITION`, `TALENT_POOL`), `notice_version`, `granted_at`, `channel` (`PORTAL`, `EMAIL_LINK`), bằng chứng (thời điểm, IP rút gọn tùy chính sách), `withdrawn_at`. Ghi lúc nộp; chỉ thêm, không sửa |
| `talent_pool_marks` | `application_id`, `marked_by`, `marked_at`, lý do ngắn (không tự do chứa PII), `removed_at`; HR đánh dấu hồ sơ đủ điều kiện (D-TP-04) |
| `talent_pool_scans` | mỗi lượt quét: `scan_id`, `position_id` đích, `criteria_version_id` đã duyệt, người gọi, số hồ sơ đủ điều kiện, số bị loại theo từng lý do (chỉ số) |
| `talent_pool_scan_results` | kết quả chấm: `scan_id`, `application_id`, điểm, độ phủ bằng chứng, `criterion_results` + trích dẫn (cùng schema `criterion_assessment_results`/`evidence_items` hoặc bảng song song), `hr_decision` (`CONTACT`, `SKIP`, `LATER`), `decided_by`, `decided_at` |

**Chấm lại hồ sơ cũ cho vị trí mới:** `assessment_runs` buộc `position_id`, nên một lượt quét tạo lượt chấm trong bảng kết quả riêng ở trên (không tạo application mới trong vị trí đích cho tới khi HR chọn `CONTACT`). Cần xác nhận khi làm pha 1 cách tái dùng `profile_version` đã trích mà không phải trích lại.

**Tương tác với retention:** hạn pool là `application_data_consents.granted_at + 60 tháng`; hạn application là ngày đóng vị trí + 60 tháng theo migration `00022`. Chu kỳ retention hủy case chưa xóa thuộc chính sách cũ đã bị thay thế, giữ legal hold `ON_HOLD`. Pool không quét hồ sơ trong case `SCHEDULED_FOR_DELETION` hoặc `ON_HOLD`. Rút đồng ý chặn dùng lại và bỏ đánh dấu pool; hiện chưa tự sinh case xóa theo sự kiện này. Hồ sơ nguồn vẫn theo chính sách retention của vị trí.

**Có còn cần "bản sao tối thiểu" không?** Không, với điều kiện D-TP-01 và D-TP-02 được xác nhận. Chỉ cần lại nếu hóa ra thời hạn 5 năm không áp dụng cho hồ sơ không được tuyển (khi đó quay về phương án giữ bản sao có consent riêng, như bản spec trước).

## 6. Luồng nghiệp vụ

### 6.1 Consent và đánh dấu

1. **Lúc nộp hồ sơ** (cổng công khai P3-3 hoặc form nộp hiện hành): ô tick mục đích Talent Pool (D-TP-01). Hệ thống ghi `application_data_consents` cùng phiên bản câu chữ. Chưa có form công khai thì pha 1 làm API ghi consent để cổng sau này gọi, và dữ liệu thử dùng bản ghi tổng hợp.
2. HR mở application đủ điều kiện (D-TP-04), bấm **"Đưa vào Talent Pool"**; hệ thống từ chối nếu không có consent hợp lệ. Không có tự động đưa vào.
3. Rút đồng ý: ứng viên yêu cầu (hoặc HR nhập theo yêu cầu bằng văn bản): ghi `withdrawn_at`, **chặn quét ngay**, xếp hàng xóa qua cơ chế F2.07.
4. Hồ sơ cũ không có bản ghi tick: không vào pool (D-TP-05). Gửi email xin consent là hạng mục tùy chọn sau này, cần P3-0 (Microsoft Graph/SMTP).

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
| POST | `/applications/{id}/mark` | HR phụ trách vị trí nguồn / HR Lead | Đánh dấu vào pool; từ chối nếu thiếu consent `TALENT_POOL` hợp lệ hoặc trạng thái không đủ điều kiện (D-TP-04) |
| DELETE | `/applications/{id}/mark` | như trên | Bỏ đánh dấu |
| GET | `/marks` | HR Lead, HR được phân công | Danh sách và trạng thái consent; **không** trả nội dung CV |
| POST | `/applications/{id}/withdraw-consent` | HR Lead/Admin (thay mặt theo văn bản) | Ghi `withdrawn_at`, chặn quét, xếp hàng xóa |
| POST | `/positions/{id}/talent-pool/scan` | theo D-TP-03 | Trả `scan_id`, chạy bất đồng bộ giống assessment |
| GET | `/scans/{scan_id}` | người tạo, HR Lead | Kết quả đã lọc hợp lệ tại thời điểm xem |
| POST | `/scans/{scan_id}/results/{application_id}/decision` | như trên | `CONTACT/SKIP/LATER` |

Endpoint ghi consent lúc nộp do cổng ứng tuyển (P3-3) gọi, nên chưa nằm trong bản này; pha 1 chỉ cung cấp hàm ghi dùng chung. Không có endpoint công khai mới trong P3-1.

## 8. Giao diện (Việt/Anh, trong Recruitment Workspace hiện có)

- Trang application (HR): nút "Đưa vào Talent Pool" và badge consent (có/không/đã rút).
- Trang **Talent Pool**: danh sách hồ sơ đã đánh dấu, trạng thái consent, hạn lưu, hàng đợi xóa (mở rộng trang "Lưu trữ & xóa dữ liệu").
- Trang vị trí: nút "Quét Talent Pool" (chỉ hiện khi vị trí OPEN và criteria APPROVED), màn kết quả có bằng chứng cạnh nhau như màn đối chiếu hiện tại, kèm cột "lưu đến ngày".

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
1. Câu chữ ô tick được HR Lead/Pháp chế xác nhận có nêu mục đích tái sử dụng.
2. 100% hồ sơ trong pool có bản ghi consent đầy đủ (phiên bản câu chữ, thời điểm), chưa rút.
3. Không có trường hợp quét nào chạm entry không hợp lệ trong bộ test tổng hợp, kể cả race.
4. Quét một vị trí mới trên pool tổng hợp 200 hồ sơ cho kết quả có bằng chứng; thời gian chấp nhận được (cần đo, chưa có số).
5. Quy trình rút đồng ý và xóa chạy đầu-cuối trên staging với dữ liệu tổng hợp.

## 9b. Trạng thái triển khai (nhánh code riêng)

- Đã làm: migration đến `00023`, consent notice `v4`, cổng công khai, đánh dấu/danh sách pool, worker quét và xếp hạng, giao diện có bằng chứng, rút consent, kiểm tra lại điều kiện khi hiển thị. Retention application dùng chính sách 60 tháng sau đóng vị trí.
- Chưa làm: quyết định `CONTACT/SKIP/LATER`, cập nhật CV qua link, nhắc hết hạn theo consent và tự sinh case xóa do rút consent; chưa nghiệm thu staging/production.
- Kiểm thử local và giới hạn mô phỏng được ghi tại [P3-3_PUBLIC_INTAKE.md](P3-3_PUBLIC_INTAKE.md).

## 10. Thứ tự triển khai đề xuất

| Pha | Nội dung | Phụ thuộc | Độ lớn |
| :--- | :--- | :--- | :-: |
| 0 | Xác nhận D-TP-01, D-TP-02, D-TP-05 (câu chữ ô tick; mốc 5 năm tính từ lúc tick đồng ý, đã chốt) | HR Lead | nhỏ |
| 1 | **Đã làm trong nhánh code:** migration consent + đánh dấu; luật đủ điều kiện; API; test | D-TP-02 | S–M |
| 2 | Quét và xếp hạng, màn kết quả có bằng chứng, quyết định HR | P3-0 (pilot Phase 2 ổn); DEP-05 nếu dùng LLM với dữ liệu thật | M |
| 3 | Rút đồng ý, nhắc hết hạn 5 năm, hàng đợi xóa + OTP (tái dùng F2.07) | F2.07 | S |
| 4 | Ô tick thật trên cổng công khai (P3-3 bước 2), cập nhật CV qua link (D-TP-07), email xin consent cho hồ sơ cũ (tùy chọn) | P3-3, P3-0 | M |

Ước lượng tổng: giảm xuống còn M–L so với bản trước vì bỏ sao chép dữ liệu, email consent và trang consent công khai. Pha 1–3 làm được ngay trên dữ liệu tổng hợp.

## 11. Rủi ro

| Rủi ro | Giảm thiểu |
| :--- | :--- |
| Câu chữ ô tick không nêu mục đích tái sử dụng | Kiểm tra ở D-TP-01 trước khi bật quét trên dữ liệu thật; fail-closed khi không có bản ghi đúng `purpose` |
| Consent cũ/HR upload không có bằng chứng đồng ý dùng lại | Form công khai `v4` ghi consent mới; không tự cấp consent cho dữ liệu cũ hoặc hồ sơ HR upload |
| Hai mốc 5 năm: consent pool và ngày đóng vị trí | Kiểm tra độc lập quyền dùng lại và retention; không coi consent pool là gia hạn hoặc cho phép vượt case đang chờ xóa/hold |
| Giữ lâu hơn, tăng bề mặt rò rỉ | RLS + service_role; truy cập theo phân quyền vị trí; audit không chứa PII; xóa có xác nhận + OTP |
| Chấm lại CV cũ tốn chi phí/LLM và cần egress | Rule engine trước; LLM chỉ cho tiêu chí chưa giải được; gate DEP-05 trước khi dùng dữ liệu thật |
| Kết quả cũ "treo" sau khi rút đồng ý | Kiểm tra lại điều kiện lúc hiển thị; xóa kết quả của hồ sơ không còn hợp lệ |
