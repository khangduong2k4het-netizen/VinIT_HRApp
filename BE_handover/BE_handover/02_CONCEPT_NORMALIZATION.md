# Concept Normalization — BE gửi mention, nhận tên kỹ năng chuẩn

## 1. Khi sử dụng

Sau khi có text và các kỹ năng đã trích xuất. Bước này liên kết từng mention
với concept ESCO hoặc concept nội bộ, giữ riêng trường hợp cần duyệt.

## 2. API đề xuất

`POST /api/v1/ai/concept-normalizations`, body JSON. Nhận job_id và lấy kết quả
theo [quy ước chung](README.md).

## 3. Đầu vào BE cần gửi

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `request_id` | string | Có | ID yêu cầu |
| `document_id`, `version_id`, `text_id` | string | Có | Tài liệu và đúng bản text nguồn |
| `text` | string | Có | Nguyên văn để đối chiếu vị trí |
| `mentions` | array | Có | Danh sách cần chuẩn hóa; có thể rỗng |
| `mentions[].mention_id` | string | Có | ID lấy từ bước extraction |
| `mentions[].text` | string | Có | Cụm nguyên văn |
| `mentions[].start`, `mentions[].end` | integer | Có | Vị trí cụm trên text |

```json
{
  "request_id": "REQ-NORM-01",
  "document_id": "CV-001",
  "version_id": "CV-001-v1",
  "text_id": "TXT-001",
  "text": "Java",
  "mentions": [{"mention_id": "M-01", "text": "Java", "start": 0, "end": 4}]
}
```

## 4. Đầu ra AI trả cho BE

| Trường | Kiểu | Nội dung |
| --- | --- | --- |
| `document_id`, `version_id`, `text_id` | string | Nguồn được giữ nguyên |
| `mentions` | array | Một kết quả cho từng mention gửi vào |
| `mentions[].mention_id`, `text`, `start`, `end` | string/integer | Nhận diện và giữ vị trí nguồn |
| `mentions[].status` | string | Bốn trạng thái trong bảng bên dưới |
| `mentions[].concept_id` | string hoặc null | ID được chọn khi linked |
| `mentions[].preferred_label` | string hoặc null | Tên chuẩn của concept được chọn |
| `mentions[].namespace` | string hoặc null | `esco`, `local`, hoặc null khi chưa chọn |
| `mentions[].candidates` | array | Các lựa chọn để xem/duyệt; mỗi item có concept_id, preferred_label, namespace |

```json
{
  "document_id": "CV-001",
  "version_id": "CV-001-v1",
  "text_id": "TXT-001",
  "mentions": [
    {
      "mention_id": "M-01", "text": "Java", "start": 0, "end": 4,
      "status": "linked",
      "concept_id": "http://data.europa.eu/esco/skill/19a8293b-8e95-4de3-983f-77484079c389",
      "preferred_label": "Java (computer programming)",
      "namespace": "esco",
      "candidates": [
        {"concept_id": "http://data.europa.eu/esco/skill/19a8293b-8e95-4de3-983f-77484079c389", "preferred_label": "Java (computer programming)", "namespace": "esco"}
      ]
    }
  ]
}
```

| Trạng thái | BE hiểu và hiển thị |
| --- | --- |
| `linked` | Có một concept được chọn; giữ cả tên nguồn và tên chuẩn |
| `ambiguous` | Có nhiều lựa chọn; chưa có concept được chọn |
| `needs_review` | Có gợi ý gần đúng; chờ duyệt |
| `unmapped` | Chưa có lựa chọn phù hợp |

Ba trạng thái chưa chọn có concept_id/preferred_label/namespace là null.
BE không tự lấy candidate đầu tiên làm kết quả đã chấp nhận.

## 5. BE nối bước tiếp theo như thế nào

Lưu kết quả theo mention_id và text nguồn. Tên chuẩn có thể dùng để chuẩn bị
danh sách skill cho bước sau; trường hợp chưa chọn vẫn giữ text ban đầu và
trạng thái cần duyệt. Không ghi đè tên kỹ năng người dùng đã nhập.

Liên kết concept chưa xác nhận một ứng viên có kỹ năng đó hoặc đáp ứng số năm
kinh nghiệm. Bước này không trả điểm phù hợp CV–JD.
