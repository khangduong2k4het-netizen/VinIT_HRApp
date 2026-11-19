## VinUni AI-Native CV Matching & Ranking

> **Lưu ý triển khai (05/11/2026):** Tài liệu này mô tả yêu cầu/thiết kế mục tiêu, không phải xác nhận các chức năng đã nghiệm thu. Trạng thái mã, giới hạn privacy/recovery và trạng thái migration trên project Supabase kết nối được theo dõi tại [PHASE1_GAP_ANALYSIS.md](../audit/PHASE1_GAP_ANALYSIS.md) và [DEPLOYMENT.md](../DEPLOYMENT.md).

| Thuộc tính | Giá trị |
|---|---|
| **Phiên bản** | 1.0 — Draft for Review |
| **Trạng thái** | Bản Product Definition/Discovery dựa trên đề xuất từ BA |
| **Phạm vi nghiệp vụ** | Tuyển dụng các vị trí không phải giảng viên |
| **Nhóm pilot** | Các vị trí liên quan đến IT |
| **Người dùng chính** | HR Recruiter |
| **Quyết định tuyển dụng** | Do HR thực hiện; AI chỉ hỗ trợ phân tích và ưu tiên rà soát |

> **Lưu ý phạm vi:** Tài liệu xác định sản phẩm và trải nghiệm nghiệp vụ. Không đặc tả kiến trúc, cơ sở dữ liệu, API, công nghệ, triển khai hoặc cách xây dựng mô hình.

---

## Bối cảnh sản phẩm đã thống nhất

VinUni muốn xây dựng một hệ thống AI-Native hỗ trợ HR matching và ranking CV theo JD. Trong MVP, HR tải CV lên hệ thống; AI hỗ trợ trích xuất, đề xuất tiêu chí từ JD, đối chiếu từng CV và xếp hạng ứng viên trong cùng một vị trí.

Hệ thống cần cho HR thấy **bằng chứng và lý do** đằng sau kết quả. Hồ sơ thiếu bằng chứng, độ tin cậy thấp hoặc không đọc được phải được đưa vào luồng cần xác minh, không tự động bị loại. HR vẫn xác nhận trạng thái tuyển dụng và quyết định cuối cùng.

---

# Artifact 1 - Product Vision

## Vision Statement

Tạo ra một quy trình tuyển dụng tại VinUni trong đó mỗi ứng viên được xem xét theo các tiêu chí đã thống nhất cho vị trí, mọi nhận định đều có thể kiểm tra bằng bằng chứng trong hồ sơ, và HR có thể ưu tiên rà soát số lượng lớn CV mà không đánh mất quyền kiểm soát quyết định.

## Mission Statement

Giúp HR và Hiring Manager biến JD và CV thành một quy trình sàng lọc rõ ràng, nhất quán, có thể giải thích và phù hợp với yêu cầu bảo vệ dữ liệu ứng viên.

## Product Definition

**VinUni AI-Native CV Matching & Ranking** là sản phẩm hỗ trợ tuyển dụng, dành cho HR Recruiter, Hiring Manager và các bên có trách nhiệm liên quan.

Sản phẩm giúp:

- Tạo và duyệt bộ tiêu chí sàng lọc dựa trên JD.
- Tiếp nhận CV theo lô và nhận biết hồ sơ cần kiểm tra.
- Tìm bằng chứng trong CV để đối chiếu từng tiêu chí.
- Phân nhóm và xếp hạng ứng viên trong cùng một vị trí.
- Ghi nhận quyết định và duy trì quyền quyết định của HR.

Sản phẩm **không thay thế** HR/ Hiring Manager và không tự kết luận ứng viên được tuyển, bị loại, hoặc không trúng tuyển.

## Success Vision

Khi sản phẩm đạt mục tiêu:

- HR không cần đọc và ghi chú lại mọi nội dung CV theo cách thủ công.
- Các ứng viên cho cùng một vị trí được xem xét theo cùng một bộ tiêu chí đã duyệt.
- HR có thể xác định nhanh hồ sơ nào đủ bằng chứng, hồ sơ nào cần xác minh và hồ sơ nào có dấu hiệu không đáp ứng tiêu chí bắt buộc.
- Mọi điểm và thứ hạng đều có thể giải thích từ trọng số, kết quả từng tiêu chí và bằng chứng trong CV.
- CV không đọc được hoặc thiếu thông tin không bị loại âm thầm.
- Hiring Manager tập trung vào tiêu chí chuyên môn và phản hồi shortlist.
- Dữ liệu ứng viên được truy cập, lưu trữ và xóa theo chính sách đã được VinUni phê duyệt.

## Design Decisions

1. Tập trung vào **quyết định có căn cứ**, không chỉ tạo điểm số.
2. AI có thể đề xuất tiêu chí, matching và ranking; HR/Hiring Manager phải xác nhận những nội dung thuộc thẩm quyền của họ.
3. “Chưa rõ” hoặc “chưa tìm thấy bằng chứng” không được quy đổi thành “không đáp ứng”.
4. “Có dấu hiệu miss-match” là nhóm cần rà soát, không phải trạng thái tuyển dụng.
5. MVP chỉ xử lý CV và JD tiếng Anh; giao diện hỗ trợ tiếng Việt/tiếng Anh, mặc định tiếng Việt.
6. Pilot tập trung vào các vị trí liên quan đến IT; khả năng mở rộng sang các nhóm vị trí khác được đánh giá sau pilot.

---

# Artifact 2 - Product Define

## Product Category

Sản phẩm hỗ trợ sàng lọc tuyển dụng theo tiêu chí, có AI hỗ trợ đối chiếu bằng chứng và ưu tiên rà soát ứng viên.

## Target Market

### Thị trường ban đầu

- Bộ phận tuyển dụng HR của VinUni.
- Các vị trí không phải giảng viên.
- Pilot gồm các vị trí liên quan đến IT: Software Engineer, QA, DevOps, Data Engineer, IT Support và các vai trò IT khác.

### Mở rộng tiềm năng

Sau khi đánh giá hiệu quả và tính phù hợp của rubric, sản phẩm có thể mở rộng sang các nhóm vị trí không phải giảng viên khác.

## Product Positioning

> Dành cho HR và Hiring Manager VinUni cần sàng lọc nhiều CV, sản phẩm cung cấp một cách thức đối chiếu hồ sơ với tiêu chí của từng vị trí, hiển thị bằng chứng và ranking có giải thích — trong khi HR vẫn giữ quyền quyết định tuyển dụng.

## Competitive Landscape

Các lựa chọn thay thế cần được xem xét trong quá trình Discovery gồm:

- Đọc CV và theo dõi ứng viên thủ công bằng email, bảng tính hoặc tài liệu nội bộ.
- Tính năng tìm kiếm, lọc hoặc quản lý ứng viên trong hệ thống tuyển dụng hiện có.
- Công cụ AI tổng quát hỗ trợ đọc hoặc tóm tắt CV.
- Quy trình nội bộ kết hợp giữa HR và Hiring Manager.

Hiện chưa có khảo sát để xác nhận VinUni đang sử dụng công cụ nào hoặc so sánh với sản phẩm cụ thể. Đây là nội dung cần bổ sung nếu VinUni muốn làm phân tích cạnh tranh chi tiết.

## Product Differentiation

- **Theo rubric của từng vị trí:** Không áp dụng một bộ tiêu chí chung cho mọi ứng viên.
- **Có bằng chứng:** Nhận định phải liên kết với nội dung CV; nếu không có bằng chứng, hệ thống phải nói rõ.
- **Tách rõ thiếu thông tin và không đáp ứng:** Không dùng việc CV thiếu thông tin làm căn cứ tự động loại.
- **Ranking có giải thích:** Thứ hạng chỉ so sánh trong cùng vị trí, thể hiện trọng số, độ phủ bằng chứng và kết quả tiêu chí.
- **Human-in-control:** HR quyết định trạng thái ứng viên; Hiring Manager phê duyệt tiêu chí chuyên môn.
- **Có luồng xử lý ngoại lệ:** CV lỗi, PDF bị khóa, nội dung quá mờ, confidence thấp và hồ sơ có khả năng trùng đều được đưa ra để HR xử lý.
- **Có kiểm soát dữ liệu:** Ưu tiên xử lý cục bộ; dịch vụ bên ngoài chỉ dùng trong giai đoạn kiểm thử theo điều kiện được phê duyệt.

## Design Decisions

1. Định vị sản phẩm là **công cụ hỗ trợ quyết định**, không phải công cụ tự động tuyển dụng.
2. Định vị sản phẩm như một ATS có tiềm năng thay thế hệ thống tuyển dụng hiện có.
3. Không dùng thông tin cá nhân không liên quan đến công việc để tạo lợi thế cạnh tranh hoặc đánh giá ứng viên.
4. Chưa đưa ra tuyên bố so sánh chất lượng với nhà cung cấp bên ngoài khi chưa có khảo sát và dữ liệu kiểm chứng.

---

# Artifact 3 — Value Proposition

## User Value

### HR Recruiter

- Giảm thao tác đọc và ghi chú lặp lại.
- Có danh sách ứng viên được sắp xếp theo tiêu chí và mức độ đầy đủ của bằng chứng.
- Xem nhanh nhận định của hệ thống rồi kiểm tra lại nội dung CV gốc.
- Biết hồ sơ nào cần xác minh thay vì phải tự phát hiện mọi trường hợp ngoại lệ.
- Lưu được lý do cho quyết định sàng lọc.

### Hiring Manager

- Xác nhận tiêu chí chuyên môn trước khi HR bắt đầu sàng lọc.
- Xem shortlist kèm nội dung đánh giá và ghi chú của HR.
- Tập trung phản hồi về mức độ phù hợp chuyên môn thay vì thống nhất tiêu chí sau khi CV đã được đọc.

### HR Lead

- Theo dõi tình hình xử lý CV, hồ sơ tồn đọng và các vị trí cần hỗ trợ.
- Có dữ liệu để nhận diện điểm nghẽn của quy trình và đánh giá pilot.

## Business Value

- Tăng khả năng xử lý khối lượng CV lớn mà không cần tăng tương ứng số thao tác thủ công.
- Tăng tính nhất quán giữa các lần sàng lọc và giữa HR với Hiring Manager.
- Giảm nguy cơ bỏ sót ứng viên phù hợp do CV nhiều hoặc tiêu chí chưa được chuẩn hóa.
- Tăng khả năng giải thích và truy xuất căn cứ cho quyết định sàng lọc.
- Tạo dữ liệu thực tế để cải thiện quy trình tuyển dụng các đợt tiếp theo.

## AI Value

AI có giá trị ở cấp độ sản phẩm khi có thể:

- Chuyển nội dung CV thành thông tin nghề nghiệp có cấu trúc để HR so sánh.
- Gợi ý bản nháp tiêu chí từ JD để HR và Hiring Manager duyệt.
- Tìm bằng chứng liên quan trong CV và đối chiếu với từng tiêu chí.
- Ưu tiên hồ sơ theo rubric đã duyệt mà không tự quyết định kết quả tuyển dụng.
- Nhận biết khi bằng chứng không đủ hoặc hồ sơ khó xử lý, để yêu cầu HR xác minh.

Giá trị AI không được đo bằng số lượng tính năng AI, mà bằng việc HR có thể đưa ra quyết định tốt hơn với ít thao tác hơn và không tăng nguy cơ loại nhầm ứng viên.

## Product Value

Sản phẩm kết hợp khả năng xử lý CV số lượng lớn với cách đánh giá dễ kiểm tra: **tìm bằng chứng, phân biệt mức độ chắc chắn, xếp hạng theo rubric và để HR ra quyết định**.

## Design Decisions

1. Điểm số phải giải thích được; không hiển thị điểm như một kết luận độc lập.
2. Điểm matching và độ tin cậy/độ phủ bằng chứng phải được thể hiện riêng.
3. Mọi trạng thái “Chưa rõ” cần có lý do như thiếu thông tin, nội dung mơ hồ hoặc độ tin cậy thấp.
4. AI không tạo đánh giá về tính cách, “culture fit” hoặc những năng lực không có bằng chứng trong hồ sơ.

---

# Artifact 4 — Product Scope

## In Scope

### Quản lý vị trí và JD

- Tạo vị trí, khai báo phòng ban, Hiring Manager và JD.
- Trạng thái vị trí: Mở / Tạm dừng / Đóng.
- JD sử dụng tiếng Anh trong MVP.

### Tiêu chí tuyển dụng

- AI đề xuất tiêu chí dưới dạng bản nháp từ JD.
- HR rà soát độ rõ ràng, nhất quán và phù hợp quy trình.
- Hiring Manager phê duyệt nội dung chuyên môn.
- Tiêu chí phân loại Bắt buộc / Ưu tiên.
- Trọng số mặc định: nhóm Bắt buộc 70%, nhóm Ưu tiên 30%; điều chỉnh được và tổng phải bằng 100%.
- Rubric gồm: Đáp ứng tốt / Đáp ứng / Chưa rõ / Chưa đáp ứng.
- Không dùng tuổi, giới tính, ngoại hình hoặc thông tin không liên quan đến công việc làm tiêu chí đánh giá.
- Lưu phiên bản tiêu chí để có thể giải thích kết quả matching.

### Tiếp nhận và xử lý CV

- Tải CV theo batch, tối đa 50 file/batch.
- Tối đa 10 MB/file; tổng dung lượng tối đa 250 MB/batch.
- Hỗ trợ PDF và DOCX; MVP xử lý CV tiếng Anh.
- Đọc PDF có văn bản, OCR PDF scan, trích xuất văn bản thông thường từ DOCX.
- OCR PDF scan; không hỗ trợ OCR ảnh CV rời trong MVP.
- CV không đọc được, PDF bị khóa hoặc nội dung quá mờ được gắn “Cần HR kiểm tra”.
- Cảnh báo CV giống hệt hoặc có dấu hiệu cùng ứng viên trong cùng một vị trí; HR quyết định xử lý.
- Cho phép HR chỉnh sửa thông tin trích xuất sai.

### Matching, ranking và quản lý ứng viên

- Đánh giá từng CV theo tiêu chí đã duyệt, kèm bằng chứng trích dẫn.
- Phân biệt Đáp ứng tốt / Đáp ứng / Chưa rõ / Chưa đáp ứng.
- Ranking trong cùng một vị trí, ưu tiên mức đáp ứng tiêu chí bắt buộc trước điểm.
- Độ phủ bằng chứng dưới 70%: hiển thị “Chưa đủ dữ liệu để xếp hạng ổn định”.
- HR xác nhận trạng thái ứng viên.
- Trạng thái gồm Mới, Đang xem, Shortlist, Bị loại ở vòng sàng lọc, Đang phỏng vấn, Không trúng tuyển, Trúng tuyển, Đã nhận việc.
- Hiring Manager phê duyệt tiêu chí và xem shortlist được chia sẻ.

### Quản trị và quyền riêng tư

- Giao diện song ngữ Việt/Anh, mặc định tiếng Việt.
- Đăng nhập bằng email và mật khẩu nội bộ trong MVP; SSO dự kiến Phase 2.
- Quyền truy cập theo vai trò và vị trí được giao.
- Dashboard và báo cáo theo vai trò.
- Audit log cho các thao tác quan trọng.
- Ưu tiên xử lý cục bộ; quản trị viên được cấu hình lựa chọn model/chế độ xử lý đã được phê duyệt. Dịch vụ bên ngoài chỉ dùng cho kiểm thử trong giai đoạn đầu.
- Thời hạn lưu hồ sơ là 12 tháng từ ngày đóng vị trí; đến hạn cần HR xác nhận xóa.
- Xóa theo hồ sơ ứng tuyển. Nếu vị trí mở lại trước khi xóa, khởi động lại thời hạn từ ngày đóng mới.

## Out of Scope

- Crawl CV từ nguồn online trong MVP; ghi nhận cho Phase 2.
- SSO trong MVP; ghi nhận cho Phase 2.
- Tự động shortlist, loại ứng viên hoặc thay đổi trạng thái tuyển dụng.
- Dùng ngưỡng điểm để quyết định ứng viên được tuyển hay bị loại.
- So sánh ranking giữa các vị trí tuyển dụng khác nhau.
- Tuyển dụng giảng viên.
- Quản lý phỏng vấn chi tiết, đề nghị tuyển dụng, onboarding.
- OCR ảnh CV rời và tự động matching CV không phải tiếng Anh.
- Đánh giá “culture fit”, tính cách hoặc đặc tính cá nhân không liên quan đến công việc.
- Sử dụng dịch vụ xử lý bên ngoài với CV thật trong production nếu chưa được phê duyệt riêng.

## Assumptions

- VinUni cung cấp JD và CV mẫu được phép sử dụng để kiểm thử.
- HR và Hiring Manager có thể thống nhất tiêu chí cho các vị trí pilot.
- CV tiếng Anh, PDF và DOCX là đầu vào chính trong MVP.
- Hạ tầng xử lý nội bộ hoặc model cục bộ được ưu tiên.
- HR cung cấp hoặc xác nhận kết quả tham chiếu dùng để đánh giá matching/ranking.
- Baseline thời gian xử lý hiện tại chưa có và sẽ được thu thập trong pilot.

## Constraints

- Tuân thủ pháp luật hiện hành và chính sách xử lý dữ liệu của VinUni.
- Thời hạn retention hiện được xác định là 12 tháng từ ngày đóng vị trí, áp dụng cho cả hồ sơ chưa có kết quả và không có thời hạn riêng cho ứng viên trúng tuyển/đã nhận việc theo quyết định hiện tại. Legal/Privacy cần xác nhận trước khi áp dụng chính thức.
- CV không đọc được không được xem là không đáp ứng.
- Không có điểm hoặc ngưỡng nào tự động quyết định kết quả tuyển dụng.
- Các mốc 30 giây–2 phút cho danh sách và 2–5 phút/ứng viên cho rà soát chi tiết là ước lượng ban đầu, không phải SLA hoặc tiêu chí nghiệm thu.

## Success Metrics

| Chỉ số | Cách sử dụng |
|---|---|
| Thời gian HR rà soát một hồ sơ | Đo baseline trong pilot; đặt mục tiêu giảm sau khi có số liệu |
| Chất lượng trích xuất | Đo theo từng nhóm thông tin trên CV kiểm thử |
| Độ chính xác bằng chứng | Đo tỷ lệ trích dẫn hỗ trợ đúng nhận định |
| Sai lệch ở tiêu chí bắt buộc | Theo dõi đặc biệt trường hợp ứng viên đạt nhưng hệ thống xếp “Chưa đáp ứng” |
| Chất lượng ranking | Đánh giá thứ tự ứng viên trong cùng JD |
| Số hồ sơ cần HR kiểm tra | Theo dõi để hiểu chất lượng đầu vào và khả năng xử lý ngoại lệ |
| Thay đổi trạng thái do HR | Đảm bảo mọi quyết định tuyển dụng có người dùng thực hiện |
| Vi phạm quyền truy cập/sự cố dữ liệu | Mục tiêu không có sự cố nghiêm trọng trong pilot |

Ngưỡng đánh giá AI tại Artifact 10 là **mục tiêu khởi điểm để kiểm thử**, chưa phải cam kết cuối cùng.

## Design Decisions

1. MVP ưu tiên chất lượng matching và tính giải thích được trước khi mở rộng nguồn CV.
2. Không đưa baseline giảm thời gian vào KPI cam kết khi chưa đo được quy trình hiện tại.
3. Retention 12 tháng được ghi nhận là quyết định nghiệp vụ của VinUni; cần kiểm chứng phạm vi áp dụng với Legal/Privacy.
4. Lịch xóa được tính theo vị trí nhưng thao tác xóa áp dụng theo hồ sơ ứng tuyển.
5. Xóa cần người có quyền HR xác nhận; chưa có xác nhận thì hồ sơ ở trạng thái chờ xử lý.

---

# Artifact 5 — User Persona

## Cách phân khúc

Phân khúc theo **vai trò và quyền ra quyết định trong quy trình tuyển dụng**, vì đây là yếu tố quyết định người dùng được xem, sửa, duyệt và quyết định nội dung nào.

## Persona 1 — HR Recruiter

**Vai trò:** Persona chính.

### Background

- Thực hiện các bước tiếp nhận, đọc, rà soát và sàng lọc CV.
- Phối hợp với Hiring Manager để hiểu nhu cầu tuyển dụng.
- Có thể phụ trách một hoặc nhiều vị trí cùng lúc.

### Goals

- Xử lý CV số lượng lớn mà không bỏ sót hồ sơ.
- Áp dụng tiêu chí nhất quán cho cùng một vị trí.
- Tìm được bằng chứng nhanh và lập shortlist có căn cứ.
- Ghi nhận quyết định và lý do để trao đổi với Hiring Manager.

### Behaviors

- Đối chiếu CV với JD và tiêu chí.
- Đánh dấu trường hợp cần xác minh.
- Ghi chú, cập nhật trạng thái và chia sẻ hồ sơ phù hợp.
- Kiểm tra lại CV gốc trước khi quyết định.

### Pain Points

- Đọc CV lặp lại và tìm thông tin thủ công.
- Khó so sánh hồ sơ khi tiêu chí chưa đủ rõ.
- Hồ sơ nhiều định dạng hoặc chất lượng kém làm tăng thời gian xử lý.
- CV thiếu thông tin có thể bị hiểu nhầm là không đáp ứng.
- Khó truy lại vì sao một ứng viên được đưa vào hoặc ra khỏi shortlist.

### Motivations

- Làm việc nhanh hơn nhưng không giảm chất lượng.
- Có thể giải thích đánh giá của mình với Hiring Manager.
- Giảm việc ghi chép trùng lặp và xử lý các lỗi không cần thiết.

### AI Expectations

- Đề xuất tiêu chí để HR rà soát, không tự áp dụng tiêu chí chưa duyệt.
- Chỉ đưa ra matching khi có bằng chứng hoặc nêu rõ vì sao chưa thể đánh giá.
- Giải thích điểm và thứ hạng.
- Không tự loại ứng viên hoặc thay đổi trạng thái.

### Design Decisions

- HR là người dùng chính và người ra quyết định trạng thái ứng viên.
- Danh sách ưu tiên cần cho HR thấy nhóm matching, trạng thái tiêu chí bắt buộc, điểm và độ phủ bằng chứng.
- Chi tiết hồ sơ cần liên kết nhận định với nội dung CV gốc.
- Mốc thời gian xem danh sách/hồ sơ hiện chỉ là ước lượng, cần kiểm chứng trong pilot.

## Persona 2 — Hiring Manager

### Background

- Có trách nhiệm xác định năng lực chuyên môn cần có cho vị trí.
- Phối hợp với HR trong xây dựng tiêu chí và đánh giá shortlist.

### Goals

- Đảm bảo tiêu chí phản ánh đúng yêu cầu công việc.
- Nhận shortlist có bằng chứng và bối cảnh rõ ràng.
- Phản hồi nhanh để không làm chậm quy trình tuyển dụng.

### Behaviors

- Cung cấp hoặc rà soát JD.
- Phê duyệt tiêu chí chuyên môn.
- Xem shortlist và phản hồi HR.

### Pain Points

- JD có thể chưa diễn đạt rõ tiêu chí sàng lọc.
- Shortlist thiếu bằng chứng hoặc không giải thích được vì sao được chọn.
- Có thể phải xem lại nhiều CV không đáp ứng nhu cầu.

### Motivations

- Giảm thời gian đánh giá hồ sơ không liên quan.
- Được xem xét các ứng viên có khả năng phù hợp cao.
- Có tiếng nói rõ ràng trong việc phê duyệt tiêu chí.

### AI Expectations

- Gợi ý tiêu chí có thể truy về nội dung JD.
- Không biến suy luận của hệ thống thành yêu cầu bắt buộc.
- Kết quả matching phải cho thấy bằng chứng và mức độ chắc chắn.

### Design Decisions

- Hiring Manager duyệt chuyên môn, HR xác nhận tiêu chí rõ ràng và phù hợp quy trình.
- Hiring Manager chỉ xem các vị trí được giao và shortlist được chia sẻ, trừ khi có quyền khác được phê duyệt.

## Persona 3 — HR Lead

### Background

- Quản lý hoạt động của nhóm tuyển dụng và tiến độ các vị trí.
- Có nhu cầu theo dõi số lượng hồ sơ, tồn đọng và chất lượng quy trình.

### Goals

- Biết vị trí hoặc bước nào đang bị tắc nghẽn.
- Đánh giá lợi ích và rủi ro của sản phẩm.
- Đảm bảo việc sử dụng nhất quán giữa các recruiter.

### Behaviors

- Theo dõi số liệu tổng hợp.
- Hỗ trợ chuẩn hóa quy trình và tiêu chí.
- Xử lý hoặc phân công các vấn đề phát sinh.

### Pain Points

- Thiếu dữ liệu nhất quán về khối lượng và thời gian xử lý.
- Khó phân biệt vấn đề do JD, CV hay quy trình.
- Có thể thiếu cơ sở để quyết định mở rộng pilot.

### Motivations

- Có dữ liệu để cải thiện quy trình.
- Giảm tình trạng hồ sơ tồn đọng hoặc thiếu người phụ trách.
- Duy trì chất lượng tuyển dụng khi khối lượng tăng.

### AI Expectations

- Báo cáo phải phân biệt rõ gợi ý của hệ thống và quyết định của HR.
- Tỷ lệ HR ghi đè gợi ý cần được dùng để cải thiện sản phẩm, không tự động xem là lỗi của HR.

### Design Decisions

- HR Lead xem báo cáo tổng hợp theo phạm vi được cấp.
- Quyền xem CV chi tiết không mặc định được cấp chỉ vì người dùng là HR Lead.

## Persona 4 — Admin/Người quản trị sản phẩm

### Background

- Quản lý tài khoản, quyền và các cấu hình được VinUni phê duyệt.
- Phối hợp với IT/Security và các bộ phận phụ trách dữ liệu.

### Goals

- Bảo đảm quyền truy cập phù hợp.
- Hỗ trợ quản trị chế độ xử lý và model đã được phê duyệt.
- Có thể kiểm tra các thay đổi quan trọng.

### Behaviors

- Cấp, điều chỉnh hoặc khóa quyền.
- Quản lý danh mục lựa chọn xử lý được phép.
- Rà soát audit và hỗ trợ người dùng.

### Pain Points

- Khó quản lý rủi ro nếu người dùng tự chọn dịch vụ hoặc quyền quá rộng.
- Cần hỗ trợ vận hành mà không nhất thiết phải xem CV.

### Motivations

- Bảo vệ dữ liệu ứng viên.
- Quản lý sản phẩm theo chính sách của VinUni.

### AI Expectations

- Có thể cấu hình lựa chọn model/chế độ xử lý đã được phê duyệt.
- Mặc định ưu tiên xử lý cục bộ; dịch vụ bên ngoài chỉ được dùng trong kiểm thử ban đầu.
- Mọi thay đổi quan trọng phải truy xuất được.

### Design Decisions

- Admin không mặc định được xem CV hoặc quyết định xóa hồ sơ.
- Quyền xác nhận xóa thuộc HR được ủy quyền.

---

# Artifact 6 — User Journey

## Primary Persona: HR Recruiter

### Trigger

Một vị trí IT được mở và nhận lượng CV lớn trong một khoảng thời gian ngắn.

### Goal

Tạo shortlist có căn cứ cho Hiring Manager trong khi xử lý hồ sơ nhất quán và giảm công sức đọc thủ công.

### Current Workflow

1. Nhận JD và làm rõ nhu cầu với Hiring Manager.
2. Tự xác định hoặc trao đổi các tiêu chí cần sàng lọc.
3. Nhận CV từ các nguồn hiện có.
4. Mở từng CV, đọc và ghi chú thủ công.
5. So sánh hồ sơ với tiêu chí theo cách riêng của recruiter.
6. Tổng hợp shortlist và chia sẻ cho Hiring Manager.
7. Cập nhật trạng thái và kết quả sau các vòng tiếp theo.

### Pain Points

- HR phải lặp lại thao tác đọc, tìm và ghi thông tin trên nhiều CV.
- Tiêu chí không phải lúc nào cũng được diễn đạt hoặc áp dụng giống nhau.
- Khó nhận biết CV phù hợp nhưng trình bày khác chuẩn hoặc thiếu một số thông tin.
- Hồ sơ lỗi, PDF scan, PDF khóa hoặc quá mờ làm tăng thao tác.
- Ranking thủ công khó kiểm tra lại và khó giải thích.
- Baseline thời gian và chất lượng quy trình chưa được đo thống nhất.

### AI Opportunity

- Gợi ý bản nháp tiêu chí từ JD để HR và Hiring Manager duyệt.
- Trích xuất thông tin và bằng chứng liên quan từ CV tiếng Anh.
- Đánh giá từng tiêu chí theo rubric đã duyệt.
- Sắp xếp ứng viên trong cùng một requisition theo mức đáp ứng tiêu chí bắt buộc rồi đến điểm.
- Phát hiện trạng thái chưa chắc chắn, thiếu bằng chứng, file không đọc được hoặc hồ sơ có khả năng trùng.
- Giải thích kết quả bằng bằng chứng và cách tính điểm.

### Desired Experience

1. **HR và Hiring Manager thống nhất nhu cầu:** JD được làm rõ; tiêu chí được HR rà soát và Hiring Manager phê duyệt.
2. **HR tiếp nhận hồ sơ:** CV được tập hợp theo vị trí; từng file có trạng thái xử lý rõ ràng.
3. **HR xem danh sách ưu tiên:** nhận biết hồ sơ đáp ứng tiêu chí bắt buộc, cần xác minh hoặc có dấu hiệu miss-match.
4. **HR kiểm tra bằng chứng:** xem nhận định theo từng tiêu chí và đối chiếu với CV gốc.
5. **HR quyết định:** cập nhật trạng thái, ghi lý do khi cần và chia sẻ shortlist cho Hiring Manager.
6. **Hiring Manager phản hồi:** xem các hồ sơ được chia sẻ, bình luận hoặc yêu cầu HR xác minh thêm.
7. **HR theo dõi kết quả:** cập nhật trạng thái sau phỏng vấn, đóng vị trí và xử lý lưu/xóa theo chính sách.

### JTBD được thực hiện trong hành trình

| JTBD | Điểm trong hành trình |
|---|---|
| JTBD-01 — Chuyển JD thành tiêu chí đã duyệt | Bước 1 |
| JTBD-02 — Tiếp nhận và theo dõi CV theo lô | Bước 2 |
| JTBD-03 — Tìm và đánh giá bằng chứng trong CV | Bước 3–4 |
| JTBD-04 — Ưu tiên rà soát theo ranking có giải thích | Bước 3 |
| JTBD-05 — Xử lý hồ sơ chưa rõ, lỗi hoặc có dấu hiệu trùng | Bước 2–4 |
| JTBD-06 — Ghi nhận quyết định và chia sẻ shortlist | Bước 5–6 |
| JTBD-07 — Theo dõi tiến độ và điểm nghẽn | Bước 7 |
| JTBD-08 — Bảo vệ dữ liệu và quản trị quyền sử dụng | Điều kiện xuyên suốt, đặc biệt bước 2 và 7 |
| JTBD-09 — Duyệt tiêu chí và phản hồi shortlist | Bước 1 và 6 |

### Design Decisions

- Hành trình lấy HR Recruiter làm trung tâm nhưng bao gồm các điểm hợp tác với Hiring Manager.
- Trải nghiệm có ba mức thông tin: danh sách tổng quan cho HR, bằng chứng/CV gốc cho HR khi rà soát, và tóm tắt shortlist cho Hiring Manager.
- Ước lượng 30 giây–2 phút ở mức danh sách và 2–5 phút/ứng viên ở mức chi tiết chỉ là giả thuyết trải nghiệm.
- Hành trình phải có đường xử lý ngoại lệ; CV không đọc được không được kết thúc bằng kết luận tự động.

---

# Artifact 7 — Business Flow

## Business Goal

Tuyển được ứng viên đáp ứng nhu cầu của vị trí theo quy trình rõ ràng, có sự phối hợp giữa HR và Hiring Manager.

## Business Activity

1. **Xác nhận nhu cầu tuyển dụng**
   - Đơn vị tuyển dụng xác định nhu cầu, số lượng và thời điểm.
   - HR làm rõ JD và quy trình tuyển dụng với Hiring Manager.

2. **Thống nhất tiêu chí**
   - HR và Hiring Manager xác định tiêu chí bắt buộc và tiêu chí ưu tiên.
   - HR kiểm tra tính rõ ràng, nhất quán và phù hợp quy trình.
   - Hiring Manager phê duyệt nội dung chuyên môn.

3. **Tiếp nhận hồ sơ**
   - HR tiếp nhận CV và gắn hồ sơ vào vị trí ứng tuyển.
   - HR rà soát các hồ sơ trùng, không đọc được hoặc cần xác minh.

4. **Đánh giá ứng viên**
   - HR xem xét hồ sơ theo tiêu chí đã duyệt.
   - HR kiểm tra bằng chứng và yêu cầu xác minh thêm khi thông tin chưa đủ.

5. **Ra quyết định sàng lọc**
   - HR đưa ứng viên vào shortlist, tiếp tục xem xét hoặc đánh dấu “Bị loại” ở vòng sàng lọc.
   - Mỗi quyết định có lý do phù hợp với yêu cầu công việc.

6. **Phối hợp với Hiring Manager**
   - HR chia sẻ shortlist.
   - Hiring Manager phản hồi hoặc đề nghị làm rõ thêm.
   - HR cập nhật quyết định chính thức của hồ sơ.

7. **Theo dõi kết quả tuyển dụng**
   - Các bên cập nhật trạng thái phỏng vấn, “Không trúng tuyển”, “Trúng tuyển” hoặc “Đã nhận việc” theo quy trình.

8. **Đóng vị trí và quản lý hồ sơ**
   - Khi đóng vị trí, thời hạn lưu hồ sơ ứng tuyển bắt đầu được tính.
   - Sau 12 tháng, HR xem danh sách hồ sơ đến hạn và xác nhận việc xóa.
   - Nếu vị trí được mở lại trước khi xóa, thời hạn được khởi động lại sau lần đóng tiếp theo.

## Business Decision

- Tiêu chí chuyên môn được Hiring Manager phê duyệt.
- HR xác nhận tiêu chí đủ rõ và phù hợp quy trình.
- HR quyết định ứng viên được shortlist, bị loại ở vòng sàng lọc hoặc chuyển sang bước tiếp theo.
- Hiring Manager phản hồi shortlist nhưng không tự động thay đổi trạng thái chính thức.
- HR xác nhận kết quả cuối cùng và xác nhận xóa hồ sơ đến hạn.

## Business Outcome

- Tiêu chí tuyển dụng đã được thống nhất.
- Hồ sơ được xem xét nhất quán và có thể truy xuất lý do.
- Shortlist được tạo và phản hồi có cấu trúc.
- Kết quả tuyển dụng được cập nhật.
- Hồ sơ được lưu và xóa theo chính sách được phê duyệt.

## Design Decisions

- Trạng thái hồ sơ ứng tuyển và trạng thái xử lý file là hai loại thông tin riêng.
- “Bị loại” chỉ áp dụng ở vòng sàng lọc; “Không trúng tuyển” áp dụng sau phỏng vấn.
- “Trúng tuyển” và “Đã nhận việc” là các trạng thái riêng.
- Hồ sơ không có kết quả vẫn thuộc phạm vi retention 12 tháng kể từ ngày đóng vị trí theo quyết định hiện tại; phạm vi này cần Legal/Privacy xác nhận.

---

# Artifact 8 — AI Capability Map

## Capability AIC-01 — Hiểu nội dung CV và trích xuất thông tin nghề nghiệp

**Description:** Nhận diện các thông tin liên quan đến kinh nghiệm, học vấn, kỹ năng, chứng chỉ và ngôn ngữ từ CV tiếng Anh. Với PDF scan, sản phẩm cần hỗ trợ đọc nội dung nhưng thể hiện khi kết quả không đủ tin cậy.

**JTBD Mapping:** JTBD-02, JTBD-03, JTBD-05.  
**Business Goal Mapping:** BG-01, BG-03, BG-05.

## Capability AIC-02 — Cấu trúc tiêu chí từ JD thành bản nháp

**Description:** Chuyển nội dung JD tiếng Anh thành các tiêu chí Bắt buộc/Ưu tiên có thể được HR và Hiring Manager rà soát. Bản nháp cần cho biết nội dung JD nào làm căn cứ; không được tự áp dụng.

**JTBD Mapping:** JTBD-01, JTBD-09.  
**Business Goal Mapping:** BG-02, BG-04.

## Capability AIC-03 — Đối chiếu tiêu chí với bằng chứng trong CV

**Description:** Đánh giá từng tiêu chí bằng bốn mức đã thống nhất: Đáp ứng tốt / Đáp ứng / Chưa rõ / Chưa đáp ứng. Gợi ý phải kèm trích dẫn hoặc nêu rõ rằng chưa tìm thấy bằng chứng.

**JTBD Mapping:** JTBD-03, JTBD-05, JTBD-09.  
**Business Goal Mapping:** BG-02, BG-03, BG-04.

## Capability AIC-04 — Ưu tiên và xếp hạng hồ sơ trong cùng vị trí

**Description:** Sắp xếp hồ sơ trong cùng một requisition theo mức đáp ứng tiêu chí bắt buộc rồi đến điểm từ rubric đã duyệt. Giải thích được trọng số, điểm thành phần và độ phủ bằng chứng. Không dùng điểm để tự đưa ra quyết định tuyển dụng.

**JTBD Mapping:** JTBD-04.  
**Business Goal Mapping:** BG-01, BG-03, BG-04.

## Capability AIC-05 — Nhận diện độ không chắc chắn và trường hợp cần xác minh

**Description:** Nhận biết khi CV thiếu bằng chứng, nội dung mơ hồ, độ tin cậy thấp, file bị khóa, quá mờ hoặc không đọc được; đưa trường hợp tương ứng vào luồng HR kiểm tra thay vì kết luận tự động.

**JTBD Mapping:** JTBD-05.  
**Business Goal Mapping:** BG-03, BG-04, BG-05.

## Capability AIC-06 — Nhận diện hồ sơ có khả năng trùng

**Description:** Cảnh báo CV giống hệt hoặc có dấu hiệu thuộc cùng ứng viên trong cùng một vị trí. Cảnh báo giúp HR kiểm tra; không tự gộp, ghi đè hoặc xóa.

**JTBD Mapping:** JTBD-02, JTBD-05.  
**Business Goal Mapping:** BG-01, BG-05.

## Capability Traceability

### Mã Business Goals

- **BG-01:** Giảm công sức xử lý CV thủ công.
- **BG-02:** Tăng tính nhất quán của tiêu chí sàng lọc.
- **BG-03:** Tìm và ưu tiên ứng viên phù hợp, giảm nguy cơ bỏ sót.
- **BG-04:** Bảo đảm kết quả có thể giải thích và HR giữ quyền quyết định.
- **BG-05:** Bảo vệ dữ liệu và xử lý ngoại lệ có kiểm soát.
- **BG-06:** Giúp HR Lead theo dõi tiến độ và hoạt động tuyển dụng.

| Business Goal | JTBD | Business Flow | AI Capability |
|---|---|---|---|
| BG-01 | JTBD-02, JTBD-03, JTBD-05 | BF-03, BF-04 | AIC-01, AIC-05, AIC-06 |
| BG-02 | JTBD-01, JTBD-03, JTBD-09 | BF-01, BF-02, BF-04 | AIC-02, AIC-03 |
| BG-03 | JTBD-03, JTBD-04, JTBD-05 | BF-04, BF-05 | AIC-03, AIC-04, AIC-05 |
| BG-04 | JTBD-01, JTBD-04, JTBD-06, JTBD-09 | BF-02, BF-04, BF-05 | AIC-02, AIC-03, AIC-04, AIC-05 |
| BG-05 | JTBD-05, JTBD-08 | BF-03, BF-08 | AIC-01, AIC-05, AIC-06 |
| BG-06 | JTBD-07 | BF-05, BF-07, BF-08 | Không phụ thuộc năng lực AI; được hỗ trợ bằng báo cáo sản phẩm |

## Design Decisions

1. Mọi năng lực AI phải gắn với ít nhất một Business Goal và JTBD.
2. AI chỉ đưa ra gợi ý; mọi tiêu chí chính thức và trạng thái tuyển dụng cần người có thẩm quyền xác nhận.
3. Ranking phải phản ánh rubric đã duyệt; không tạo một điểm tổng không truy nguyên được.
4. Các trường hợp không chắc chắn là một năng lực sản phẩm cần chủ động thể hiện, không phải lỗi được ẩn đi.
5. Báo cáo hoạt động tuyển dụng là năng lực sản phẩm thông thường, không cần gán cho AI nếu không có giá trị thực tế.

---

# Artifact 9 — MVP Definition

## Must Have

| Feature | Nội dung | JTBD | Lý do thuộc MVP |
|---|---|---|---|
| **F-01 Quản lý vị trí và JD** | Tạo vị trí, gán HR/Hiring Manager, lưu JD tiếng Anh, trạng thái Mở/Tạm dừng/Đóng | JTBD-01, JTBD-09 | Matching không có ý nghĩa nếu không gắn với một vị trí cụ thể |
| **F-02 Tiêu chí và phê duyệt** | AI đề xuất bản nháp; HR rà soát; Hiring Manager phê duyệt chuyên môn; lưu phiên bản | JTBD-01, JTBD-09 | Bảo đảm có chuẩn đánh giá trước khi xếp hạng |
| **F-03 Tiếp nhận CV theo lô** | Tối đa 50 file, 10 MB/file, 250 MB/batch; PDF/DOCX; trạng thái từng file | JTBD-02, JTBD-05 | Giải quyết trực tiếp khối lượng xử lý CV lớn |
| **F-04 Trích xuất thông tin và bằng chứng** | Đọc PDF có văn bản, OCR PDF scan, trích xuất DOCX; HR sửa thông tin sai | JTBD-03, JTBD-05 | Giảm đọc và ghi chép thủ công |
| **F-05 Matching theo tiêu chí** | Bốn mức đánh giá, bằng chứng, vị trí trích dẫn và lý do “Chưa rõ” | JTBD-03, JTBD-05 | Tạo kết quả có thể kiểm chứng, hạn chế suy luận thiếu căn cứ |
| **F-06 Điểm và ranking trong cùng requisition** | Dùng trọng số đã duyệt; ưu tiên tiêu chí bắt buộc rồi đến điểm; hiển thị độ phủ | JTBD-04 | Giúp HR chọn hồ sơ cần xem trước |
| **F-07 Xử lý ngoại lệ và cảnh báo trùng** | CV lỗi vào “Cần HR kiểm tra”; phát hiện CV trùng trong cùng vị trí, chỉ cảnh báo | JTBD-02, JTBD-05 | Tránh lỗi hoặc bản ghi trùng bị bỏ qua hay xử lý tự động sai |
| **F-08 Trạng thái ứng viên và quyết định** | HR cập nhật trạng thái, ghi lý do; gồm Bị loại, Không trúng tuyển, Trúng tuyển, Đã nhận việc | JTBD-06, JTBD-09 | Giữ quyền quyết định ở con người và lưu lịch sử |
| **F-09 Shortlist và dashboard cơ bản** | Hiring Manager xem shortlist được chia sẻ; dashboard theo vai trò | JTBD-06, JTBD-07, JTBD-09 | Hỗ trợ phối hợp và theo dõi hoạt động tuyển dụng |
| **F-10 Quyền, audit, lưu trữ và xóa** | Phân quyền theo vai trò/vị trí; retention 12 tháng; HR xác nhận xóa; áp dụng theo hồ sơ ứng tuyển | JTBD-08 | Là điều kiện bắt buộc khi xử lý CV và dữ liệu cá nhân |
| **F-11 Quản trị lựa chọn model/chế độ xử lý** | Admin chọn lựa chọn đã được phê duyệt; ưu tiên xử lý cục bộ; dịch vụ bên ngoài chỉ dùng trong kiểm thử ban đầu | JTBD-08 | Cần kiểm soát cách dùng năng lực AI và dữ liệu |
| **F-12 Giao diện song ngữ** | Tiếng Việt và tiếng Anh, mặc định tiếng Việt | JTBD-01–JTBD-09 | Phù hợp người dùng nội bộ và nội dung CV/JD tiếng Anh |
| **F-13 Đánh giá pilot trước khi sử dụng rộng** | Thử nghiệm trên CV/JD có nhãn tham chiếu; rà soát kết quả và trường hợp sai | JTBD-03, JTBD-04, JTBD-05, JTBD-08 | Giảm rủi ro đưa ranking chưa được kiểm chứng vào quy trình |

## Should Have

| Feature | Nội dung | JTBD | Lý do |
|---|---|---|---|
| **F-14 Phản hồi trực tiếp của Hiring Manager** | Comment trên shortlist và yêu cầu HR xác minh thêm | JTBD-06, JTBD-09 | Giảm trao đổi rời rạc; có thể ưu tiên sau khi luồng cơ bản chạy ổn định |
| **F-15 Báo cáo nâng cao** | Thời gian xử lý, hồ sơ tồn đọng, số lần cần xác minh, tỷ lệ chỉnh sửa | JTBD-07 | Hữu ích để cải tiến nhưng cần định nghĩa chỉ số sau khi có baseline |
| **F-16 Mẫu tiêu chí theo nhóm IT** | Gợi ý mẫu cho Software Engineer, QA, DevOps, Data Engineer, IT Support | JTBD-01, JTBD-09 | Giúp bắt đầu nhanh nhưng không thay thế duyệt theo JD |

## Could Have

| Feature | Nội dung | JTBD | Lý do |
|---|---|---|---|
| **F-17 Xuất báo cáo chi tiết** | Xuất dữ liệu theo quyền, phạm vi và chính sách đã duyệt | JTBD-07, JTBD-08 | Chỉ cần nếu các bên xác nhận báo cáo ngoài hệ thống là nhu cầu thực tế |
| **F-18 Phân tích nguyên nhân HR điều chỉnh gợi ý** | Tổng hợp lý do HR không đồng ý để cải thiện tiêu chí và cách trình bày | JTBD-04, JTBD-07 | Giá trị tăng dần sau khi có đủ dữ liệu và quy tắc quản trị phù hợp |

## Won’t Have trong MVP

| Nội dung | JTBD liên quan | Lý do không đưa vào MVP |
|---|---|---|
| Crawl CV từ nguồn online | JTBD-02 | Ghi nhận cho Phase 2; cần đánh giá nguồn dữ liệu và quyền sử dụng riêng |
| SSO | JTBD-08 | Đã thống nhất chuyển sang Phase 2 |
| Tự động shortlist hoặc loại ứng viên | JTBD-04, JTBD-06 | Không phù hợp nguyên tắc HR ra quyết định |
| Quyết định theo ngưỡng điểm | JTBD-04, JTBD-06 | Điểm chỉ dùng ưu tiên rà soát |
| Ranking giữa nhiều vị trí | JTBD-04 | Các vị trí có rubric và nhu cầu khác nhau |
| Quản lý lịch phỏng vấn/onboarding | JTBD-06 | Ngoài phạm vi sàng lọc CV |
| Tuyển dụng giảng viên | JTBD-01 | Quy trình và tiêu chí khác phạm vi pilot |
| Matching CV không phải tiếng Anh | JTBD-03 | Ngoài ngôn ngữ đã thống nhất cho MVP |
| OCR ảnh CV rời | JTBD-05 | MVP chỉ hỗ trợ OCR PDF scan |
| Sử dụng dịch vụ ngoài với CV thật trong production | JTBD-08 | Dịch vụ ngoài chỉ dùng cho kiểm thử ban đầu, trừ khi được phê duyệt riêng |
| Đánh giá “culture fit”, tuổi, giới tính, ngoại hình | JTBD-01, JTBD-03 | Không phải tiêu chí phù hợp cho matching |

## Why These Features Belong to MVP

MVP tập trung vào vấn đề lớn nhất: HR cần xử lý nhiều CV và so khớp với JD. Vì vậy, các năng lực thiết yếu là:

1. Chuẩn hóa tiêu chí.
2. Tìm bằng chứng từ CV.
3. Matching và ranking có giải thích.
4. Xử lý được CV lỗi hoặc thiếu bằng chứng.
5. Bảo đảm HR giữ quyền quyết định.
6. Kiểm soát dữ liệu và đánh giá chất lượng trước khi mở rộng.

Crawl, SSO, quản lý phỏng vấn và mở rộng ngôn ngữ không giải quyết trực tiếp vòng sàng lọc đầu tiên nên được để sau.

## MVP Success Definition

MVP được xem là đạt yêu cầu pilot khi:

- HR và Hiring Manager xác nhận các tiêu chí được duyệt phản ánh nhu cầu vị trí.
- Các gợi ý matching có bằng chứng phù hợp và ranking có thể giải thích.
- CV không đọc được, thiếu thông tin hoặc confidence thấp được đưa vào xử lý thủ công, không tự động bị loại.
- HR vẫn tự cập nhật mọi trạng thái tuyển dụng.
- Chất lượng AI đạt các ngưỡng pilot được phê duyệt sau khi kiểm tra tập dữ liệu.
- Không có truy cập trái quyền hoặc sự cố dữ liệu nghiêm trọng.
- Thời gian xử lý được đo trong pilot; mục tiêu cải thiện được đặt sau khi có baseline.

## Design Decisions

1. “Must Have” bao gồm cả năng lực sản phẩm và điều kiện quản trị cần thiết để thử nghiệm an toàn.
2. Không coi điểm số là kết quả tuyển dụng.
3. MVP dùng hỗ trợ trực tiếp cho các vị trí IT nhưng chất lượng cần đánh giá riêng theo từng nhóm vai trò.
4. Các hạng mục “Should” và “Could” không được làm ảnh hưởng đến việc hoàn thành luồng cốt lõi.
5. Các mốc hiệu năng chưa được chốt vì thời gian hiển thị hiện chỉ là ước lượng ban đầu.

---

# Artifact 10 — Acceptance Criteria

## A. Product Acceptance Criteria

| ID | Tiêu chí |
|---|---|
| **PAC-01** | HR có thể tạo vị trí với JD tiếng Anh, phòng ban và Hiring Manager. |
| **PAC-02** | Tiêu chí AI đề xuất được nhận diện là bản nháp; HR rà soát và Hiring Manager phê duyệt trước khi áp dụng. |
| **PAC-03** | Trọng số mặc định nhóm Bắt buộc/Ưu tiên là 70%/30%; chỉnh sửa được; tổng trọng số phải bằng 100% khi phê duyệt. |
| **PAC-04** | Matching hiển thị một trong bốn mức Đáp ứng tốt / Đáp ứng / Chưa rõ / Chưa đáp ứng, có trích dẫn hoặc nêu rõ không tìm thấy bằng chứng. |
| **PAC-05** | “Chưa rõ” được phân biệt với “Chưa đáp ứng”; CV không có thông tin không bị tự hiểu là không đạt. |
| **PAC-06** | Ranking chỉ so sánh ứng viên trong cùng vị trí; hiển thị thứ tự đáp ứng tiêu chí bắt buộc trước, rồi đến điểm. |
| **PAC-07** | Mọi điểm có thể giải thích từ trọng số và kết quả từng tiêu chí; hiển thị độ phủ bằng chứng. |
| **PAC-08** | Độ phủ dưới 70% được gắn “Chưa đủ dữ liệu để xếp hạng ổn định”. |
| **PAC-09** | Không có ngưỡng điểm tự động shortlist, loại hoặc thay đổi trạng thái ứng viên. |
| **PAC-10** | HR là người xác nhận chuyển trạng thái ứng viên; “Bị loại” và “Không trúng tuyển” là hai trạng thái khác nhau. |
| **PAC-11** | Trúng tuyển và Đã nhận việc được ghi nhận là trạng thái riêng. |
| **PAC-12** | CV không đọc được, PDF bị khóa hoặc quá mờ có trạng thái “Cần HR kiểm tra”; không được tính điểm hoặc tự động loại. |
| **PAC-13** | Cảnh báo trùng chỉ áp dụng trong cùng vị trí; HR quyết định, không tự gộp hoặc xóa. |
| **PAC-14** | Hiring Manager chỉ xem shortlist được chia sẻ và các vị trí được giao theo quyền được phê duyệt. |
| **PAC-15** | Giao diện chuyển được giữa tiếng Việt và tiếng Anh; mặc định tiếng Việt. |

## B. Business Acceptance Criteria

| ID | Tiêu chí |
|---|---|
| **BAC-01** | Mỗi vị trí bắt đầu matching bằng bộ tiêu chí đã được HR và Hiring Manager xác nhận. |
| **BAC-02** | HR có thể giải thích với Hiring Manager vì sao một ứng viên được xếp vào một nhóm hoặc thứ tự nhất định. |
| **BAC-03** | HR rà soát các trường hợp có dấu hiệu miss-match, tiêu chí bắt buộc chưa rõ hoặc CV cần xử lý thủ công trước khi ra quyết định. |
| **BAC-04** | Không hồ sơ nào bị loại hoặc shortlist chỉ bởi điểm số của hệ thống. |
| **BAC-05** | HR ghi nhận lý do khi chuyển sang “Bị loại” hoặc “Không trúng tuyển”. |
| **BAC-06** | Baseline về thời gian và khối lượng được đo trong pilot trước khi đặt mục tiêu giảm thời gian. |
| **BAC-07** | Các bên thống nhất cách đánh giá chất lượng shortlist và ranking trước khi dùng kết quả để hỗ trợ quy trình thực tế. |

## C. Technical Acceptance Criteria

> Phần này quy định các điều kiện sử dụng và chất lượng mà người dùng có thể kiểm chứng; không quy định kiến trúc hoặc cách triển khai.

| ID | Tiêu chí |
|---|---|
| **TAC-01** | Mỗi batch tối đa 50 file, 10 MB/file và 250 MB tổng dung lượng; vượt giới hạn phải có thông báo rõ. |
| **TAC-02** | Hỗ trợ đọc PDF có văn bản, OCR PDF scan và trích xuất văn bản thông thường từ DOCX. |
| **TAC-03** | Không hỗ trợ OCR ảnh CV rời trong MVP; file không đọc được được đưa vào “Cần HR kiểm tra”. |
| **TAC-04** | Mỗi file có trạng thái xử lý riêng; lỗi không bị bỏ qua âm thầm. |
| **TAC-05** | Dùng model cục bộ là lựa chọn ưu tiên; dịch vụ xử lý bên ngoài chỉ dùng cho kiểm thử trong giai đoạn đầu. Admin chỉ cấu hình lựa chọn đã được phê duyệt. |
| **TAC-06** | Đăng nhập bằng email và mật khẩu nội bộ trong MVP; SSO nằm trong Phase 2. Yêu cầu chi tiết tuân thủ tiêu chuẩn bảo mật nội bộ do IT phê duyệt. |
| **TAC-07** | Người dùng không xem được CV hoặc vị trí ngoài quyền; thao tác xem, sửa, tải, chia sẻ, xuất hoặc xóa phải được ghi nhận theo chính sách audit. |
| **TAC-08** | Hệ thống hỗ trợ đếm 12 tháng từ ngày đóng vị trí, đưa hồ sơ đến hạn vào danh sách chờ HR xác nhận xóa, và khởi động lại thời hạn khi vị trí được mở lại rồi đóng lần tiếp theo. |
| **TAC-09** | Xóa một hồ sơ ứng tuyển không tự động xóa hồ sơ của cùng ứng viên ở vị trí khác. |
| **TAC-10** | Chưa đặt thời gian xử lý tối đa cho batch/CV trong PRD; cần đo trên dữ liệu và điều kiện sử dụng pilot rồi thống nhất mục tiêu. |
| **TAC-11** | Ngưỡng chất lượng AI dưới đây là mục tiêu khởi điểm và chỉ được chốt sau khi đánh giá tập CV/JD kiểm thử. |

### Mục tiêu đánh giá chất lượng AI đề xuất

| Chỉ số | Ngưỡng khởi điểm |
|---|---:|
| Trích xuất email/SĐT sau chuẩn hóa, trên trường có mặt | ≥95% |
| Trích xuất học vấn, kinh nghiệm, kỹ năng, chứng chỉ | F1 ≥85% theo từng nhóm trường |
| Matching theo tiêu chí | Macro-F1 ≥0.80 |
| Trường hợp chuyên gia xác nhận đạt tiêu chí bắt buộc nhưng AI kết luận “Chưa đáp ứng” | ≤5% |
| Kết luận “Chưa đáp ứng” có bằng chứng phù hợp | ≥90% |
| Trích dẫn hỗ trợ nhận định | ≥95% trên mẫu kiểm tra |
| Chất lượng ranking trong cùng JD | NDCG@5 ≥0.75 |
| File lỗi/không đọc được được gắn trạng thái phù hợp | 100% |
| Trạng thái tuyển dụng tự động thay đổi bởi AI | 0 trường hợp |
| Truy cập trái quyền thành công trong kiểm thử | 0 trường hợp |

Các chỉ số phải được báo cáo theo nhóm vị trí IT, không chỉ theo một con số tổng hợp.

## D. Project Acceptance Criteria

| ID | Tiêu chí |
|---|---|
| **PRJ-AC-01** | HR, Hiring Manager, PO, IT/Security và Legal/Privacy được mời rà soát các yêu cầu thuộc phạm vi của mình. |
| **PRJ-AC-02** | Tập kiểm thử có CV, JD, rubric và nhãn đánh giá được HR/Hiring Manager xác nhận. |
| **PRJ-AC-03** | Mục tiêu tập thử nghiệm: khoảng 300 cặp CV–JD–rubric; mức tối thiểu đề xuất 200 cặp. Nếu số lượng thấp hơn, kết quả phải được ghi là tham khảo, không khẳng định chất lượng cho toàn bộ nhóm vị trí. |
| **PRJ-AC-04** | Tập thử nghiệm bao phủ Software Engineer, QA, DevOps, Data Engineer và IT Support nếu có dữ liệu được phép dùng. |
| **PRJ-AC-05** | Tập kiểm thử bao gồm hồ sơ đáp ứng, không đáp ứng, thiếu bằng chứng, CV scan, PDF khóa, nội dung mờ và tình huống trùng lặp. |
| **PRJ-AC-06** | HR/Hiring Manager đánh giá độc lập các mẫu kiểm thử; bất đồng quan trọng có người phân xử. |
| **PRJ-AC-07** | Có giai đoạn đánh giá kết quả trong đó HR vẫn chịu trách nhiệm quyết định, trước khi dùng ranking rộng hơn trong quy trình. |
| **PRJ-AC-08** | Legal/Privacy xác nhận chính sách retention 12 tháng, phạm vi hồ sơ và yêu cầu xóa trước khi áp dụng chính thức. |
| **PRJ-AC-09** | IT/Security phê duyệt xác thực, quyền truy cập, điều kiện sử dụng dịch vụ ngoài trong kiểm thử và các yêu cầu bảo mật liên quan. |
| **PRJ-AC-10** | Người dùng pilot được hướng dẫn về giới hạn của ranking, phân biệt “Chưa rõ” và “Chưa đáp ứng”, và quy trình xử lý CV ngoại lệ. |

## Requirement Traceability

| Business Goal | JTBD | Business Flow | AI Capability | Feature | Acceptance Criteria |
|---|---|---|---|---|---|
| BG-01 Giảm công sức thủ công | JTBD-02, JTBD-03, JTBD-05 | BF-03, BF-04 | AIC-01, AIC-05, AIC-06 | F-03, F-04, F-07 | PAC-12, PAC-13, TAC-01–04 |
| BG-02 Tăng tính nhất quán | JTBD-01, JTBD-03, JTBD-09 | BF-01, BF-02, BF-04 | AIC-02, AIC-03 | F-01, F-02, F-05 | PAC-01–05, BAC-01 |
| BG-03 Nhận diện và ưu tiên hồ sơ phù hợp | JTBD-03, JTBD-04, JTBD-05 | BF-04, BF-05 | AIC-03, AIC-04, AIC-05 | F-04, F-05, F-06, F-07 | PAC-06–09, BAC-02–04, TAC-11 |
| BG-04 Minh bạch và giữ quyền quyết định | JTBD-01, JTBD-04, JTBD-06, JTBD-09 | BF-02, BF-04, BF-05 | AIC-02, AIC-03, AIC-04, AIC-05 | F-02, F-05, F-06, F-08 | PAC-07–11, BAC-02–05 |
| BG-05 Bảo vệ dữ liệu và xử lý ngoại lệ | JTBD-05, JTBD-08 | BF-03, BF-08 | AIC-05, AIC-06 | F-07, F-10, F-11 | TAC-05–09, PRJ-AC-08–09 |
| BG-06 Theo dõi hoạt động tuyển dụng | JTBD-07, JTBD-06 | BF-05, BF-07, BF-08 | Không phụ thuộc AI | F-09, F-15 | BAC-06–07 |

## Design Decisions

1. Các tiêu chí AI được nghiệm thu theo bằng chứng và ảnh hưởng đến quyết định, không chỉ theo độ chính xác trích xuất.
2. Chất lượng ranking được đánh giá trong cùng một JD và với nhãn tham chiếu từ HR/Hiring Manager.
3. Chưa có SLA hiệu năng vì các mốc thời gian hiện tại mới là ước lượng.
4. Các ngưỡng AI là mục tiêu kiểm thử; sau khi có tập dữ liệu đại diện, các bên có thể điều chỉnh trước khi ký nghiệm thu.
5. Nếu hệ thống chưa đạt ngưỡng an toàn về tiêu chí bắt buộc hoặc chất lượng bằng chứng, ranking chỉ dùng để đánh giá nội bộ, không dùng để ưu tiên hồ sơ trong quy trình thật.

---

# Final Summary

## Product Vision

Giúp VinUni sàng lọc CV theo tiêu chí đã thống nhất, dựa trên bằng chứng có thể kiểm tra, với ranking hỗ trợ HR ưu tiên rà soát nhưng không thay thế quyết định tuyển dụng.

## Primary Persona

**HR Recruiter** — người trực tiếp xử lý CV, kiểm tra bằng chứng, quyết định shortlist/bị loại và phối hợp với Hiring Manager.

## Core User Journey

Vị trí IT mở → HR và Hiring Manager thống nhất tiêu chí → HR nhận CV theo lô → rà soát bằng chứng và hồ sơ cần xác minh → tạo shortlist → Hiring Manager phản hồi → HR cập nhật kết quả và xử lý dữ liệu theo retention.

## Core Business Flow

Xác nhận nhu cầu → thống nhất JD và tiêu chí → tiếp nhận hồ sơ → HR đánh giá → HR quyết định sàng lọc → Hiring Manager phản hồi → cập nhật kết quả tuyển dụng → đóng vị trí và quản lý retention.

## Core AI Capabilities

- Hiểu nội dung và trích xuất thông tin nghề nghiệp từ CV.
- Đề xuất bản nháp tiêu chí từ JD.
- Đối chiếu tiêu chí với bằng chứng trong CV.
- Xếp hạng hồ sơ trong cùng một vị trí theo rubric.
- Nhận diện trường hợp chưa rõ hoặc cần HR xác minh.
- Cảnh báo hồ sơ có khả năng trùng trong cùng vị trí.

## MVP Scope

- Vị trí và JD tiếng Anh.
- Tiêu chí AI đề xuất nhưng do HR/Hiring Manager duyệt.
- CV tiếng Anh PDF/DOCX, đọc PDF có văn bản, OCR PDF scan.
- Upload tối đa 50 file/batch, 10 MB/file và 250 MB/batch.
- Matching theo tiêu chí, điểm và ranking có giải thích.
- Hàng chờ HR cho CV không đọc được và cảnh báo trùng.
- HR xác nhận thủ công mọi trạng thái tuyển dụng.
- Phân quyền, dashboard theo vai trò, retention 12 tháng có HR xác nhận xóa.
- Xử lý cục bộ là ưu tiên; dịch vụ ngoài chỉ dùng trong kiểm thử ban đầu.
- Đánh giá pilot trên CV/JD/rubric có nhãn tham chiếu.


# Đề xuất roadmap sau MVP

Mở rộng theo thứ tự **đo lường và chuẩn hóa → tái sử dụng CV → hoàn thiện quy trình tuyển dụng → mở rộng quy mô**.

## Phase 2 — Chuẩn hóa và tăng giá trị matching

1. **Đo lường hiệu quả — bắt đầu ngay trong pilot**
   - Theo dõi thời gian đến lần rà soát đầu tiên/shortlist, tỷ lệ CV cần HR kiểm tra, độ phủ bằng chứng, mức HR điều chỉnh gợi ý AI, và tỷ lệ shortlist chuyển sang phỏng vấn.
   - Đo chất lượng AI trên mẫu CV–JD được HR/Hiring Manager đánh giá; theo dõi cả trường hợp AI có thể bỏ sót ứng viên phù hợp.
   - Vì chưa có baseline, chưa nên cam kết trước một KPI giảm thời gian cố định.

2. **Thư viện JD và rubric theo nhóm vị trí**
   - Bắt đầu với các nhóm IT trong pilot, sau đó mở rộng sang Admin, Marketing, Finance, Student Affairs.
   - Mỗi mẫu nên có yêu cầu bắt buộc/ưu tiên, cấp độ vị trí, rubric đánh giá và phiên bản; HR/Hiring Manager có thể chỉnh sửa và phê duyệt.
   - Tránh để mẫu trở thành tiêu chí cứng áp dụng máy móc cho mọi vị trí.

3. **Tái sàng lọc kho CV theo JD mới — Candidate Rediscovery**
   - Quy trình đề xuất: đưa JD vào → AI tạo bản nháp tiêu chí → HR/Hiring Manager duyệt → hệ thống tìm và xếp hạng hồ sơ đủ điều kiện trong kho.
   - Kết quả vẫn cần có bằng chứng để HR kiểm tra; chỉ xếp hạng trong từng vị trí, không tự loại ứng viên.
   - **Điều kiện quan trọng:** chỉ dùng hồ sơ còn trong thời hạn và được phép tái sử dụng; không lấy hồ sơ đã đến hạn hoặc đang chờ xóa. Cần làm rõ với Legal/Privacy cách thông báo và retention nếu hồ sơ được dùng cho vị trí mới.

## Phase 3 — Hoàn thiện trải nghiệm tuyển dụng

4. **Booking phỏng vấn**
   - Quản lý khung giờ, mời ứng viên chọn lịch, xác nhận/nhắc lịch/đổi lịch; hỗ trợ cả phỏng vấn online và offline.
   - Nên bắt đầu với HR kiểm soát việc gửi lời mời; tích hợp lịch sâu hơn sau khi xác nhận nhu cầu và quy trình hiện tại.

5. **Bài đánh giá online/offline**
   - Cung cấp bài đánh giá theo nhóm vị trí, hướng dẫn và rubric; hỗ trợ ghi nhận điểm bài online hoặc nhập kết quả bài offline.
   - Bài đánh giá cần liên quan trực tiếp đến công việc, có phương án hỗ trợ tiếp cận phù hợp và **không tự động loại ứng viên**. Không đưa personality/culture fit vào đánh giá.

6. **Tự động hóa feedback**
   - Chuẩn hóa form nhận xét của HR/Hiring Manager/người phỏng vấn; nhắc người đánh giá còn thiếu feedback.
   - AI có thể tổng hợp ý kiến và soạn nháp phản hồi cho ứng viên, nhưng HR duyệt trước khi gửi; không tự tạo lý do từ chối chưa được xác minh.

## Phase 4 — Mở rộng quy mô

7. **Cổng ứng viên / talent pool có đăng ký**
   - Cho phép ứng viên cập nhật CV, sở thích vị trí và trạng thái đồng ý được xem xét cho cơ hội khác; giúp kho CV mới và chính xác hơn.
   - Cần thống nhất rõ cơ chế đồng ý, rút lại sự đồng ý và thời hạn lưu hồ sơ.

8. **Mở rộng báo cáo và kết nối quy trình**
   - Sau khi quy trình ổn định, xem xét kết nối với các hệ thống lịch, tuyển dụng hoặc đánh giá hiện có để giảm nhập liệu lặp lại.
   - Có thể bổ sung phân tích kết quả tuyển dụng dài hạn ở mức tổng hợp, nếu dữ liệu và quyền sử dụng đã được phê duyệt.

**Thứ tự ưu tiên:** đo lường pilot → thư viện JD/rubric → tái sàng lọc kho CV đủ điều kiện → booking và feedback → bài đánh giá → cổng ứng viên và mở rộng tích hợp.