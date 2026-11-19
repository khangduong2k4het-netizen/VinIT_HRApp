# PRODUCT DEVELOPMENT ROADMAP SPECIFICATION
## Dự án: VinUni AI-Native CV Matching & Ranking (HRA)

## 1. Tổng quan Kiến trúc & Lộ trình phát triển (8 Tuần)

Sản phẩm được phát triển theo lộ trình chuẩn hóa **8 tuần liên tục** gồm 4 giai đoạn nối tiếp (mỗi Phase thực hiện trong **2 tuần** tương ứng với 1 Sprint), đảm bảo vừa kiểm chứng thực nghiệm chặt chẽ vừa đẩy nhanh tiến độ đưa vào vận hành thực tế tại VinUni:


* **Phase 1 (Tuần 1 – Tuần 2):** Xác lập nền tảng cốt lõi với nhóm vị trí IT, CV tiếng Anh, tải file trực tiếp, matching 4 mức có dẫn chứng và ranking minh bạch có giải thích.
* **Phase 2 (Tuần 3 – Tuần 4):** Chuẩn hóa thư viện tiêu chí theo nhóm ngành, số hóa quy trình phối hợp HR–HM, giám sát chất lượng OCR/Matching, tự động hóa retention, phát hiện trùng chéo vị trí, OCR ảnh scan và kết nối SSO nội bộ.
* **Phase 3 (Tuần 5 – Tuần 6):** Tích hợp hai chiều với ATS/HRIS của VinUni, tự động tiếp nhận CV từ email/cổng tuyển dụng, xây dựng Talent Pool tái sàng lọc (Candidate Rediscovery) kèm cơ chế Consent độc lập, quản lý lịch phỏng vấn & scorecard, và xử lý đa ngôn ngữ Việt – Anh.
* **Phase 4 (Tuần 7 – Tuần 8):** Phân tích hiệu quả phễu tuyển dụng, kiểm toán chống thiên lệch thuật toán (DEI/Anti-bias), triển khai Cổng ứng viên tự phục vụ (Candidate Portal) và Trợ lý ảo AI hỗ trợ ứng viên 24/7.

> **Cập nhật triển khai (07/11/2026):** nền tảng pgvector/BGE semantic retrieval và LTR đã có trong mã/migration nhưng **chưa kích hoạt production**. Đây là hạ tầng hỗ trợ cho F1.05/F1.06, không phải Talent Pool/Candidate Rediscovery của Phase 3: semantic retrieval hiện chỉ tìm chunk trong đúng CV đang đánh giá, không tìm xuyên vị trí/ứng viên và không thay đổi yêu cầu consent. LTR chỉ được chuyển từ `OFF` sang `SHADOW`/`ACTIVE` sau khi có labelled dataset HR, holdout gate và phê duyệt artifact.

---

## 2. Đặc tả Chi tiết các Phase Phát triển 

---

### PHASE 1 — MVP Pilot: Nền tảng Matching & Kiểm chứng Nghiệp vụ (Tuần 1 – Tuần 2)
*Phạm vi: Thử nghiệm thực tế trên nhóm vị trí IT, sử dụng CV tiếng Anh định dạng PDF/DOCX.*

#### F1.01. Quản lý Vị trí Tuyển dụng & JD (Requisition & JD Management)
* **Mô tả chức năng:**
  * Khởi tạo vị trí tuyển dụng với thông tin: Tên vị trí, Phòng ban/Viện, Hiring Manager phụ trách, Recruiter phụ trách.
  * Quản lý trạng thái vị trí: Mở (Open) / Tạm dừng (Paused) / Đóng (Closed).
  * Tiếp nhận và lưu trữ bản mô tả công việc (JD) định dạng text hoặc file văn bản (tiếng Anh).
* **Nguyên tắc & Ràng buộc:** Mỗi đợt sàng lọc phải gắn chặt với một Requisition ID cụ thể; không matching trôi nổi ngoài vị trí.

#### F1.02. Trích xuất & Phê duyệt Tiêu chí Tuyển dụng (Criteria Extraction & Dual Approval)
* **Mô tả chức năng:**
  * AI tự động phân tích JD tiếng Anh, bóc tách và đề xuất bản nháp tiêu chí tuyển dụng phân thành 2 nhóm: **Bắt buộc (Must-have)** và **Ưu tiên (Nice-to-have)**.
  * Thiết lập trọng số mặc định: Bắt buộc 70% / Ưu tiên 30% (cho phép HR điều chỉnh, tổng phải bằng 100%).
  * Quy trình phê duyệt hai cấp: Recruiter rà soát tính rõ ràng và phù hợp quy trình; Hiring Manager phê duyệt nội dung chuyên môn.
  * Lưu trữ lịch sử phiên bản tiêu chí (Criteria Versioning) để phục vụ đối soát kết quả matching.
* **Nguyên tắc & Ràng buộc:** Tuyệt đối không dùng thông tin cá nhân phi công việc (tuổi tác, giới tính, ngoại hình) làm tiêu chí; tiêu chí AI đề xuất chỉ là bản nháp, bắt buộc phải có phê duyệt của con người mới được kích hoạt.

#### F1.03. Tiếp nhận CV theo Batch (Batch CV Ingestion)
* **Mô tả chức năng:**
  * Cho phép HR tải lên hàng loạt CV theo lô: Tối đa 50 file/batch; dung lượng tối đa 10 MB/file; tổng dung lượng tối đa 250 MB/batch.
  * Định dạng hỗ trợ: PDF và DOCX (ngôn ngữ tiếng Anh).
  * Hiển thị thanh tiến trình xử lý từng file và quản lý trạng thái tải lên độc lập.
* **Nguyên tắc & Ràng buộc:** Vượt quá giới hạn phải có cảnh báo rõ ràng; lỗi một file không làm gián đoạn cả batch.

#### F1.04. Trích xuất Thông tin Nghề nghiệp & OCR (Parsing & Evidence Extraction)
* **Mô tả chức năng:**
  * Đọc PDF có văn bản gốc, trích xuất text thông thường từ DOCX.
  * Bộ giải mã OCR dành cho PDF scan (bản quét).
  * Tự động trích xuất các trường thông tin: Kinh nghiệm làm việc, Học vấn, Kỹ năng chuyên môn, Chứng chỉ nghề nghiệp.
  * Cho phép HR chỉnh sửa trực tiếp các thông tin trích xuất sai trên giao diện.
* **Nguyên tắc & Ràng buộc:** File bị hỏng, PDF bị khóa mật khẩu hoặc bản scan quá mờ được chuyển ngay vào trạng thái *"Cần HR kiểm tra"* (Manual Review Queue), không tự động bị loại.

#### F1.05. Matching theo Tiêu chí có Bằng chứng Kiểm chứng (Evidence-based Matching)
* **Mô tả chức năng:**
  * Đối chiếu hồ sơ từng ứng viên với từng tiêu chí trong rubric đã duyệt.
  * Đánh giá theo 4 mức chuẩn mực: **Đáp ứng tốt (Strong Match) / Đáp ứng (Match) / Chưa rõ (Unclear) / Chưa đáp ứng (No Match)**.
  * Mọi nhận định đánh giá đều phải hiển thị trích dẫn cụ thể (kèm số trang, đoạn văn trong CV gốc).
  * Trường hợp không tìm thấy bằng chứng trong CV phải hiển thị trạng thái "Chưa rõ" kèm lý do chi tiết.
* **Nguyên tắc & Ràng buộc:** Tuyệt đối không đánh đồng trạng thái "Chưa rõ / Chưa tìm thấy bằng chứng" với "Không đáp ứng".
* **Cập nhật:** Khi semantic retrieval được bật, BGE/pgvector có thể bổ sung candidate chunks bị lexical retrieval bỏ sót; kết quả vẫn phải qua cùng rule/LLM fallback và verbatim verification.

#### F1.06. Điểm số & Xếp hạng Ứng viên Minh bạch (Explainable Ranking)
* **Mô tả chức năng:**
  * Xếp hạng ứng viên **trong cùng một vị trí** theo quy tắc ưu tiên: Mức độ đáp ứng tiêu chí bắt buộc được xét trước, sau đó mới tính đến điểm số trọng số tổng hợp.
  * Hiển thị chỉ số **Độ phủ bằng chứng (Evidence Coverage)**. Nếu độ phủ dưới 70%, hệ thống gắn cảnh báo: *"Chưa đủ dữ liệu để xếp hạng ổn định"*.
  * Bảng giải thích chi tiết điểm số (Score Breakdown): Cho phép HR nhấp vào xem cách tính điểm từ trọng số và kết quả từng tiêu chí.
* **Nguyên tắc & Ràng buộc:** Không sử dụng điểm số như một ngưỡng tự động quyết định đỗ/trượt; thứ tự xếp hạng chỉ nhằm hỗ trợ HR ưu tiên thứ tự đọc hồ sơ.
* **Cập nhật:** LTR (nếu được phê duyệt) chỉ reorder trong cùng mandatory/coverage gate; không dùng LTR để vượt hồ sơ bị `POSSIBLE_MISMATCH` hoặc chưa đủ coverage.

#### F1.07. Xử lý Ngoại lệ & Cảnh báo Trùng cùng Vị trí (Duplicate Warning)
* **Mô tả chức năng:**
  * Cảnh báo hồ sơ nghi ngờ trùng lặp (dựa trên email, số điện thoại, trùng lặp nội dung file) **trong cùng một vị trí tuyển dụng**.
  * Gom các file lỗi vào hàng đợi riêng để HR thao tác thủ công.
* **Nguyên tắc & Ràng buộc:** Chỉ hiển thị cảnh báo; hệ thống không tự ý gộp, ghi đè hoặc xóa bất kỳ hồ sơ nào.

#### F1.08. Quản trị Quyết định & Trạng thái Tuyển dụng (Human-in-control State Transition)
* **Mô tả chức năng:**
  * Quản lý chu trình trạng thái ứng viên: Mới (New) → Đang xem (Reviewing) → Shortlist → Bị loại ở vòng sàng lọc (Rejected at Screen) → Đang phỏng vấn (Interviewing) → Không trúng tuyển (Rejected Post-Interview) → Trúng tuyển (Offered) → Đã nhận việc (Hired).
  * HR là người trực tiếp chuyển trạng thái và bắt buộc nhập lý do khi đánh dấu Bị loại hoặc Không trúng tuyển.
* **Nguyên tắc & Ràng buộc:** AI hoàn toàn không có quyền thay đổi trạng thái tuyển dụng của ứng viên.

#### F1.09. Shortlist Chia sẻ & Dashboard Cơ bản (Shortlist Sharing & Operational Dashboard)
* **Mô tả chức năng:**
  * HR tạo danh sách Shortlist kèm tóm tắt bằng chứng để chia sẻ cho Hiring Manager của vị trí đó xem xét.
  * Dashboard hiển thị số lượng hồ sơ tiếp nhận, phân bổ trạng thái và tiến độ xử lý của từng vị trí.
* **Nguyên tắc & Ràng buộc:** Hiring Manager chỉ được phân quyền xem các vị trí và danh sách Shortlist được chia sẻ cụ thể.

#### F1.10. Phân quyền RBAC, Audit Log & Quản trị Lưu trữ (Retention & Compliance Baseline)
* **Mô tả chức năng:**
  * Phân quyền truy cập dựa trên vai trò (HR Recruiter, Hiring Manager, HR Lead, System Admin).
  * Ghi nhận nhật ký kiểm toán (Audit Log) không thể chỉnh sửa đối với các hành vi: Xem CV, sửa dữ liệu trích xuất, thay đổi trạng thái, tải file, xuất dữ liệu.
  * Bộ đếm thời hạn lưu trữ: Tự động đếm 12 tháng kể từ ngày vị trí tuyển dụng chuyển sang trạng thái "Đóng". Khi hết hạn, hồ sơ được đưa vào danh sách chờ HR có thẩm quyền xác nhận xóa thủ công.
* **Nguyên tắc & Ràng buộc:** Tuân thủ thời hạn lưu trữ 12 tháng theo quy chuẩn nội bộ; việc xóa dữ liệu thực hiện theo từng hồ sơ ứng tuyển, không xóa tự động hàng loạt nếu chưa có người xác nhận.

#### F1.11. Quản trị Lựa chọn Model & Hạ tầng Cục bộ (Local AI Mode Priority)
* **Mô tả chức năng:**
  * Thiết lập kiến trúc ưu tiên sử dụng mô hình AI xử lý cục bộ (On-premise / Private Environment) để bảo vệ tuyệt đối dữ liệu CV.
  * Quản trị viên chỉ được kích hoạt các dịch vụ AI bên ngoài khi đã có văn bản phê duyệt an ninh thông tin riêng cho môi trường kiểm thử.
* **Nguyên tắc & Ràng buộc:** Dữ liệu CV thật trong vận hành chính thức không được gửi ra các API đám mây công cộng chưa được thẩm định.

#### F1.12. Giao diện Đa ngôn ngữ (Bilingual UI)
* **Mô tả chức năng:** Hỗ trợ chuyển đổi giao diện song ngữ Tiếng Việt và Tiếng Anh (mặc định Tiếng Việt), phù hợp với người dùng nội bộ VinUni.

#### F1.13. Đánh giá Nghiệm thu Pilot trên Tập Nhãn Chuẩn (Pilot Evaluation Framework)
* **Mô tả chức năng:**
  * Bộ công cụ kiểm thử trên tập dữ liệu chuẩn mực (tối thiểu 200–300 cặp CV–JD–Rubric thuộc các vị trí IT: Software Engineer, QA, DevOps, Data Engineer, IT Support).
  * Đo đạc các chỉ số: Độ chính xác trích xuất trường thông tin (F1 ≥ 85%), Macro-F1 matching theo tiêu chí (≥ 0.80), tỷ lệ sai lệch tiêu chí bắt buộc (≤ 5%), và chất lượng xếp hạng (NDCG@5 ≥ 0.75).
* **Nguyên tắc & Ràng buộc:** Kết quả đo đạc dùng làm căn cứ quyết định chuyển giao sang Phase 2.

---

### PHASE 2 — Hoàn thiện sau Pilot & Tối ưu hóa Vận hành (Tuần 3 – Tuần 4)
*Phạm vi: Củng cố chất lượng thuật toán, mở rộng ra toàn bộ các khối ngành chức năng của VinUni (Hành chính, Tài chính, Sinh viên vụ, Truyền thông...), chuẩn hóa sự phối hợp HR–HM và tích hợp SSO.*

#### F2.01. Thư viện Rubric & Tiêu chí Chuẩn hóa theo Nhóm Vị trí (Rubric Library by Job Family)
* **Mục tiêu & Pain point:** Khi mở rộng ra ngoài IT, HR mất 30–60 phút soạn tiêu chí cho mỗi vị trí mới; tiêu chí giữa các phòng ban thiếu tính nhất quán.
* **Mô tả chức năng:**
  * Xây dựng thư viện khung rubric mẫu chuẩn hóa cho các khối vị trí tại VinUni:
    1. *Khối Công nghệ & Kỹ thuật số (IT, Data, Systems)*
    2. *Khối Vận hành & Hành chính (Operations, Facilities, Admin)*
    3. *Khối Tài chính & Kế toán (Finance, Accounting, Procurement)*
    4. *Khối Quản lý Đào tạo & Sinh viên vụ (Student Affairs, Registrar, Academic Support)*
    5. *Khối Tuyển sinh, Hợp tác & Truyền thông (Marketing, Admissions, Global Engagement)*
  * Mỗi template định nghĩa sẵn: Bộ năng lực cốt lõi, danh sách tiêu chí Bắt buộc/Ưu tiên, mức kỳ vọng kinh nghiệm, rubric chấm điểm 4 mức và từ khóa bằng chứng.
  * Cho phép HR nhân bản (clone) template, hiệu chỉnh linh hoạt theo từng vị trí cụ thể, lưu vết phiên bản (Versioning) và lưu danh tính người phê duyệt.
* **Lưu ý & Ràng buộc:** Template chỉ đóng vai trò khung tham chiếu ban đầu, Hiring Manager và HR vẫn phải bấm phê duyệt chính thức cho từng vị trí cụ thể.
* **Giá trị mang lại:** Giảm 75% thời gian thiết lập tiêu chí cho vị trí mới (từ 60 phút xuống 15 phút); chuẩn hóa mặt bằng tuyển dụng toàn trường.
* **Độ phức tạp:** Thấp – Trung bình.

#### F2.02. Quản lý Quy trình & Cộng tác HR – Hiring Manager (Structured Collaborative Workflow)
* **Mục tiêu & Pain point:** Trao đổi qua email/chat rời rạc; phản hồi của Hiring Manager chậm trễ và thiếu cấu trúc đánh giá cụ thể.
* **Mô tả chức năng:**
  * **Không gian phối hợp trực tuyến:** HR gán danh sách hồ sơ cần thẩm định cho Hiring Manager trực tiếp trên hệ thống.
  * **Phiếu đánh giá sàng lọc có cấu trúc (Screening Scorecard):** Hiring Manager mở danh sách Shortlist, xem tóm tắt bằng chứng AI đối chiếu và đánh giá nhanh theo các tiêu chí chuyên môn trực tiếp trên màn hình.
  * **Phân quyền ghi chú nội bộ 2 tầng:**
    * *Ghi chú nội bộ HR (HR Private Note):* Chỉ các chuyên viên nhân sự đọc được (trao đổi về mức lương kỳ vọng, thái độ, background check sơ bộ).
    * *Ghi chú trao đổi vị trí (Recruitment Discussion):* Kênh trao đổi hai chiều giữa Recruiter và Hiring Manager.
  * **Hệ thống nhắc việc tự động (Task Reminders):** Tự động gửi cảnh báo in-app và email nếu Hiring Manager quá 3 ngày làm việc chưa hoàn thành thẩm định Shortlist được giao.
* **Lưu ý & Ràng buộc:** Đảm bảo bảo mật nghiêm ngặt ghi chú nội bộ HR; quyền quyết định chuyển trạng thái tuyển dụng chính thức vẫn thuộc thẩm quyền của HR.
* **Giá trị mang lại:** Tăng tốc độ phản hồi của Hiring Manager lên gấp 2 lần; lưu vết đầy đủ mọi ý kiến chuyên môn phục vụ công tác kiểm toán nội bộ.
* **Độ phức tạp:** Trung bình.

#### F2.03. Bảng Theo dõi Pilot & Báo cáo Hiệu năng Vận hành Thực tế (Operational Analytics Dashboard)
* **Mục tiêu & Pain point:** Thiếu dữ liệu định lượng tổng hợp để chứng minh hiệu quả tiết kiệm thời gian và phát hiện các nút thắt trong quy trình tuyển dụng sau giai đoạn thử nghiệm.
* **Mô tả chức năng:**
  * Báo cáo tổng hợp số liệu vận hành: Tổng số hồ sơ xử lý, thời gian trung bình từ lúc upload đến khi hoàn tất Shortlist, tỷ lệ chuyển đổi qua các vòng.
  * **Chỉ số điều chỉnh gợi ý AI (HR Override Tracking):** Thống kê chi tiết tỷ lệ và danh sách các trường hợp HR thay đổi kết luận của AI (ví dụ: AI báo "Chưa đáp ứng" nhưng HR sửa thành "Đáp ứng" sau khi phỏng vấn làm rõ).
  * Phân tích lý do điều chỉnh: Cho phép HR chọn lý do nhanh (CV dùng từ đồng nghĩa, chứng chỉ tương đương, bằng chứng ngầm định...). Dữ liệu này được tổng hợp báo cáo cho HR Lead để cải tiến tiêu chí.
  * Báo cáo tỷ lệ lỗi kỹ thuật: Tần suất file hỏng, file scan mờ, file sai định dạng.
* **Lưu ý & Ràng buộc:** Dữ liệu báo cáo dùng để tối ưu hóa quy trình và thuật toán, tuyệt đối không dùng làm chỉ số KPI đơn lẻ để xếp hạng hoặc đánh giá hiệu suất cá nhân của recruiter.
* **Giá trị mang lại:** Cung cấp cơ sở dữ liệu thực nghiệm để HR Lead và Ban Giám hiệu đánh giá ROI của dự án.
* **Độ phức tạp:** Trung bình.

#### F2.04. Công cụ Giám sát Chất lượng OCR & AI Matching (Quality Assurance & Sample Inspection)
* **Mục tiêu & Pain point:** Đảm bảo hệ thống vận hành tin cậy, phát hiện sớm các trường hợp OCR đọc sai hoặc AI suy luận sai, đặc biệt ngăn ngừa rủi ro bỏ sót ứng viên tiềm năng (False Negatives).
* **Mô tả chức năng:**
  * **Cơ chế trích mẫu kiểm định tự động (Sample Inspection Queue):** Hệ thống tự động trích xuất:
    * 10% hồ sơ ngẫu nhiên trong mỗi đợt tuyển dụng.
    * 100% các hồ sơ rơi vào vùng rủi ro cao: Hồ sơ bị kết luận "Chưa đáp ứng" ở duy nhất 1 tiêu chí bắt buộc, hoặc hồ sơ có độ phủ bằng chứng sát ngưỡng 70%.
  * **Giao diện đối soát song song (Side-by-side Inspection View):** Hiển thị văn bản OCR / bằng chứng AI trích xuất song song với ảnh chụp CV gốc để HR Lead hoặc Chuyên viên kiểm soát chất lượng kiểm tra đối chiếu bằng mắt nhanh chóng.
  * **Cơ chế gắn cờ và tạo tập phản hồi (Feedback Flagging):** Cho phép gắn cờ *"Bằng chứng không chính xác"* hoặc *"Bỏ sót nội dung"* -> Dữ liệu được đóng gói gửi về đội kỹ thuật để cập nhật bộ luật/prompt.
* **Lưu ý & Ràng buộc:** Quy trình kiểm định mẫu được thực hiện định kỳ hàng tuần; các hồ sơ bị phát hiện đánh giá sai phải được HR cập nhật lại trạng thái ngay lập tức.
* **Giá trị mang lại:** Giữ vững độ tin cậy của hệ thống; triệt tiêu rủi ro bỏ sót người tài do hạn chế kỹ thuật của AI.
* **Độ phức tạp:** Trung bình.

#### F2.05. Phát hiện Hồ sơ Trùng giữa Nhiều Vị trí (Cross-Requisition Duplicate Detection)
* **Mục tiêu & Pain point:** Ứng viên nộp hồ sơ đồng thời vào nhiều vị trí khác nhau trong trường; các recruiter phụ trách từng vị trí không biết, dẫn đến việc liên hệ chồng chéo, hỏi trùng lặp hoặc đưa ra thông điệp thiếu nhất quán.
* **Mô tả chức năng:**
  * Quét tự động toàn bộ cơ sở dữ liệu tuyển dụng dựa trên: Email chuẩn hóa, số điện thoại và thuật toán so khớp độ tương đồng họ tên/nội dung (Fuzzy Matching).
  * Hiển thị bảng cảnh báo nổi bật trên hồ sơ ứng viên: *"Ứng viên này đã nộp hồ sơ vào vị trí [Tên vị trí A] (ngày dd/mm/yyyy - Trạng thái: Đang phỏng vấn)"*.
  * Cho phép Recruiter bấm vào xem lịch sử ứng tuyển tổng thể của ứng viên tại VinUni và liên hệ nhanh với Recruiter đang phụ trách vị trí kia để phối hợp.
* **Lưu ý & Ràng buộc:** Hệ thống chỉ đưa ra cảnh báo thông tin; **tuyệt đối không tự động gộp (merge) hay xóa** bất kỳ bản ghi ứng tuyển nào để bảo toàn hồ sơ pháp lý riêng của từng vị trí.
* **Giá trị mang lại:** Ngăn chặn việc lãng phí nguồn lực tuyển dụng; nâng cao tính chuyên nghiệp của thương hiệu VinUni trong mắt ứng viên.
* **Độ phức tạp:** Thấp – Trung bình.

#### F2.06. Mở rộng Định dạng CV: OCR Ảnh rời & Ảnh nhúng trong DOCX (Expanded Format OCR)
* **Mục tiêu & Pain point:** Nhiều ứng viên các khối ngành Hành chính, Thiết kế, Truyền thông nộp CV dạng ảnh thiết kế (JPG, PNG) hoặc chèn ảnh scan chứng chỉ/bằng cấp vào bên trong file Word.
* **Mô tả chức năng:**
  * Cho phép tải lên trực tiếp các định dạng ảnh độc lập: JPG, JPEG, PNG (tối đa 10 MB/file).
  * Bộ giải nén và quét OCR tự động cho các ảnh nhúng bên trong thân tài liệu DOCX/DOC.
  * Tiền xử lý ảnh thông minh: Tự động xoay thẳng góc (Deskew), tăng độ tương phản, khử nhiễu trước khi nhận dạng chữ.
  * Cảnh báo và chuyển vào hàng đợi xử lý thủ công nếu ảnh có độ phân giải quá thấp (< 150 DPI) hoặc bị mờ nhòe không thể nhận dạng.
* **Lưu ý & Ràng buộc:** Giữ nguyên quy định hiển thị link đối chiếu về ảnh gốc để HR kiểm chứng khi cần.
* **Giá trị mang lại:** Nâng tỷ lệ xử lý hồ sơ thành công lên > 98%, xóa bỏ rào cản ứng viên phải nộp lại file PDF văn bản.
* **Độ phức tạp:** Trung bình.

#### F2.07. Tự động hóa Cảnh báo Retention & Quy trình Xóa Dữ liệu An toàn (Automated Retention & Deletion)
* **Mục tiêu & Pain point:** Việc theo dõi thủ công hạn 12 tháng lưu trữ hồ sơ theo Nghị định 13/2023/NĐ-CP rất dễ bị quên sót hoặc xóa nhầm các hồ sơ đang trong diện xem xét khiếu nại.
* **Mô tả chức năng:**
  * **Bộ đếm chu kỳ tự động:** Tự động tính toán mốc hết hạn 12 tháng kể từ ngày vị trí tuyển dụng chính thức chuyển sang trạng thái "Đóng".
  * **Thông báo nhắc nhở đa tầng:** Tự động gửi email thông báo cho HR phụ trách và HR Lead trước thời điểm hết hạn vào các mốc: **Trước 30 ngày, 15 ngày và 7 ngày**.
  * **Bảng điều khiển Quản trị Vòng đời Dữ liệu (Retention Management Console):** Hiển thị danh sách hồ sơ sắp đến hạn xóa; cung cấp 2 lựa chọn cho HR có thẩm quyền:
    1. *Xác nhận Phê duyệt Xóa (Purge):* Hệ thống tiến hành xóa vĩnh viễn file CV gốc, văn bản trích xuất và các dữ liệu định danh cá nhân; chỉ lưu lại bản ghi nhật ký kiểm toán ẩn danh (Anonymized Audit Record).
    2. *Tạm hoãn Xóa có lý do chính đáng (Retention Exception Hold):* Cho phép gia hạn lưu trữ trong trường hợp đặc biệt (ví dụ: đang giải quyết khiếu nại, phục vụ thanh kiểm tra) kèm văn bản phê duyệt của Pháp chế (Legal).
  * Xử lý trường hợp vị trí mở lại: Nếu vị trí tuyển dụng được mở lại (Re-opened), chu kỳ 12 tháng được thiết lập lại từ đầu kể từ ngày đóng mới.
* **Lưu ý & Ràng buộc:** **Chỉ triển khai sau khi Phòng Pháp chế (Legal & Privacy) phê duyệt** quy trình và biểu mẫu ngoại lệ; thao tác xóa dữ liệu vật lý phải có chữ ký điện tử hoặc xác nhận OTP của HR được ủy quyền.
* **Giá trị mang lại:** Tuân thủ pháp lý 100%, bảo vệ VinUni trước các rủi ro chế tài về bảo vệ dữ liệu cá nhân.
* **Độ phức tạp:** Trung bình.

#### F2.08. Tích hợp Đăng nhập Đơn lẻ SSO (Single Sign-On Integration)
* **Mục tiêu & Pain point:** Sử dụng tài khoản email/mật khẩu riêng rẽ gây phiền toái cho nhân sự, khó quản lý tập trung và tiềm ẩn rủi ro an ninh khi nhân sự nghỉ việc nhưng chưa kịp khóa tài khoản hệ thống HRA.
* **Mô tả chức năng:**
  * Tích hợp cơ chế xác thực SSO qua giao thức SAML 2.0 / OpenID Connect với hệ thống định danh Microsoft Azure Active Directory (Azure AD / Microsoft 365) của VinUni.
  * Tự động nhận diện và phân quyền ban đầu dựa trên nhóm bảo mật (Security Groups): Nhóm Tuyển dụng (HR Recruiters), Nhóm Lãnh đạo Khoa/Phòng (Hiring Managers).
  * Tự động vô hiệu hóa quyền truy cập ngay khi tài khoản email VinUni của nhân sự bị khóa trên hệ thống tổng.
* **Lưu ý & Ràng buộc:** Phối hợp cùng Bộ phận IT & An toàn thông tin VinUni để đăng ký Enterprise Application và kiểm thử luồng xác thực đa yếu tố (MFA).
* **Giá trị mang lại:** Đăng nhập 1 chạm an toàn, đồng bộ chính sách bảo mật nội bộ của VinUni.
* **Độ phức tạp:** Thấp – Trung bình.

#### F2.09. So sánh Ứng viên Song song & Xuất Báo cáo Tùy biến (Side-by-side Comparison & Export)
* **Mục tiêu & Pain point:** Khi cần lựa chọn giữa 2–4 ứng viên xuất sắc tương đương nhau cho vòng phỏng vấn cuối, HR và Hiring Manager phải lật mở nhiều tab trình duyệt để ghi nhớ và so sánh thủ công.
* **Mô tả chức năng:**
  * Cho phép tích chọn từ 2 đến 4 ứng viên trong danh sách -> Chọn chức năng *"So sánh song song (Side-by-side)"*.
  * Giao diện đối chiếu dạng lưới ma trận: So sánh trực diện từng tiêu chí (Bắt buộc, Ưu tiên), highlight các điểm mạnh nổi trội, số năm kinh nghiệm thực tế, bằng cấp, chứng chỉ và các điểm còn mơ hồ cần làm rõ trong phỏng vấn.
  * **Xuất báo cáo tùy biến (Custom Export):** Cho phép xuất danh sách ứng viên và kết quả matching ra file Excel hoặc PDF; cho phép tùy chọn các cột thông tin cần xuất (ẩn/hiện thông tin liên hệ, điểm số, trích dẫn bằng chứng) phù hợp với mục đích sử dụng.
* **Lưu ý & Ràng buộc:** Thao tác xuất dữ liệu phải được ghi nhận chi tiết vào Audit Log; người xuất phải có thẩm quyền tương ứng với vị trí.
* **Giá trị mang lại:** Rút ngắn thời gian ra quyết định shortlist trong các phiên họp tuyển dụng từ 45 phút xuống 10 phút.
* **Độ phức tạp:** Thấp.

---

### PHASE 3 — Tự động hóa Sâu & Kết nối Hệ sinh thái (Tuần 5 – Tuần 6)
*Phạm vi: Tích hợp trực tiếp vào hạ tầng phần mềm nhân sự của VinUni (ATS, HRIS, Email, Calendar); xây dựng kho nhân tài tái sàng lọc và mở rộng năng lực xử lý đa ngôn ngữ.*

#### F3.01. Talent Pool & Tái Khám phá Ứng viên Tiềm năng (Candidate Rediscovery)
* **Mục tiêu & Pain point:** Các ứng viên có năng lực tốt nhưng chỉ xếp thứ hai trong đợt tuyển trước bị lãng quên; khi phát sinh nhu cầu mới lại phải tốn ngân sách đăng tuyển và lọc lại từ đầu.
* **Mô tả chức năng:**
  * **Cơ chế gắn nhãn Talent Pool:** HR đánh dấu các hồ sơ đạt chuẩn phỏng vấn nhưng chưa nhận offer vào danh mục *"Ứng viên tiềm năng (Talent Pool)"*.
  * **Quản lý sự đồng ý riêng biệt (Explicit Consent Management):** Hệ thống tự động gửi email xin ý kiến ứng viên về việc lưu trữ hồ sơ trong Kho nhân tài VinUni với thời hạn gia hạn cụ thể (ví dụ: 24 tháng). Ứng viên có link chuyên biệt để chủ động cập nhật CV mới hoặc rút lại sự đồng ý (Opt-out) bất cứ lúc nào.
  * **Tính năng Tái khám phá Ứng viên (Candidate Rediscovery):** Khi một vị trí mới được tạo và phê duyệt rubric, HR có thêm nút chọn: *"Quét kho Talent Pool"*. AI tự động đối chiếu rubric mới với các hồ sơ còn hạn trong kho nhân tài và xếp hạng các ứng viên tiềm năng phù hợp nhất để HR chủ động liên hệ phỏng vấn ngay.
* **Lưu ý & Ràng buộc:** **Chỉ quét các hồ sơ còn hạn lưu trữ hợp pháp và có sự đồng ý rõ ràng** của ứng viên; tuyệt đối không quét các hồ sơ đã hết hạn retention 12 tháng đang chờ xóa.
* **Giá trị mang lại:** Giảm 40–60% thời gian tuyển dụng (Time-to-fill) cho các vị trí phổ biến; tiết kiệm đáng kể chi phí đăng tin tuyển dụng.
* **Độ phức tạp:** Trung bình – Cao.

#### F3.02. Tích hợp Hai chiều Hệ thống ATS / HRIS hiện có của VinUni (Enterprise ATS/HRIS Sync)
* **Mục tiêu & Pain point:** Dữ liệu nhân sự bị phân mảnh; sau khi tuyển xong recruiter phải gõ lại toàn bộ thông tin ứng viên trúng tuyển sang phần mềm nhân sự tổng thể của nhà trường.
* **Mô tả chức năng:**
  * Xây dựng cổng kết nối API hai chiều an toàn với hệ thống nhân sự / ATS mà VinUni đang vận hành (như Base, SAP, Workday, hoặc phần mềm nội bộ).
  * Tự động đồng bộ thông tin vị trí tuyển dụng, mã Requisition ID và cơ cấu phòng ban từ HRIS sang HRA.
  * Khi ứng viên chuyển sang trạng thái *"Trúng tuyển / Đã nhận việc"* trên HRA, hệ thống tự động đẩy gói hồ sơ hoàn chỉnh (thông tin cá nhân chuẩn hóa, file CV gốc, lịch sử đánh giá) sang HRIS để kích hoạt quy trình chuẩn bị tiếp nhận nhân sự (Pre-onboarding).
* **Lưu ý & Ràng buộc:** Yêu cầu Bộ phận IT & An toàn thông tin VinUni phê duyệt kiến trúc kết nối API, mã hóa dữ liệu đường truyền (TLS 1.3) và xác thực định danh dịch vụ (OAuth2 / mTLS).
* **Giá trị mang lại:** Thiết lập nguồn dữ liệu duy nhất (Single Source of Truth), loại bỏ 100% công sức nhập liệu trùng lặp giữa các hệ thống phần mềm.
* **Độ phức tạp:** Cao.

#### F3.03. Tự động Tiếp nhận CV Đa kênh (Multi-channel Automated CV Ingestion)
* **Mục tiêu & Pain point:** HR phải đăng nhập thủ công vào các trang tuyển dụng đối tác (VietnamWorks, TopCV, LinkedIn) hoặc tải từng file đính kèm trong hộp thư tuyển dụng về máy tính cá nhân.
* **Mô tả chức năng:**
  * **Tích hợp Hộp thư Tuyển dụng (Email Gateway Ingestion):** Thiết lập kết nối an toàn với hòm thư tuyển dụng chính thức của VinUni (`recruitment@vinuni.edu.vn`). Hệ thống tự động quét các email có tiêu đề chứa mã vị trí tuyển dụng, bóc tách file CV đính kèm, tạo hồ sơ ứng viên và tự động xếp vào vị trí tương ứng.
  * **Kết nối Cổng việc làm VinUni (Careers Portal Webhook):** Cung cấp API/Webhook để form ứng tuyển trên website VinUni Careers tự động đẩy CV và dữ liệu ứng viên thẳng vào hàng đợi xử lý của HRA.
* **Lưu ý & Ràng buộc:** Có cơ chế lọc thư rác (Spam Filter) và kiểm tra mã độc (Antivirus Scan) đối với toàn bộ file đính kèm trước khi đưa vào hệ thống bóc tách dữ liệu.
* **Giá trị mang lại:** Tự động hóa hoàn toàn khâu tiếp nhận; hồ sơ được bóc tách và phân tích ngay trong vòng vài phút sau khi ứng viên nộp.
* **Độ phức tạp:** Cao.

#### F3.04. Quản lý Lịch Phỏng vấn & Scorecard Số hóa (Interview Self-Scheduling & Digital Scorecard)
* **Mục tiêu & Pain point:** Việc xếp lịch phỏng vấn giữa ứng viên và hội đồng tuyển dụng (thường gồm 2–3 lãnh đạo/giảng viên) mất nhiều ngày trao đổi email; phiếu chấm điểm phỏng vấn ghi giấy dễ phân tán, khó tổng hợp.
* **Mô tả chức năng:**
  * **Đồng bộ Lịch biểu (Calendar Integration):** Kết nối với Microsoft Outlook Calendar của VinUni để nhận diện các khoảng thời gian trống của hội đồng phỏng vấn và phòng họp khả dụng.
  * **Ứng viên tự chọn khung giờ (Candidate Self-Scheduling):** Hệ thống gửi link chuyên biệt cho ứng viên lọt vào Shortlist; ứng viên chủ động chọn khung giờ phù hợp trong danh sách khung giờ trống được định sẵn.
  * Tự động gửi thư mời họp kèm link phòng họp trực tuyến (Microsoft Teams / Zoom) và tạo lịch hẹn trên Calendar của tất cả các bên liên quan.
  * **Phiếu đánh giá phỏng vấn số hóa (Digital Interview Scorecard):** Cung cấp form chấm điểm trực tiếp trên giao diện web theo các tiêu chí đã định; các thành viên hội đồng chấm độc lập; hệ thống tự động tổng hợp điểm bình quân và hiển thị phân tích chênh lệch nhận định giữa các giám khảo.
* **Lưu ý & Ràng buộc:** Có cơ chế thông báo hủy lịch/đổi lịch tự động với thời hạn báo trước tối thiểu (ví dụ 24h).
* **Giá trị mang lại:** Rút ngắn thời gian chốt lịch phỏng vấn từ 3–5 ngày xuống còn vài giờ; số hóa hoàn toàn biên bản phỏng vấn.
* **Độ phức tạp:** Trung bình – Cao.

#### F3.05. Hệ thống Thông báo Ứng viên Bán tự động (Automated Candidate Communication)
* **Mục tiêu & Pain point:** Số lượng hồ sơ lớn khiến HR không thể gửi thư thông báo kết quả cho từng ứng viên, gây ảnh hưởng không tốt đến hình ảnh chuyên nghiệp của VinUni.
* **Mô tả chức năng:**
  * Kho thư viện mẫu email thương hiệu VinUni chuẩn mực: Thư xác nhận tiếp nhận hồ sơ, Thư mời bổ sung thông tin, Thư mời phỏng vấn, Thư thông báo chưa phù hợp (kèm lời cảm ơn lịch sự và trân trọng).
  * Hỗ trợ chèn các trường dữ liệu động cá nhân hóa (Họ tên ứng viên, Tên vị trí ứng tuyển, Thời gian nộp...).
  * **Quy trình bán tự động an toàn (Human-in-the-loop Guardrail):** Khi HR thay đổi trạng thái hồ sơ (ví dụ chuyển sang "Bị loại ở vòng sàng lọc"), hệ thống tạo sẵn bản nháp email tương ứng; HR xem trước nội dung (Preview) và bấm xác nhận gửi hàng loạt.
* **Lưu ý & Ràng buộc:** **Tuyệt đối không bật chế độ tự động gửi email từ chối** mà không có thao tác xác nhận chủ động từ HR, nhằm tránh trường hợp gửi nhầm thư từ chối cho ứng viên đạt yêu cầu.
* **Giá trị mang lại:** Xây dựng trải nghiệm ứng viên đẳng cấp quốc tế; tiết kiệm 5–10 giờ soạn thảo email mỗi tuần cho chuyên viên tuyển dụng.
* **Độ phức tạp:** Trung bình.

#### F3.06. Xử lý CV Đa ngôn ngữ Hoàn chỉnh (Comprehensive Multi-language Support)
* **Mục tiêu & Pain point:** VinUni tiếp nhận đồng thời cả CV tiếng Việt và tiếng Anh; nhiều ứng viên quốc tế hoặc ứng viên người Việt nộp hồ sơ bằng các ngôn ngữ khác nhau cần được đánh giá trên cùng một chuẩn mực công bằng.
* **Mô tả chức năng:**
  * Nâng cấp mô hình xử lý ngôn ngữ tự nhiên (NLP) để hiểu sâu sắc cấu trúc văn bản, thuật ngữ học thuật và nghề nghiệp bằng cả **Tiếng Việt và Tiếng Anh**.
  * Khả năng chuẩn hóa và ánh xạ ngữ nghĩa xuyên ngôn ngữ (ví dụ: hiểu tương đương giữa "Cử nhân Xuất sắc Đại học Bách Khoa" với "Bachelor of Engineering with High Distinction").
  * Giao diện đối chiếu thông minh: Cho phép HR xem bản trích xuất tiêu chí bằng ngôn ngữ làm việc tùy chọn trong khi luôn hiển thị song song đoạn văn bản gốc của ứng viên để kiểm chứng.
* **Lưu ý & Ràng buộc:** Luôn ưu tiên căn cứ vào nội dung gốc trong CV; không tự ý diễn dịch suy diễn nếu ngôn từ trong CV không rõ ràng.
* **Giá trị mang lại:** Đảm bảo đánh giá công bằng, không bỏ sót nhân tài do rào cản ngôn ngữ.
* **Độ phức tạp:** Cao.

#### F3.07. Tìm kiếm & Lọc Ngữ nghĩa Nâng cao (Semantic Search & Advanced Filtering)
* **Mục tiêu & Pain point:** Khó khăn trong việc tìm kiếm lại các ứng viên có bộ kỹ năng đặc thù hoặc kinh nghiệm chuyên sâu trong toàn bộ kho dữ liệu hồ sơ đã tiếp nhận.
* **Mô tả chức năng:**
  * Kết hợp bộ lọc có cấu trúc (Structured Filters): Lọc theo khoảng năm kinh nghiệm, bậc học vấn cao nhất, trường đào tạo, chứng chỉ chuyên môn, trạng thái tuyển dụng.
  * **Công cụ tìm kiếm ngữ nghĩa (Semantic Search Engine):** Cho phép nhập câu hỏi hoặc mô tả yêu cầu bằng ngôn ngữ tự nhiên (ví dụ: *"Tìm ứng viên có kinh nghiệm triển khai hệ sinh thái dữ liệu trên Cloud và có chứng chỉ AWS"*).
  * Hệ thống tự động phân tích ngữ nghĩa, tìm kiếm các hồ sơ phù hợp nhất và trích xuất đúng đoạn văn bằng chứng liên quan.
* **Lưu ý & Ràng buộc:** Tìm kiếm chỉ được thực hiện trên các hồ sơ còn trong thời hạn lưu trữ hợp pháp theo quy định retention.
* **Giá trị mang lại:** Biến kho dữ liệu CV thành tài sản tri thức nhân sự có khả năng khai thác tức thì.
* **Độ phức tạp:** Trung bình – Cao.

---

### PHASE 4 — Phân tích Nâng cao, Đảm bảo Công bằng & Quản trị Thông minh (Tuần 7 – Tuần 8)
*Phạm vi: Ứng dụng trí tuệ dữ liệu hỗ trợ hoạch định chiến lược nhân sự, kiểm soát rủi ro định kiến thuật toán, xây dựng quy trình tuyển dụng công bằng, minh bạch và hoàn thiện cổng tự phục vụ.*

#### F4.01. Phân tích Hiệu quả Tuyển dụng & Dự báo Xu hướng (Predictive Recruiting Analytics)
* **Mục tiêu & Pain point:** Ban Giám hiệu và Lãnh đạo Nhân sự thiếu dữ liệu vĩ mô để đánh giá toàn diện hiệu quả tuyển dụng: Nguồn nào mang lại ứng viên chất lượng nhất? Khâu nào đang gây ách tắc quy trình?
* **Mô tả chức năng:**
  * **Phân tích Phễu Tuyển dụng Toàn diện (Full-funnel Recruiting Analytics):** Đo lường tỷ lệ chuyển đổi chi tiết qua từng bước (Nộp hồ sơ → Đạt tiêu chí → Phỏng vấn vòng 1 → Phỏng vấn vòng 2 → Nhận Offer → Đến làm việc) theo từng phòng ban/viện đào tạo.
  * **Định vị Điểm nghẽn Quy trình (Bottleneck Identification):** Tính toán chính xác thời gian tồn đọng trung bình ở từng mắt xích: Thời gian HR duyệt hồ sơ, thời gian Hiring Manager phản hồi Shortlist, thời gian xếp lịch phỏng vấn.
  * **Phân tích Hiệu quả Nguồn tuyển dụng (Source Quality Attribution):** Đánh giá nguồn ứng viên nào (LinkedIn, TopCV, Giới thiệu nội bộ, Website trường) mang lại tỷ lệ ứng viên trúng tuyển cao nhất và có chi phí tuyển dụng tối ưu nhất.
* **Lưu ý & Ràng buộc:** Báo cáo phân tích vĩ mô vận hành dựa trên dữ liệu lịch sử tuyển dụng được nạp từ HRIS/ATS và dữ liệu vận hành thực tế qua các Sprint.
* **Giá trị mang lại:** Cung cấp thông tin tình báo nhân sự (Talent Intelligence) giúp tối ưu hóa ngân sách và nâng cao năng lực hoạch định nhân lực của nhà trường.
* **Độ phức tạp:** Cao.

#### F4.02. Giám sát Tính Công bằng & Kiểm toán Rủi ro Thiên lệch (Fairness, Anti-Bias & DEI Analytics)
* **Mục tiêu & Pain point:** Là trường đại học quốc tế theo chuẩn mực kiểm định kiểm soát chất lượng cao nhất, VinUni cần đảm bảo tuyệt đối không có sự phân biệt đối xử ngầm hoặc định kiến thuật toán (Algorithmic Bias) trong tuyển dụng.
* **Mô tả chức năng:**
  * **Mô-đun Kiểm toán Định kiến Thuật toán (Bias Audit Engine):** Định kỳ kiểm tra phân phối đánh giá của AI theo các nhóm nhân khẩu học để phát hiện các dấu hiệu sai lệch thống kê bất thường.
  * **Bảng điều khiển Đa dạng & Hòa nhập (DEI Analytics Dashboard):** Báo cáo tổng hợp số liệu về tỷ lệ đa dạng (phân bố giới tính, vùng miền, quốc tịch) ở các giai đoạn trong phễu tuyển dụng.
  * **Cơ chế Kỹ thuật Tách biệt Dữ liệu Nhạy cảm (Blind Screening Guardrail):** Toàn bộ dữ liệu nhân khẩu học nhạy cảm (tuổi, giới tính, ảnh chân dung, tình trạng hôn nhân) **bị loại bỏ hoàn toàn khỏi mô hình đánh giá matching và ranking**. Dữ liệu này chỉ được lưu trữ riêng biệt phục vụ mục đích báo cáo thống kê tổng hợp theo quy định pháp luật.
* **Lưu ý & Ràng buộc:** Phối hợp cùng Hội đồng Đạo đức và Pháp chế VinUni để định kỳ đánh giá tính minh bạch và công bằng của các thuật toán AI.
* **Giá trị mang lại:** Bảo vệ uy tín học thuật và thương hiệu quốc tế của VinUni; xây dựng môi trường tuyển dụng văn minh, bình đẳng.
* **Độ phức tạp:** Cao.

#### F4.03. Cổng Thông tin Ứng viên Tự phục vụ (Candidate Self-Service Portal)
* **Mục tiêu & Pain point:** Ứng viên thường xuyên lo lắng về tình trạng hồ sơ, liên tục gửi email hoặc gọi điện hỏi thăm gây quá tải cho bộ phận tuyển dụng.
* **Mô tả chức năng:**
  * Cung cấp trang web tra cứu bảo mật dành riêng cho ứng viên (đăng nhập qua mã hồ sơ hoặc xác thực OTP qua email cá nhân).
  * Ứng viên theo dõi trực quan tiến trình hồ sơ của mình theo các chặng minh bạch: *Đã tiếp nhận → Đang đánh giá chuyên môn → Đã lên lịch phỏng vấn → Hoàn tất quy trình*.
  * Cho phép ứng viên chủ động cập nhật bản CV mới nhất, đính kèm chứng chỉ bổ sung hoặc thực hiện quyền yêu cầu rút hồ sơ và xóa dữ liệu cá nhân theo quy định của pháp luật.
* **Lưu ý & Ràng buộc:** Không hiển thị điểm số chi tiết nội bộ hoặc các nhận xét chuyên môn nhạy cảm của người phỏng vấn cho ứng viên; chỉ hiển thị trạng thái tổng quan.
* **Giá trị mang lại:** Nâng cao vượt bậc trải nghiệm ứng viên; giảm 80% các câu hỏi kiểm tra trạng thái gửi về cho HR.
* **Độ phức tạp:** Trung bình – Cao.

#### F4.04. Trợ lý Ảo AI Tương tác Tuyển dụng 24/7 (Candidate Inquiry Chatbot)
* **Mục tiêu & Pain point:** HR phải dành nhiều thời gian trả lời lặp đi lặp lại các thắc mắc chung về chính sách đãi ngộ, văn hóa làm việc, quy cách nộp hồ sơ và cơ sở vật chất của VinUni.
* **Mô tả chức năng:**
  * Chatbot AI thông minh tích hợp trực tiếp trên Cổng tuyển dụng của trường, hoạt động liên tục 24/7 bằng cả tiếng Anh và tiếng Việt.
  * Được huấn luyện trên kho tài liệu chính sách tuyển dụng công khai, hướng dẫn ứng tuyển và các câu hỏi thường gặp (FAQs) của VinUni.
  * Hỗ trợ hướng dẫn ứng viên chọn vị trí phù hợp với năng lực và chuẩn hóa hồ sơ đúng quy cách trước khi nộp.
* **Lưu ý & Ràng buộc:** Chatbot chỉ cung cấp thông tin giải đáp chính sách chung; tuyệt đối không đưa ra các cam kết tuyển dụng hoặc nhận định về khả năng trúng tuyển của ứng viên.
* **Giá trị mang lại:** Thu hút nhân tài trẻ năng động; giảm tải công việc hỗ trợ thông tin ban đầu cho đội ngũ tuyển dụng.
* **Độ phức tạp:** Trung bình.

#### F4.05. Tích hợp Nền tảng Đánh giá Năng lực Trực tuyến (Skill Assessment Platform Integration)
* **Mục tiêu & Pain point:** Thông tin kỹ năng trong CV mang tính tự khai báo, khó kiểm chứng mức độ thành thạo thực tế nếu không có bài kiểm tra năng lực chuẩn hóa trước vòng phỏng vấn.
* **Mô tả chức năng:**
  * Kết nối API với các nền tảng kiểm tra kỹ năng uy tín (ví dụ: bài test lập trình cho vị trí IT, bài test nghiệp vụ kế toán, bài test tiếng Anh thương mại hoặc phân tích dữ liệu).
  * Tự động gửi link bài test năng lực cho các ứng viên vượt qua vòng thẩm định hồ sơ (Shortlist); thiết lập thời hạn hoàn thành bài kiểm tra.
  * Tự động đồng bộ kết quả làm bài (điểm số, thời gian làm, báo cáo chi tiết năng lực) vào hồ sơ ứng viên trên hệ thống HRA để hội đồng phỏng vấn tham khảo.
* **Lưu ý & Ràng buộc:** Điểm số bài kiểm tra năng lực là thông tin tham khảo bổ trợ cho hội đồng phỏng vấn; không dùng điểm bài test làm ngưỡng loại trừ tự động duy nhất nếu chưa có sự phê duyệt của HR Lead.
* **Giá trị mang lại:** Gia tăng tính khách quan và chuẩn xác trong đánh giá năng lực thực tế của ứng viên; giảm tỷ lệ mời nhầm ứng viên không đạt chuẩn vào vòng phỏng vấn trực tiếp.
* **Độ phức tạp:** Cao.

#### F4.06. Hỗ trợ Hồ sơ Video Giới thiệu (Video Resume Viewing — R&D Guardrail)
* **Đánh giá rủi ro & Định hướng chuẩn mực:** Các nghiên cứu quốc tế và hướng dẫn của Ủy ban Cơ hội Việc làm Bình đẳng (EEOC) chỉ ra rằng việc sử dụng AI để tự động phân tích cảm xúc, giọng nói, nét mặt từ video tiềm ẩn nguy cơ thiên lệch phân biệt đối xử cực kỳ nghiêm trọng và thiếu độ tin cậy khoa học.
* **Chuẩn hóa chức năng:**
  * **Tuyệt đối không sử dụng AI để chấm điểm, nhận diện cảm xúc hay xếp hạng video của ứng viên.**
  * Hệ thống chỉ đóng vai trò kênh lưu trữ và phát video (Media Player): Cho phép ứng viên nộp kèm đường dẫn video giới thiệu bản thân ngắn gọn (2–3 phút) nếu vị trí có yêu cầu đặc thù về kỹ năng thuyết trình/giao tiếp (ví dụ: Giảng viên phụ tá, Chuyên viên truyền thông).
  * **Con người (HR và Hiring Manager) trực tiếp xem video** và tự đưa ra nhận định chuyên môn trong phiên phỏng vấn.
* **Giá trị mang lại:** Đảm bảo an toàn pháp lý tuyệt đối cho nhà trường, tuân thủ các chuẩn mực đạo đức AI quốc tế cao nhất trong khi vẫn hỗ trợ đa dạng hóa phương thức thể hiện của ứng viên.
* **Độ phức tạp:** Thấp (Lưu trữ và phát video đơn thuần).

---

## 3. Ma trận Tổng hợp Tính năng & Ưu tiên Triển khai (Consolidated Matrix)

| Mã | Tên tính năng chuẩn hóa | Phase | Giá trị nghiệp vụ | Độ phức tạp kỹ thuật | Điều kiện tiên quyết & Phụ thuộc | Mức độ ưu tiên |
|---|---|:---:|:---:|:---:|---|:---:|
| **F1.01–13** | **Toàn bộ 13 Tính năng Cốt lõi MVP Pilot** | **1** | ⭐⭐⭐⭐⭐ | Trung bình | PRD v1.0, Dữ liệu mẫu IT | 🔥 **Đang triển khai** |
| **F2.01** | Thư viện Rubric theo nhóm vị trí | **2** | ⭐⭐⭐⭐⭐ | Thấp – TB | Pilot Rubric IT hoàn tất | 🔥 **Khẩn cấp** |
| **F2.02** | Quy trình cộng tác HR–HM & Scorecard | **2** | ⭐⭐⭐⭐⭐ | Trung bình | Web Portal Phase 1 | 🔥 **Khẩn cấp** |
| **F2.03** | Báo cáo Pilot & Hiệu năng thực tế | **2** | ⭐⭐⭐⭐⭐ | Trung bình | Dữ liệu Log vận hành Pilot | 🔥 **Khẩn cấp** |
| **F2.04** | Giám sát chất lượng OCR & Matching | **2** | ⭐⭐⭐⭐⭐ | Trung bình | Dữ liệu mẫu kiểm chuẩn | 🔥 **Khẩn cấp** |
| **F2.05** | Phát hiện trùng giữa nhiều vị trí | **2** | ⭐⭐⭐⭐ | Thấp – TB | Cơ sở dữ liệu ứng viên Phase 1 | ⚡ **Ưu tiên cao** |
| **F2.06** | Mở rộng OCR ảnh JPG/PNG & DOCX | **2** | ⭐⭐⭐⭐ | Trung bình | Module OCR nội bộ | ⚡ **Ưu tiên cao** |
| **F2.07** | Tự động hóa cảnh báo Retention & Xóa | **2** | ⭐⭐⭐⭐⭐ | Trung bình | Pháp chế (Legal) phê duyệt quy trình | 🔥 **Khẩn cấp** |
| **F2.08** | Tích hợp SSO (Azure AD / Office 365) | **2** | ⭐⭐⭐⭐ | Thấp – TB | IT VinUni cấp Enterprise App | ⚡ **Ưu tiên cao** |
| **F2.09** | So sánh song song & Xuất dữ liệu tùy biến | **2** | ⭐⭐⭐ | Thấp | Giao diện web Phase 1 | 🟢 **Bình thường** |
| **F3.01** | Talent Pool & Candidate Rediscovery | **3** | ⭐⭐⭐⭐⭐ | TB – Cao | Quy chế Consent độc lập được duyệt | 🔥 **Khẩn cấp** |
| **F3.02** | Tích hợp hai chiều ATS / HRIS VinUni | **3** | ⭐⭐⭐⭐⭐ | Cao | IT VinUni mở cổng API kết nối | ⚡ **Ưu tiên cao** |
| **F3.03** | Tự động tiếp nhận CV (Email/Careers Web) | **3** | ⭐⭐⭐⭐ | Cao | Hạ tầng Mail Gateway / Webhook | ⚡ **Ưu tiên cao** |
| **F3.04** | Lịch phỏng vấn tự động & Scorecard số | **3** | ⭐⭐⭐⭐ | TB – Cao | Kết nối Outlook Calendar API | ⚡ **Ưu tiên cao** |
| **F3.05** | Thông báo ứng viên bán tự động | **3** | ⭐⭐⭐⭐ | Trung bình | Cấu hình Mail Server VinUni | ⚡ **Ưu tiên cao** |
| **F3.06** | Xử lý CV Đa ngôn ngữ (Anh - Việt) | **3** | ⭐⭐⭐⭐ | Cao | Huấn luyện mô hình NLP đa ngữ | ⚡ **Ưu tiên cao** |
| **F3.07** | Tìm kiếm ngữ nghĩa & Lọc nâng cao | **3** | ⭐⭐⭐ | TB – Cao | Cơ sở dữ liệu Vector / Search Engine | 🟢 **Bình thường** |
| **F4.01** | Phân tích phễu & Dự báo tuyển dụng | **4** | ⭐⭐⭐⭐ | Cao | Dữ liệu lịch sử HRIS/ATS | 📌 **Tuần 7-8** |
| **F4.02** | Giám sát công bằng (DEI & Anti-bias) | **4** | ⭐⭐⭐⭐⭐ | Cao | Hội đồng Đạo đức AI & Pháp chế | 📌 **Tuần 7-8** |
| **F4.03** | Cổng ứng viên tự phục vụ | **4** | ⭐⭐⭐ | TB – Cao | Hạ tầng Web Portal công khai | 📌 **Tuần 7-8** |
| **F4.04** | Trợ lý ảo AI giải đáp ứng viên 24/7 | **4** | ⭐⭐⭐ | Trung bình | Kho tri thức chính sách tuyển dụng | 📌 **Tuần 7-8** |
| **F4.05** | Tích hợp bài test kỹ năng tự động | **4** | ⭐⭐⭐ | Cao | Kết nối nền tảng khảo thí đối tác | 📌 **Tuần 7-8** |
| **F4.06** | Hỗ trợ xem Video CV (Chỉ xem, không AI) | **4** | ⭐⭐ | Thấp | Hạ tầng lưu trữ Video nội bộ | 📌 **Tuần 7-8** |

---

## 4. Lộ trình Thực hiện Khả thi (Feasible Implementation Roadmap — 8 Tuần)

Lộ trình thực hiện được chuẩn hóa gói gọn trong **8 tuần liên tục**, áp dụng mô hình phát triển linh hoạt Agile/Scrum tăng tốc (Fast-track Iterative Delivery). Toàn bộ dự án chia thành **4 Sprint tương ứng với 4 Phase (mỗi Phase triển khai tập trung trong 2 tuần)**:

### 4.1. Biểu đồ Tiến độ Tổng thể 8 Tuần

```
    section Phase 1 (Tuần 1 - 2)
    Khởi tạo Requisition & Bóc tách JD IT           :p1_1, 2026-11-09, 2026-11-13
    Gợi ý tiêu chí, Batch Upload & OCR PDF/DOCX     :p1_2, 2026-11-11, 2026-11-16
    Matching 4 mức, Ranking minh bạch & Cảnh báo    :p1_3, 2026-11-16, 2026-11-20
    Nghiệm thu Pilot IT & Đo Baseline hiệu năng     :p1_4, 2026-11-19, 2026-11-22

    section Phase 2 (Tuần 3 - 4)
    Thư viện Rubric 5 khối ngành & HR-HM Workspace  :p2_1, 2026-11-23, 2026-11-27
    Dashboard theo dõi Pilot & Giám sát chất lượng  :p2_2, 2026-11-25, 2026-11-30
    Phát hiện trùng đa vị trí & OCR ảnh scan/DOCX   :p2_3, 2026-11-30, 2026-12-04
    Tự động hóa Retention 12 tháng & SSO Azure AD   :p2_4, 2026-12-02, 2026-12-06

    section Phase 3 (Tuần 5 - 6)
    Tích hợp ATS / HRIS VinUni & Email Ingestion    :p3_1, 2026-12-07, 2026-12-11
    Talent Pool & Quản lý Consent độc lập           :p3_2, 2026-12-09, 2026-12-14
    Lịch phỏng vấn tự động & Scorecard số hóa       :p3_3, 2026-12-14, 2026-12-18
    CV Đa ngôn ngữ (Anh - Việt) & Semantic Search   :p3_4, 2026-12-16, 2026-12-20

    section Phase 4 (Tuần 7 - 8)
    Phân tích phễu, Điểm nghẽn & Dự báo xu hướng    :p4_1, 2026-12-21, 2026-12-25
    Kiểm toán thiên lệch thuật toán & DEI Board     :p4_2, 2026-12-23, 2026-12-28
    Cổng ứng viên tự phục vụ & Chatbot FAQ 24/7     :p4_3, 2026-12-28, 2027-01-01
    Đánh giá kỹ năng, Video Resume & E2E Sign-off   :p4_4, 2026-12-30, 2027-01-03
```

### 4.2. Kế hoạch Triển khai Chi tiết theo Tuần (Sprint Breakdown)

#### Sprint 1 (Tuần 1 – Tuần 2): PHASE 1 — Nền tảng Matching & Kiểm chứng Nghiệp vụ Pilot (IT Roles)
* **Mục tiêu bàn giao:** Vận hành trơn tru luồng tải CV, bóc tách dữ liệu, gợi ý tiêu chí, đối chiếu bằng chứng và ranking có giải thích trên tập vị trí IT pilot.
* **Chi tiết công việc theo tuần:**
  * **Tuần 1:**
    * Cấu hình module Quản lý Vị trí Tuyển dụng & JD tiếng Anh (F1.01).
    * Triển khai AI bóc tách JD và cơ chế phê duyệt tiêu chí Bắt buộc/Ưu tiên 2 cấp (F1.02).
    * Xây dựng giao diện tiếp nhận CV theo batch (tối đa 50 file, 250 MB) và OCR PDF/DOCX (F1.03, F1.04).
  * **Tuần 2:**
    * Phát triển core engine Matching 4 mức có bằng chứng trích dẫn và Ranking minh bạch theo tiêu chí bắt buộc (F1.05, F1.06).
    * Thiết lập hàng đợi xử lý ngoại lệ cho file lỗi/mờ và cảnh báo hồ sơ trùng trong cùng vị trí (F1.07, F1.08).
    * Thiết lập phân quyền RBAC cơ bản, Audit log và cấu hình ưu tiên xử lý mô hình AI nội bộ (F1.10, F1.11, F1.12).
    * Chạy kiểm thử nghiệm thu Pilot trên tập 200–300 cặp CV–JD chuẩn để đo đạc baseline hiệu năng (F1.13).

#### Sprint 2 (Tuần 3 – Tuần 4): PHASE 2 — Hoàn thiện sau Pilot, Mở rộng Khối ngành & Bảo mật SSO
* **Mục tiêu bàn giao:** Khắc phục triệt để các rào cản phát hiện từ pilot, mở rộng rubric sang 5 khối ngành toàn trường, số hóa không gian làm việc HR–HM, tự động hóa retention và kết nối SSO.
* **Chi tiết công việc theo tuần:**
  * **Tuần 3:**
    * Xây dựng Thư viện Rubric mẫu chuẩn hóa cho 5 khối chức danh chính tại VinUni (F2.01).
    * Thiết lập Không gian cộng tác số HR – Hiring Manager kèm Screening Scorecard và ghi chú nội bộ 2 tầng (F2.02).
    * Xây dựng Dashboard theo dõi Pilot và báo cáo phân tích tỷ lệ điều chỉnh gợi ý của HR (F2.03).
    * Triển khai Công cụ trích mẫu kiểm định chất lượng OCR/Matching tự động (F2.04).
  * **Tuần 4:**
    * Triển khai thuật toán Phát hiện hồ sơ trùng chéo giữa nhiều vị trí tuyển dụng (F2.05).
    * Tích hợp bộ giải mã OCR ảnh chụp JPG/PNG và ảnh scan nhúng trong file Word DOCX (F2.06).
    * Cấu hình và tích hợp SSO Azure AD / Microsoft 365 nội bộ trường (F2.08).
    * Hoàn thiện module cảnh báo tự động trước hạn và quy trình phê duyệt xóa hồ sơ theo Retention 12 tháng (F2.07).
    * Bổ sung tính năng So sánh ứng viên song song và Xuất báo cáo tùy biến Excel/PDF (F2.09).

#### Sprint 3 (Tuần 5 – Tuần 6): PHASE 3 — Tự động hóa Sâu, Tích hợp Hệ thống & Đa ngôn ngữ
* **Mục tiêu bàn giao:** Xóa bỏ hoàn toàn thao tác thủ công qua kết nối ATS/HRIS, tiếp nhận CV tự động, quản lý lịch phỏng vấn và vận hành kho ứng viên tiềm năng (Talent Pool).
* **Chi tiết công việc theo tuần:**
  * **Tuần 5:**
    * Xây dựng kết nối API hai chiều đồng bộ vị trí và hồ sơ trúng tuyển với ATS/HRIS của VinUni (F3.02).
    * Kích hoạt Email Gateway Ingestion tự động bóc tách CV gửi đến hòm thư tuyển dụng và webhook cổng trường (F3.03).
    * Khởi tạo module Talent Pool và luồng xin Consent gia hạn lưu trữ ứng viên tiềm năng độc lập (F3.01).
  * **Tuần 6:**
    * Tích hợp đồng bộ lịch phỏng vấn với Outlook Calendar và số hóa Digital Interview Scorecard (F3.04).
    * Triển khai hệ thống gửi email ứng viên bán tự động có kiểm duyệt an toàn (Human-in-the-loop) (F3.05).
    * Nâng cấp mô hình NLP hỗ trợ phân tích và đối chiếu CV đa ngôn ngữ Việt – Anh hoàn chỉnh (F3.06).
    * Kích hoạt công cụ Tìm kiếm ngữ nghĩa Semantic Search trên toàn bộ kho hồ sơ hợp pháp (F3.07).

#### Sprint 4 (Tuần 7 – Tuần 8): PHASE 4 — Phân tích Vĩ mô, Đảm bảo Công bằng & Nghiệm thu Toàn diện
* **Mục tiêu bàn giao:** Cung cấp thông tin tình báo nhân sự vĩ mô, kiểm toán đạo đức AI/DEI, đưa vào vận hành Cổng ứng viên tự phục vụ và hoàn tất nghiệm thu toàn hệ sinh thái.
* **Chi tiết công việc theo tuần:**
  * **Tuần 7:**
    * Xây dựng hệ thống Phân tích phễu chuyển đổi tuyển dụng và định vị điểm nghẽn quy trình (F4.01).
    * Thiết lập bộ kiểm toán định kiến thuật toán (Bias Audit) và DEI Dashboard tách biệt dữ liệu nhạy cảm (F4.02).
    * Tích hợp API nền tảng kiểm tra kỹ năng trực tuyến Skill Assessment (F4.05).
  * **Tuần 8:**
    * Triển khai Cổng thông tin ứng viên tự phục vụ Candidate Portal (F4.03).
    * Tích hợp Trợ lý ảo AI 24/7 giải đáp chính sách tuyển dụng trên cổng trường (F4.04).
    * Kích hoạt tính năng xem Video CV giới thiệu (chỉ xem trực tiếp, không AI chấm điểm) (F4.06).
    * Chạy kiểm thử tích hợp E2E toàn diện, rà soát an toàn thông tin lần cuối và ký biên bản nghiệm thu toàn dự án.

---

## 5. Phân công Trách nhiệm & Điều kiện Tiên quyết (RACI Matrix & Prerequisites)

| Hạng mục công việc chính | Phòng Nhân sự (HR) | Bộ phận IT & An ninh | Pháp chế & Bảo mật (Legal) | Lãnh đạo Khoa/Phòng (HM) |
|---|:---:|:---:|:---:|:---:|
| **Xây dựng & Phê duyệt Rubric mẫu** | **A / R** | C | C | **C / R** |
| **Cấu hình & Duyệt tích hợp SSO (Azure AD)** | C | **A / R** | I | I |
| **Giám sát chất lượng OCR/Matching định kỳ** | **A / R** | C | I | I |
| **Phê duyệt Quy trình Retention & Xóa hồ sơ** | **A / R** | C | **A / C** | I |
| **Thiết lập Khung Consent cho Talent Pool** | R | I | **A / C** | I |
| **Mở cổng kết nối API hệ thống ATS/HRIS** | C | **A / R** | C | I |
| **Quyết định trạng thái ứng viên & Shortlist** | **A / R** | I | I | C |

*(Ghi chú: **A** - Accountable: Chịu trách nhiệm chính; **R** - Responsible: Trực tiếp thực hiện; **C** - Consulted: Được tham vấn chuyên môn; **I** - Informed: Được thông báo).*

---

## 6. Tiêu chí Chuyển giao Giai đoạn (Phase Gates & Exit Criteria theo Tuần)

Hệ thống bắt buộc phải vượt qua các cổng kiểm soát chất lượng tại cuối mỗi chặng 2 tuần để được phép nghiệm thu chuyển pha:

1. **Cổng 1 (Cuối Tuần 2 — Nghiệm thu Phase 1 chuyển giao Phase 2):**
   * Tập kiểm thử tối thiểu 200 cặp CV–JD IT đạt các chỉ tiêu cam kết: Macro-F1 Matching ≥ 0.80, tỷ lệ False Negatives ở tiêu chí bắt buộc ≤ 5%, NDCG@5 xếp hạng ≥ 0.75.
   * 100% hồ sơ lỗi định dạng, bản scan mờ được phân luồng vào hàng đợi HR xử lý thủ công an toàn.
   * Không có bất kỳ sự cố rò rỉ dữ liệu hoặc truy cập trái quyền nào trong suốt quá trình thử nghiệm.
   * Có biên bản đo lường baseline thời gian xử lý hồ sơ thực tế có ký duyệt của HR Lead.
2. **Cổng 2 (Cuối Tuần 4 — Nghiệm thu Phase 2 chuyển giao Phase 3):**
   * Tỷ lệ trích xuất thành công trên các định dạng mở rộng (PDF scan, Word nhúng ảnh, ảnh JPG/PNG) đạt > 98%.
   * 5 bộ Rubric mẫu được HR Lead và đại diện các Khối phòng ban phê duyệt chính thức trên hệ thống.
   * Phòng Pháp chế (Legal & Privacy) phê duyệt văn bản quy trình cảnh báo và phê duyệt xóa theo Retention 12 tháng.
   * IT & Security phê duyệt hoàn tất nghiệm thu kết nối SSO Azure AD nội bộ.
3. **Cổng 3 (Cuối Tuần 6 — Nghiệm thu Phase 3 chuyển giao Phase 4):**
   * Kết nối đồng bộ hai chiều với ATS/HRIS và Email Gateway chạy ổn định, không phát sinh lỗi mất gói tin.
   * Quy trình xin Consent cho Talent Pool được Legal phê duyệt và 100% ứng viên lưu kho có xác nhận đồng ý rõ ràng.
   * Tính năng phỏng vấn tự động đồng bộ lịch Outlook hoạt động chính xác với tỷ lệ phản hồi tích cực từ Hiring Manager đạt ≥ 85%.
   * Mô hình NLP xử lý song ngữ Anh - Việt đạt độ chính xác trích xuất tương đương phiên bản tiếng Anh đơn ngữ.
4. **Cổng 4 (Cuối Tuần 8 — Nghiệm thu Tổng thể Toàn bộ Hệ sinh thái HRA):**
   * Hệ thống phễu phân tích báo cáo và kiểm toán chống thiên lệch thuật toán (Anti-bias Audit) hoạt động chính xác, đảm bảo tách biệt 100% dữ liệu nhân khẩu học nhạy cảm khỏi thuật toán matching.
   * Cổng ứng viên tự phục vụ và Chatbot AI 24/7 vận hành ổn định, không có lỗi bảo mật hoặc thông tin sai lệch.
   * Hoàn thành kiểm thử tải (Stress Test) và quét lỗ hổng bảo mật an toàn thông tin (Penetration Test) có xác nhận của IT VinUni.
   * Bàn giao đầy đủ tài liệu hướng dẫn vận hành, quy chế bảo vệ dữ liệu và tổ chức đào tạo chuyển giao cho toàn thể người dùng.

---

## 7. Nguyên tắc Vận hành Bất biến (Core Operating Principles)

1. **Con người nắm toàn quyền quyết định (Human-in-control):** Mọi điểm số, phân nhóm và gợi ý của AI chỉ mang tính chất tham mưu, hỗ trợ tối ưu hóa năng suất. Quyết định lựa chọn, đưa vào Shortlist, từ chối hay tuyển dụng ứng viên **hoàn toàn do con người (HR và Hiring Manager) thực hiện**.
2. **Minh bạch và Luôn có Dẫn chứng (Explainability with Evidence):** Không chấp nhận bất kỳ cơ chế chấm điểm "hộp đen" nào. Mọi đánh giá của hệ thống phải truy nguyên được về từng câu chữ trong hồ sơ gốc và trọng số trong rubric đã phê duyệt.
3. **Bảo vệ Quyền riêng tư theo Tiêu chuẩn Quốc tế (Privacy by Design):** Toàn bộ dữ liệu ứng viên được bảo vệ nghiêm ngặt theo Nghị định 13/2023/NĐ-CP và tiêu chuẩn bảo mật dữ liệu giáo dục quốc tế. Dữ liệu phải được mã hóa, giới hạn quyền truy cập theo vị trí và xóa dứt điểm khi hết thời hạn quy định.
