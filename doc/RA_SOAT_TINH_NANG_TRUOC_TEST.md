# Rà soát tính năng trước buổi test lại từ đầu

> Ngày 2026-11-30. Bản đang chạy: `c6ceaa9` (đã gộp UX freebuff).
> Mọi số dưới đây **đếm từ code và OpenAPI**, không lấy từ tài liệu kế hoạch.

---

## 1. Bản đang chạy có gì

| | Số lượng |
|---|---|
| API operation | **155** trên 135 path, 23 nhóm |
| Migration đã áp | 41 (`00001`–`00041`), Supabase có 34 bản ghi (3 file demo gộp vào 1) |
| Trang frontend | 20 nhóm route (xem §2) |
| Component | 29 file · lib 41 file |
| Service backend | 38 file |
| Test | backend **671** · FE **183** |

### Ma trận trạng thái hồ sơ — chỉ 7 trạng thái, đúng như đã chốt

```
NEW → IN_REVIEW → SHORTLIST → INTERVIEW → OFFERED → ACCEPTED
        ↓            ↓            ↓
  REJECTED_SCREENING   REJECTED_SCREENING   REJECTED_INTERVIEW
```

`SHORTLIST` còn lùi được về `IN_REVIEW`. Ba trạng thái cuối là **cuối đường** —
mở lại cần quyền riêng. **Lịch phỏng vấn KHÔNG phải điều kiện để vào `INTERVIEW`**
— đúng quyết định đã chốt.

---

## 2. Tính năng theo màn — dùng để test

| # | Màn | Làm được gì | API |
|---|---|---|---|
| 1 | Đăng nhập | 5 endpoint auth, đổi mật khẩu | `/v1/auth` |
| 2 | Tổng quan công việc | hàng đợi việc theo vai, badge (nay cập nhật khi đổi trang) | `/v1/dashboard/work-queue`, `/summary` |
| 3 | Vị trí | tạo/sửa, JD nhiều phiên bản, đổi HM, tín hiệu trùng, workspace | 7 route |
| 4 | Tiêu chí | sinh bằng AI, sửa tay, trọng số, duyệt 2 cấp + duyệt trực tiếp, huỷ bản nháp | 11 route |
| 5 | Thư viện rubric | mẫu theo nhóm vị trí, sinh từ JD, áp vào vị trí, phiên bản + publish | 9 route |
| 6 | Hồ sơ ứng viên | tải batch CV, xem/duyệt, đổi trạng thái, ghi chú riêng, gán người phụ trách, tải lại CV | 11 route |
| 7 | Chấm điểm AI | chạy assessment, xếp hạng, duyệt kết quả | 5 route |
| 8 | Shortlist | chia sẻ cho HM, phản hồi, thu hồi | 7 route |
| 9 | **Lịch phỏng vấn** | tạo/sửa, đổi người tham gia, chặn trùng giờ, **xuất .ics** | 5 route |
| 10 | **Phiếu chấm** | chấm theo tiêu chí, hạn chót, mở lại, nhắc | 8 route |
| 11 | **Thông báo** | trong app, chuông ở header, poll 60s | 2 route |
| 12 | Talent Pool | tra cứu lại, rút đồng ý | 2 route |
| 13 | Tuyển dụng công khai | `/careers` danh sách + nộp CV | 3 route |
| 14 | Lưu trữ & xoá | retention, xoá dữ liệu test | 6 + 3 route |
| 15 | Quản trị | tài khoản, phòng ban, nhóm vị trí, cấu hình AI | 31 route |

---

## 3. BỐN điều sẽ trông như hỏng trong buổi test, nhưng là đúng thiết kế

Ghi trước để anh không mất thời gian đoán.

### 3.1. `/careers` trả 404 — vì cờ đang tắt

`PUBLIC_CAREERS_ENABLED=false` và `PUBLIC_CAREERS_TEST_INTAKE_ENABLED=false` trong
`.env.example`. Muốn test nộp CV công khai thì phải bật **cả hai**. Đây là fail-safe
có chủ ý, không phải lỗi.

### 3.2. Chấm điểm AI có thể ra kết quả "tất định" thay vì AI

`LLM_API_KEY` để trống thì hệ thống dùng `deterministic_matching` — chấm theo luật,
không gọi model. Kết quả **vẫn ra điểm**, nên rất dễ tưởng là AI đang chạy. Muốn
kiểm AI thật thì phải điền key và xem log.

### 3.3. Tìm kiếm ngữ nghĩa không hoạt động

`SEMANTIC_RETRIEVAL_ENABLED=false`, `ALLOW_EXTERNAL_API=false`. Đây là **F3.07 chưa
làm**, không phải lỗi cấu hình.

### 3.4. Nhận CV sẽ bị chặn nếu thiếu ClamAV

`careers_intake` **fail-closed**. ClamAV chết → nhận CV hỏng. Nhưng `/health/ready`
**vẫn báo ready** (chỉ báo cáo trạng thái máy quét, trừ khi bật
`READINESS_REQUIRE_CLAMAV`). Nên: **health xanh không có nghĩa là nhận CV được.**

---

## 4. HAI lỗi thật tìm thấy khi rà — nên biết trước khi test

### 4.1. OCR chỉ có tiếng Anh — ĐÃ SỬA

`document_processor.py:115` gọi `pytesseract.image_to_string(image, lang='eng')`,
và `Dockerfile` chỉ cài `tesseract-ocr` + `tesseract-ocr-eng`.

Hệ quả: **PDF scan tiếng Việt** (ảnh, không phải PDF text) sẽ ra chữ mất dấu hoặc
rác. "Nguyễn Văn An" có thể thành "Nguyen Van An". Việc này ảnh hưởng trực tiếp
đến chất lượng chấm điểm, vì OCR sai thì chấm trên chữ sai.

Đây là lỗi thật, không phải "chưa làm F2.06" — OCR đã chạy, chỉ là chạy sai ngôn ngữ.

**Đã sửa** (`document_processor.py` + `backend/Dockerfile`): dò xem máy có gói
`vie` không rồi chọn `vie+eng`, lùi về `eng` nếu thiếu. Không hard-code `vie` vì
máy thiếu gói sẽ ném lỗi lúc chạy, hỏng cả luồng nhận CV thay vì chỉ giảm chất
lượng. Đã thêm `tesseract-ocr-vie` vào Dockerfile và lưu `ocr_language` vào kết
quả để biết trang nào đọc bằng ngôn ngữ nào.

Có test khoá (`test_ocr_language.py`), **đã kiểm ngược**: gắn cứng `eng` trở lại
thì test đỏ.

⚠️ **VPS dùng PM2, không dùng Dockerfile này.** Cần cài tay gói tiếng Việt:
```bash
sudo apt-get install -y tesseract-ocr-vie
tesseract --list-langs   # phải thấy 'vie'
```
Chưa cài thì hệ thống vẫn chạy, chỉ là OCR lùi về tiếng Anh — **không hỏng**, nhưng
CV scan tiếng Việt sẽ mất dấu.

### 4.2. Badge "việc cần làm" — vừa sửa, cần kiểm riêng

Bản trước `d459dad` badge chỉ cập nhật lúc đăng nhập rồi đứng im (bug của freebuff).
Đã sửa. **Kiểm:** mở trang khác, quay lại, badge phải đổi.

---

## 5. Xoá dữ liệu — xoá gì, GIỮ gì

Dùng `/v1/admin/test-data/preview` rồi `/execute`. Cần quyền ADMIN, gõ `OK` để xác nhận.

| Scope | Xoá |
|---|---|
| `CV` | hồ sơ, tài liệu CV, text trích xuất, profile, ghi chú, trạng thái, share, điểm |
| `JD` | JD, phiên bản tiêu chí, tiêu chí, lịch sử duyệt rubric |
| `POSITIONS` | vị trí, phân công, quyền, lịch sử trạng thái, yêu cầu tạo |
| `OPERATIONS` | operation nền, lần xử lý tài liệu, batch CV, retention, audit |

**GIỮ NGUYÊN — `PROTECTED_TABLES`, không bao giờ chạm:**

```
auth.users · user_profiles · user_role_assignments
departments · job_families · app_settings
ai_configuration_versions · ai_policy_versions
assessment_policy_versions · retention_policy_versions
```

Nghĩa là: **xoá xong vẫn đăng nhập được bằng tài khoản cũ**, phòng ban và nhóm vị
trí vẫn còn, cấu hình AI vẫn còn. Chỉ dữ liệu tuyển dụng mất. Đúng ý "test lại từ
đầu".

⚠️ **`00035_purge_test_cv_jd_data.sql` không dùng được ở đây.** Đó là migration SQL
một lần, đòi schema backup `app_backup_20261119` không tồn tại trên Supabase. Dùng
API ở trên, đừng chạy file đó.

---

## 6. Kịch bản test từ đầu — 12 bước, theo thứ tự phụ thuộc

Mỗi bước ghi **kỳ vọng** và **nếu hỏng thì lỗi ở đâu**. Không nhảy bước: bước sau
dùng dữ liệu bước trước.

| # | Việc | Kỳ vọng | Nếu hỏng, xem ở |
|---|---|---|---|
| 0 | Kiểm `/health/ready` | `db: connected` | `.env` DB |
| 1 | Đăng nhập bằng tài khoản cũ | Vào được (purge giữ tài khoản) | auth |
| 2 | Tạo phòng ban / kiểm nhóm vị trí có sẵn | Có danh sách | departments, job_families |
| 3 | Tạo vị trí + dán JD tiếng Việt | Vị trí OPEN, JD v1, ngôn ngữ tự dò = `vi` | positions |
| 4 | Sinh tiêu chí AI | Ra bộ tiêu chí DRAFT, có trọng số | criteria. Nếu LLM chưa có key → ra bộ tất định, **vẫn hợp lệ** |
| 5 | Duyệt bộ tiêu chí lần 1 | APPROVED | criteria/approve |
| 6 | **Duyệt bộ thứ 2 cho cùng vị trí** | Bộ 1 thành SUPERSEDED, **không 500** | ★ bug vừa sửa. Đây là bước quan trọng nhất |
| 7 | Tải 3 CV: 1 PDF text, 1 DOCX, 1 PDF scan | Cả 3 nhận; PDF scan có text nhưng có thể sai dấu | applications/upload-batch |
| 8 | Chạy chấm điểm + xếp hạng | Có điểm và thứ tự, có dẫn chứng | assessments |
| 9 | Đổi trạng thái: NEW→IN_REVIEW→SHORTLIST | Đúng ma trận; nhảy cóc phải bị chặn | applications/status |
| 10 | Chia sẻ shortlist cho HM, HM phản hồi | Share hiện ở `/shortlist` của HM | shortlist |
| 11 | Tạo lịch PV 2 người, 1 OBSERVER | OBSERVER **không** có phiếu chấm; xuất .ics mở được | interviews |
| 12 | Chấm phiếu, kiểm nhắc hạn, mở lại | Điểm lưu; `reopen` có lịch sử | scorecards |

### Kiểm riêng sau bước 12

- **Trùng giờ:** tạo buổi thứ 2 cùng người, cùng giờ → phải **409** kèm giờ bị trùng.
- **Thông báo:** người bị mời phải thấy chuông; người tự thao tác **không** nhận.
- **Badge:** đổi trang → badge đổi (bug vừa sửa).
- **`.ics`:** tải về mở bằng lịch, giờ phải đúng giờ Việt Nam.

---

## 7. Thứ tự ưu tiên khi có lỗi

| Mức | Nghĩa | Ví dụ |
|---|---|---|
| **P0** | Chặn cả luồng | Không đăng nhập được, tạo vị trí 500 |
| **P1** | Sai kết quả nghiệp vụ | Chấm điểm sai, trạng thái nhảy sai |
| **P2** | Đúng nhưng khó dùng | Nhãn sai, thiếu thông báo |
| **P3** | Mỹ phẩm | Lệch khoảng cách |

Đừng gộp nhiều lỗi vào một báo cáo mà không tách mức — khi sửa sẽ không biết cái
nào chặn cái nào.
