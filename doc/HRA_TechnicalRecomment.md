# Đề xuất công nghệ sử dụng — Phase 1

## 1. Khuyến nghị tổng thể

Đề xuất xây dựng **modular monolith** cho Phase 1: một ứng dụng web, một lớp API và một tiến trình worker xử lý CV/AI. API và worker có thể dùng chung codebase nhưng chạy thành các tiến trình riêng.

Cách này giữ được các hợp đồng CAPI/FAPI đã thiết kế, đồng thời tránh thêm nhiều dịch vụ vận hành khi quy mô mới ở mức pilot.

## 2. Stack đề xuất

| Lớp | Công nghệ đề xuất | Vai trò |
|---|---|---|
| Web | **Next.js, React, TypeScript** | Giao diện HR và Hiring Manager; hỗ trợ tiếng Việt/Anh. |
| UI | Ưu tiên design system hiện có của VinUni; nếu chưa có, dùng **MUI** | Thành phần giao diện nhất quán, hỗ trợ biểu mẫu và bảng dữ liệu. |
| Đa ngôn ngữ | **next-intl** hoặc giải pháp i18n tương đương | Quản lý nhãn và nội dung UI tiếng Việt/Anh. |
| API ứng dụng | **Python, FastAPI, Pydantic** | Thực hiện các hợp đồng `/v1` FAPI/CAPI, kiểm tra quyền và điều phối tác vụ AI bất đồng bộ. |
| Dữ liệu | **Supabase PostgreSQL + PostgREST** | Lưu dữ liệu nghiệp vụ và cung cấp lớp truy cập dữ liệu cho API. |
| Vector retrieval (tùy chọn) | **pgvector trong PostgreSQL** + BGE qua endpoint `/embeddings` | Lưu/truy vấn embedding của CV chunks khi semantic retrieval được bật; không cần vector database riêng ở quy mô hiện tại. |
| Học xếp hạng (tùy chọn) | **Pairwise logistic LTR train offline** | Train/đánh giá artifact theo group/position; registry trong PostgreSQL; mặc định `OFF`, chỉ `SHADOW`/`ACTIVE` khi đạt gate. |
| Đăng nhập | **Supabase Auth** | Tài khoản nội bộ email/mật khẩu theo phạm vi Phase 1. SSO/MFA chưa nằm trong Phase 1. |
| Tệp | **Supabase Storage**, bucket private | Lưu CV gốc và nội dung trích xuất; API cấp quyền tải lên/tải xuống có thời hạn. |
| Hàng đợi | **Supabase Queues/pgmq**, nếu có trong deployment được chọn | Điều phối xử lý file, matching và ranking bất đồng bộ. |
| Worker | **Python worker** dùng chung codebase với API | Xử lý PDF/DOCX/OCR, gọi model được duyệt và lưu kết quả. |
| Model AI | Ưu tiên chạy cục bộ bằng **vLLM** nếu môi trường có GPU phù hợp | Trích xuất thông tin và đề xuất matching; model cụ thể cần được đánh giá trước khi chọn. |
| Đọc tài liệu | `pypdf`, `python-docx`, **OCRmyPDF + Tesseract** | Trích xuất PDF có văn bản, DOCX và OCR cho PDF scan. |
| Hiển thị CV | **PDF.js** | Xem CV và đối chiếu bằng chứng trong tài liệu. |
| Kiểm thử | **pytest**, **Playwright** và kiểm thử hợp đồng API | Kiểm tra nghiệp vụ, luồng giao diện, quyền truy cập và các API đã thiết kế. |
| Quan sát hệ thống | OpenTelemetry và công cụ logging/metrics được VinUni phê duyệt | Theo dõi lỗi và tác vụ; tránh ghi CV hoặc PII vào log. |

## 3. Luồng kiến trúc đề xuất

```text
Người dùng
   │
   ├── Đăng nhập ────────────> Supabase Auth
   │
   └── Gọi API /v1 ─────────> FastAPI: FAPI + CAPI
                                 │
                                 ├── PostgREST
                                 │     └── PostgreSQL
                                 │
                                 ├── Cấp quyền tải file có thời hạn
                                 │     └── Supabase Storage private
                                 │
                                 └── Hàng đợi tác vụ
                                       └── Python worker
                                             ├── Kiểm tra và trích xuất file
                                             ├── OCR PDF scan
                                             ├── Model AI được phê duyệt
                                             └── Ghi assessment/ranking
```

**Khuyến nghị quan trọng:** trình duyệt gọi FastAPI theo các hợp đồng `/v1` đã thiết kế; không expose trực tiếp các bảng nghiệp vụ qua PostgREST cho frontend. FastAPI dùng PostgREST để truy cập dữ liệu được phép, còn các view/RPC chỉ được mở theo danh sách cho phép. Cách này giữ API nghiệp vụ ổn định và tránh để client thao tác trực tiếp với các bảng nhạy cảm.

## 4. Các quyết định kỹ thuật cần giữ rõ

### Supabase và PostgREST

- Tổ chức dữ liệu theo hướng:
  - `auth`: tài khoản do Supabase Auth quản lý.
  - `app_private`: bảng nghiệp vụ và thông tin nhạy cảm, không expose trực tiếp.
  - `api`: các view/RPC được phép truy cập qua PostgREST.
- Bật RLS cho dữ liệu được expose; kiểm tra quyền theo **người dùng, vai trò, vị trí và quyền chia sẻ**.
- Dùng RPC cho thao tác cần cập nhật nhiều dữ liệu nhất quán, chẳng hạn cập nhật trạng thái ứng tuyển đồng thời ghi lịch sử trạng thái.
- Không đưa khóa `service_role` vào trình duyệt. Quyền của worker cũng cần được giới hạn; không cấp quyền đổi trạng thái hồ sơ ứng tuyển cho tác vụ AI.
- Quản lý thay đổi cơ sở dữ liệu bằng migration có phiên bản, chẳng hạn qua Supabase CLI.

### Upload và xử lý CV

- API kiểm tra số lượng file, dung lượng batch và định dạng trước khi nhận.
- Dùng **10 MB = 10.000.000 byte** cho giới hạn mỗi file; tối đa 50 file và tổng batch 250.000.000 byte.
- Có thể để trình duyệt tải file trực tiếp lên bucket private qua URL có thời hạn ngắn; API xác nhận batch và xếp hàng xử lý sau khi upload hoàn tất.
- Kiểm tra loại file thực tế, không chỉ dựa vào phần mở rộng. Khuyến nghị quét file độc hại trước khi đưa vào bước trích xuất.
- Chạy trích xuất/OCR trong worker riêng, giới hạn tài nguyên và thời gian xử lý.
- PDF bị khóa, quá mờ hoặc không đọc được chuyển sang **Cần HR kiểm tra**; không tự loại hồ sơ.

### AI và matching

- Ưu tiên model chạy cục bộ. Model và cấu hình cụ thể chỉ được chọn sau khi thử nghiệm chất lượng trên dữ liệu tổng hợp hoặc đã được phép sử dụng.
- Không gửi CV thật tới API ngoài nếu chưa được phê duyệt theo chính sách sử dụng dữ liệu.
- Chuyển kết quả model qua cấu trúc đầu ra có kiểm tra kiểu/schema; không lưu chain-of-thought.
- Dùng **logic xác định** trong backend để tính điểm, độ phủ bằng chứng và thứ hạng theo policy đã chọn. Không giao cho model tự quyết định các phép tính này.
- Không cần vector database riêng. Bản hiện thực dùng **pgvector trong cùng PostgreSQL** cho semantic retrieval tùy chọn; lexical/rule retrieval vẫn là đường chính và semantic chỉ bổ sung candidate chunks cho LLM fallback.
- BGE phải chạy qua endpoint embedding được phê duyệt (TEI/Xinference/vLLM hoặc dịch vụ tương thích). Không mô tả provider `hash` trong test là BGE.
- LTR không train online và không tự kích hoạt. Artifact phải train offline từ labelled data, tách holdout theo position/group, đăng ký `DRAFT` và chỉ được phê duyệt sau khi đạt metric gate.
- Không cần framework agent tự động cho Phase 1; ưu tiên luồng điều phối rõ ràng và danh sách tool được cho phép.

### Tác vụ bất đồng bộ

CAPI xử lý CV, matching và ranking nên tiếp tục trả `202 Accepted` cùng `operationId`, như đã nêu trong interface design.

- Ưu tiên dùng Supabase Queues/pgmq nếu dịch vụ đó có trong mô hình triển khai được duyệt.
- Nếu không có, dùng hàng đợi PostgreSQL đơn giản cho pilot.
- Chưa cần thêm Redis, Kafka hoặc hệ thống microservices chỉ để xử lý khối lượng pilot.

## 5. Hosting, bảo mật và vận hành

**Mô hình Supabase cần quyết định trước khi dùng CV thật:**

- Nếu Supabase managed đáp ứng yêu cầu về vùng lưu trữ, quyền truy cập, sao lưu và điều kiện sử dụng của VinUni, có thể dùng để giảm công sức vận hành.
- Nếu không phù hợp, triển khai Supabase trong môi trường được VinUni phê duyệt; cần tính thêm công sức quản trị và sao lưu.
- Dùng dữ liệu tổng hợp hoặc đã khử định danh cho kiểm thử cho tới khi môi trường và luồng dữ liệu được IT/Security chấp thuận.

Các yêu cầu vận hành nên có trong Phase 1:

- Tách môi trường phát triển, kiểm thử và pilot.
- Dùng TLS khi truyền dữ liệu; dùng bucket private và quyền tải file có thời hạn.
- Không đưa CV, tên ứng viên hoặc trích đoạn bằng chứng vào log lỗi, công cụ analytics hay báo cáo ngoài môi trường được duyệt.
- Có backup cho PostgreSQL và Storage; thử khôi phục định kỳ.
- Kiểm thử RLS theo từng vai trò, đặc biệt quyền của Hiring Manager, Viewer và Admin.
- Ghi audit cho các thao tác quan trọng như duyệt tiêu chí, đổi trạng thái hồ sơ, thay đổi quyền, chia sẻ shortlist và xác nhận xóa.
- Triển khai bằng container trên nền tảng được VinUni phê duyệt; **không cần đưa Kubernetes vào chỉ để phục vụ pilot** nếu nền tảng hiện có không yêu cầu.

## 6. Những lựa chọn chưa nên đưa vào Phase 1

Để hạn chế độ phức tạp, chưa khuyến nghị:

- Microservices cho từng capability.
- Vector database hoặc dịch vụ tìm kiếm riêng tách khỏi PostgreSQL/pgvector.
- Redis/Kafka nếu hàng đợi pilot đáp ứng được.
- Nhiều nhà cung cấp model hoặc cơ chế fallback sang provider chưa được duyệt.
- Kết nối CRM/ATS/HRIS.
- Deploy frontend hoặc gửi telemetry tới dịch vụ SaaS chưa được VinUni phê duyệt.

## 7. Kết luận đề xuất

Stack khuyến nghị cho Phase 1 là:

> **Next.js/React/TypeScript + FastAPI/Python + Supabase PostgreSQL/PostgREST/Auth/Storage + hàng đợi PostgreSQL phù hợp + Python worker + xử lý PDF/DOCX/OCR + model AI cục bộ được đánh giá và phê duyệt.**

Cập nhật 07/11/2026: pgvector/BGE semantic retrieval và LTR đã được thêm như lớp tùy chọn tắt mặc định trên cùng stack PostgreSQL/FastAPI/worker. Chúng không làm thay đổi kết luận stack Phase 1; điều kiện kích hoạt nằm ở [MATCHING_STABILITY.md](MATCHING_STABILITY.md).

Ba quyết định cần chốt trước khi triển khai với CV thật là: **managed hay self-hosted Supabase; môi trường triển khai được VinUni phê duyệt; và khả năng chạy model cục bộ phù hợp với khối lượng pilot.**