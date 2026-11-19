# Kiến trúc giải pháp — HR CV & JD Ranking

> **Tài liệu:** `docs/architecture-design.md`  
> **Phiên bản:** 1.0 — Draft for Architecture Review  
> **Trạng thái:** Kiến trúc logic, chưa được phê duyệt cuối cùng  
> **Nguồn yêu cầu:** BRD — Requirement Analysis v1.0 và Product Definition v1.0. Cả hai hiện là tài liệu dự thảo; Product Readiness được đánh giá **AMBER**.
> **Cập nhật triển khai (07/11/2026):** kiến trúc logic dưới đây đã có phần hiện thực gồm deterministic matching, pgvector/BGE semantic retrieval và Learning-to-Rank theo hướng tắt mặc định/có gate. Chi tiết hiện trạng, cấu hình và giới hạn production nằm ở [MATCHING_STABILITY.md](MATCHING_STABILITY.md) và [PGVECTOR_BGE_LTR_IMPLEMENTATION.md](../audit/PGVECTOR_BGE_LTR_IMPLEMENTATION.md); tài liệu này không tự tuyên bố BGE/LTR đã kích hoạt production.

## Phạm vi và cách đọc tài liệu

Tài liệu chuyển các yêu cầu sản phẩm/nghiệp vụ thành kiến trúc **logic, độc lập với công nghệ và phương án triển khai**. Tài liệu không xác định kiến trúc cụ thể theo nhà cung cấp, ngăn xếp công nghệ, cấu trúc lưu trữ vật lý, lược đồ dữ liệu, hợp đồng tích hợp hoặc cách triển khai.

Các từ **CRM**, **tool**, **module logic** và **tích hợp** bên dưới mô tả năng lực hoặc miền trách nhiệm; không giả định VinUni đã chọn một sản phẩm CRM, ATS, HRIS hay dịch vụ bên ngoài cụ thể.

### Phạm vi MVP

- Tuyển dụng các vị trí **không phải giảng viên**, pilot với các nhóm Software Engineer, QA, DevOps, Data Engineer và IT Support.
- HR upload CV theo vị trí; không crawl CV từ nguồn trực tuyến.
- CV/JD tiếng Anh; giao diện Việt/Anh, mặc định tiếng Việt.
- Hỗ trợ PDF có văn bản, OCR cho PDF scan và trích xuất văn bản DOCX.
- AI đề xuất tiêu chí, trích xuất nội dung, đối chiếu theo rubric đã duyệt và hỗ trợ ranking **trong cùng một vị trí**.
- HR và Hiring Manager duyệt tiêu chí. HR là người quyết định và cập nhật trạng thái ứng tuyển.
- Ranking là công cụ ưu tiên rà soát, không phải quyết định tuyển/loại.
- Ưu tiên model cục bộ. API model bên ngoài chỉ dùng trong kiểm thử giai đoạn đầu, theo điều kiện dữ liệu đã được phê duyệt.
- Xác thực bằng email và mật khẩu nội bộ trong MVP; SSO chưa thuộc MVP.

### Quy ước truy vết

| Loại | Mã | Ý nghĩa |
|---|---|---|
| Business Goal | **BG-01 … BG-08** | Mục tiêu kinh doanh trong BRD |
| JTBD | **JTBD-01 … JTBD-09** | Jobs To Be Done đã được xác định |
| User Journey | **UJ-01 … UJ-06** | Các hành trình người dùng trong Product Definition |
| Business Flow | **BF-01 … BF-08** | Các bước nghiệp vụ mô tả trong tài liệu này |
| AI Capability | **AIC-01 … AIC-06** | Năng lực AI trong BRD/PRD |
| Component | **C-01 … C-11** | Thành phần logic trong kiến trúc |
| Tool | **T-…** | Năng lực logic được AI hoặc hệ thống gọi có kiểm soát |
| Integration | **INT-01 … INT-07** | Luồng trao đổi logic giữa các miền |
| Acceptance Criteria | **AC-01 … AC-14** | Điều kiện kiểm chứng kiến trúc suy ra từ yêu cầu |
| Logical Module | **LM-01 … LM-06** | Nhóm module logic; không phải ranh giới code hay đơn vị triển khai |

---

# Artifact 0 — Architecture Traceability Matrix

Bảng dưới đây nối Business Goal, JTBD và quy trình nghiệp vụ với năng lực AI, thành phần logic, tool, tích hợp và điều kiện kiểm chứng. Cột **Logical Module** là cách nhóm năng lực ở mức sản phẩm, không phải thiết kế code hoặc kế hoạch triển khai.

| Business Goal | JTBD / Journey | Business Flow | AI Capability | Architecture Component | Tool | Integration | Logical Module | Acceptance Criteria / Requirement |
|---|---|---|---|---|---|---|---|---|
| BG-01, BG-06, BG-07 | JTBD-01 / UJ-01 | BF-01, BF-02 | AIC-01 | C-03, C-07, C-09 | T-CRM-01, T-CRM-02, T-KNO-01, T-GEN-01 | INT-01, INT-02, INT-04 | LM-02, LM-04, LM-05 | AC-01; FR-01–FR-04 |
| BG-01, BG-03, BG-04, BG-07 | JTBD-03 / UJ-03 | BF-04, BF-05 | AIC-02, AIC-03, AIC-05 | C-05, C-06, C-07, C-08, C-09 | T-GEN-02, T-REC-01, T-REC-03, T-UTL-01–04, T-UTL-06 | INT-02, INT-03, INT-04, INT-05 | LM-03, LM-04, LM-05 | AC-02–AC-04, AC-12; FR-05–FR-11 |
| BG-03, BG-04, BG-07 | JTBD-04 / UJ-03 | BF-05 | AIC-03, AIC-04, AIC-05 | C-07, C-08, C-09 | T-REC-01–03, T-UTL-05, T-UTL-06 | INT-04, INT-05 | LM-04, LM-05 | AC-05; FR-12–FR-14 |
| BG-02, BG-03, BG-08 | JTBD-02 / UJ-02 | BF-03, BF-04 | AIC-02, AIC-05, AIC-06 | C-02, C-04, C-05, C-06, C-11 | T-CRM-03, T-GEN-02, T-REC-03, T-REC-04, T-UTL-01–03, T-UTL-06 | INT-01, INT-03, INT-04, INT-07 | LM-01, LM-03, LM-05, LM-06 | AC-02, AC-03, AC-06, AC-08, AC-12, AC-13; FR-05–FR-09, FR-17, FR-19 |
| BG-02, BG-04, BG-07, BG-08 | JTBD-05 / UJ-02, UJ-03 | BF-04, BF-05 | AIC-05, AIC-06 | C-05, C-06, C-07, C-08, C-11 | T-REC-03, T-REC-04, T-UTL-04, T-UTL-06 | INT-03, INT-04, INT-05 | LM-03, LM-04, LM-06 | AC-03, AC-04, AC-06, AC-12; FR-07, FR-08, FR-11, FR-19 |
| BG-01, BG-07, BG-08 | JTBD-06 / UJ-04 | BF-06, BF-07 | AIC-03, AIC-04 **chỉ cung cấp thông tin hỗ trợ**; không có AI cập nhật trạng thái | C-01, C-04, C-08, C-09, C-11 | T-CRM-04 chỉ ghi nhận kết quả đánh giá AI; không có tool AI ghi trạng thái ứng tuyển | INT-05, INT-06 | LM-01, LM-04, LM-05, LM-06 | AC-07, AC-14; FR-15, FR-16, FR-24 |
| BG-05, BG-08 | JTBD-07 / UJ-05 | BF-08 | AIC-02, AIC-03, AIC-04, AIC-05 cung cấp **tín hiệu chất lượng** để theo dõi; không ra quyết định nghiệp vụ | C-06, C-10, C-11 | Không cần AI tool cho tổng hợp báo cáo; T-UTL-05 chỉ phục vụ quy tắc tính điểm/độ phủ đã duyệt | INT-06 | LM-06 | AC-10, AC-11; FR-24–FR-26 |
| BG-01, BG-06, BG-07 | JTBD-09 / UJ-01, UJ-04 | BF-02, BF-07 | AIC-01, AIC-03 | C-03, C-07, C-08, C-09 | T-GEN-01, T-CRM-02, T-REC-01 | INT-01, INT-02, INT-05 | LM-02, LM-04, LM-05 | AC-01, AC-14; FR-02–FR-04, FR-16 |
| BG-02, BG-08 | JTBD-08 / UJ-06 | BF-03, BF-08 | **Không có AI ra quyết định về quyền, retention hoặc xóa.** Mọi AIC chịu các chính sách dữ liệu và phạm vi truy cập tương ứng. | C-02, C-04, C-06, C-11 | T-KNO-01, T-UTL-06; thao tác retention/xóa không được cung cấp cho AI | INT-01, INT-06 | LM-01, LM-05, LM-06 | AC-08–AC-10, AC-12; FR-17, FR-19–FR-24 |

### Mã Acceptance Criteria

| Mã | Điều kiện kiểm chứng |
|---|---|
| **AC-01** | Tiêu chí AI tạo từ JD phải là bản nháp; chỉ được sử dụng cho đánh giá chính thức sau khi HR và Hiring Manager hoàn tất phê duyệt theo trách nhiệm đã xác định. |
| **AC-02** | MVP xử lý PDF/DOCX tiếng Anh; batch tối đa 50 file, tổng tối đa 250 MB và mỗi file nhỏ hơn 10 MB. |
| **AC-03** | File bị khóa, không đọc được hoặc quá mờ phải hiện “Cần HR kiểm tra”; không tự động loại ứng viên hoặc gán điểm 0. |
| **AC-04** | Nhận định theo tiêu chí có bằng chứng truy về CV; thiếu bằng chứng hoặc confidence thấp được phân biệt với “Chưa đáp ứng”. |
| **AC-05** | Ranking chỉ trong cùng vị trí; hiển thị riêng điểm matching và độ phủ bằng chứng; không dùng điểm để tự quyết định tuyển/loại. |
| **AC-06** | Hồ sơ giống hệt/có khả năng trùng chỉ tạo cảnh báo trong cùng vị trí; không tự gộp, ghi đè hoặc xóa. |
| **AC-07** | AI không tự cập nhật trạng thái tuyển dụng, không tự loại, shortlist hoặc gửi quyết định tuyển dụng. |
| **AC-08** | Người dùng chỉ xem dữ liệu thuộc vai trò và vị trí được cấp quyền; Viewer không xem CV/PII. |
| **AC-09** | Hồ sơ đến hạn được đưa vào danh sách chờ; HR được cấp quyền xác nhận xóa; phạm vi xóa theo hồ sơ ứng tuyển. Điều kiện này phụ thuộc Legal/Privacy phê duyệt chính sách. |
| **AC-10** | Có thể truy vết các sự kiện nghiệp vụ quan trọng, bao gồm duyệt tiêu chí, đổi trạng thái, điều chỉnh đánh giá AI, thay đổi quyền và xác nhận xóa. |
| **AC-11** | Pilot thu thập được baseline và số liệu chất lượng quy trình/AI; chưa cam kết KPI giảm thời gian cố định khi chưa có baseline. |
| **AC-12** | Dữ liệu AI chỉ được xử lý theo model và phạm vi dữ liệu đã được phê duyệt; không mặc định cho phép nhà cung cấp bên ngoài dùng CV để huấn luyện. |
| **AC-13** | Giao diện hỗ trợ tiếng Việt/Anh, mặc định tiếng Việt; CV và JD của MVP bằng tiếng Anh. |
| **AC-14** | Hiring Manager chỉ xem shortlist được chia sẻ của vị trí phụ trách; HR vẫn sở hữu trạng thái và quyết định sàng lọc. |

---

# Artifact 1 — Solution Overview

## 1.1 Tóm tắt giải pháp

Giải pháp là một sản phẩm hỗ trợ sàng lọc tuyển dụng, kết nối các miền nghiệp vụ sau:

1. Quản lý vị trí, JD, tiêu chí và trạng thái phê duyệt.
2. Tiếp nhận CV theo vị trí, nhận diện lỗi và hỗ trợ xử lý nội dung.
3. Đối chiếu tiêu chí với bằng chứng trong CV và đề xuất thứ tự rà soát.
4. Cung cấp thông tin cho HR/Hiring Manager để họ tự đánh giá, phản hồi và cập nhật trạng thái.
5. Ghi nhận hoạt động, quyền truy cập, số liệu pilot và vòng đời dữ liệu.

AI là năng lực lõi hỗ trợ **đề xuất, trích xuất, đối chiếu, cảnh báo và xếp hạng**. AI không phải chủ thể ra quyết định tuyển dụng. JD, rubric, trạng thái hồ sơ và quyết định của HR được quản lý như dữ liệu nghiệp vụ riêng, không bị thay thế bởi kết quả AI.

## 1.2 Business Architecture

### Các năng lực nghiệp vụ

| Năng lực nghiệp vụ | Người sở hữu nghiệp vụ chính | Mục tiêu |
|---|---|---|
| Quản lý nhu cầu tuyển dụng, vị trí và JD | HR và phòng ban tuyển dụng | Xác định phạm vi và yêu cầu của từng vị trí |
| Quản trị tiêu chí và rubric | HR; Hiring Manager duyệt chuyên môn | Tạo tiêu chí rõ, nhất quán và đã phê duyệt |
| Tiếp nhận và rà soát ứng viên | HR Recruiter | Quản lý CV và ưu tiên hồ sơ cần xem |
| Phối hợp với Hiring Manager | HR và Hiring Manager | Chia sẻ shortlist, nhận xét và phản hồi |
| Quản lý trạng thái tuyển dụng | HR Recruiter | Ghi nhận quyết định do con người đưa ra |
| Theo dõi hiệu quả và chất lượng | HR Lead/HR Product Owner | Đo tiến độ, baseline và chất lượng trong pilot |
| Quản trị dữ liệu và quyền | HR, Legal/Privacy, IT/Security | Kiểm soát quyền truy cập, retention và audit |

### Ranh giới quyết định nghiệp vụ

- HR và Hiring Manager sở hữu quyết định về yêu cầu vị trí và tiêu chí.
- AI tạo đánh giá **mang tính khuyến nghị**, không phải nguồn dữ liệu chuẩn về ứng viên.
- HR là chủ sở hữu trạng thái hồ sơ và quyết định vòng sàng lọc.
- Legal/Privacy sở hữu việc xác nhận chính sách retention và điều kiện sử dụng dữ liệu.
- IT/Security xác nhận chính sách truy cập, xác thực và môi trường xử lý được phép.

## 1.3 Solution Architecture — nguyên tắc

1. **Theo mục tiêu sản phẩm:** thành phần kiến trúc phục vụ một hoặc nhiều BG/JTBD; không mở rộng chức năng không được chứng minh là cần thiết.
2. **Tách dữ liệu nghiệp vụ khỏi đánh giá AI:** trạng thái tuyển dụng do HR cập nhật; kết quả AI được lưu/hiển thị như đánh giá tư vấn có phiên bản và nguồn gốc.
3. **Human-in-the-loop:** tiêu chí phải được duyệt; trường hợp thiếu bằng chứng hoặc chưa chắc chắn được chuyển HR; quyết định tuyển dụng thuộc HR.
4. **Bằng chứng trước điểm số:** mọi nhận định quan trọng phải truy ngược được về CV; điểm và độ phủ được thể hiện riêng.
5. **Phân lập theo vị trí:** context và ranking bị giới hạn trong cùng vị trí; không suy diễn hoặc trộn dữ liệu từ ứng viên/vị trí khác.
6. **Quyền tối thiểu và bảo vệ dữ liệu:** chỉ dùng thông tin liên quan đến công việc; quyền theo vai trò và vị trí.
7. **Ranh giới thành phần rõ:** miền sở hữu JD/tiêu chí, hồ sơ ứng tuyển, bằng chứng, kết quả AI và audit không chồng lấn trách nhiệm.
8. **Độc lập công nghệ:** kiến trúc mô tả năng lực logic, không ràng buộc nhà cung cấp, stack hoặc topology cụ thể.

## 1.4 Mục tiêu kiến trúc

| Mã | Mục tiêu kiến trúc | Business Goal |
|---|---|---|
| **AG-01** | Giảm công sức tìm thông tin và đọc CV bằng cách trình bày nội dung có cấu trúc, có bằng chứng. | BG-03, BG-04 |
| **AG-02** | Đưa JD và rubric đã duyệt thành ngữ cảnh thống nhất cho mọi đánh giá trong một vị trí. | BG-01, BG-06 |
| **AG-03** | Đảm bảo HR kiểm tra được lý do, bằng chứng, độ phủ và trạng thái chưa rõ. | BG-04, BG-07 |
| **AG-04** | Giữ trạng thái hồ sơ và quyết định tuyển dụng thuộc quyền của HR. | BG-07, BG-08 |
| **AG-05** | Bảo vệ CV, hạn chế quyền truy cập và áp dụng retention theo chính sách đã phê duyệt. | BG-02, BG-08 |
| **AG-06** | Thu thập số liệu đủ tin cậy để đánh giá pilot và quyết định mở rộng. | BG-05 |

## 1.5 Biên giải pháp

### Trong MVP

- Quản lý vị trí, JD và phiên bản tiêu chí.
- Upload CV trực tiếp theo vị trí; PDF/DOCX tiếng Anh.
- OCR chỉ cho PDF scan.
- Tạo bản nháp tiêu chí từ JD và yêu cầu phê duyệt trước khi dùng.
- Đánh giá theo tiêu chí, bằng chứng, trạng thái chưa rõ và ranking trong cùng vị trí.
- Cảnh báo file lỗi và CV có dấu hiệu trùng để HR xác minh.
- HR cập nhật trạng thái hồ sơ; Hiring Manager xem shortlist được chia sẻ.
- Dashboard cơ bản cho số liệu pilot.
- Phân quyền, audit và quy trình retention dự kiến.

### Ngoài MVP

- Crawl CV trực tuyến.
- Tích hợp ATS/HRIS, job board, email tự động hoặc lịch phỏng vấn.
- Talent Pool và tái sử dụng CV giữa nhiều vị trí.
- Ranking giữa các vị trí.
- AI tự động loại, shortlist, đổi trạng thái hoặc gửi kết quả cho ứng viên.
- SSO, chatbot ứng viên, video screening, dự báo xác suất nhận offer.
- OCR ảnh CV rời; matching CV không phải tiếng Anh.

### Quyết định thiết kế chính

- Tách ba loại trạng thái: xử lý file, nhóm matching và trạng thái ứng tuyển.
- Kết quả AI gắn với phiên bản JD/rubric và CV cụ thể.
- Ưu tiên xử lý trong môi trường được VinUni phê duyệt; dịch vụ ngoài chỉ phục vụ kiểm thử khi được phép.
- Không tích hợp hệ thống tuyển dụng bên ngoài trước khi xác nhận hệ thống hiện hành, nguồn dữ liệu chuẩn và nhu cầu nghiệp vụ.

---

# Artifact 2 — Domain Model

## 2.1 Business Domains

| Miền nghiệp vụ | Phạm vi | Chủ sở hữu nghiệp vụ |
|---|---|---|
| **Hiring Position & Criteria** | Vị trí, JD, tiêu chí, trọng số, rubric và phê duyệt | HR; Hiring Manager sở hữu nội dung chuyên môn |
| **Candidate Intake** | Ứng viên, hồ sơ ứng tuyển, tài liệu CV và trạng thái xử lý file | HR |
| **Assessment & Evidence** | Nội dung trích xuất, bằng chứng theo tiêu chí, nhận định và ranking AI | HR sở hữu cách diễn giải; AI chỉ tạo khuyến nghị |
| **Application Lifecycle** | Trạng thái sàng lọc và kết quả tuyển dụng | HR |
| **Review & Collaboration** | Shortlist, chia sẻ, ghi chú và phản hồi của Hiring Manager | HR và Hiring Manager theo quyền được cấp |
| **Access & Governance** | Người dùng, vai trò, phạm vi vị trí, chính sách, retention và audit | HR, Legal/Privacy, IT/Security |
| **Recruiting Measurement** | Số liệu tiến độ, pilot, chất lượng trích xuất và matching | HR Lead/HR Product Owner |

## 2.2 Domain Objects và quan hệ

### Vị trí và tiêu chí

- **Position/Requisition:** một vị trí tuyển dụng; là phạm vi của ranking và phân quyền.
- **Job Description Version:** một phiên bản JD gắn với vị trí.
- **Criteria Set Version:** bộ tiêu chí gắn với phiên bản JD hoặc lần đánh giá được phê duyệt.
- **Criterion:** tiêu chí Bắt buộc hoặc Ưu tiên, có mức đánh giá và trọng số theo rubric được duyệt.
- **Criteria Approval:** ghi nhận HR và Hiring Manager đã phê duyệt phần thuộc trách nhiệm của mình.

**Quan hệ:** một vị trí có thể có nhiều phiên bản JD và rubric; mỗi lần đánh giá phải tham chiếu chính xác phiên bản đã sử dụng. Bản AI đề xuất chưa phê duyệt không được xem là tiêu chí chính thức.

### Ứng viên và hồ sơ

- **Candidate/Applicant:** danh tính ứng viên trong phạm vi nghiệp vụ tuyển dụng.
- **Application:** hồ sơ ứng tuyển của ứng viên cho một vị trí cụ thể.
- **CV Document:** tài liệu được nộp trong một hồ sơ ứng tuyển.
- **File Processing Status:** trạng thái tiếp nhận/xử lý tài liệu.
- **Application Recruitment Status:** trạng thái do người dùng có quyền cập nhật.

**Quan hệ:** một vị trí có nhiều hồ sơ ứng tuyển; một hồ sơ thuộc một vị trí và có thể có một hoặc nhiều tài liệu liên quan. Việc liên kết cùng một ứng viên giữa nhiều vị trí không tạo quyền xem hoặc matching xuyên vị trí. Phát hiện trùng trong MVP chỉ giới hạn cùng một vị trí.

> Việc liên kết danh tính giữa nhiều hồ sơ và xử lý dữ liệu dùng chung khi xóa một hồ sơ cần Legal/Privacy xác nhận.

### Bằng chứng và đánh giá

- **Extracted Profile:** thông tin nghề nghiệp được trích xuất từ một tài liệu.
- **Evidence Item:** trích đoạn hoặc vị trí nội dung trong CV hỗ trợ một nhận định.
- **Assessment Run:** lần đánh giá được gắn với hồ sơ, CV, JD, rubric và chính sách model cụ thể.
- **Criterion Finding:** kết quả theo từng tiêu chí: Đáp ứng tốt / Đáp ứng / Chưa rõ / Chưa đáp ứng, kèm bằng chứng và mức độ chưa chắc chắn.
- **Matching Group:** Đáp ứng tiêu chí bắt buộc / Cần HR xác minh / Có dấu hiệu miss-match / Chưa đánh giá.
- **Match Score và Evidence Coverage:** hai chỉ số riêng biệt; chỉ được tính theo quy tắc đã được phê duyệt.
- **Ranking Snapshot:** thứ tự hỗ trợ ưu tiên rà soát trong một vị trí tại một thời điểm.
- **Semantic Chunk Embedding:** vector phái sinh của một chunk CV, gắn với document/chunk/text hash và embedding model/index version; chỉ dùng để tìm candidate chunks cho bước đối chiếu, không phải bằng chứng độc lập.
- **LTR Model Version:** artifact xếp hạng train offline từ dữ liệu đã gán nhãn, có holdout metrics, trạng thái phê duyệt và version riêng; không phải quyết định tuyển dụng.
- **Duplicate Alert:** cảnh báo hồ sơ giống hệt hoặc có khả năng cùng ứng viên, không phải quyết định gộp/xóa.

**Quan hệ:** mỗi Assessment Run chỉ được dùng một phiên bản rubric và một tập tài liệu xác định. Kết quả cũ phải nhận diện được là dựa trên phiên bản nào; khi JD hoặc rubric thay đổi, kết quả liên quan cần được xem là không còn hiện hành cho đến khi được đánh giá lại.

### Quyết định và phối hợp

- **Application Decision/Status:** trạng thái do HR cập nhật, gồm Mới, Đang xem, Shortlist, Bị loại ở vòng sàng lọc, Đang phỏng vấn, Không trúng tuyển sau phỏng vấn, Trúng tuyển và Đã nhận việc.
- **Shortlist Share:** phạm vi hồ sơ được HR chia sẻ cho Hiring Manager.
- **HR Note:** ghi chú nghiệp vụ của HR; mặc định không chia sẻ cho Hiring Manager.
- **Hiring Manager Feedback:** nhận xét từ Hiring Manager theo quyền của vị trí.
- **Audit Event:** sự kiện ghi lại hành động nghiệp vụ quan trọng.

### Retention và đo lường

- **Retention Schedule:** thời hạn nghiệp vụ dự kiến gắn với vị trí/hồ sơ.
- **Deletion Confirmation:** xác nhận của HR được cấp quyền trước khi xóa.
- **Metric Definition / Measurement:** định nghĩa và số liệu phục vụ pilot hoặc báo cáo.
- **Quality Signal:** số liệu về lỗi trích xuất, mức độ HR điều chỉnh, độ phủ bằng chứng và chất lượng matching.

## 2.3 Nguyên tắc về nguồn dữ liệu chuẩn

| Nội dung | Nguồn chuẩn trong phạm vi sản phẩm |
|---|---|
| JD và trạng thái vị trí | Miền Position & Criteria |
| Tiêu chí/rubric được dùng | Phiên bản đã được HR/Hiring Manager duyệt |
| Trạng thái xử lý file | Miền Candidate Intake |
| Trạng thái tuyển dụng | Miền Application Lifecycle; chỉ do người dùng có quyền cập nhật |
| Điểm, bằng chứng, nhóm matching, ranking | Kết quả tư vấn AI; không thay thế quyết định của HR |
| Quyền và retention | Chính sách được VinUni phê duyệt; điều kiện retention hiện còn chờ Legal/Privacy |

---

# Artifact 3 — Component Architecture

## 3.1 Logical Components

| ID / Component | Mục đích và trách nhiệm | Đầu vào | Đầu ra | Phụ thuộc chính | Chủ sở hữu | Hỗ trợ AI Capability |
|---|---|---|---|---|---|---|
| **C-01 Experience & Review Workspace** | Cung cấp trải nghiệm theo vai trò: danh sách, chi tiết, CV gốc, bằng chứng, shortlist, dashboard. | Yêu cầu người dùng, kết quả nghiệp vụ, kết quả tư vấn. | Màn hình và thao tác được phân quyền. | C-02 đến C-10 theo chức năng. | HR Product Owner. | Trình bày AIC-01–06 để HR kiểm tra; không ra quyết định. |
| **C-02 Identity & Position Authorization** | Xác thực và xác định quyền theo vai trò và vị trí. | Danh tính người dùng, role, phạm vi vị trí. | Quyết định cho phép/từ chối xem hoặc thực hiện tác vụ. | Chính sách truy cập của VinUni; C-01. | IT/Security và HR. | Giới hạn context và dữ liệu được AIC-01–06 tiếp cận. Đây là thành phần kiểm soát, không phải năng lực AI. |
| **C-03 Position & Criteria Governance** | Quản lý vị trí, JD, phiên bản tiêu chí, trọng số, rubric và phê duyệt. | Nhu cầu tuyển dụng, JD, đề xuất tiêu chí, phản hồi HR/HM. | JD/rubric đã duyệt; bản nháp được đánh dấu rõ; phiên bản và phê duyệt. | C-02, C-01. | HR; Hiring Manager sở hữu phê duyệt chuyên môn. | Cung cấp ngữ cảnh chuẩn cho AIC-01, AIC-03, AIC-04. |
| **C-04 Application Lifecycle** | Quản lý hồ sơ ứng tuyển, phân công và trạng thái tuyển dụng do người dùng cập nhật. | Hồ sơ, người phụ trách, quyết định của HR. | Trạng thái ứng tuyển chuẩn và lịch sử thay đổi. | C-02, C-03, C-09, C-11. | HR Recruiter. | Gắn kết quả AIC-03/04 với hồ sơ nhưng chặn AI sửa trạng thái. |
| **C-05 CV Intake & Document Processing** | Tiếp nhận file, kiểm tra định dạng/chất lượng và trích xuất văn bản theo định dạng được hỗ trợ. | PDF/DOCX upload và metadata vị trí. | Trạng thái file, văn bản trích xuất, cảnh báo cần kiểm tra. | C-02, C-03, C-06, C-07. | HR vận hành; IT/Security quản lý điều kiện xử lý. | Hỗ trợ AIC-02, AIC-05 và dữ liệu cho AIC-06. |
| **C-06 Evidence & AI Assessment Records** | Quản lý nội dung trích xuất, bằng chứng, kết quả đánh giá tư vấn và provenance. | Văn bản CV, nhận định, phiên bản rubric/model/policy. | Bằng chứng, bản đánh giá, điểm/độ phủ và tham chiếu nguồn. | C-03, C-04, C-05, C-07, C-08, C-11. | HR sở hữu ý nghĩa nghiệp vụ; sản phẩm quản lý hồ sơ đánh giá. | Lưu trữ kết quả của AIC-02–06 để HR kiểm chứng. |
| **C-07 AI Orchestration & Model Governance** | Điều phối các tác vụ AI có giới hạn; áp chính sách context, tool allowlist, model được duyệt và ranh giới dữ liệu. | Yêu cầu được ủy quyền, rubric, tài liệu, policy. | Kế hoạch tác vụ giới hạn, kết quả có nguồn gốc hoặc lỗi/ngoại lệ. | C-02, C-03, C-05, C-06, C-08, C-11. | HR Product Owner về tác vụ; IT/Security về model và dữ liệu. | Điều phối toàn bộ AIC-01–06. |
| **C-08 Matching & Ranking** | Đối chiếu theo tiêu chí, tạo nhóm matching, ranking trong cùng vị trí, tính tín hiệu chưa chắc chắn và cảnh báo trùng. Có thể dùng semantic retrieval để bổ sung candidate chunks cho LLM fallback và LTR đã phê duyệt để reorder có gate. | CV/evidence, rubric đã duyệt, quy tắc điểm đã duyệt, embedding model/index version, artifact LTR đã phê duyệt nếu bật. | Nhận định theo tiêu chí, bằng chứng, score, coverage, ranking, `ltr_score` nếu có và cảnh báo. | C-03, C-04, C-06, C-07, C-11. | HR sở hữu cách sử dụng; HR/HM duyệt rubric. | Thực hiện AIC-03–06. |
| **C-09 Human Review & Collaboration** | Quản lý review của HR, chia sẻ shortlist, ghi chú và phản hồi Hiring Manager. | Hồ sơ được phép xem, kết quả AI, quyền chia sẻ. | Ý kiến và phản hồi có cấu trúc; chỉ thị cập nhật trạng thái do HR thực hiện. | C-02, C-04, C-06, C-08. | HR và Hiring Manager theo quyền. | Cho phép người dùng kiểm tra và phản hồi AIC-03/04/05; không tự quyết định. |
| **C-10 Reporting & Quality Measurement** | Tổng hợp tiến độ, baseline pilot và tín hiệu chất lượng AI/quy trình. | Sự kiện vị trí, hồ sơ, trạng thái, kết quả đánh giá và thời gian. | Dashboard và số liệu tổng hợp. | C-03, C-04, C-06, C-09, C-11. | HR Lead/HR Product Owner. | Theo dõi chất lượng AIC-02–05; không dùng dữ liệu để mặc định xếp hạng hiệu suất cá nhân. |
| **C-11 Privacy, Retention & Audit Governance** | Áp dụng giới hạn dữ liệu, ghi nhận sự kiện, quản lý danh sách hồ sơ đến hạn và xác nhận xóa theo chính sách được duyệt. | Chính sách, sự kiện nghiệp vụ, ngày đóng vị trí, xác nhận của HR. | Audit, danh sách chờ xử lý, trạng thái retention/xóa. | C-02, C-04, C-05, C-06, C-07, C-10. | Legal/Privacy xác nhận chính sách; HR thực hiện xác nhận; IT/Security giám sát. | Đặt guardrail và truy vết cho AIC-01–06; không tự ra quyết định quyền hoặc xóa dữ liệu. |

## 3.2 Component Diagram — mô tả logic

```text
HR Recruiter / Hiring Manager / HR Lead / Admin / Viewer
                            |
               C-01 Experience & Review Workspace
                  |                         |
        C-02 Identity & Scope       C-10 Reporting
                  |
       +----------+----------------------------+
       |                 |                     |
 C-03 Position &   C-04 Application      C-09 Human Review
 Criteria           Lifecycle             & Collaboration
       |                 |                     |
       +-----------+-----+---------------------+
                   |
          C-05 CV Intake & Processing
                   |
           C-06 Evidence & Assessment Records
                   |
        C-07 AI Orchestration & Model Governance
                   |
      +------------+-------------------+
      |                                |
C-05 Document capabilities     C-08 Matching & Ranking
      |                                |
      +----------- advisory results ---+
                   |
          C-06 AI Assessment Records

C-11 Privacy, Retention & Audit Governance: kiểm soát xuyên suốt.
C-10 Reporting: đọc dữ liệu nghiệp vụ và kết quả đánh giá ở mức được phép.
```

**Ranh giới trách nhiệm quan trọng:**

- C-03 là nguồn chuẩn của JD và tiêu chí đã duyệt.
- C-04 là nguồn chuẩn của trạng thái tuyển dụng.
- C-05 là nguồn chuẩn của trạng thái xử lý file.
- C-06 quản lý kết quả AI và bằng chứng như dữ liệu tư vấn.
- C-08 đánh giá; C-07 điều phối; hai thành phần này không sở hữu quyết định tuyển dụng.
- C-09 ghi nhận phối hợp và feedback, không thay thế chức năng trạng thái của C-04.
- C-11 đặt ràng buộc, ghi nhận và điều phối vòng đời dữ liệu; không cấp quyền HR cho AI tự xóa hồ sơ.

## 3.3 Logical Modules

| Module | Thành phần tập hợp | Mục tiêu |
|---|---|---|
| **LM-01 Experience & Access** | C-01, C-02 | Giao diện theo vai trò và kiểm soát phạm vi truy cập |
| **LM-02 Position & Criteria** | C-03 | JD, rubric, phê duyệt và phiên bản |
| **LM-03 CV Intake & Evidence** | C-05, C-06 | Tiếp nhận file, trích xuất và quản lý bằng chứng |
| **LM-04 AI Assessment** | C-07, C-08 | Điều phối tác vụ và tạo kết quả matching/ranking |
| **LM-05 Application & Review** | C-04, C-09 | Trạng thái do con người cập nhật và phối hợp HR/HM |
| **LM-06 Governance & Measurement** | C-10, C-11 | Đo lường, audit, retention và chính sách dữ liệu |

---

# Artifact 4 — Business Sequence

> Phần này mô tả riêng hoạt động nghiệp vụ. Quyết định tuyển dụng vẫn thuộc người dùng có trách nhiệm.

| Mục đích nghiệp vụ | Hoạt động | Quyết định nghiệp vụ | Kết quả |
|---|---|---|---|
| **BF-01 — Xác nhận nhu cầu tuyển dụng** | Phòng ban gửi nhu cầu; HR làm rõ vị trí, phạm vi và yêu cầu. | HR và Hiring Manager thống nhất nhu cầu tuyển dụng có đầy đủ cơ sở hay cần làm rõ thêm. | Nhu cầu và vị trí dự kiến được xác định. |
| **BF-02 — Hoàn thiện JD và tiêu chí** | HR và Hiring Manager rà soát JD, thống nhất tiêu chí bắt buộc/ưu tiên và rubric. | Hiring Manager xác nhận yêu cầu chuyên môn; HR xác nhận tiêu chí rõ, nhất quán và phù hợp quy trình. | Bộ tiêu chí được duyệt để sử dụng cho vị trí. |
| **BF-03 — Mở vị trí và phân công** | HR mở vị trí, phân công recruiter và xác định Hiring Manager/người tham gia. | HR xác định ai được xem hồ sơ và ai được xem shortlist. | Vị trí sẵn sàng nhận hồ sơ trong phạm vi được giao. |
| **BF-04 — Tiếp nhận và kiểm tra hồ sơ** | HR tiếp nhận CV theo vị trí; kiểm tra file lỗi, khó đọc hoặc có cảnh báo trùng. | HR quyết định hồ sơ nào có thể tiếp tục rà soát và hồ sơ nào cần xác minh thủ công. | Hồ sơ được quản lý đúng vị trí; ngoại lệ có người phụ trách. |
| **BF-05 — Rà soát và ưu tiên hồ sơ** | HR xem thông tin, bằng chứng theo tiêu chí và thứ tự ưu tiên trong vị trí. | HR đánh giá hồ sơ, xác minh phần chưa rõ và quyết định hồ sơ nào cần xem xét tiếp. | HR có căn cứ để ưu tiên rà soát, không mặc định loại hồ sơ. |
| **BF-06 — Cập nhật kết quả sàng lọc** | HR ghi nhận trạng thái ứng tuyển sau khi đã rà soát. | HR quyết định shortlist, loại ở vòng sàng lọc hoặc chuyển sang trạng thái nghiệp vụ phù hợp. | Trạng thái ứng tuyển phản ánh quyết định của HR. |
| **BF-07 — Phối hợp với Hiring Manager** | HR chia sẻ shortlist theo vị trí; Hiring Manager xem xét và gửi phản hồi. | HR quyết định phạm vi chia sẻ; Hiring Manager cung cấp nhận xét theo trách nhiệm của mình. | Các bên thống nhất hồ sơ cần xem xét tiếp. |
| **BF-08 — Theo dõi, đóng vị trí và xử lý hồ sơ đến hạn** | HR Lead theo dõi tiến độ; HR đóng vị trí và xử lý danh sách hồ sơ đến hạn theo chính sách. | HR được cấp quyền xác nhận xóa sau khi chính sách được phê duyệt; nếu vị trí mở lại, thời hạn được tính theo quyết định nghiệp vụ đã xác định. | Tiến độ được theo dõi; vòng đời hồ sơ được xử lý có kiểm soát. |

---

# Artifact 5 — Business → AI Mapping & AI Sequence

## Part A — Business Step Mapping

| Business Step | AI Capability | Mục tiêu AI | Kết quả mong đợi |
|---|---|---|---|
| **BF-01 — Xác nhận nhu cầu** | Không yêu cầu AIC. | Không tự xác định nhu cầu kinh doanh. | Nhu cầu vẫn do phòng ban, HR và Hiring Manager xác nhận. |
| **BF-02 — Hoàn thiện JD và tiêu chí** | AIC-01 | Đề xuất bản nháp tiêu chí từ JD đã cung cấp. | HR/Hiring Manager có bản nháp để xem xét; không tự phê duyệt. |
| **BF-03 — Mở vị trí và phân công** | AIC-01 chỉ sử dụng sau khi tiêu chí được duyệt. | Bảo đảm đánh giá dùng đúng phiên bản JD/rubric. | Không có đánh giá chính thức dựa trên tiêu chí chưa duyệt. |
| **BF-04 — Tiếp nhận và kiểm tra hồ sơ** | AIC-02, AIC-05, AIC-06 | Trích xuất nội dung nghề nghiệp, nhận diện dữ liệu chưa chắc chắn và cảnh báo hồ sơ có thể trùng trong cùng vị trí. | Thông tin CV được cấu trúc; ngoại lệ chuyển HR; cảnh báo trùng không tự gộp/xóa. |
| **BF-05 — Rà soát và ưu tiên hồ sơ** | AIC-02, AIC-03, AIC-04, AIC-05, AIC-06 | So khớp tiêu chí với bằng chứng; hỗ trợ thứ tự rà soát; thể hiện dữ liệu thiếu và cảnh báo. | HR có nhận định có thể kiểm tra, điểm và độ phủ riêng, không có quyết định tuyển/loại tự động. |
| **BF-06 — Cập nhật kết quả sàng lọc** | Không có AI cập nhật trạng thái. | Không thay người có thẩm quyền quyết định. | HR tự cập nhật trạng thái ứng tuyển. |
| **BF-07 — Phối hợp với Hiring Manager** | AIC-03, AIC-04 cung cấp bằng chứng/kết quả để HR chia sẻ; không thay thế feedback của Hiring Manager. | Hỗ trợ xem lại hồ sơ và hiểu căn cứ đánh giá. | Hiring Manager phản hồi trên shortlist được phép xem. |
| **BF-08 — Theo dõi và xử lý hồ sơ đến hạn** | AIC-02–05 chỉ cung cấp tín hiệu chất lượng tổng hợp khi cần; không quyết định retention hoặc xóa. | Hỗ trợ đánh giá pilot và chất lượng sản phẩm. | Báo cáo có số liệu; HR/Legal/Privacy giữ quyền quyết định về retention và xóa. |

## Part B — AI Sequence

### 1. Goal — Mục tiêu tác vụ

Xác định tác vụ AI cụ thể trong quy trình, chẳng hạn đề xuất tiêu chí từ JD, trích xuất thông tin CV, đối chiếu tiêu chí, xếp hạng trong vị trí hoặc cảnh báo hồ sơ cần xác minh.

Tác vụ phải gắn với vị trí và người dùng được phân quyền; không nhận yêu cầu mở để tự quyết định ứng viên.

### 2. Intent — Diễn giải mục đích

Phân loại yêu cầu thành một trong các tác vụ được phép:

- Tạo **bản nháp** tiêu chí.
- Trích xuất nội dung từ CV.
- Đánh giá CV theo rubric đã được duyệt.
- Tính điểm/độ phủ và xếp hạng trong cùng vị trí.
- Phát hiện thiếu dữ liệu, file lỗi hoặc dấu hiệu trùng.

Tác vụ không hợp lệ hoặc đòi hỏi hành động tuyển dụng phải được từ chối hoặc chuyển người dùng xử lý.

### 3. Planning — Lập kế hoạch giới hạn

Lập chuỗi bước hữu hạn theo tác vụ đã chọn. Ví dụ đánh giá CV:

1. Kiểm tra hồ sơ và tài liệu thuộc đúng vị trí.
2. Xác định định dạng và khả năng đọc file.
3. Trích xuất nội dung được hỗ trợ.
4. Tải tiêu chí đã duyệt.
5. Đối chiếu từng tiêu chí với bằng chứng.
6. Tính chỉ số theo quy tắc đã được phê duyệt.
7. Kiểm tra trường hợp chưa rõ, lỗi hoặc dấu hiệu trùng.
8. Trả kết quả tư vấn cho HR.

Đây là quy trình có giới hạn; không phải cơ chế tự đề ra mục tiêu mới hoặc tự triển khai hành động tuyển dụng.

### 4. Context Loading — Nạp ngữ cảnh

Chỉ nạp dữ liệu tối thiểu cần cho tác vụ:

- Vai trò người dùng và phạm vi vị trí được phép.
- JD và phiên bản rubric đã duyệt.
- CV/tài liệu thuộc hồ sơ đang đánh giá.
- Các quy tắc được phê duyệt về matching, điểm số, độ phủ và thông tin không được sử dụng.
- Định dạng/ngôn ngữ tài liệu và trạng thái xử lý file.

Không trộn CV, nhận xét hoặc tiêu chí giữa các ứng viên/vị trí. Nội dung CV/JD được xem là **dữ liệu đầu vào không tin cậy**, không phải chỉ thị cho công cụ.

### 5. Reasoning — Đánh giá theo tiêu chí

- Đối chiếu từng tiêu chí dựa trên nội dung CV có thể kiểm chứng.
- Không suy luận thông tin không có trong CV.
- Không đồng nhất “không tìm thấy bằng chứng” với “Chưa đáp ứng”.
- Giữ riêng kết quả từng tiêu chí, điểm tổng hợp, độ phủ và mức chưa chắc chắn.
- Không dùng tuổi, giới tính, ngoại hình/ảnh, tình trạng hôn nhân, tính cách hoặc “culture fit” để đánh giá.
- Không yêu cầu hiển thị reasoning nội bộ ẩn của model; người dùng cần phần giải thích ngắn gọn, bằng chứng và tham chiếu CV.

### 6. Tool Selection — Chọn công cụ

Chọn tool từ danh sách cho phép theo đúng tác vụ. Việc gọi tool bị giới hạn bởi:

- Phân quyền của người dùng và phạm vi vị trí.
- Dữ liệu được phép dùng cho tác vụ.
- Mục đích đọc/trích xuất/đánh giá đã xác định.
- Hạn chế hành động ghi dữ liệu: chỉ được ghi **bản đánh giá AI tư vấn**; không được thay đổi trạng thái tuyển dụng, xóa hồ sơ hoặc gửi quyết định ứng viên.

### 7. Execution — Thực hiện tác vụ

- PDF có văn bản được trích xuất trực tiếp.
- PDF scan sử dụng năng lực OCR PDF scan.
- DOCX được trích xuất văn bản thông thường; không yêu cầu OCR.
- CV được cấu trúc và đối chiếu với rubric đã duyệt.
- Nếu dữ liệu không đủ hoặc file lỗi, chuyển trạng thái thích hợp để HR xác minh thay vì gán kết luận bất lợi.

### 8. Observation — Kiểm tra kết quả

Trước khi đưa kết quả cho người dùng, kiểm tra ở mức nghiệp vụ rằng:

- Có tham chiếu đến tài liệu và phiên bản rubric đã dùng.
- Bằng chứng không trỏ tới hồ sơ/vị trí khác.
- “Chưa rõ”, lỗi đọc và độ phủ thấp được phản ánh đúng.
- Kết quả không tạo trạng thái tuyển dụng hoặc hành động ngoài phạm vi.
- Không dùng thuộc tính bị cấm làm căn cứ đánh giá.
- Trường hợp bất thường được chuyển thành cảnh báo cho HR.

### 9. Response — Trả kết quả

Trả kết quả tư vấn trong ngữ cảnh ứng viên và vị trí tương ứng, gồm:

- Kết quả từng tiêu chí và bằng chứng.
- Điểm matching và độ phủ bằng chứng riêng biệt, nếu quy tắc tính điểm đã được duyệt.
- Nhóm matching, cảnh báo chưa rõ hoặc file cần kiểm tra.
- Ranking chỉ trong cùng vị trí, kèm giải thích và giới hạn sử dụng.
- Tùy chọn HR kiểm tra CV gốc và tự cập nhật trạng thái ứng tuyển.

---

# Artifact 6 — Tool Map

Các tool dưới đây là **năng lực logic** trong kiến trúc. Đây không phải hợp đồng tích hợp hoặc danh sách hàm/API. Mọi tool được gọi trong phạm vi của một tác vụ, một người dùng và một vị trí được phép.

## 6.1 CRM Tools

| Tool | Mục đích; đầu vào → đầu ra | Business Capability / AIC / BG | Source System | Consumers / giới hạn |
|---|---|---|---|---|
| **T-CRM-01 — Position & JD Reader** | Đọc mã vị trí → JD, trạng thái vị trí, đơn vị và phạm vi vị trí. | Quản lý vị trí; AIC-01, AIC-03, AIC-04; BG-01, BG-06, BG-07. | C-03 | C-07; chỉ đọc vị trí người dùng/tác vụ được phép. |
| **T-CRM-02 — Approved Criteria Reader** | Đọc vị trí và phiên bản → tiêu chí, rubric, trọng số, trạng thái/người phê duyệt. | Quản trị tiêu chí; AIC-01, AIC-03, AIC-04; BG-01, BG-06, BG-07. | C-03 | C-07, C-08; chỉ đọc tiêu chí đã duyệt cho đánh giá chính thức. |
| **T-CRM-03 — Application & Document Reference Reader** | Đọc mã hồ sơ → tài liệu liên quan và trạng thái xử lý tối thiểu cần cho tác vụ. | Tiếp nhận/đánh giá hồ sơ; AIC-02, AIC-05, AIC-06; BG-02, BG-03, BG-08. | C-04, C-05 | C-07; không trả thông tin không cần thiết như liên hệ nếu tác vụ không yêu cầu. |
| **T-CRM-04 — AI Assessment Draft Writer** | Nhận kết quả tư vấn và provenance → lưu bản đánh giá AI gắn với phiên bản đầu vào. | Lưu kết quả tư vấn; AIC-02–06; BG-03, BG-04, BG-07. | C-06 | C-07, C-08; chỉ ghi bản đánh giá tư vấn. **Không** ghi trạng thái ứng tuyển, xóa hồ sơ hoặc gửi thông báo. |

## 6.2 Knowledge Tools

| Tool | Mục đích; đầu vào → đầu ra | Business Capability / AIC / BG | Source System | Consumers / giới hạn |
|---|---|---|---|---|
| **T-KNO-01 — Approved Hiring Policy Reader** | Đọc tác vụ/vị trí → định nghĩa rubric, nguyên tắc dữ liệu, tiêu chí được phép/không được phép và các chính sách đã duyệt. | Dùng tri thức được duyệt; AIC-01, AIC-03, AIC-05; BG-01, BG-02, BG-06, BG-07. | C-03, C-11 và tài liệu chính sách được phê duyệt | C-07; không dùng thư viện template nghề ở MVP. Template là khả năng Phase 2, chưa phải dữ liệu chuẩn hiện tại. |

## 6.3 Generation Tools

| Tool | Mục đích; đầu vào → đầu ra | Business Capability / AIC / BG | Source System | Consumers / giới hạn |
|---|---|---|---|---|
| **T-GEN-01 — JD Criteria Draft Generator** | JD → bản nháp tiêu chí và cảnh báo mơ hồ/thiếu thông tin nếu có căn cứ. | Chuẩn hóa yêu cầu; AIC-01; BG-01, BG-06, BG-07. | C-03 | C-07, C-03; đầu ra phải mang nhãn chưa duyệt. |
| **T-GEN-02 — CV Structure Extractor** | Văn bản CV đã trích xuất → thông tin nghề nghiệp có cấu trúc. | Trích xuất CV; AIC-02; BG-03, BG-04. | C-05 | C-07, C-06; không dùng thông tin cá nhân không liên quan để đánh giá. |

## 6.4 Recommendation Tools

| Tool | Mục đích; đầu vào → đầu ra | Business Capability / AIC / BG | Source System | Consumers / giới hạn |
|---|---|---|---|---|
| **T-REC-01 — Criterion Evidence Matcher** | Rubric đã duyệt + bằng chứng CV → nhận định theo từng tiêu chí. | Matching theo rubric; AIC-03; BG-01, BG-04, BG-07. | C-03, C-06 | C-07, C-08, C-09; thiếu bằng chứng không đồng nghĩa chưa đáp ứng. |
| **T-REC-02 — Same-Position Ranker** | Nhận định đã có + quy tắc điểm đã duyệt + hồ sơ trong cùng vị trí → ranking có giải thích. | Ưu tiên rà soát; AIC-04; BG-03, BG-04, BG-07. | C-06, C-08 | C-07, C-09; không ranking xuyên vị trí, không có ngưỡng tự loại. |
| **T-REC-03 — Uncertainty & Exception Classifier** | Trạng thái file, độ phủ, bằng chứng và confidence → cảnh báo/nhóm cần HR xác minh. | Xử lý ngoại lệ; AIC-05; BG-02, BG-04, BG-07, BG-08. | C-05, C-06 | C-07, C-08, C-09; không gán trạng thái tuyển dụng. |
| **T-REC-04 — Same-Position Duplicate Signal** | Các tài liệu/hồ sơ thuộc cùng vị trí → tín hiệu giống hệt hoặc có khả năng cùng ứng viên. | Nhận diện trùng; AIC-06; BG-03, BG-08. | C-04, C-05 | C-07, C-08, C-09; chỉ cảnh báo, không gộp/xóa. |

## 6.5 Utility Tools

| Tool | Mục đích; đầu vào → đầu ra | Business Capability / AIC / BG | Source System | Consumers / giới hạn |
|---|---|---|---|---|
| **T-UTL-01 — File Type & Readability Check** | File → định dạng hỗ trợ, khóa, lỗi hoặc cảnh báo chất lượng đọc. | Kiểm tra file; hỗ trợ AIC-02/AIC-05; BG-03, BG-08. | C-05 | C-05, C-07; file lỗi được chuyển “Cần HR kiểm tra”. |
| **T-UTL-02 — Text Extractor** | PDF có văn bản hoặc DOCX → văn bản được trích xuất. | Trích xuất tài liệu; hỗ trợ AIC-02; BG-03. | C-05 | C-05, C-07; không bao gồm OCR DOCX. |
| **T-UTL-03 — Scanned PDF OCR** | PDF scan → văn bản và cảnh báo chất lượng OCR. | Đọc PDF scan; hỗ trợ AIC-02/AIC-05; BG-03, BG-08. | C-05 | C-05, C-07; MVP chỉ yêu cầu OCR cho PDF scan. |
| **T-UTL-04 — Evidence Locator & Reference Validator** | Nhận định/bằng chứng → xác nhận tham chiếu trỏ tới nội dung của CV đúng hồ sơ. | Kiểm chứng bằng chứng; hỗ trợ AIC-03/AIC-05; BG-01, BG-04, BG-07. | C-06 | C-07, C-08; tham chiếu không hợp lệ dẫn tới cần HR xác minh. |
| **T-UTL-05 — Approved Score & Coverage Calculator** | Kết quả tiêu chí và rubric đã duyệt → điểm/độ phủ theo quy tắc được phê duyệt. | Tính chỉ số ranking; hỗ trợ AIC-04; BG-03, BG-04, BG-07. | C-03, C-06 | C-08; không tự đặt rubric hoặc ngưỡng tuyển dụng. |
| **T-UTL-06 — AI Policy & Output Guard** | Context/kết quả đề xuất → kiểm tra phạm vi dữ liệu, output không đúng chính sách và thuộc tính bị cấm. | Kiểm soát AI; hỗ trợ mọi AIC theo chính sách; BG-02, BG-07, BG-08. | C-11, T-KNO-01 | C-07, C-08; không thay thế phân quyền tại C-02 hoặc phê duyệt của HR. |

---

# Artifact 7 — Context Design

## 7.1 Các loại context

| Context | Mục đích | Lifetime | Owner | Source | Storage | Consumers | Thiết kế kiểm soát |
|---|---|---|---|---|---|---|---|
| **Conversation Context** | Nắm yêu cầu hiện tại của người dùng trong phiên làm việc. | Trong phiên hoặc đến khi tác vụ hiện tại hoàn thành. | Người dùng đang đăng nhập; C-01 quản lý trải nghiệm. | Yêu cầu người dùng và lựa chọn trên giao diện. | Ngữ cảnh phiên; không lưu thành bộ nhớ AI dài hạn mặc định. | C-01, C-07. | Không dùng để suy ra sở thích tuyển dụng cá nhân; không trộn thông tin nhiều ứng viên. |
| **Business Context** | Xác định vị trí, hồ sơ, vai trò và phiên bản tiêu chí cho tác vụ. | Theo từng yêu cầu hoặc lần đánh giá. | HR sở hữu dữ liệu nghiệp vụ; C-02 kiểm soát phạm vi. | C-02, C-03, C-04. | Context làm việc có giới hạn; nguồn chuẩn vẫn ở miền nghiệp vụ. | C-07, C-08, C-09. | Luôn có vị trí và mã hồ sơ; chỉ nạp phạm vi người dùng được phép. |
| **Working Context** | Hỗ trợ xử lý CV/JD, bằng chứng và kết quả tạm thời trong một tác vụ. | Một lần xử lý; chỉ giữ phần cần thiết cho bản đánh giá đã được lưu theo chính sách. | HR là chủ thể dữ liệu; C-07 chịu trách nhiệm điều phối. | C-05, C-06, C-03. | Ngữ cảnh tạm thời; các kết quả lưu lâu dài được chuyển thành record có mục đích và provenance. | C-07, C-08, T-… | Không chia sẻ giữa các ứng viên/vị trí; nội dung tài liệu không được hiểu là lệnh gọi tool. |
| **Knowledge Context** | Cung cấp định nghĩa và chính sách đã duyệt về rubric, bảo mật và dữ liệu. | Tồn tại theo phiên bản chính sách; thay đổi cần có người sở hữu và ngày hiệu lực. | HR, Legal/Privacy, IT/Security theo loại chính sách. | C-03, C-11 và tài liệu được duyệt. | Kho tri thức logic có phiên bản; thư viện template nghề chưa nằm trong MVP. | C-07, C-08. | Chỉ sử dụng nguồn đã duyệt; không thay thế rubric riêng của vị trí bằng template chưa phê duyệt. |
| **CRM/Business Context** | Đại diện trạng thái hiện hành của vị trí, hồ sơ, tài liệu và quyết định trong sản phẩm. | Theo vòng đời hồ sơ nghiệp vụ và chính sách retention. | HR; hệ thống nghiệp vụ là nguồn chuẩn trong phạm vi sản phẩm. | C-03, C-04, C-05, C-09. | Các miền hồ sơ nghiệp vụ; CRM/ATS ngoài VinUni chưa được xác nhận. | C-01, C-07, C-08, C-10. | Kết quả AI không ghi đè JD, rubric hoặc trạng thái tuyển dụng. |
| **Persistent Context** | Lưu những dữ liệu có mục đích nghiệp vụ đã được duyệt: CV, tiêu chí, kết quả đánh giá, trạng thái và audit. | Theo từng loại dữ liệu và chính sách được duyệt. | Chủ sở hữu theo miền: HR, Legal/Privacy, IT/Security. | C-03–C-11. | Nhóm dữ liệu logic riêng theo chủ đích và retention; không quy định công nghệ lưu trữ. | Người dùng có quyền, báo cáo, audit và quy trình retention. | Áp retention, phân quyền và deletion scope riêng; không dùng mặc định để huấn luyện model. |
| **Derived Retrieval Context** | Vector embedding của chunk CV và điểm tương đồng semantic dùng để tìm thêm candidate chunks. | Theo vòng đời document/application và embedding index version. | C-06/C-08; IT/Security kiểm soát endpoint/model. | CV text đã redaction, requirement spec đã duyệt. | Kho vector trong cùng PostgreSQL (pgvector) ở bản hiện thực; không lưu thêm raw CV text. | C-08, LLM fallback. | Similarity không phải evidence score; chunk được chọn vẫn phải qua quote verification. Không tìm kiếm xuyên vị trí/ứng viên. |

## 7.2 Đường đi của context

```text
Yêu cầu người dùng
    ↓
Xác định người dùng, vai trò và phạm vi vị trí
    ↓
Tải Business Context: vị trí/hồ sơ/JD/rubric đã duyệt
    ↓
Tải Knowledge Context: chính sách, giới hạn và quy tắc được duyệt
    ↓
Tạo Working Context cho đúng một tác vụ và một phạm vi dữ liệu
    ↓
Thực hiện các tác vụ được phép; kiểm tra bằng chứng và chính sách
    ↓
Lưu kết quả AI dưới dạng tư vấn có nguồn gốc và phiên bản
    ↓
Hiển thị cho HR/Hiring Manager theo quyền
    ↓
Chỉ người có quyền cập nhật quyết định/status nghiệp vụ
```

### Quy tắc context

- Không có bộ nhớ AI dùng chung giữa ứng viên hoặc giữa vị trí.
- Không đưa ảnh, tuổi, giới tính, tình trạng hôn nhân hoặc thuộc tính không liên quan vào context đánh giá.
- JD và CV là dữ liệu đầu vào; không thực thi chỉ dẫn nằm bên trong nội dung tài liệu.
- Mỗi kết quả phải tham chiếu phiên bản JD/rubric và tài liệu đã dùng.
- Đánh giá cũ được phân biệt với đánh giá theo rubric mới.
- Lưu dữ liệu lâu dài tuân theo chính sách retention được phê duyệt; hiện tại thời hạn 12 tháng là quyết định nghiệp vụ dự kiến và cần Legal/Privacy xác nhận.

---

# Artifact 8 — Integration & Data Flow

## Part A — Integration Flow

### Luồng tổng thể

```text
Frontend
   ↓
Backend / miền nghiệp vụ
   ↓
AI orchestration và các năng lực xử lý được phép
   ↓
Dịch vụ/model trong phạm vi được VinUni phê duyệt
   ↓
Backend kiểm tra, ghi nhận kết quả tư vấn và audit
   ↓
Frontend trả kết quả cho HR/Hiring Manager
```

### Diễn giải

1. **Frontend:** người dùng đăng nhập, chọn vị trí/hồ sơ và yêu cầu thao tác theo vai trò. UI hiển thị rõ các trạng thái file, matching, đánh giá và tuyển dụng.
2. **Backend/miền nghiệp vụ:** kiểm tra quyền theo vai trò/vị trí; cung cấp JD, rubric, CV và dữ liệu cần thiết cho tác vụ. Vị trí, tiêu chí đã duyệt và trạng thái ứng tuyển giữ nguồn chuẩn riêng.
3. **AI:** C-07 chọn tác vụ có giới hạn, nạp context tối thiểu và gọi các tool được phép. C-08 tạo nhận định, bằng chứng, ranking hoặc cảnh báo.
4. **External systems:**
   - Ưu tiên xử lý bằng năng lực/model trong phạm vi môi trường được VinUni phê duyệt.
   - API model bên ngoài chỉ dùng để kiểm thử giai đoạn đầu khi có phê duyệt phù hợp.
   - Khi kiểm thử, ưu tiên dữ liệu tổng hợp hoặc đã khử định danh; nếu gọi dịch vụ ngoài phải có biện pháp mask PII theo chính sách. Mask không được xem là bảo đảm ẩn danh tuyệt đối.
   - Không có kết nối job board, ATS/HRIS, lịch, email tự động hoặc dịch vụ ứng viên trong MVP.
5. **Response:** hệ thống kiểm tra kết quả, lưu đánh giá tư vấn có liên kết đến nguồn và phiên bản, rồi hiển thị cho người dùng. HR tự quyết định có xác minh, shortlist, loại hoặc cập nhật trạng thái hay không.

### Mã Integration

| Mã | Luồng logic | Phạm vi |
|---|---|---|
| **INT-01** | Frontend ↔ các miền vị trí, tiêu chí, hồ sơ và quyền | Nội bộ sản phẩm |
| **INT-02** | JD/rubric đã duyệt → AI context | Chỉ dữ liệu của vị trí và phiên bản được phép |
| **INT-03** | CV upload → kiểm tra/trích xuất → evidence | Luồng tiếp nhận tài liệu |
| **INT-04** | AI orchestration ↔ tool allowlist/năng lực AI được duyệt | Tác vụ giới hạn; không tự thay đổi trạng thái |
| **INT-05** | Kết quả AI tư vấn → hồ sơ đánh giá → màn hình review | Kết quả tách khỏi trạng thái ứng tuyển |
| **INT-06** | Sự kiện nghiệp vụ/AI → audit, retention và báo cáo | Chỉ người có quyền được xem dữ liệu tương ứng |
| **INT-07** | Môi trường kiểm thử → dịch vụ model ngoài được duyệt | Kiểm thử giới hạn; dữ liệu/PII phải tuân thủ chính sách |

## Part B — Data Flow

| Data Producer | Data Transformation | AI Processing | Consumer | Quyền sở hữu và xử lý |
|---|---|---|---|---|
| HR/Hiring Manager tạo hoặc cập nhật JD | Tạo phiên bản JD, rà soát nội dung | AIC-01 có thể tạo bản nháp tiêu chí | HR/Hiring Manager | JD do đơn vị tuyển dụng sở hữu; chỉ phiên bản tiêu chí đã duyệt mới là input chính thức. |
| HR upload CV | Kiểm tra định dạng, trạng thái đọc; trích xuất PDF/DOCX/OCR PDF scan | AIC-02 cấu trúc thông tin nghề nghiệp | HR Recruiter | CV vẫn là dữ liệu ứng viên; file lỗi/không rõ được chuyển kiểm tra thủ công. |
| C-05 tạo văn bản/bằng chứng | Liên kết nội dung với CV và hồ sơ ứng tuyển cụ thể | AIC-03 đối chiếu từng tiêu chí; AIC-05 nhận diện chưa rõ | HR Recruiter, Hiring Manager nếu được chia sẻ | Bằng chứng là dữ liệu dẫn xuất, không thay thế CV gốc. |
| AIC-03/AIC-04 tạo kết quả | Gắn kết quả với CV, rubric, JD và policy version | Tính score/coverage/ranking theo quy tắc đã duyệt | HR Recruiter | Kết quả là khuyến nghị; HR là người quyết định cách sử dụng. |
| HR cập nhật quyết định | Ghi nhận trạng thái và người thực hiện | Không có AI cập nhật trạng thái | HR, Hiring Manager theo quyền | Trạng thái ứng tuyển thuộc miền nghiệp vụ, không lấy kết quả AI làm nguồn chuẩn. |
| Sự kiện quy trình và đánh giá | Tổng hợp ở mức được phép, loại bỏ dữ liệu không cần cho báo cáo | Không yêu cầu suy luận tuyển dụng để tạo dashboard cơ bản | HR Lead/HR Product Owner | Chỉ dùng báo cáo theo mục đích đã duyệt; không mặc định xếp hạng hiệu suất cá nhân. |
| HR đóng vị trí; chính sách xác định đến hạn | Tạo danh sách hồ sơ cần xem xét xóa | Không có AI quyết định retention hoặc xóa | HR được cấp quyền, Legal/Privacy theo trách nhiệm | Xóa theo hồ sơ ứng tuyển sau khi có xác nhận; chính sách chờ phê duyệt pháp lý. |

### Quyền sở hữu

- HR sở hữu quy trình tuyển dụng, định nghĩa trạng thái và ý nghĩa vận hành của kết quả.
- Hiring Manager sở hữu đánh giá yêu cầu chuyên môn trong phạm vi vị trí phụ trách.
- Legal/Privacy xác nhận mục đích sử dụng, retention và quy định dữ liệu.
- IT/Security xác nhận tiêu chuẩn bảo mật và phạm vi dịch vụ xử lý.
- AI assessment là dữ liệu do sản phẩm tạo ra; không phải sự thật xác nhận về ứng viên.
- Vai trò pháp lý chính thức của VinUni trong xử lý dữ liệu cần Legal/Privacy xác nhận; tài liệu này không suy diễn từ yêu cầu nghiệp vụ.

### Trust boundary

1. **Ranh giới người dùng:** danh tính và quyền quyết định ai được xem vị trí/hồ sơ.
2. **Ranh giới nghiệp vụ:** JD, rubric, trạng thái ứng tuyển và ý kiến của người dùng là dữ liệu chuẩn theo từng miền.
3. **Ranh giới xử lý CV/AI:** CV là dữ liệu không tin cậy; kết quả phải được kiểm tra và truy xuất về nguồn.
4. **Ranh giới nhà cung cấp ngoài:** không gửi CV production ra ngoài khi chưa phê duyệt; điều kiện dùng dữ liệu và model phải được xác định rõ.
5. **Ranh giới báo cáo:** số liệu tổng hợp không mặc định làm lộ CV hoặc PII.

### Đồng bộ và thay đổi dữ liệu

- MVP chưa đồng bộ hai chiều với ATS/HRIS hoặc job board.
- JD và rubric được quản lý theo phiên bản; mỗi đánh giá tham chiếu đúng phiên bản.
- Khi rubric thay đổi, kết quả cũ phải được nhận diện là dựa trên bản trước; không trộn ranking giữa hai phiên bản mà không có cảnh báo.
- HR là nguồn chuẩn cho mọi thay đổi trạng thái ứng tuyển.
- Một vị trí mở lại trước khi hồ sơ bị xóa sẽ khởi động lại thời hạn từ lần đóng kế tiếp, theo quyết định nghiệp vụ hiện tại.
- Xóa theo hồ sơ ứng tuyển; dữ liệu liên kết giữa nhiều hồ sơ của cùng ứng viên cần được xử lý theo chính sách được Legal/Privacy duyệt.

---

# Artifact 9 — Deployment View

> Đây là **mô tả ranh giới runtime logic**, không xác định hosting, topology, công nghệ, cấu hình triển khai hoặc nhà cung cấp.

## 9.1 Các vùng logic

### A. User Access Zone

- Người dùng: HR Recruiter, Hiring Manager, HR Lead, Admin, Viewer.
- Kênh: giao diện sản phẩm trong phạm vi truy cập được VinUni phê duyệt.
- Xác thực MVP: email và mật khẩu nội bộ.
- SSO chưa thuộc phạm vi MVP.

### B. VinUni-Approved Product Boundary

Bao gồm các năng lực logic:

- Trải nghiệm người dùng.
- Xác thực/phân quyền theo vai trò và vị trí.
- Vị trí, JD, criteria, ứng dụng và trạng thái tuyển dụng.
- Intake CV và xử lý định dạng.
- Review, phối hợp và báo cáo.
- Audit/retention theo chính sách.

### C. AI & Document Processing Boundary

Bao gồm các năng lực logic:

- Điều phối tác vụ AI có giới hạn.
- Đọc nội dung tài liệu và OCR PDF scan.
- Trích xuất, matching, ranking, phát hiện bất định và cảnh báo trùng.
- Quản lý model/policy được phép và provenance của kết quả.

Ưu tiên đặt xử lý trong phạm vi môi trường được VinUni phê duyệt. Việc model “cục bộ” cụ thể được đặt ở đâu chưa được xác định bởi tài liệu nghiệp vụ.

### D. External Provider Boundary

- Dịch vụ model/API bên ngoài chỉ được xem xét cho kiểm thử giai đoạn đầu.
- Cần được phê duyệt về bảo mật, quyền riêng tư, mục đích và điều kiện dữ liệu.
- Ưu tiên dữ liệu tổng hợp hoặc đã khử định danh; nếu sử dụng dữ liệu cần che PII, không xem việc che PII là bảo đảm ẩn danh.
- Không cho phép nhà cung cấp dùng CV để huấn luyện nếu chưa được phê duyệt.

### E. Future External Integrations

Ngoài MVP và chưa được xác nhận là có trong môi trường VinUni:

- ATS/HRIS.
- Nền tảng đăng tuyển hoặc nguồn CV bên ngoài.
- Email/calendar cho đặt lịch và gửi thông báo.
- Cổng ứng viên hoặc chatbot.

Việc mở rộng phụ thuộc discovery hệ thống hiện hữu, thỏa thuận, quyền truy cập và xác định nguồn dữ liệu chuẩn.

## 9.2 Nhóm dữ liệu lưu trữ logic

| Nhóm dữ liệu | Mục đích | Quyền truy cập |
|---|---|---|
| **Vị trí, JD và rubric** | Quản lý yêu cầu và bản tiêu chí đã duyệt. | Theo vai trò và vị trí. |
| **CV gốc và trạng thái file** | Rà soát hồ sơ và xử lý ngoại lệ. | Chỉ người được cấp quyền xem hồ sơ. |
| **Văn bản trích xuất và bằng chứng** | Hỗ trợ kiểm tra nhận định theo tiêu chí. | Chỉ người được cấp quyền; quản lý theo chính sách retention. |
| **Kết quả AI tư vấn** | Lưu điểm, độ phủ, bằng chứng, nhóm matching và version provenance. | HR; Hiring Manager theo shortlist được chia sẻ. |
| **Embedding và artifact LTR** | Lưu vector chunk phái sinh và model xếp hạng offline để truy vết retrieval/ranking. | Backend/worker và người vận hành được ủy quyền; không expose cho browser. |
| **Trạng thái ứng tuyển** | Ghi nhận quyết định do HR cập nhật. | HR có quyền cập nhật; các bên khác theo quyền xem. |
| **Audit** | Truy vết phê duyệt, quyền, trạng thái, điều chỉnh và xóa. | Người dùng có trách nhiệm giám sát. |
| **Số liệu tổng hợp** | Đo baseline và hiệu quả pilot. | HR Lead/HR Product Owner theo quyền. |
| **Chính sách và cấu hình được duyệt** | Kiểm soát rubric, model và giới hạn sử dụng dữ liệu. | Người được ủy quyền; Admin không mặc định xem CV. |

## 9.3 Hành vi khi năng lực xử lý không khả dụng

- Nếu một file không thể đọc, hiển thị trạng thái cần HR kiểm tra; không tạo kết luận không đáp ứng.
- Nếu tác vụ AI không hoàn thành, không hiển thị kết quả như thể đã được đánh giá.
- Nếu AI hoặc dịch vụ xử lý không khả dụng, trạng thái tuyển dụng hiện tại không bị thay đổi.
- HR vẫn có thể kiểm tra CV gốc và tiếp tục quy trình theo chính sách nghiệp vụ.

---

# Artifact 10 — Architecture Decision Records

## ADR-01 — AI là năng lực hỗ trợ; HR giữ quyền quyết định

- **Context:** Sản phẩm cần giảm công sức rà soát nhưng không thay HR trong tuyển dụng.
- **Problem:** Nếu ranking hoặc matching có thể tự đổi trạng thái, kết quả AI có thể trở thành quyết định tuyển/loại ngầm.
- **Options:** Cho AI cập nhật trạng thái; cho AI gợi ý nhưng HR xác nhận; chỉ dùng AI để trích xuất, không đưa gợi ý.
- **Decision:** AI được đề xuất, matching, cảnh báo và ranking; HR tự xác minh và cập nhật trạng thái.
- **Reason:** Phù hợp BG-07, JTBD-03/04/06 và FR-15.
- **Trade-offs:** Cần HR tham gia xử lý ngoại lệ và phê duyệt; đổi lại quyết định có người chịu trách nhiệm.  
  **Traceability:** BG-07, BG-08; JTBD-03, JTBD-04, JTBD-06; AC-07.

## ADR-02 — Tách ba miền trạng thái

- **Context:** File có thể lỗi dù hồ sơ vẫn hợp lệ; matching có thể chưa rõ mà không có quyết định loại.
- **Problem:** Dùng một trạng thái chung dễ làm người dùng nhầm tình trạng file, kết quả matching và kết quả tuyển dụng.
- **Options:** Một trạng thái chung; hai trạng thái; ba nhóm trạng thái riêng.
- **Decision:** Tách trạng thái xử lý file, nhóm matching và trạng thái ứng tuyển.
- **Reason:** Tránh đồng nhất lỗi đọc hoặc thiếu bằng chứng với quyết định không đạt; phù hợp BG-01/BG-08.
- **Trade-offs:** UI và báo cáo phải trình bày nhiều chiều trạng thái hơn.  
  **Traceability:** BG-01, BG-08; JTBD-02, JTBD-05, JTBD-06; AC-03, AC-04, AC-07.

## ADR-03 — Matching phải có bằng chứng; thiếu thông tin không phải “Chưa đáp ứng”

- **Context:** Bằng chứng trong CV có thể không được tìm thấy hoặc tài liệu có thể không đọc được.
- **Problem:** Chấm điểm 0 cho nội dung chưa rõ có thể gây đánh giá sai.
- **Options:** Coi thiếu thông tin là không đáp ứng; loại khỏi điểm nhưng không cảnh báo; chuyển HR xác minh và thể hiện độ phủ riêng.
- **Decision:** Hiển thị bằng chứng, trạng thái chưa rõ, điểm matching và độ phủ riêng; không kết luận bất lợi chỉ vì thiếu bằng chứng.
- **Reason:** Bảo vệ khả năng giải thích và giảm nguy cơ bỏ sót ứng viên.
- **Trade-offs:** Có thể có thêm hồ sơ HR phải kiểm tra; ranking có thể báo chưa ổn định.  
  **Traceability:** BG-01, BG-04, BG-07; JTBD-03, JTBD-05; AC-04, AC-05.

## ADR-04 — Ranking giới hạn trong cùng một vị trí

- **Context:** Các vị trí có JD và rubric khác nhau.
- **Problem:** Điểm hoặc thứ hạng giữa vị trí khác nhau có thể không có ý nghĩa so sánh.
- **Options:** Ranking toàn bộ ứng viên; ranking theo nhóm nghề; ranking trong một vị trí.
- **Decision:** Chỉ xếp hạng hồ sơ trong cùng một vị trí, dựa trên rubric đã duyệt.
- **Reason:** Phù hợp mục tiêu hỗ trợ HR ưu tiên rà soát, không tạo điểm so sánh không hợp lệ.
- **Trade-offs:** Không thể dùng một ranking toàn trường để chọn ứng viên từ nhiều nhóm nghề.  
  **Traceability:** BG-03, BG-04, BG-07; JTBD-04; AC-05.

## ADR-05 — Tách dữ liệu chuẩn nghiệp vụ khỏi kết quả AI

- **Context:** Sản phẩm cần lưu kết quả AI để HR rà soát nhưng không được xem kết quả đó là trạng thái chuẩn.
- **Problem:** Ghi đè trạng thái hoặc criteria bằng kết quả AI làm mất quyền kiểm soát và khả năng truy vết.
- **Options:** Ghi trực tiếp kết quả AI vào trạng thái ứng tuyển; lưu riêng assessment và trạng thái do HR cập nhật; chỉ hiển thị kết quả tạm thời.
- **Decision:** Lưu đánh giá AI tách khỏi trạng thái ứng tuyển; HR là nguồn chuẩn của trạng thái.
- **Reason:** Tách rõ trách nhiệm và hỗ trợ audit/versioning.
- **Trade-offs:** Cần hiển thị hai loại thông tin liên quan trên giao diện mà không làm người dùng nhầm lẫn.  
  **Traceability:** BG-07, BG-08; JTBD-06; AC-07, AC-10.

## ADR-06 — Context và tool bị giới hạn theo vai trò, vị trí và hồ sơ

- **Context:** CV chứa dữ liệu cá nhân; người dùng chỉ được xem một số vị trí/hồ sơ.
- **Problem:** Context quá rộng làm tăng nguy cơ truy cập hoặc sử dụng dữ liệu không cần thiết.
- **Options:** Context dùng chung; context theo phiên làm việc; context riêng theo vị trí và hồ sơ.
- **Decision:** Mỗi tác vụ AI phải có context tối thiểu, kiểm tra quyền trước khi nạp dữ liệu, giới hạn trong hồ sơ/vị trí được phép.
- **Reason:** Hỗ trợ nguyên tắc quyền tối thiểu và giảm trộn dữ liệu.
- **Trade-offs:** Tác vụ không thể tự tận dụng dữ liệu ngoài phạm vi hiện tại; đúng với giới hạn MVP.  
  **Traceability:** BG-02, BG-08; JTBD-02, JTBD-08; AC-08, AC-12.

## ADR-07 — Ưu tiên xử lý model trong phạm vi được VinUni phê duyệt

- **Context:** Người dùng ưu tiên model cục bộ; API ngoài chỉ dùng giai đoạn đầu để kiểm thử.
- **Problem:** Gửi CV tới bên ngoài khi chưa phê duyệt có thể tạo rủi ro dữ liệu và điều kiện sử dụng.
- **Options:** Dùng dịch vụ ngoài mặc định; chỉ dùng xử lý nội bộ; ưu tiên nội bộ và giới hạn dịch vụ ngoài cho test được duyệt.
- **Decision:** Ưu tiên xử lý/model trong phạm vi được VinUni phê duyệt; external API chỉ dùng test theo chính sách dữ liệu và phê duyệt.
- **Reason:** Phù hợp BG-02 và yêu cầu về dữ liệu.
- **Trade-offs:** Có thể giới hạn lựa chọn model trong pilot; việc “local” cụ thể chưa được xác định.  
  **Traceability:** BG-02, BG-08; JTBD-08; AC-12.

## ADR-08 — Phạm vi tài liệu đúng với khả năng được yêu cầu

- **Context:** MVP xác định PDF văn bản, PDF scan và DOCX có cách xử lý khác nhau.
- **Problem:** Mở rộng OCR ngoài phạm vi dễ làm tăng chất lượng không ổn định và scope.
- **Options:** OCR mọi định dạng; parser/OCR theo định dạng được xác định; chỉ hỗ trợ văn bản số.
- **Decision:** PDF văn bản trích xuất trực tiếp, PDF scan dùng OCR, DOCX trích xuất văn bản thông thường; chưa OCR ảnh CV rời hoặc DOCX.
- **Reason:** Bám sát MVP và làm rõ các trường hợp cần HR kiểm tra.
- **Trade-offs:** Một số CV ảnh rời hoặc nội dung mờ vẫn cần xử lý thủ công.  
  **Traceability:** BG-03, BG-05; JTBD-02, JTBD-05; AC-02, AC-03.

## ADR-09 — Versioning cho JD/rubric và đánh giá

- **Context:** Ranking phụ thuộc nội dung JD, tiêu chí, trọng số và rubric.
- **Problem:** Nếu thay criteria mà không nhận diện kết quả cũ, người dùng có thể so sánh các assessment dựa trên tiêu chí khác nhau.
- **Options:** Chỉ lưu kết quả mới nhất; lưu kết quả kèm phiên bản đầu vào; tự động chấm lại ngay khi criteria đổi.
- **Decision:** Mỗi kết quả phải tham chiếu phiên bản JD/rubric và CV đã dùng. Khi criteria đổi, kết quả cũ được nhận diện rõ; việc đánh giá lại chỉ dựa trên rubric đã duyệt.
- **Reason:** Bảo đảm tính giải thích và truy vết.
- **Trade-offs:** Cần thể hiện phiên bản và trạng thái cũ/mới trong review; cách đánh giá lại cần được HR chốt.  
  **Traceability:** BG-01, BG-06, BG-07; JTBD-01, JTBD-03; AC-01, AC-04, AC-05.

## ADR-10 — Phát hiện trùng là cảnh báo, không phải hợp nhất hồ sơ

- **Context:** Có thể có CV giống hệt hoặc cùng ứng viên trong một vị trí.
- **Problem:** Tự gộp hồ sơ có thể làm mất thông tin hoặc gộp nhầm ứng viên.
- **Options:** Bỏ qua; tự gộp; cảnh báo để HR xử lý.
- **Decision:** Cảnh báo trong cùng vị trí; HR quyết định; không tự gộp, ghi đè hoặc xóa.
- **Reason:** Giảm trùng lặp nhưng giữ quyền kiểm tra của HR.
- **Trade-offs:** HR vẫn phải xác minh cảnh báo; có thể có cảnh báo sai.  
  **Traceability:** BG-03, BG-08; JTBD-02, JTBD-05; AC-06.

## ADR-11 — Retention và xóa theo hồ sơ ứng tuyển, có xác nhận HR

- **Context:** Yêu cầu nghiệp vụ hiện tại là lưu dự kiến 12 tháng từ ngày đóng vị trí, HR xác nhận xóa và xóa theo hồ sơ ứng tuyển.
- **Problem:** Tự động xóa hoặc xóa dữ liệu dùng chung mà chưa rõ phạm vi có thể vi phạm chính sách.
- **Options:** Tự xóa khi hết hạn; HR xác nhận trước khi xóa; giữ đến khi có quyết định pháp lý khác.
- **Decision:** Đưa hồ sơ đến hạn vào danh sách chờ; HR được cấp quyền xác nhận; xóa theo hồ sơ ứng tuyển. Chính sách 12 tháng là **điều kiện chờ Legal/Privacy xác nhận**.
- **Reason:** Bám sát yêu cầu nghiệp vụ hiện tại mà không khẳng định đã xác nhận tuân thủ pháp luật.
- **Trade-offs:** Có thể phát sinh hồ sơ chờ xác nhận; quyền xác nhận và xử lý chậm hạn cần được chốt.  
  **Traceability:** BG-02, BG-08; JTBD-08; AC-09.

## ADR-12 — Phân quyền theo vai trò và vị trí; quyền quản trị không đồng nghĩa quyền xem CV

- **Context:** HR, Hiring Manager, HR Lead, Admin và Viewer có nhu cầu dữ liệu khác nhau.
- **Problem:** Dùng quyền quản trị rộng có thể làm lộ dữ liệu ứng viên không cần thiết.
- **Options:** Quyền chung theo tổ chức; quyền theo vai trò; quyền theo vai trò và vị trí với nguyên tắc tối thiểu.
- **Decision:** Áp dụng phân quyền theo vai trò và vị trí. Admin không mặc định xem CV hoặc xác nhận xóa; Viewer chỉ xem số liệu tổng hợp.
- **Reason:** Phù hợp yêu cầu quyền tối thiểu và sở hữu nghiệp vụ.
- **Trade-offs:** Cần quản lý phân công và quyền theo vị trí nhất quán.  
  **Traceability:** BG-02, BG-08; JTBD-02, JTBD-08; AC-08.

## ADR-13 — Đo baseline và chất lượng trước khi cam kết KPI

- **Context:** Chưa có baseline được xác nhận cho thời gian xử lý và chất lượng matching.
- **Problem:** Cam kết con số tiết kiệm trước khi có số liệu có thể tạo kỳ vọng không có căn cứ.
- **Options:** Đặt KPI giảm thời gian trước pilot; chỉ thu thập số liệu; pilot đo baseline rồi cùng các bên chốt KPI.
- **Decision:** Thu thập baseline, chất lượng OCR/matching và mức HR điều chỉnh trong pilot; chốt KPI sau khi có kết quả.
- **Reason:** Phù hợp BG-05 và yêu cầu không tự đặt mục tiêu giảm thời gian.
- **Trade-offs:** Không thể công bố ROI định lượng trước khi có kết quả pilot.  
  **Traceability:** BG-05; JTBD-07; AC-11.

## ADR-14 — Hoãn tích hợp ngoài phạm vi MVP cho đến khi rõ nguồn chuẩn

- **Context:** CRM/ATS/HRIS và nền tảng đăng tuyển hiện có chưa được xác nhận.
- **Problem:** Đồng bộ với hệ thống chưa biết có thể tạo trùng dữ liệu, xung đột trạng thái hoặc scope không cần thiết.
- **Options:** Tích hợp ngay; thiết kế theo giả định về hệ thống; giữ ranh giới logic và discovery trước khi tích hợp.
- **Decision:** MVP không tích hợp ATS/HRIS/job board/email/calendar; trước Phase sau phải xác định hệ thống, chủ sở hữu dữ liệu và hướng đồng bộ.
- **Reason:** Tránh giả định về hệ thống chưa được kiểm chứng.
- **Trade-offs:** MVP có thể cần HR upload trực tiếp và cập nhật thông tin trong sản phẩm.  
  **Traceability:** BG-03, BG-05, BG-08; JTBD-02, JTBD-06, JTBD-07.

## ADR-15 — Không dùng thuộc tính nhạy cảm hoặc “culture fit” để đánh giá

- **Context:** CV có thể chứa ảnh và thông tin cá nhân không liên quan tới công việc.
- **Problem:** Đưa các thông tin này vào matching có thể tạo đánh giá không phù hợp và thiên lệch.
- **Options:** Cho phép dùng mọi dữ liệu trong CV; dùng dữ liệu có liên quan đến công việc; thêm các chỉ số dựa trên video/tính cách.
- **Decision:** Không dùng tuổi, giới tính, ngoại hình/ảnh, tình trạng hôn nhân, tính cách hoặc “culture fit” làm tiêu chí. Không đưa video screening vào roadmap kiến trúc hiện tại.
- **Reason:** Phù hợp nguyên tắc đánh giá dựa trên công việc và yêu cầu bảo vệ ứng viên.
- **Trade-offs:** Một số ý tưởng phân tích đặc điểm cá nhân bị loại khỏi phạm vi hiện tại.  
  **Traceability:** BG-01, BG-02, BG-07; JTBD-03, JTBD-05; AC-04, AC-12.

## ADR-16 — Tách điều phối AI khỏi đánh giá và khỏi quản lý quy trình

- **Context:** Giải pháp có nhiều loại năng lực AI và nhiều loại dữ liệu nghiệp vụ.
- **Problem:** Một thành phần duy nhất xử lý context, scoring, trạng thái và giao diện sẽ làm trách nhiệm khó kiểm soát.
- **Options:** Một thành phần tổng hợp; tách điều phối, đánh giá, hồ sơ nghiệp vụ và review theo trách nhiệm; tách thành phần theo công nghệ cụ thể.
- **Decision:** Dùng các ranh giới logic C-03 đến C-11; không quy định các ranh giới này là service, process hay đơn vị triển khai.
- **Reason:** Tách rõ nguồn chuẩn, hành động được phép và chủ sở hữu nghiệp vụ trong khi vẫn độc lập công nghệ.
- **Trade-offs:** Có nhiều ranh giới logic cần thống nhất; không khẳng định topology hoặc mức phân tách runtime.  
  **Traceability:** BG-01–BG-08; JTBD-01–JTBD-09; AC-01–AC-14.

## ADR-17 — Semantic retrieval chỉ bổ sung candidate, không quyết định matching

- **Context:** Lexical/rule retrieval có thể bỏ sót diễn đạt paraphrase trong CV.
- **Problem:** Nếu dùng similarity để kết luận đạt/không đạt, hệ thống có thể tạo false match và mất khả năng kiểm chứng.
- **Options:** Chỉ lexical; semantic tự quyết định; semantic bổ sung candidate cho LLM fallback.
- **Decision:** Dùng pgvector/BGE (khi được cấu hình) để bổ sung tối đa 5 candidate chunks cho LLM fallback. Finding vẫn phải có quote được verify; deterministic outcome không bị semantic similarity ghi đè.
- **Reason:** Tăng recall nhưng giữ evidence verification, fingerprint và deterministic gate.
- **Trade-offs:** Cần vận hành embedding endpoint, index version và đo chất lượng trên golden set trước khi bật.
  **Traceability:** BG-01, BG-04, BG-07; JTBD-03, JTBD-05; AC-04, AC-12.

## ADR-18 — LTR train offline, có gate và không vượt mandatory/coverage gate

- **Context:** Sau pilot, dữ liệu quyết định HR có thể hỗ trợ học thứ hạng ưu tiên rà soát.
- **Problem:** LTR train từ weak label hoặc dữ liệu ít có thể khuếch đại thiên lệch quy trình và làm ranking khó giải thích.
- **Options:** Không dùng LTR; LTR thay ranking; LTR shadow/active có gate trong cùng nhóm đủ điều kiện.
- **Decision:** Train LTR offline theo group/position, tách holdout theo group, đăng ký artifact ở `DRAFT`, chỉ `APPROVED` mới được dùng ở `ACTIVE`. `SHADOW` không đổi thứ hạng; `ACTIVE` chỉ reorder trong cùng mandatory status và coverage-eligibility gate.
- **Reason:** Giữ ranking policy hiện tại làm nguồn kiểm soát chính và cho phép đo tác động trước khi ảnh hưởng thứ hạng.
- **Trade-offs:** Cần labelled dataset HR đủ lớn, quy trình phê duyệt artifact và giám sát drift/bias.
  **Traceability:** BG-03, BG-04, BG-05, BG-07; JTBD-04, JTBD-07; AC-05, AC-11, AC-12.

---

# Final Architecture Review

## Kiểm tra chất lượng kiến trúc

### 1. Mỗi Business Goal có ít nhất một JTBD không?

**Có.**

- BG-01 → JTBD-01, JTBD-03, JTBD-06, JTBD-09.
- BG-02 → JTBD-02, JTBD-05, JTBD-08.
- BG-03 → JTBD-02, JTBD-03, JTBD-04.
- BG-04 → JTBD-03, JTBD-04, JTBD-05.
- BG-05 → JTBD-07.
- BG-06 → JTBD-01, JTBD-09.
- BG-07 → JTBD-03, JTBD-04, JTBD-05, JTBD-06, JTBD-09.
- BG-08 → JTBD-02, JTBD-05, JTBD-06, JTBD-07, JTBD-08.

### 2. Mỗi JTBD có được ánh xạ tới User Journey không?

**Có.** JTBD-01 đến JTBD-09 được ánh xạ tới UJ-01–UJ-06 trong bảng JTBD của BRD; quan hệ được sử dụng lại trong Architecture Traceability Matrix.

### 3. Mỗi AI Capability có hỗ trợ ít nhất một JTBD và Business Goal không?

**Có.**

| AI Capability | JTBD hỗ trợ | Business Goal |
|---|---|---|
| AIC-01 — Đề xuất tiêu chí từ JD | JTBD-01, JTBD-09 | BG-01, BG-06, BG-07 |
| AIC-02 — Trích xuất CV | JTBD-02, JTBD-03 | BG-03, BG-04 |
| AIC-03 — Matching có bằng chứng | JTBD-03, JTBD-04, JTBD-06, JTBD-09 | BG-01, BG-04, BG-07 |
| AIC-04 — Ranking trong cùng vị trí | JTBD-04, JTBD-06 | BG-03, BG-04, BG-07 |
| AIC-05 — Nhận diện chưa chắc chắn/ngoại lệ | JTBD-03, JTBD-05 | BG-02, BG-04, BG-07, BG-08 |
| AIC-06 — Cảnh báo CV trùng | JTBD-02, JTBD-05 | BG-03, BG-08 |

### 4. Mỗi Component có hỗ trợ ít nhất một AI Capability không?

**Có**, theo nghĩa thực hiện, điều phối, giới hạn, lưu trữ, kiểm tra hoặc trình bày kết quả AI. Không phải mọi component đều tự thực hiện suy luận:

- **C-01:** trình bày kết quả AIC-01–06 cho người dùng.
- **C-02:** giới hạn dữ liệu và context theo quyền.
- **C-03:** cung cấp JD/rubric chính thức.
- **C-04:** gắn assessment với hồ sơ và chặn thay đổi trạng thái tự động.
- **C-05:** cung cấp tài liệu/văn bản đầu vào và trạng thái lỗi cho AIC-02/AIC-05.
- **C-06:** lưu bằng chứng và kết quả AIC-02–06.
- **C-07:** điều phối AIC-01–06.
- **C-08:** thực hiện AIC-03–06.
- **C-09:** cho phép con người rà soát AIC-03/04/05.
- **C-10:** đo tín hiệu chất lượng liên quan AIC-02–05.
- **C-11:** kiểm soát dữ liệu, audit và retention cho toàn bộ AIC.

C-02 và C-11 là thành phần **hỗ trợ/kiểm soát** AI, không phải thành phần tự tạo đánh giá ứng viên.

### 5. Mỗi Tool có thể truy vết về Business Goal không?

**Có.** Mỗi tool trong Tool Map được ánh xạ đến AI Capability, mục đích nghiệp vụ, miền nguồn và Business Goal. Tool không có quyền tự cập nhật trạng thái tuyển dụng hoặc tự xóa hồ sơ.

### 6. Mỗi Context có owner rõ không?

**Có.** Conversation, Business, Working, Knowledge, CRM/Business và Persistent Context đều có owner, nguồn, thời hạn và giới hạn sử dụng được nêu trong Artifact 7.

### 7. Có trách nhiệm bị trùng lặp không?

Không thấy trùng lặp kiến trúc chủ ý. Các ranh giới chính được giữ riêng:

- C-03 quản lý JD/rubric; C-04 quản lý trạng thái ứng tuyển.
- C-05 tiếp nhận/trích xuất tài liệu; C-06 quản lý bằng chứng và kết quả đánh giá.
- C-07 điều phối tác vụ; C-08 đánh giá và xếp hạng.
- C-09 quản lý phối hợp; C-04 là nguồn chuẩn của trạng thái tuyển dụng.
- C-10 tổng hợp số liệu; C-11 quản lý audit/retention/chính sách dữ liệu.

### 8. Có Component không cần thiết không?

Không có component riêng nào chỉ phục vụ ý tưởng ngoài MVP. C-10 và C-11 cần thiết cho đo lường pilot, quyền truy cập, audit và quản trị dữ liệu. Các tích hợp ATS/HRIS, Talent Pool, booking và chatbot không được đưa thành component MVP.

### 9. MVP có xử lý các pain point lớn nhất không?

**Có, với điều kiện kiểm chứng qua pilot.** Kiến trúc ưu tiên đọc/trích xuất CV, matching theo tiêu chí, bằng chứng, ranking trong cùng vị trí và chuyển ngoại lệ cho HR. Chưa có baseline nên chưa khẳng định mức giảm thời gian hoặc ROI.

## Architecture Risks

1. **Chất lượng OCR/trích xuất biến thiên:** PDF scan mờ hoặc CV không chuẩn có thể làm thiếu/sai bằng chứng.
2. **Sai lệch trong ranking:** AI có thể đánh giá sai tiêu chí hoặc đưa ra thứ tự không phù hợp; cần kiểm thử trên dữ liệu có nhãn HR/HM.
3. **Quá tin vào ranking:** người dùng có thể xem điểm như quyết định, dù kiến trúc chỉ cho phép hỗ trợ rà soát.
4. **Rủi ro dữ liệu với dịch vụ ngoài:** mask PII không đồng nghĩa ẩn danh hoàn toàn; cần kiểm soát phạm vi dữ liệu và điều kiện nhà cung cấp.
5. **Retention chưa được xác nhận pháp lý:** không nên triển khai xử lý production theo thời hạn dự kiến trước khi Legal/Privacy duyệt.
6. **Chưa rõ CRM/ATS/HRIS hiện hữu:** có thể phát sinh trùng lặp hoặc thiếu luồng dữ liệu khi mở rộng.
7. **Thiếu baseline:** khó xác định giá trị vận hành và ngưỡng chất lượng AI phù hợp.
8. **Liên kết danh tính qua nhiều hồ sơ:** chưa rõ cách xóa dữ liệu dùng chung khi xóa theo từng hồ sơ ứng tuyển.
9. **Thay đổi JD/rubric:** nếu không thể hiện rõ phiên bản và độ cũ của kết quả, ranking có thể bị so sánh sai.
10. **Nội dung tài liệu không tin cậy:** CV/JD có thể chứa nội dung không phù hợp; phải xem đó là dữ liệu, không phải chỉ thị cho công cụ.

## Architecture Assumptions

- Phạm vi MVP là tuyển dụng non-faculty với nhóm vị trí IT được xác định.
- Upload trực tiếp là cách tiếp nhận CV của MVP.
- CV và JD trong MVP bằng tiếng Anh; UI hỗ trợ tiếng Việt và tiếng Anh.
- Tiêu chí AI đề xuất chỉ được dùng sau phê duyệt.
- HR là nguồn chuẩn của trạng thái ứng tuyển.
- Ranking chỉ trong một vị trí.
- Model cục bộ được ưu tiên nhưng chưa xác định vị trí/môi trường cụ thể.
- ATS/HRIS, CRM và các dịch vụ tuyển dụng bên ngoài hiện chưa được xác định.
- Không có KPI thời gian hoặc ngưỡng AI nào được xem là đã phê duyệt chỉ từ các đề xuất hiện tại.

## Architecture Constraints

- Không tự động loại, shortlist, cập nhật trạng thái hoặc xóa hồ sơ bằng AI.
- Không dùng tuổi, giới tính, ngoại hình/ảnh, tình trạng hôn nhân, tính cách hoặc “culture fit”.
- Ranking và matching phải có bằng chứng; thiếu bằng chứng không đồng nghĩa không đáp ứng.
- Chỉ PDF scan được yêu cầu OCR trong MVP.
- Batch tối đa 50 file, tổng tối đa 250 MB, mỗi file nhỏ hơn 10 MB.
- Xác thực MVP bằng email/mật khẩu; SSO là phase sau.
- API bên ngoài chỉ dùng kiểm thử giai đoạn đầu theo điều kiện dữ liệu được duyệt.
- Tài liệu này không xác định code, database schema, API, stack hoặc deployment scripts.

## Architecture Improvement Opportunities

1. Xác nhận hệ thống hiện tại, quyền sở hữu dữ liệu và nguồn chuẩn trước khi thiết kế tích hợp tương lai.
2. Thống nhất định nghĩa trạng thái và sự kiện tuyển dụng trước khi xây báo cáo funnel nâng cao.
3. Hoàn tất chính sách retention, quyền xác nhận xóa và phạm vi dữ liệu cần xóa với Legal/Privacy.
4. Chốt rubric, cách quy đổi điểm và ngưỡng độ phủ với HR/Hiring Manager trước pilot.
5. Xây tập CV–JD–rubric được HR gắn nhãn và chốt tiêu chí đánh giá AI trước khi mở rộng người dùng.
6. Kiểm chứng quy trình HR xử lý file lỗi, HR chưa xác nhận xóa và vị trí được mở lại.
7. Chỉ thêm Talent Pool, đồng bộ xuyên hệ thống, booking, đánh giá kỹ năng hoặc báo cáo nâng cao sau khi có nhu cầu được HR xác nhận và đủ phê duyệt dữ liệu.

## Vấn đề còn lại và mâu thuẫn cần khóa

1. **Nguồn tài liệu chưa được phê duyệt:** BRD và Product Definition hiện là draft; kiến trúc này không phải quyết định production.
2. **Retention:** thời hạn 12 tháng từ ngày đóng vị trí, bao gồm hồ sơ chưa có kết quả và không có thời hạn riêng cho hồ sơ trúng tuyển/đã nhận việc, cần Legal/Privacy xác nhận. Tài liệu không xác minh độc lập nội dung “Luật 91/2025”.
3. **Giới hạn file:** tài liệu dùng quy tắc mỗi file **nhỏ hơn 10 MB**; cần xác nhận file đúng 10 MB có bị từ chối không.
4. **Rubric và ranking:** quy đổi điểm, trọng số mặc định 70/30 và ngưỡng độ phủ 70% đang là đề xuất; kiến trúc không hardcode các giá trị chưa được duyệt.
5. **Chất lượng AI:** các ngưỡng đánh giá đề xuất chưa được HR/PO phê duyệt và chưa có tập test chính thức.
6. **Hệ thống hiện tại:** chưa xác nhận CRM/ATS/HRIS và các nguồn CV đang được VinUni sử dụng; do đó chưa thiết kế tích hợp cụ thể.
7. **Dữ liệu ứng viên qua nhiều vị trí:** cần chốt cách quản lý định danh liên kết và phạm vi xóa khi một ứng viên có nhiều hồ sơ.
8. **Mốc phase:** các khoảng thời gian trong đề xuất nâng cấp là định hướng; chưa được xem là cam kết thời gian.

**Kết luận review:** Kiến trúc nhất quán với định hướng sản phẩm: AI hỗ trợ matching/ranking có bằng chứng; HR giữ quyền quyết định; dữ liệu nghiệp vụ và kết quả AI được tách biệt; không giả định CRM hay hệ thống ngoài cụ thể. Các vấn đề retention, rubric, dữ liệu pilot, giới hạn file và hệ thống hiện hành cần được khóa trước khi phê duyệt kiến trúc cuối cùng.