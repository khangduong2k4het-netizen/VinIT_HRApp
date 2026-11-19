# VinIT HRApp — Audit Report Round 1

Date: 2026-11-05
Scope: Full Phase 1 MVP codebase (Backend, Frontend, Database, Configuration)

---

## Issues Summary

| Mức độ | Số lượng |
|---|:---:|
| Critical (Bug/Logic error, security risk) | 5 |
| High (Functional gap, data integrity issue) | 6 |
| Medium (Code quality, maintainability) | 7 |
| Low (Cosmetic, optimization) | 4 |

---

## Critical Issues (Must fix before demo)

### C1: Generate Criteria API không load JD từ database
- **File:** `backend/app/api/criteria.py`
- **Vấn đề:** Endpoint `/criteria/generate` nhận `jd_content` từ request body, thay vì load JD đã được lưu trong database khi tạo vị trí. Frontend hiện tại truyền chuỗi rỗng, khiến LLM không có dữ liệu JD để phân tích → không thể tạo tiêu chí.
- **Fix:** Load nội dung JD mới nhất từ `jd_versions` của vị trí, bỏ tham số không cần thiết khỏi request.

### C2: Worker _run_assessments và _generate_ranking là placeholder rỗng
- **File:** `backend/app/workers/processor.py`
- **Vấn đề:** Sau khi xử lý CV xong, hệ thống tự động queue ASSESSMENT operation, nhưng hàm xử lý assessment chỉ tạo operation rỗng cho ranking → Không có đánh giá nào thực sự chạy, không có kết quả matching nào được tạo ra.
- **Fix:** Implementation đầy đủ các bước xử lý assessment: load criteria, load CV text/profile, gọi LLM matching, kiểm tra verbatim quote, tính điểm tất định bằng matching_engine, lưu kết quả.

### C3: API trả về FileResponse trực tiếp trong đường dẫn trả về JSON cho getCvUrl
- **File:** `backend/app/api/applications.py`
- **Vấn đề:** Endpoint `/applications/{id}/cv-download-url` trả về FileResponse trực tiếp khi dùng local storage, thay vì trả về URL như frontend mong đợi → Frontend không thể xử lý kết quả, không thể hiển thị CV trong iframe.
- **Fix:** Trả về `/v1/applications/{id}/cv-file` cho local storage, thêm endpoint riêng để serve file.

### C4: Worker SQLAlchemy truy vấn không có commit/thoát session đúng cách
- **File:** `backend/app/workers/processor.py`
- **Vấn đề:** Worker mở SessionLocal một lần lúc đầu và giữ session trong suốt quá trình lặp, không có rollback đúng cách khi có lỗi → rò rỉ kết nối database, lỗi transaction không được rollback.
- **Fix:** Quản lý vòng đời session đúng cách: mở/đóng session cho mỗi operation, rollback ngay khi có exception.

### C5: Supabase client là singleton cached nhưng cấu hình SUPABASE_URL là Optional
- **File:** `backend/app/db/supabase.py`
- **Vấn đề:** Nếu `SUPABASE_URL` không được cấu hình, gọi `get_supabase_client()` sẽ crash với lỗi URL rỗng. Không có kiểm tra khi storage backend là "local".
- **Fix:** Trả về None khi Supabase không được cấu hình, thêm kiểm tra ở nơi gọi.

---

## High Priority Issues (Functional gaps)

### H1: Phân quyền RBAC chưa được implement trong API
- **File:** Tất cả các API endpoint đều có comment `TODO: Check if user has access`
- **Vấn đề:** Bất kỳ người dùng đã đăng nhập nào cũng có thể thấy và sửa tất cả vị trí, hồ sơ ứng viên của mọi người → Không có phân chia theo vị trí được phân công.
- **Fix:** Implement helper kiểm tra quyền truy cập vị trí từ bảng `position_assignments`, áp dụng vào tất cả các endpoint.

### H2: Worker _save_extracted_text tạo thư mục chưa đúng đường dẫn
- **File:** `backend/app/workers/processor.py`
- **Vấn đề:** Hàm `_save_extracted_text()` tạo directory với `os.makedirs(full_dir)` nhưng `full_dir` chỉ chứa `application_id/document_id`, thiếu bucket name prefix → lỗi khi lưu file.
- **Fix:** Sửa đường dẫn chính xác bao gồm bucket root.

### H3: Endpoint operation status trả về sai kiểu dữ liệu
- **File:** `backend/app/api/operations.py`
- **Vấn đề:** Khi truy vấn kết quả batch progress, lỗi `dict(zip(...))` vì row là tuple kết nối SQLAlchemy, mapping columns sai thứ tự.
- **Fix:** Dùng Row._mapping để convert đúng sang dictionary.

### H4: Admin endpoint cho enable AI config không ném lỗi khi không tìm thấy config
- **File:** `backend/app/api/admin.py`
- **Vấn đề:** Nếu config_id không tồn tại, hàm vẫn trả về thành công thay vì 404.
- **Fix:** Kiểm tra số dòng affected, trả về 404 nếu không tìm thấy.

### H5: Không có RLS policy cho bảng operations, cv_batches
- **File:** `supabase/migrations/00001_initial_schema.sql`
- **Vấn đề:** Thiếu RLS trên các bảng tác vụ xử lý → bất kỳ ai cũng có thể xem trạng thái xử lý.
- **Fix:** Bổ sung policy cơ bản.

### H6: Local file serving không có kiểm tra quyền truy cập
- **Vấn đề:** Khi serve file CV local, endpoint không kiểm tra người dùng có quyền xem hồ sơ không → bất kỳ ai biết URL đều có thể tải CV.
- **Fix:** Kiểm tra quyền trước khi trả file.

---

## Medium Priority Issues

### M1: Pydantic schemas chưa chặt chẽ
Nhiều trường optional quá, thiếu validation cho các giá trị enum.

### M2: Worker không retry khi LLM thất bại tạm thời
Hiện tại khi lỗi LLM sẽ đánh dấu cả hồ sơ cần review, nên retry 1-2 lần trước khi báo lỗi.

### M3: Logging có thể in nội dung CV khi lỗi
Cần đảm bảo nội dung CV/PII không được ghi vào log.

### M4: Frontend types còn thiếu cho nhiều đối tượng
Các TypeScript interface chưa bao gồm đầy đủ các trường từ API.

### M5: API axios interceptor xử lý lỗi không lấy chi tiết lỗi từ response
Hiện tại chỉ lấy `detail` ở một số nơi.

### M6: Duplicate detection chỉ chạy trên contact info sau ranking
Cần chạy sớm hơn ngay sau khi trích xuất xong profile.

### M7: Không có index cho operation_id và status trên bảng operations
Sẽ chậm khi worker poll liên tục.

---

## Low Priority Issues

### L1: File status badge màu sắc chưa khớp hoàn toàn với style guide ở một số chỗ
### L2: Placeholder các trang "Ứng viên" trong sidebar chưa có trang tương ứng
### L3: Login page chưa link logo đúng đường dẫn
### L4: README thiếu hướng dẫn chạy worker quy trình đầy đủ

---

## Fixing Progress
Đang sửa tất cả các Critical và High issues trước.
