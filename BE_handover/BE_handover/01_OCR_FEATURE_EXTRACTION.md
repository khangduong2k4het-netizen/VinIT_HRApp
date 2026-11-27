# OCR + Feature Extraction — BE gửi file, nhận text và kỹ năng

## 1. Khi sử dụng

Khi người dùng đưa CV hoặc JD dạng PDF, ảnh hoặc DOCX vào hệ thống. Bước này
đọc nội dung và tìm các cụm kỹ năng xuất hiện trong tài liệu.

## 2. API đề xuất

`POST /api/v1/ai/ocr-extractions`, gửi multipart gồm file và các trường bên dưới.
Phản hồi 202 có job_id; lấy kết quả theo [quy ước chung](README.md).

## 3. Đầu vào BE cần gửi

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `request_id` | string | Có | ID yêu cầu |
| `document_id` | string | Có | ID tài liệu BE quản lý |
| `document_type` | string | Có | `cv` hoặc `jd` |
| `version_id` | string | Có | Bản nội dung của file này |
| `file` | file | Có | PDF, PNG, JPG/JPEG hoặc DOCX |

Giới hạn theo tài liệu hiện có: 20 MiB/file, 20 trang. File text thuần không
cần OCR; BE có thể dùng text sẵn có cho các bước phía sau.

## 4. Đầu ra AI trả cho BE

Đây là object trong trường `result` của job:

| Trường | Kiểu | Nội dung |
| --- | --- | --- |
| `document_id`, `document_type`, `version_id` | string | Giữ đúng nguồn yêu cầu |
| `text` | string | Toàn văn sau khi đọc tài liệu |
| `skills` | array | Các lần xuất hiện của kỹ năng; có thể rỗng |
| `skills[].mention_id` | string | ID một lần xuất hiện |
| `skills[].text` | string | Cụm nguyên văn trong text |
| `skills[].start`, `skills[].end` | integer | Vị trí trong text trả về |
| `skills[].section` | string hoặc null | Mục tài liệu nếu xác định được |
| `skills[].page_index` | integer hoặc null | Trang, tính từ 0 |
| `warnings` | string[] | Điểm cần người dùng kiểm tra; có thể rỗng |

Ví dụ rút gọn:

```json
{
  "document_id": "CV-001",
  "document_type": "cv",
  "version_id": "CV-001-v1",
  "text": "Java and SQL",
  "skills": [
    {"mention_id": "M-01", "text": "Java", "start": 0, "end": 4, "section": "skills", "page_index": 0},
    {"mention_id": "M-02", "text": "SQL", "start": 9, "end": 12, "section": "skills", "page_index": 0}
  ],
  "warnings": []
}
```

## 5. BE nối bước tiếp theo như thế nào

BE lưu text trả về thành một bản text mới và cấp `text_id`. Gửi text, text_id
và skills sang [Concept Normalization](02_CONCEPT_NORMALIZATION.md); giữ nguyên
mention_id và vị trí ký tự. Cùng một kỹ năng xuất hiện hai nơi vẫn giữ hai mention.

Không dùng danh sách này như một Master Profile hoàn chỉnh. Chưa có đủ thông
tin kinh nghiệm, mối liên kết bằng chứng hoặc các constraint của JD thì phải
bổ sung trước khi chạy CV Tailor. Skill rỗng không tự chứng minh file không có
kỹ năng; xem lại text và warnings nếu kết quả bất thường.
