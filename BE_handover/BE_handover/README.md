# Bàn giao kết nối BE — Đầu vào và đầu ra của các tính năng AI

Bộ tài liệu này mô tả **BE gửi gì cho AI, AI trả gì cho BE và BE cần lưu gì**.
Đây là hợp đồng kết nối đề xuất, chưa phải thông báo các endpoint đã triển khai.
Các khác biệt với dữ liệu nội bộ của module sẽ do lớp tích hợp AI chuyển đổi;
BE làm việc với các trường trong bộ bàn giao này.

Ví dụ trong từng file là dữ liệu hư cấu độc lập, không phải cùng một bộ CV/JD
chạy xuyên suốt tất cả tính năng.

## 1. Danh sách bàn giao

| Tính năng              | Tài liệu                        | Đầu vào chính                         | Đầu ra chính                                                |
| ------------------------ | --------------------------------- | ----------------------------------------- | -------------------------------------------------------------- |
| OCR + Feature Extraction | [01](01_OCR_FEATURE_EXTRACTION.md) | File CV/JD                                | Văn bản và các lần xuất hiện của kỹ năng             |
| Concept Normalization    | [02](02_CONCEPT_NORMALIZATION.md)  | Văn bản và kỹ năng đã trích xuất | Concept được liên kết hoặc danh sách chờ duyệt        |
| PII Masking              | [03](03_PII_MASKING.md)            | Một chuỗi văn bản                     | Văn bản đã che và vị trí đã che trên bản gốc       |
| CV Tailor                | [04](04_CV_TAILOR.md)              | CV cấu trúc và JD cấu trúc           | Skill được chọn, mục Skills và bullet được viết lại |
| JD–CV Matching          | [05](05_JD_CV_MATCHING.md)         | Kỹ năng JD và CV                       | Kết quả từng yêu cầu, độ bao phủ và điểm tham khảo |
| AI Interview             | [06](06_AI_INTERVIEW.md)           | JD/tiêu chí, câu trả lời             | Câu hỏi tiếp theo và báo cáo luyện phỏng vấn          |
| Dữ liệu lưu lại      | [07](07_DU_LIEU_BE_CAN_LUU.md)     | Input và output của các bước         | Các nhóm bản ghi BE cần quản lý                          |

| Thao tác                            | Endpoint đề xuất                                                                |
| ------------------------------------ | ---------------------------------------------------------------------------------- |
| Đọc file và trích kỹ năng      | `POST /api/v1/ai/ocr-extractions`                                                |
| Chuẩn hóa concept                  | `POST /api/v1/ai/concept-normalizations`                                         |
| Che thông tin cá nhân             | `POST /api/v1/ai/pii-maskings`                                                   |
| Chọn skill theo JD                  | `POST /api/v1/ai/cv-tailor/selections`                                           |
| Viết lại nội dung CV              | `POST /api/v1/ai/cv-tailor/wordings`                                             |
| Đối chiếu JD–CV                  | `POST /api/v1/ai/jd-cv-matches`                                                  |
| Bắt đầu nhánh Interview          | `POST /api/v1/ai/interview/criteria`, sau đó `/api/v1/ai/interview/sessions` |
| Lấy trạng thái/kết quả tác vụ | `GET /api/v1/ai/jobs/{job_id}`                                                   |

## 2. Cách nhận kết quả AI

Prefix đề xuất: `/api/v1/ai`. Endpoint chạy xử lý trả 202 và một `job_id`:

```json
{
  "job_id": "JOB-001",
  "status": "queued"
}
```

BE gọi `GET /api/v1/ai/jobs/{job_id}` để kiểm tra kết quả:

```json
{
  "job_id": "JOB-001",
  "request_id": "REQ-001",
  "feature": "concept_normalization",
  "status": "completed",
  "result": {},
  "error": null
}
```

`result` là object đầu ra được mô tả riêng trong từng tài liệu. `status` gồm
`queued`, `processing`, `completed`, `failed`. Trước khi completed, `result`
là null; failed có `error: {code, message, field?}`. Không coi lỗi xử lý là kết
quả thành công rỗng. Những API thao tác phiên Interview có phản hồi riêng được
ghi rõ trong tài liệu Interview.

Mọi request xử lý có `request_id` do BE tạo để đối chiếu. Gửi lại cùng request
ID và cùng nội dung trả lại cùng job; thay nội dung phải dùng request ID mới.
Quy tắc này áp dụng trong 24 giờ từ lúc nhận request; sau thời gian đó BE dùng
job ID đã lưu để tra cứu thay vì gửi lại để tìm kết quả cũ.

## 3. Quy ước dữ liệu giữa BE và AI

| Trường                                                      | Ai tạo                              | Cách dùng                                                                    |
| ------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------ |
| `request_id`                                                | BE                                   | Đối chiếu một yêu cầu xử lý                                            |
| `document_id` / `cv_id` / `jd_id`                       | BE                                   | Nhận diện tài liệu nghiệp vụ                                             |
| `version_id`                                                | BE                                   | Nhận diện đúng bản nội dung; sửa CV/JD tạo version mới                |
| `text_id`                                                   | BE                                   | Nhận diện một bản text đã lưu, ví dụ text sau OCR                     |
| `mention_id`                                                | AI khi trích xuất, BE giữ lại    | Một lần xuất hiện của kỹ năng trong text                                |
| `skill_id`, `evidence_id`, `requirement_id`             | BE hoặc bước chuẩn bị dữ liệu | Giữ nguyên giữa các bước, không tạo lại khi đổi thứ tự hiển thị |
| `job_id`, `selection_id`, `session_id`, `question_id` | AI                                   | BE lưu để lấy kết quả và nối các thao tác sau                        |

`start`, `end` là vị trí ký tự trên **đúng chuỗi text gửi vào**, bắt đầu từ 0,
không lấy ký tự ở vị trí end. Ví dụ text `Java` có khoảng `[0,4)`. Không dùng
offset của bản đã che để đánh dấu trên bản gốc. Trong ứng dụng JavaScript cần
đổi vị trí khi chuỗi có emoji, vì cách đếm ký tự có thể khác phía AI.

BE gửi nội dung cần xử lý cùng các ID, không chỉ gửi một ID rồi yêu cầu AI tự
đọc database BE. BE quản lý dữ liệu nghiệp vụ; AI giữ trạng thái job/phiên đủ
để trả kết quả. Sau khi nhận kết quả, BE lưu theo [danh mục dữ liệu](07_DU_LIEU_BE_CAN_LUU.md).

## 4. Dữ liệu CV cấu trúc dùng cho CV Tailor

| Trường                   | Kiểu             | Bắt buộc | Nội dung                                                                             |
| -------------------------- | ----------------- | ---------- | ------------------------------------------------------------------------------------- |
| `cv_id`, `version_id`  | string            | Có        | CV và bản nội dung dùng xử lý                                                   |
| `text`                   | string hoặc null | Không     | Toàn văn nếu có                                                                   |
| `skills`                 | array             | Có        | Có thể rỗng                                                                        |
| `skills[].skill_id`      | string            | Có        | ID skill trong CV                                                                     |
| `skills[].text`          | string            | Có        | Cách viết trong hồ sơ                                                             |
| `skills[].normalized`    | string hoặc null | Không     | Tên đã chuẩn hóa nếu có                                                        |
| `skills[].evidence_ids`  | string[]          | Có        | Bằng chứng đã liên kết; không có thì `[]`                                  |
| `evidence`               | array             | Có        | Có thể rỗng                                                                        |
| `evidence[].evidence_id` | string            | Có        | ID bằng chứng                                                                       |
| `evidence[].parent_id`   | string            | Có        | Project/experience/education chứa bằng chứng này                                  |
| `evidence[].kind`        | string            | Có        | `experience`, `project`, `education`, `activity`, `outcome` hoặc `award` |
| `evidence[].text`        | string            | Có        | Nội dung người dùng đã cung cấp                                                |
| `sections`               | object            | Không     | Các mục hồ sơ nếu cần giữ lại                                                 |

Mỗi evidence ID được tham chiếu phải có trong cùng CV. Liên kết skill–evidence
phải do bước chuẩn bị hồ sơ xác định hoặc người dùng xác nhận, không tự nối vì
hai đoạn có từ gần giống nhau. Chỉ có skill và text sau OCR chưa đủ tạo toàn bộ
CV cấu trúc này.

## 5. Dữ liệu JD cấu trúc dùng cho CV Tailor

| Trường                          | Kiểu             | Bắt buộc          | Nội dung                                                       |
| --------------------------------- | ----------------- | ------------------- | --------------------------------------------------------------- |
| `jd_id`, `version_id`         | string            | Có                 | JD và bản nội dung dùng xử lý                             |
| `text`                          | string hoặc null | Không              | Toàn văn nếu có                                             |
| `requirements`                  | array             | Có                 | Các yêu cầu đã xác định; có thể rỗng                 |
| `requirements[].requirement_id` | string            | Có                 | ID yêu cầu                                                    |
| `requirements[].kind`           | string            | Có                 | `skill` hoặc `constraint`                                  |
| `requirements[].text`           | string            | Có                 | Nội dung yêu cầu                                             |
| `requirements[].normalized`     | string hoặc null | Không              | Tên kỹ năng chuẩn hóa nếu có                             |
| `requirements[].priority`       | string            | Có                 | `must`, `nice`, `unknown`                                 |
| `requirements[].constraint`     | object hoặc null | Khi kind=constraint | `type`, `operator`, `value`, `applies_to`, `evidence` |

Không tự biến “3 năm Python” thành một skill chứng minh đã đạt 3 năm kinh
nghiệm. Yêu cầu về năm, địa điểm, bằng cấp phải giữ tách khỏi skill.

## 6. Những điểm BE cần giữ đúng

- Mỗi kết quả gắn đúng CV/JD version được gửi, không lấy bản người dùng vừa sửa
  để hiển thị như thể đó là nguồn của kết quả cũ.
- `null` hoặc chưa xác định không đổi thành 0, false hoặc không đáp ứng.
- Kết quả chưa khớp kỹ năng không tự biến thành kết luận loại ứng viên.
- Các trường trong request/response là hợp đồng đề xuất cho BE. Cần phía AI
  triển khai lớp chuyển đổi và endpoint; tài liệu không yêu cầu BE tự viết lại
  phần xử lý AI.
