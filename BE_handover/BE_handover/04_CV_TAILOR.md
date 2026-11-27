# CV Tailor — Chọn nội dung phù hợp JD và viết lại CV

## 1. Hai thao tác BE cần nối

1. Gửi CV/JD có cấu trúc để nhận danh sách skill được chọn.
2. Gửi CV/JD cùng kết quả selection để nhận mục Skills và bullet được viết lại.

Đầu ra là nội dung đề xuất, chưa phải file CV PDF/DOCX hoàn chỉnh.

## 2. API chọn skill

`POST /api/v1/ai/cv-tailor/selections`, body JSON. Phản hồi 202 và job_id theo
[quy ước chung](README.md).

### BE gửi

| Trường | Kiểu | Bắt buộc | Nội dung |
| --- | --- | --- | --- |
| `request_id` | string | Có | ID yêu cầu |
| `cv` | object | Có | [CV cấu trúc](README.md): cv_id, version_id, skills, evidence |
| `jd` | object | Có | [JD cấu trúc](README.md): jd_id, version_id, requirements |

Ví dụ tối thiểu:

```json
{
  "request_id": "REQ-SELECT-01",
  "cv": {
    "cv_id": "CV-001", "version_id": "CV-001-v1",
    "skills": [
      {"skill_id": "S-01", "text": "Java", "normalized": "Java", "evidence_ids": ["E-01"]},
      {"skill_id": "S-02", "text": "SQL", "normalized": "SQL", "evidence_ids": []}
    ],
    "evidence": [
      {"evidence_id": "E-01", "parent_id": "PROJECT-01", "kind": "project", "text": "Built REST APIs using Java."}
    ]
  },
  "jd": {
    "jd_id": "JD-001", "version_id": "JD-001-v1",
    "requirements": [
      {"requirement_id": "R-01", "kind": "skill", "text": "Java", "normalized": "Java", "priority": "must"},
      {"requirement_id": "R-02", "kind": "skill", "text": "AWS", "normalized": "AWS", "priority": "nice"}
    ]
  }
}
```

### AI trả

| Trường | Kiểu | Nội dung |
| --- | --- | --- |
| `selection_id` | string | ID của bản lựa chọn |
| `cv_id`, `cv_version_id`, `jd_id`, `jd_version_id` | string | Nguồn được dùng |
| `selected_skills` | array | Skill trong CV được chọn; có thể rỗng |
| `selected_skills[].skill_id` | string | ID skill gốc |
| `selected_skills[].matched_requirement_ids` | string[] | Những skill requirement mà skill này được chọn cho |
| `selected_skills[].evidence_status` | string | `listed_only` hoặc `evidenced` |
| `selected_skills[].evidence_ids` | string[] | Bằng chứng được phép dùng cho skill này |
| `unmatched_requirements` | string[] | Các skill requirement chưa có lựa chọn phù hợp |
| `constraints_evaluated` | boolean | false trong phạm vi này |

```json
{
  "selection_id": "SEL-001",
  "cv_id": "CV-001", "cv_version_id": "CV-001-v1",
  "jd_id": "JD-001", "jd_version_id": "JD-001-v1",
  "selected_skills": [
    {"skill_id": "S-01", "matched_requirement_ids": ["R-01"], "evidence_status": "evidenced", "evidence_ids": ["E-01"]}
  ],
  "unmatched_requirements": ["R-02"],
  "constraints_evaluated": false
}
```

`listed_only` có evidence_ids rỗng và chỉ dùng trong mục Skills. `evidenced`
có ít nhất một evidence đã liên kết với chính skill đó. Requirement về số năm,
địa điểm hoặc bằng cấp không nằm trong unmatched_requirements.

## 3. API viết lại nội dung

`POST /api/v1/ai/cv-tailor/wordings`, body JSON. Phản hồi 202 và job_id.

### BE gửi

| Trường | Kiểu | Bắt buộc | Nội dung |
| --- | --- | --- | --- |
| `request_id` | string | Có | ID yêu cầu mới |
| `cv` | object | Có | Đúng CV và version dùng ở selection |
| `jd` | object | Có | Đúng JD và version dùng ở selection |
| `selection` | object | Có | Toàn bộ object selection đã nhận, không chỉ selection_id |

BE không cần tự quyết định câu nào được viết hoặc tự ghép prompt. AI lấy những
skill/evidence được phép, xử lý che thông tin cá nhân cần thiết trước khi viết
và kiểm tra nội dung trả về. Nếu cần che riêng ở phía BE, có thể dùng API PII,
nhưng không thay text/evidence gốc bằng bản che trong cùng một version.

### AI trả

| Trường | Kiểu | Nội dung |
| --- | --- | --- |
| `selection_id`, `cv_id`, `cv_version_id`, `jd_id`, `jd_version_id` | string | Giữ nguồn và lựa chọn |
| `status` | string | `generated`, `partial_fallback`, `fallback` |
| `skills_section` | array | skill_id, display_text, evidence_status |
| `bullets` | array | Nội dung theo từng project/experience |
| `bullets[].bullet_id`, `parent_id` | string | Bullet và mục hồ sơ chứa bullet |
| `bullets[].text` | string | Nội dung cuối cùng để hiển thị |
| `bullets[].skill_ids`, `source_evidence_ids` | string[] | Nguồn của nội dung được viết |
| `bullets[].fallback_used` | boolean | Có dùng lại nội dung nguồn vì bản viết không đạt hay không |
| `warnings` | string[] | Điểm cần người dùng kiểm tra |

```json
{
  "selection_id": "SEL-001",
  "cv_id": "CV-001", "cv_version_id": "CV-001-v1",
  "jd_id": "JD-001", "jd_version_id": "JD-001-v1",
  "status": "generated",
  "skills_section": [{"skill_id": "S-01", "display_text": "Java", "evidence_status": "evidenced"}],
  "bullets": [
    {"bullet_id": "B-01", "parent_id": "PROJECT-01", "text": "Developed REST APIs using Java.", "skill_ids": ["S-01"], "source_evidence_ids": ["E-01"], "fallback_used": false}
  ],
  "warnings": []
}
```

## 4. BE lưu và hiển thị

Giữ selection và bản viết lại tách biệt. Hiển thị đề xuất cạnh nội dung gốc,
cho người dùng chọn áp dụng. Bản CV người dùng chấp nhận trở thành version
mới; không ghi đè CV nguồn. Không thêm thành tích, số liệu, kỹ năng hay số năm
kinh nghiệm không có trong bằng chứng. Lỗi hoặc thiếu bằng chứng không được
thay bằng một câu tự tạo để lấp chỗ trống.
