# Chẩn đoán: "Đã tạo vị trí nhưng chưa tạo được tiêu chí"

## Nguyên nhân thật (đã tìm ra và đã sửa)

Lỗi **không** phải do AI trả về tiêu chí kém, và **không** phải do proxy cắt
request. Nguyên nhân nằm ở một dòng trong bộ suy luận tiêu chí.

`build_requirement_spec` xét xem một tiêu chí có phải yêu cầu **ngoại ngữ**
không bằng cách tìm các từ như `communication`, `proficiency`, `language`.
Nhưng "Excellent **communication** skills" hay "**proficiency** in presenting"
là kỹ năng mềm, không phải ngoại ngữ. Kết quả là tiêu chí bị gắn
`kind = "LANGUAGE"` **mà không kèm ngôn ngữ nào và không có ngưỡng nào**.

Schema response `RequirementSpec` bắt buộc tiêu chí `LANGUAGE` phải có ngôn ngữ
hoặc mức yêu cầu (IELTS/TOEIC/CEFR). Vì vậy:

1. Tiêu chí và vị trí **đã được ghi vào DB thành công**;
2. FastAPI **serialize response thì hỏng**;
3. FastAPI trả **500 plain text "Internal Server Error"** — **không có `detail`**;
4. Giao diện không có gì để hiện nên dùng câu dự phòng:
   *"Đã tạo vị trí nhưng chưa tạo được tiêu chí"*.

Đúng như những gì đã thấy. Một ca cụ thể đã tái hiện được:

```text
name="Communication" description="Excellent verbal and written communication skills"
  -> kind=LANGUAGE, required_languages=[], required_ielts=None, ...
  -> RequirementSpec: "Tiêu chí ngoại ngữ cần ngôn ngữ hoặc mức yêu cầu"
```

## Đã sửa ba lớp

| Lớp | Sửa | Tệp |
|---|---|---|
| Gốc | Chỉ gắn `kind=LANGUAGE` khi **thật sự** có ngôn ngữ hoặc ngưỡng | `app/services/deterministic_matching.py` |
| Phòng thủ | Bỏ `requirement_spec` hỏng khỏi response thay vì làm hỏng cả request | `app/api/criteria.py` (`_sanitize_criteria_response`) |
| Phía giao diện | Lỗi không có `detail` thì **hỏi lại server** thay vì đoán | `frontend/src/lib/criteriaGeneration.ts` |

Lớp thứ hai quan trọng vì **dữ liệu cũ vẫn còn trong DB**: những bản tiêu chí
đã lưu với spec hỏng sẽ làm hỏng cả lần **đọc** (tab Tiêu chí đánh giá) chứ
không chỉ lần tạo. Hàm làm sạch áp dụng cho cả lần tạo, lần liệt kê và lần đọc.

## Cách kiểm chứng trên VPS

```bash
cd /home/ubuntu/hra
bash scripts/deploy.sh --branch arena/ea6e2570-vinit-hrapp --migrations-verified
pm2 logs hra-backend --lines 50 | grep -E "requirement_spec omitted|rejected by local validation"
```

- Thấy `requirement_spec omitted from response` → đã gặp dòng dữ liệu cũ và đã
  được xử lý an toàn (endpoint vẫn trả về bình thường).
- Tạo một vị trí mới với JD có các câu kiểu "communication skills",
  "proficiency in presenting", "teamwork" → phải ra tiêu chí bình thường.

Kiểm tra dữ liệu trực tiếp (chỉ đọc):

```bash
docker compose exec -T backend python -c "
from app.db.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
rows = db.execute(text('''
    SELECT p.position_code, c.version_number, c.status,
           count(i.criterion_id) AS items
    FROM app_private.positions p
    LEFT JOIN app_private.criteria_versions c ON c.position_id = p.position_id
    LEFT JOIN app_private.criteria_items i ON i.criteria_version_id = c.criteria_version_id
    GROUP BY 1,2,3 ORDER BY p.created_at DESC LIMIT 5
''')).mappings()
for row in rows: print(dict(row))
"
```

## Về lâu dài (chưa làm, cần anh quyết)

`POST /criteria/generate/{position_id}` khai báo trả `202 ACCEPTED` nhưng **chạy
LLM ngay trong request** (mỗi lần gọi tối đa 120 giây, có retry và fallback).
Nghĩa là một request đồng bộ có thể kéo dài vài phút — mọi lỗi tầng mạng đều
biến thành "không biết kết quả".

Backend **đã có sẵn** hạ tầng xử lý nền (`app/workers/processor.py`,
`operationsApi` / `OperationProgressPanel`) nhưng luồng tiêu chí chưa dùng.
Chuyển sang mô hình đó sẽ bỏ hẳn nhóm lỗi này. Tôi chưa tự đổi vì đây là thay
đổi kiến trúc, cần anh đồng ý.
