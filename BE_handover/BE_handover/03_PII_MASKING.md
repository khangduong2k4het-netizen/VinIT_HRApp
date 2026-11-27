# PII Masking — BE gửi text, nhận bản đã che thông tin cá nhân

## 1. Khi sử dụng

Khi cần một bản sao văn bản để đưa vào bước xử lý tiếp theo mà giảm thông tin
nhận diện cá nhân. Bản gốc vẫn được giữ riêng.

## 2. API đề xuất

`POST /api/v1/ai/pii-maskings`, body JSON. Nhận job_id và lấy kết quả theo
[quy ước chung](README.md).

## 3. Đầu vào BE cần gửi

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `request_id` | string | Có | ID yêu cầu |
| `document_id`, `version_id`, `text_id` | string | Có | Nguồn của chuỗi cần che |
| `text` | string | Có | Nguyên văn; chuỗi rỗng được chấp nhận |

```json
{
  "request_id": "REQ-MASK-01",
  "document_id": "CV-001",
  "version_id": "CV-001-v1",
  "text_id": "TXT-002",
  "text": "Email: demo@example.com"
}
```

Không gửi cả object CV hoặc file PDF vào trường text. Nếu cần che từng đoạn
trong hồ sơ, mỗi đoạn phải có text_id riêng và liên kết về evidence nguồn.

## 4. Đầu ra AI trả cho BE

| Trường | Kiểu | Nội dung |
| --- | --- | --- |
| `document_id`, `version_id`, `text_id` | string | Tham chiếu bản gốc |
| `masked_text` | string | Văn bản đã thay các đoạn phát hiện bằng placeholder |
| `matches` | array | Các vị trí đã che; có thể rỗng |
| `matches[].start`, `matches[].end` | integer | Vị trí trên text gốc |
| `matches[].pii_type` | string | Loại thông tin, ví dụ EMAIL, PHONE, PERSON_NAME |

```json
{
  "document_id": "CV-001",
  "version_id": "CV-001-v1",
  "text_id": "TXT-002",
  "masked_text": "Email: [EMAIL]",
  "matches": [{"start": 7, "end": 23, "pii_type": "EMAIL"}]
}
```

## 5. BE nối bước tiếp theo như thế nào

Lưu masked_text thành bản riêng, cấp text_id mới nếu tiếp tục xử lý bản đó.
Các match trong kết quả vẫn trỏ về TXT-002 gốc. Không thay nội dung TXT-002
bằng masked_text vì sẽ làm sai vị trí các bằng chứng đã lưu.

Kết quả không trả lại giá trị cá nhân đã che hoặc bảng hoàn nguyên. Có thể còn
thông tin chưa được phát hiện; matches rỗng chỉ có nghĩa không phát hiện đoạn
cần che trong lần xử lý này. Nếu bước masking lỗi, BE không tự dùng raw text
thay cho bản đã che trong luồng yêu cầu masking.
