# Dữ liệu BE cần lưu để nối các tính năng

Tài liệu này liệt kê dữ liệu nghiệp vụ cần giữ, không quy định công nghệ
database, cách tạo bảng hay câu lệnh SQL. BE có thể ánh xạ vào database đang dùng.

## 1. CV/JD đầu vào

| Nhóm bản ghi | Các trường cần giữ | Mục đích |
| --- | --- | --- |
| Tài liệu | document_id, owner/user liên quan, document_type=cv/jd, tên hiển thị, thời điểm tạo | Xác định tài liệu thuộc ai và là CV hay JD |
| Phiên bản tài liệu | version_id, document_id, file nguồn hoặc JSON/text nguồn, thời điểm tạo | Giữ đúng nguồn của mỗi kết quả AI |
| Bản text | text_id, version_id, text, loại original/parsed/masked, text_id gốc nếu là bản che | Không nhầm text sau OCR, bản gốc và bản đã che |
| Skill CV | cv_id, version_id, skill_id, text, normalized nếu có, evidence_ids | Dùng cho selection và chuẩn bị matching |
| Evidence CV | cv_id, version_id, evidence_id, parent_id, kind, text | Chỉ ra nội dung nguồn trong project/experience nào |
| Requirement JD | jd_id, version_id, requirement_id, kind, text, normalized nếu có, priority, constraint nếu có | Giữ skill và điều kiện tuyển dụng riêng |
| Tier JD dùng matching | jd_id, version_id, requirement_id, tier hoặc null, người/nguồn phân nhóm | Không tự lấy must/nice thay cho tier |

Khi người dùng sửa nội dung đã chạy AI, tạo version mới. Các ID skill/evidence/
requirement được hiểu trong phạm vi version tương ứng, không chỉ tra theo ID
đơn lẻ. Không sửa text cũ rồi giữ nguyên những vị trí ký tự đã được AI trả về.

## 2. Kết quả của từng feature

| Feature | Các trường BE cần lưu | Liên kết về đầu vào |
| --- | --- | --- |
| OCR + extraction | job_id, text trả về, skills/mention_id, start/end, section/page, warnings | document_id + version_id; cấp text_id cho text trả về |
| Concept normalization | job_id, mention_id, status, concept_id, preferred_label, namespace, candidates | document_id + version_id + text_id + mention_id |
| PII masking | job_id, masked_text, matches gồm start/end/pii_type | text_id gốc; bản che có text_id riêng |
| CV selection | job_id, selection_id, selected_skills, matched_requirement_ids, evidence_status, evidence_ids, unmatched_requirements | cv_id/cv_version_id + jd_id/jd_version_id |
| CV wording | job_id, selection_id, status, skills_section, bullets, source_evidence_ids, parent_id, fallback_used, warnings | Đúng selection và CV/JD version dùng tạo selection |
| JD–CV matching | job_id, requirements/status/evidence refs, score, score_status, unresolved_tier_count, evidence_coverage, eligibility, constraints_evaluated | Đúng cặp CV/JD và version |
| AI Interview | session_id, role, JD/CV nguồn, criteria, questions, answers, self-assessment, report, thời hạn lưu | session_id; các nhận xét trỏ đúng answer_id/sentence_id |

Giữ toàn bộ object kết quả để có thể hiển thị lại; các trường quan trọng có
thể tách riêng để tìm kiếm/lọc. Nếu AI trả tên field khác với bộ bàn giao, cần
thống nhất trước khi nối, không tự bỏ các trường thể hiện thiếu thông tin.

## 3. Theo dõi yêu cầu xử lý

| Trường | Nội dung |
| --- | --- |
| request_id | Yêu cầu do BE tạo |
| job_id | Tác vụ AI trả về |
| feature | Tính năng đang xử lý |
| input_refs | Các document/version/text/selection liên quan |
| status | queued, processing, completed, failed |
| result | Object hoàn chỉnh khi completed |
| error | Mã/thông báo lỗi khi failed |
| created_at, completed_at | Thời điểm gửi và nhận kết quả |

Chỉ hiển thị kết quả như dữ liệu đã sẵn sàng khi completed. Gửi lại cùng nội
dung không được tạo nhiều bản đề xuất khiến người dùng hiểu nhầm là nhiều lần
chấm độc lập. Khi kết quả AI được người dùng chấp nhận để sửa CV, lưu thêm
version CV mới và liên kết tới bản đề xuất đã áp dụng.

## 4. Các giá trị không được diễn giải lại

- `needs_review`, `ambiguous`, `unmapped`: chưa có concept được chọn.
- `UNKNOWN`: chưa có bằng chứng kỹ năng trong input CV, không phải FAIL.
- `score=null`: chưa có điểm tổng hợp hợp lệ, không đổi thành 0.
- `listed_only`: skill chỉ được khai báo, chưa có evidence liên kết để viết bullet.
- `constraints_evaluated=false`: chưa đánh giá điều kiện tuyển dụng.
- `fallback_used=true`: nội dung cuối dùng lại nguồn; không trình bày là AI đã
  tạo thành tích mới.

Chính sách lưu/xóa dữ liệu cá nhân áp dụng cả input, output và các bản text dẫn
xuất. Xóa một phiên luyện tập không đồng nghĩa xóa CV/JD mà người dùng đã lưu
độc lập trong hồ sơ cá nhân.
