# RUBRIC LÀ GÌ, VÀ DÙNG NHƯ THẾ NÀO

Viết cho HR mới. Đọc 5 phút là hiểu, không cần biết kỹ thuật.

---

## 1. Một câu

**Rubric là bộ tiêu chí để chấm ứng viên cho một nhóm công việc.**

Không có rubric thì hệ thống không biết "giỏi" nghĩa là gì, và mọi điểm số đều
vô nghĩa. Có rubric thì hai ứng viên khác nhau được đo bằng cùng một thước.

---

## 2. Vì sao phải có, thay vì HR tự chấm bằng cảm nhận

Khi không có tiêu chí viết trước, chuyện này xảy ra:

- HR A thích ứng viên có kinh nghiệm dự án; HR B chỉ quan tâm bằng cấp. Hai
  người đọc cùng một CV, cho hai kết quả khác nhau, cả hai đều thấy mình đúng.
- Tiêu chí bị **đổi giữa chừng**: ứng viên đầu được chấm "cần 5 năm", đến ứng
  viên thứ mười thì "3 năm cũng được" — vì người chấm đã quen tay.
- Không trả lời được câu **"tại sao loại ứng viên này?"** khi ứng viên hỏi.

Rubric khoá những thứ đó lại *trước khi* xem CV. Đó là toàn bộ giá trị của nó:
**quyết định thước đo trước khi biết ai là người được đo.**

---

## 3. Hai nhóm tiêu chí, và trọng số

Mỗi rubric chia tiêu chí làm hai nhóm:

| Nhóm | Nghĩa | Ví dụ |
|---|---|---|
| **Bắt buộc** (MUST_HAVE) | Thiếu là loại, không cần xem tiếp | "4 năm Python" |
| **Ưu tiên** (NICE_TO_HAVE) | Có thì tốt hơn | "từng làm Kubernetes" |

Hai con số ở đầu rubric — mặc định **70 / 30** — là **tỉ lệ đóng góp của hai
nhóm vào điểm cuối**. Đặt 70/30 nghĩa là: một ứng viên đáp ứng hoàn hảo mọi yêu
cầu bắt buộc nhưng không có gì ở phần ưu tiên vẫn được 70 điểm, không phải 100.

Trọng số **bên trong** mỗi nhóm cộng lại phải bằng 100. Hệ thống tự kiểm tra khi
xuất bản; không cần tự nhẩm.

---

## 4. Ba vòng đời, đừng nhầm

Đây là chỗ HR mới hay lẫn nhất. Có **ba thứ khác nhau**, không phải một:

```
① RUBRIC MẪU (thư viện)    ② BỘ TIÊU CHÍ CỦA VỊ TRÍ    ③ KẾT QUẢ CHẤM
   dùng lại nhiều lần   →      sinh ra từ rubric mẫu   →    điểm từng ứng viên
```

| | ① Rubric mẫu | ② Tiêu chí của vị trí | ③ Kết quả chấm |
|---|---|---|---|
| Ở đâu | `/rubrics` | Tab Tiêu chí trong vị trí | Tab Ứng viên |
| Thuộc về | Một **nhóm vị trí** | Một **vị trí cụ thể** | Một **ứng viên** |
| Dùng mấy lần | Nhiều vị trí | Một vị trí | Một lần chấm |
| Sửa được sau khi dùng | Có (tạo phiên bản mới) | Không — phải tạo bộ mới | Không |

**Điểm mấu chốt:** rubric mẫu là *khuôn*, không phải *bản đã ký*. Sửa rubric mẫu
**không** làm thay đổi bộ tiêu chí của vị trí đã dùng nó. Ngược lại, sửa tiêu chí
của một vị trí cũng không đụng tới thư viện.

---

## 5. Đi từng bước: đăng một job mới

### Bước 0 — Chuẩn bị (làm một lần)

Kiểm tra `/rubrics` đã có rubric mẫu **đã xuất bản** cho nhóm anh sắp dùng chưa.
Chưa có thì làm mục 6 bên dưới trước.

### Bước 1 — Tạo vị trí, **chọn Nhóm vị trí**

Vào Vị trí → Tạo vị trí. Điền JD, **và chọn Nhóm vị trí**.

> Nhóm vị trí là sợi dây nối vị trí với thư viện rubric. Bỏ trống thì vẫn tạo
> được vị trí, nhưng lúc lấy rubric hệ thống không biết nhóm nào là đúng, và
> **không sinh được rubric từ JD** (nút đó yêu cầu có nhóm).

### Bước 2 — Chọn nguồn tiêu chí **ngay khi tạo vị trí**

Trang tạo vị trí có **bước 3 — Bộ tiêu chí đầu tiên**, chọn một trong hai:

| Chọn | Hệ thống làm gì | Nên dùng khi |
|---|---|---|
| **AI sinh từ JD** (mặc định) | Đọc JD, đề xuất tiêu chí + trọng số, ra bản nháp | Tuyển một vị trí, chỉ cần bám sát JD |
| **Dùng rubric mẫu đã xuất bản** | Chép tiêu chí + trọng số của rubric mẫu vào vị trí, ra bản nháp | Sẽ tuyển loại vị trí này nhiều lần, muốn giữ nguyên một thước |

Cả hai đều ra **bản nháp** và đều phải qua duyệt HR → Hiring Manager trước khi
chấm. Bỏ qua bước chọn này là lý do trước đây HR bị kẹt: xem mục dưới.

> **Vì sao phải chọn ngay từ đầu, không để áp sau:** bộ tiêu chí AI ở trạng thái
> nháp **chặn** việc áp rubric mẫu (máy chủ trả 409 "Vị trí đã có tiêu chí đang
> xử lý"). Trước đây muốn đổi sang rubric mẫu, HR buộc phải đưa bộ AI qua **cả
> vòng duyệt** chỉ để mở một cái nút — rồi sau đó duyệt lại từ đầu cho rubric
> mẫu, và bộ AI ở lại vĩnh viễn với trạng thái đã duyệt.

### Bước 2b — Đã lỡ tạo rồi mới muốn đổi sang rubric mẫu

Vào vị trí, tab **Tiêu chí**. Nếu bộ hiện tại còn **Nháp**, có dòng thông báo
kèm nút **"Huỷ bản nháp này"**. Huỷ xong thì nút **"Dùng rubric đã xuất bản"**
mở ra và áp được ngay.

Ba thứ **không** huỷ được, và đó là cố ý:

- Bộ đã gửi duyệt hoặc đã duyệt — đã có người khác xem và có ý kiến.
- Bộ đã từng dùng để chấm ứng viên — xoá đi là mất dấu vết đã chấm bằng gì.
- Bộ của vị trí mà anh không phải HR phụ trách.

Huỷ bản nháp **không** xoá vị trí, không xoá JD. Sinh lại bộ AI lúc nào cũng được.

### Bước 3 — Vào vị trí, tab **Tiêu chí**

Xem lại bộ tiêu chí vừa có, sửa/xoá/thêm tiêu chí nếu cần.

Nút **"Dùng rubric đã xuất bản"** nằm cạnh nút **Ứng viên** ở đầu trang vị trí.
Danh sách đã được xếp rubric **cùng nhóm lên đầu**; rubric khác nhóm vẫn chọn
được nhưng có nhãn đỏ `(khác nhóm vị trí)` — đó phải là lựa chọn có chủ ý,
không phải bấm nhầm.

### Bước 4 — Duyệt tiêu chí

Bộ tiêu chí vừa tạo ở trạng thái **Nháp**. Phải qua duyệt (HR → Hiring Manager)
thì mới dùng để chấm được. Hệ thống chặn chấm điểm khi chưa duyệt.

> Đây là điểm khác với thói quen: **không ai được chấm ứng viên bằng một bộ tiêu
> chí chưa duyệt.** Kể cả chính người viết ra nó.

### Bước 5 — Tải CV, chấm điểm

Tải CV → hệ thống bóc nội dung → chấm từng tiêu chí → xếp hạng.

---

## 6. Tạo rubric mẫu trong thư viện

Vào `/rubrics`. Có **ba nút**, đừng nhầm:

| Nút | Nó làm gì | Có dùng AI? |
|---|---|---|
| **Tạo rubric nháp** | Mở biểu mẫu **trống**, anh tự gõ 100% | Không |
| **Sinh từ JD của một vị trí** | Chọn một vị trí đã có JD → AI đọc JD và **đề xuất** bộ tiêu chí → anh sửa → lưu | **Có** |
| **Dùng bộ mẫu ví dụ (Backend Python)** | Điền sẵn 5 tiêu chí viết cứng trong mã nguồn, để xem một rubric tốt trông thế nào | Không |

Hai điều cần biết về nút thứ hai và thứ ba:

- **"Sinh từ JD" không tự lưu.** Nó điền vào biểu mẫu rồi dừng. Anh phải đọc,
  sửa, rồi bấm **Lưu bản nháp**. Đây là cố ý: model sai một tiêu chí mà ghi
  thẳng vào thư viện thì cả thư viện nhiễm bẩn và không ai nhớ để dọn.
- **"Bộ mẫu ví dụ" không phải AI.** Đó là văn bản viết sẵn trong mã nguồn. Nó
  tồn tại để người mới nhìn thấy một rubric đầy đủ trông ra sao.

### Xuất bản

Rubric mới ở trạng thái **Nháp** — chỉ người tạo thấy. Bấm **Xuất bản** thì mới
hiện cho mọi HR và mới dùng được cho vị trí.

> Chỉ **HR Lead** xuất bản được. HR thường tạo nháp, HR Lead duyệt. Đây là chủ ý:
> xuất bản là cam kết "bộ tiêu chí này dùng chung được", không phải thao tác lưu.

### Sửa rubric đã xuất bản

Không sửa trực tiếp. Bấm **Tạo phiên bản nháp mới** → sửa bản mới → xuất bản.
Bản cũ vẫn còn, các vị trí đã dùng nó **không bị đổi theo**. Đó là cách hệ thống
giữ được câu trả lời cho "vị trí này đã chấm theo tiêu chí nào".

---

## 7. Trả lời nhanh vài câu hay gặp

**"Rubric mẫu có cần cho mọi vị trí không?"**
Không. Để tuyển **một** vị trí, bộ AI tự sinh không thua kém gì — mọi ứng viên
của vị trí đó vẫn được chấm bằng đúng một bộ tiêu chí, nên vẫn công bằng. Rubric
mẫu chỉ đáng công khi:

1. **Tuyển một loại vị trí qua nhiều đợt** (ví dụ mỗi quý tuyển 2 kỹ sư backend).
   Để AI tự sinh mỗi lần thì trọng số trôi giữa các đợt: cùng một người có thể
   được 94 điểm ở đợt 1 và 70 điểm ở đợt 3 mà không ai giải thích được. Thước
   chung khoá trọng số lại.
2. **JD quá sơ sài** khiến AI sinh ra tiêu chí vô nghĩa — dùng rubric mẫu như
   bản nháp đã có người viết.

Đừng bật rubric mẫu chỉ vì thấy nó "chuẩn hơn". Nó khác, không chắc đúng hơn:
rubric mẫu mang quan niệm chung của công ty về "giỏi", có thể hạ thấp đúng thứ
vị trí này cần nhất.

**"Sửa rubric mẫu có làm hỏng vị trí đang chạy không?"**
Không. Vị trí đã có bộ tiêu chí riêng, tách rời. Đó chính là lý do phải "áp dụng"
rubric vào vị trí thay vì dùng trực tiếp.

**"Vì sao phải duyệt tiêu chí, tôi viết rồi mà?"**
Vì tiêu chí là thước đo dùng để loại người. Một tiêu chí viết sai (hoặc vi phạm
quy định như giới tính, tuổi) gây thiệt hại mà không sửa lại được sau khi đã
loại ứng viên. Duyệt là chốt chặn cuối.

**"Trọng số 70/30 có bắt buộc không?"**
Không. Đó là mặc định. Nhưng hai nhóm phải cộng bằng 100.

**"Nhóm vị trí bỏ trống được không?"**
Được, vị trí vẫn tạo được. Nhưng mất ba thứ: không lọc được rubric đúng nhóm,
không sinh được rubric từ JD, và trang Careers hiển thị không có ngành để lọc.
Nên chọn.

---

## 8. Những chỗ dễ sai (đọc để tránh)

1. **Tưởng "Sinh từ JD" đã tạo xong rubric.** Chưa. Phải bấm Lưu, rồi Xuất bản.
2. **Tưởng sửa rubric mẫu là mọi vị trí đổi theo.** Không. Phải áp dụng lại.
3. **Chấm điểm khi tiêu chí chưa duyệt.** Hệ thống chặn, nhưng đừng chờ nó chặn.
4. **Để trọng số trong nhóm không cộng 100.** Xuất bản sẽ bị từ chối.
5. **Dùng rubric khác nhóm mà không để ý.** Có nhãn đỏ cảnh báo — đọc nó.
