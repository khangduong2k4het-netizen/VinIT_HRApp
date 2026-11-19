# E2E staging cho Phase 1

> Mục đích: kiểm chứng toàn bộ luồng bằng dịch vụ thật trên staging với dữ liệu tổng hợp hoặc dữ liệu đã được phê duyệt sử dụng. Tài liệu này là runbook/khung bằng chứng; việc có runbook không đồng nghĩa E2E đã đạt.

Checklist thực thi từng bước và mẫu ký duyệt nằm tại [`E2E_STAGING_EXECUTION_CHECKLIST.md`](E2E_STAGING_EXECUTION_CHECKLIST.md). Bộ dữ liệu tổng hợp đi kèm nằm tại `staging/synthetic/manifest.json`; sinh DOCX upload bằng `backend/scripts/generate_staging_fixtures.py`.

## 1. Điều kiện an toàn

- Chỉ dùng staging tách biệt, không dùng database/Supabase project production hoặc project chứa CV thật chưa được phê duyệt.
- Dữ liệu kiểm thử là CV/JD tổng hợp, đã ẩn danh hoặc được HR/Legal cho phép bằng văn bản.
- Không đưa secret/API key vào Git, log, screenshot hoặc báo cáo.
- Legacy Supabase key chưa đóng không chặn E2E kỹ thuật bằng dữ liệu tổng hợp, nhưng chặn pilot bằng CV thật.

## 2. Chuẩn bị môi trường

1. Áp toàn bộ migration trong `supabase/migrations` theo thứ tự tên file lên database staging dùng riêng; ghi lại version thực tế của môi trường.
2. Tạo Supabase Auth users tổng hợp cho ADMIN, HR Lead, HR Recruiter, Hiring Manager và Viewer.
3. Tạo ít nhất hai positions, gán user theo ma trận quyền; một position cố ý không gán cho một số role để kiểm tra scope.
4. Chuẩn bị:
   - Một PDF có text tiếng Anh.
   - Một PDF scan cần OCR.
   - Một DOCX.
   - Một CV tiếng Việt.
   - Một CV thiếu bằng chứng cho tiêu chí bắt buộc.
   - Một CV có bằng chứng rõ ràng cho tiêu chí bắt buộc.
5. Cấu hình LLM endpoint thật đã được phê duyệt cho staging.
6. Nếu kiểm tra BGE, cấu hình BGE-M3 qua Cloudflare Workers AI hoặc endpoint self-host; ghi lại provider/model/index version, không ghi API key.
7. Đặt `LTR_MODE=OFF` cho vòng E2E đầu. LTR SHADOW chỉ chạy khi đã có artifact và quy trình riêng.

## 3. Kịch bản bắt buộc

| Nhóm | Kịch bản | Kết quả kỳ vọng |
|---|---|---|
| Auth/RBAC | Đăng nhập từng role; mở position được gán và không được gán | Đúng scope; không có dữ liệu ngoài position được gán |
| Admin | Mở `/v1/admin/semantic/health`, `/v1/admin/ltr/models`, worker health bằng non-admin và ADMIN | Non-admin 403; ADMIN 200 |
| JD/Criteria | Tạo JD, tạo/sửa criteria, HR approve, HM approve bằng tài khoản khác | Dual approval đúng; bản APPROVED không sửa được |
| Upload | Upload PDF text, PDF scan/OCR, DOCX theo batch | File hợp lệ được xử lý; file lỗi báo rõ; không dùng dữ liệu ngoài staging |
| Profile | Kiểm tra profile facts và sửa profile tạo version mới | Assessment cũ không bị trộn với profile mới |
| Matching | Chạy assessment cho CV có bằng chứng, thiếu bằng chứng và mâu thuẫn mandatory | Đúng STRONG_MATCH/MATCH/UNCLEAR/NO_MATCH; quote mở đúng chunk/page |
| Scoring | Kiểm tra case STRONG_MATCH + UNCLEAR theo `matching-v2.1` | Score tính trên phần đã có bằng chứng; coverage thấp vẫn cần HR xác minh |
| Ranking | Chạy ranking trong position | Thứ tự tôn trọng mandatory status, score, coverage; snapshot truy vết được |
| Semantic | Bật BGE ở staging, kiểm tra semantic health và candidate chunks | Health không ở trạng thái MISCONFIGURED; semantic chỉ bổ sung candidate, không đổi rule outcome |
| LTR governance | Đăng ký artifact tổng hợp DRAFT, approve/reject bằng Admin API | Có actor/reason/artifact hash/review event; artifact bị sửa bị worker từ chối |
| Shortlist | HR chia sẻ cho HM với quyền phù hợp, HM feedback, HR revoke | HM chỉ thấy phần được chia sẻ; revoke có hiệu lực |
| Worker recovery | Dừng/restart worker trong job tổng hợp nếu môi trường cho phép | Job được phục hồi theo cơ chế at-least-once, không tuyên bố exactly-once |

## 4. Bằng chứng phải lưu

Mỗi lần chạy E2E cần lưu vào báo cáo closure hoặc ticket nghiệm thu:

- Commit SHA và môi trường staging.
- Migration versions thực tế.
- Danh sách kịch bản PASS/FAIL và log/screenshot đã loại bỏ dữ liệu nhạy cảm.
- Provider/model LLM và embedding đã dùng, không lưu secret.
- Số lượng test tự động đã chạy trong CI và job integration tương ứng.
- Các lỗi còn mở, mức độ và quyết định chấp nhận rủi ro nếu có.

## 5. Điều kiện đạt

- Không có lỗi rò rỉ position scope hoặc xem CV ngoài quyền.
- Không có finding thiếu quote hợp lệ được tính điểm.
- Không có trường hợp UNCLEAR bị tính như NO_MATCH trong status/score.
- Worker/API không ghi CV text, prompt đầy đủ hoặc API key vào log kiểm tra.
- Các lỗi còn lại được ghi vào `audit/PHASE1_REVIEW_2026-11-07.md` với trạng thái rõ ràng.
