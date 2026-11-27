# AI Interview — BE nối phiên hỏi đáp và báo cáo

## 1. Luồng cần nối

JD → danh sách tiêu chí → tạo phiên → lấy câu hỏi → nộp câu trả lời → tự đánh
giá → nhận báo cáo. Một phiên có 6 câu chính, tối đa một câu đào sâu cho mỗi
câu chính. Các API dưới đây là hợp đồng bàn giao đề xuất.

## 2. Chuẩn bị tiêu chí từ JD

`POST /api/v1/ai/interview/criteria`, nhận job_id theo [quy ước chung](README.md).

| Input BE gửi | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `request_id` | string | Có | ID yêu cầu |
| `role` | string | Có | Vị trí muốn luyện |
| `jd.jd_id`, `jd.version_id` | string | Có | Nguồn JD |
| `jd.text` | string | Có | Nội dung JD |

| Output AI trả | Kiểu | Ý nghĩa |
| --- | --- | --- |
| `criteria_id` | string | ID bộ tiêu chí |
| `jd_id`, `jd_version_id` | string | Nguồn JD |
| `criteria` | array | Mỗi item có criterion_id, name, category |
| `criteria[].category` | string | `technical` hoặc `behavioral` |

```json
{
  "criteria_id": "CRITERIA-001",
  "jd_id": "JD-001", "jd_version_id": "JD-001-v1",
  "criteria": [
    {"criterion_id": "CRIT-01", "name": "Java and API development", "category": "technical"}
  ]
}
```

BE cho người dùng xem bộ tiêu chí trước khi bắt đầu. Trong phạm vi bàn giao
đầu tiên, tiêu chí dùng nguyên bộ AI trả về; chỉnh tiêu chí cần tạo bộ mới để
không sửa nghĩa ID đã dùng trong phiên.

## 3. Tạo và theo dõi phiên

`POST /api/v1/ai/interview/sessions`, trả 201 với session_id, status và planning_job_id.

| Input BE gửi | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `request_id` | string | Có | ID yêu cầu |
| `role` | string | Có | Vị trí muốn luyện |
| `jd` | object | Có | jd_id, version_id, text của JD đã dùng |
| `criteria` | object | Có | Toàn bộ output của bước tiêu chí, gồm criteria_id |
| `cv` | object | Không | CV cấu trúc nếu có để cá nhân hóa |
| `target_interview_date` | date hoặc null | Không | Ngày dự kiến phỏng vấn |
| `warmup_answer` | string hoặc null | Không | Câu trả lời mở đầu người dùng muốn đưa vào phiên |
| `retain_data` | boolean | Có | Có chọn giữ dữ liệu luyện tập lâu hơn 24 giờ không |
| `consent` | boolean | Có | Phải là true để lưu và xử lý phiên |

Output ví dụ:

```json
{
  "session_id": "SES-001",
  "status": "planning",
  "planning_job_id": "JOB-PLAN-01",
  "total_questions": 6
}
```

BE gọi `GET /api/v1/ai/interview/sessions/{session_id}` để nhận session_id,
status, current_question_index, total_questions và report_ready.
Status gồm `planning`, `live`, `awaiting_self_assessment`, `scoring`, `completed`.

## 4. Lấy câu hỏi và gửi câu trả lời

`POST /api/v1/ai/interview/sessions/{session_id}/next-question`, body có request_id.
Trả 200 khi câu đã sẵn sàng; gọi lại khi chưa trả lời vẫn nhận đúng câu hiện tại.

```json
{
  "session_id": "SES-001",
  "question_id": "Q-02",
  "question_index": 2,
  "is_followup": false,
  "question_text": "Describe a project where you used Java.",
  "criterion_id": "CRIT-01"
}
```

`POST /api/v1/ai/interview/sessions/{session_id}/answers`, body:

```json
{
  "request_id": "REQ-ANSWER-02",
  "question_id": "Q-02",
  "client_turn_id": "TURN-02",
  "answer_text": "I built REST APIs using Java for a course booking project."
}
```

Các trường đều bắt buộc, là string. client_turn_id do BE tạo cho một lượt trả
lời, giữ nguyên khi gửi lại cùng nội dung. Thay nội dung phải tạo lượt mới theo
luồng được chấp nhận; không ghi đè câu đã nộp trong phiên đang chấm.

API trả 202 với job_id. Khi job hoàn tất, result có:

| Trường | Kiểu | Ý nghĩa |
| --- | --- | --- |
| `session_id`, `answer_id`, `question_id` | string | Liên kết đúng phiên và câu trả lời |
| `status` | string | `followup_required` hoặc `turn_completed` |
| `followup_question` | object hoặc null | question_id, question_index, is_followup=true, question_text, criterion_id |

Nếu có follow-up, BE hiển thị nó rồi gửi câu trả lời bằng cùng API answers.
Nếu turn_completed, lấy câu chính tiếp theo; hết câu chính thứ 6 thì chuyển
sang tự đánh giá. Nếu planning chưa xong hoặc sai trạng thái, API trả lỗi
`session_not_ready`/`invalid_turn_sequence`, không tự bỏ qua câu hỏi.

## 5. Tự đánh giá và nhận báo cáo

`POST /api/v1/ai/interview/sessions/{session_id}/self-assessment`, body có
request_id và ratings:

```json
{
  "request_id": "REQ-SELF-01",
  "ratings": [
    {"criterion_id": "CRIT-01", "self_rating": "developing"}
  ]
}
```

Mỗi tiêu chí có một self_rating: `needs_practice`, `developing`, `competent`.
Đây là bộ nhãn đề xuất cho giao diện kết nối; BE và AI cần dùng cùng bộ nhãn.
API trả 202 và job_id tổng hợp báo cáo.

`GET /api/v1/ai/interview/sessions/{session_id}/report` trả 200 khi sẵn sàng;
chưa sẵn sàng trả lỗi `report_not_ready`.

| Trường output | Kiểu | Nội dung |
| --- | --- | --- |
| `session_id`, `role` | string | Phiên và vị trí đã luyện |
| `strengths` | array | criterion_id, comment, answer_id, sentence_id, evidence_quote |
| `improvement_priorities` | array | criterion_id, issue, actionable_advice |
| `english_coaching` | array | answer_id, original_phrase, suggested_phrase, category |
| `sample_answers` | array | question_id, model_template |

Ví dụ report rút gọn:

```json
{
  "session_id": "SES-001",
  "role": "Backend Developer",
  "strengths": [
    {"criterion_id": "CRIT-01", "comment": "Đã nêu được công nghệ và mục đích của dự án.", "answer_id": "ANSWER-02", "sentence_id": "TURN-02-S01", "evidence_quote": "I built REST APIs using Java for a course booking project."}
  ],
  "improvement_priorities": [
    {"criterion_id": "CRIT-01", "issue": "Chưa nêu rõ phần việc cá nhân.", "actionable_advice": "Bổ sung những API bạn trực tiếp xây dựng."}
  ],
  "english_coaching": [],
  "sample_answers": [
    {"question_id": "Q-02", "model_template": "I built REST APIs using Java for a course booking project. My specific responsibility was [fill: your actual contribution]."}
  ]
}
```

Nhận xét có trích dẫn phải giữ answer_id/sentence_id để BE hiển thị đúng câu
trả lời nguồn. Câu mẫu có chỗ cần người dùng tự bổ sung thì giữ placeholder,
không coi đó là kinh nghiệm có thật của người dùng.

## 6. Nhánh giọng nói, nếu BE hỗ trợ

| Endpoint | BE gửi | AI trả |
| --- | --- | --- |
| `POST /api/v1/ai/interview/sessions/{session_id}/transcriptions` | Multipart: request_id, question_id, file WebM/WAV tối đa 3 phút | 202 job_id; khi xong có transcript_text và question_id |
| `GET /api/v1/ai/interview/questions/{question_id}/audio` | question_id | 200 audio; nếu đang tạo thì 202 job_id |

Người dùng xem/sửa transcript rồi BE mới submit answer_text. Upload audio không
tự động coi là đã nộp câu trả lời. Audio đầu vào được xóa sau khi chuyển text
hoặc khi tác vụ lỗi; BE không giữ bản sao audio ngoài nhu cầu đã thống nhất.

## 7. BE lưu và hiển thị

Lưu phiên, nguồn JD/CV, bộ tiêu chí, câu hỏi, câu trả lời, tự đánh giá và report
theo session_id. Khi retain_data=false, dữ liệu phiên và các bản dẫn xuất được
đặt hạn xóa 24 giờ; CV/JD đã lưu riêng trong hồ sơ cá nhân không tự bị xóa theo.
Không tự cho admin/cố vấn xem nội dung riêng nếu người dùng chưa chia sẻ.
