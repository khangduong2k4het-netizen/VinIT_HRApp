# JD–CV Matching — BE gửi skill, nhận đối chiếu từng yêu cầu

## 1. Khi sử dụng

Khi cần xem các kỹ năng JD yêu cầu có được thể hiện trong dữ liệu CV đã cung
cấp hay không. Phạm vi hiện tại là kỹ năng, chưa kết luận đủ điều kiện tuyển dụng.

## 2. API đề xuất

`POST /api/v1/ai/jd-cv-matches`, body JSON. Nhận job_id và lấy kết quả theo
[quy ước chung](README.md).

## 3. Đầu vào BE cần gửi

| Trường | Kiểu | Bắt buộc | Nội dung |
| --- | --- | --- | --- |
| `request_id` | string | Có | ID yêu cầu |
| `jd.jd_id`, `jd.version_id` | string | Có | JD được đánh giá |
| `jd.skills` | array | Có | Các skill yêu cầu; có thể rỗng |
| `jd.skills[].requirement_id` | string | Có | ID yêu cầu nguồn |
| `jd.skills[].normalized` | string | Có | Tên kỹ năng dùng để đối chiếu |
| `jd.skills[].tier` | string hoặc null | Không | `T1`, `T2`, `T3`, `T4`, hoặc chưa xác định |
| `jd.skills[].requirement` | string hoặc null | Không | `must`, `nice`, hoặc chưa xác định |
| `cv.cv_id`, `cv.version_id` | string | Có | CV được đánh giá |
| `cv.skills` | array | Có | Kỹ năng CV; có thể rỗng |
| `cv.skills[].skill_id` | string | Có | ID skill nguồn |
| `cv.skills[].normalized` | string | Có | Tên kỹ năng dùng để đối chiếu |

```json
{
  "request_id": "REQ-MATCH-01",
  "jd": {
    "jd_id": "JD-001", "version_id": "JD-001-v1",
    "skills": [
      {"requirement_id": "R-01", "normalized": "Python", "tier": "T1", "requirement": "must"},
      {"requirement_id": "R-02", "normalized": "Kubernetes", "tier": "T2", "requirement": "must"}
    ]
  },
  "cv": {
    "cv_id": "CV-001", "version_id": "CV-001-v1",
    "skills": [
      {"skill_id": "S-01", "normalized": "Python"},
      {"skill_id": "S-02", "normalized": "Docker"}
    ]
  }
}
```

Mỗi phía tối đa 250 skill; normalized không rỗng, tối đa 200 ký tự. Không gửi
điểm mong muốn hoặc nhãn ứng viên đạt/trượt trong request. Tên skill phải được
chuẩn bị nhất quán ở hai phía; bước này chưa tự hiểu mọi tên công nghệ liên quan
là thay thế được nhau. Tier không tự suy từ must/nice.

## 4. Đầu ra AI trả cho BE

| Trường | Kiểu | Nội dung |
| --- | --- | --- |
| `jd_id`, `jd_version_id`, `cv_id`, `cv_version_id` | string | Hai bản nguồn đã so sánh |
| `requirements` | array | Một dòng cho mỗi nhóm kỹ năng yêu cầu sau gộp trùng |
| `requirements[].requirement_ids` | string[] | Những ID yêu cầu nguồn thuộc nhóm |
| `requirements[].name` | string | Tên kỹ năng yêu cầu |
| `requirements[].tier` | string hoặc null | Tier dùng cho nhóm |
| `requirements[].status` | string | `PASS` hoặc `UNKNOWN` |
| `requirements[].evidence_skill_ids` | string[] | Skill trong CV dùng làm bằng chứng |
| `requirements[].reason` | string | `normalized_name_equal` hoặc `no_skill_evidence` |
| `score` | number hoặc null | Điểm tham khảo 0–100, không phải xác suất được tuyển |
| `score_status` | string | Trạng thái điểm theo bảng dưới |
| `unresolved_tier_count` | integer | Số nhóm yêu cầu còn thiếu/mâu thuẫn tier |
| `evidence_coverage` | number hoặc null | Độ bao phủ bằng chứng trên phần đã có tier, 0–100 |
| `eligibility` | string | `NOT_EVALUATED` |
| `constraints_evaluated` | boolean | false |

```json
{
  "jd_id": "JD-001", "jd_version_id": "JD-001-v1",
  "cv_id": "CV-001", "cv_version_id": "CV-001-v1",
  "requirements": [
    {"requirement_ids": ["R-01"], "name": "Python", "tier": "T1", "status": "PASS", "evidence_skill_ids": ["S-01"], "reason": "normalized_name_equal"},
    {"requirement_ids": ["R-02"], "name": "Kubernetes", "tier": "T2", "status": "UNKNOWN", "evidence_skill_ids": [], "reason": "no_skill_evidence"}
  ],
  "score": 78.125,
  "score_status": "EXPERIMENTAL_PROPOSED_TIERS",
  "unresolved_tier_count": 0,
  "evidence_coverage": 56.25,
  "eligibility": "NOT_EVALUATED",
  "constraints_evaluated": false
}
```

| score_status | BE hiển thị |
| --- | --- |
| `EXPERIMENTAL_PROPOSED_TIERS` | Có điểm tham khảo; cách phân nhóm và tính điểm còn ở mức thử nghiệm |
| `INCOMPLETE_TIERS` | score=null; chưa đủ phân nhóm để trả điểm tổng |
| `EMPTY_JD` | score=null; JD không có yêu cầu kỹ năng để tính điểm |

## 5. BE lưu và hiển thị

`PASS` nghĩa là có skill tương ứng trong input CV, chưa xác minh năng lực ngoài
đời. `UNKNOWN` nghĩa là chưa có bằng chứng trong dữ liệu đã gửi, không đổi thành
FAIL. Evidence refs là skill ID của input, chưa phải trích dẫn vị trí trong CV.

Lưu cả kết quả từng requirement và các version nguồn. Hiển thị score cùng
score_status, evidence_coverage và phần chưa rõ tier; không dùng một điểm số
để tự kết luận đủ điều kiện hoặc loại ứng viên. Mỗi cặp JD–CV có kết quả riêng;
muốn so nhiều CV thì gửi các cặp và giữ riêng từng job.
