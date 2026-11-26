# Rà soát nhánh `freebuff/1434fda45407dc1a68600843` và kế hoạch đồng bộ

> Ngày 2026-11-30. Rà soát **trước khi gộp**, chưa gộp gì.
> Mọi con số dưới đây đo bằng `git`, không ước lượng.

---

## 0. Việc đầu tiên: repo cục bộ đã bị lệch, đã sửa

Trước khi rà soát, `HEAD` cục bộ là `3bad733` — commit gốc **chỉ có 10 file `doc/`**.
Toàn bộ `backend/`, `frontend/`, `supabase/` nằm trong working tree nhưng **không
được track**. Remote vẫn đúng ở `48ac07b` (616 file).

Đã kiểm trước khi sửa: working tree **khớp tuyệt đối** với `48ac07b` (0 file khác,
so bằng index tạm). Không mất gì. Đã `git reset` về `48ac07b`, tree sạch.

**Nếu ai thấy repo "sạch" mà `git ls-files | wc -l` ra 10 thì đó chính là lỗi này.**

---

## 1. Tên nhánh

Không có nhánh tên `freebuff`. Tên thật:
`refs/heads/freebuff/1434fda45407dc1a68600843`.

## 2. Quan hệ lịch sử — đừng so bằng số commit

| | |
|---|---|
| Gốc chung | `3bad733` (2026-11-05) |
| `freebuff` | 336 commit, commit cuối `8fc5f0b` |
| Nhánh ta | 8 commit (đều sau `3bad733`) |
| `main` | **1 commit duy nhất** `ce17c47`, chứa toàn bộ code |

⚠️ `main` và `freebuff` **không có merge-base** — hai lịch sử rời nhau. `main` là
bản squash của cả dự án. Vì vậy:

- Đừng so `freebuff` với `main` — kết quả vô nghĩa.
- Đừng đọc "336 commit" như "đi trước 336 commit". Gốc `3bad733` **không có code**,
  nên cả hai nhánh đều "thêm mới" toàn bộ codebase. Số commit chỉ đo độ dài, không
  đo khoảng cách.

## 3. Nội dung: ai có gì

| | Số file |
|---|---|
| Chỉ `freebuff` có | **31** — toàn file **mới**, không trùng file nào của ta |
| Chỉ ta có | **43** — gồm toàn bộ lịch phỏng vấn/scorecard/thông báo |
| Cả hai có, **nội dung giống hệt** | 498 |
| Cả hai có, **nội dung khác** | **67** |
| Sẽ **conflict** nếu gộp | **4** |

### 3.1. `freebuff` là nhánh gì

Nhánh **UX/trải nghiệm phía frontend**, không đụng DB:

- `frontend/src/lib/`: `criterionQueue`, `duplicateCompare`, `finishSuggestion`,
  `idle`, `meCache`, `profilePrefetch`, `rubricCache` — tối ưu tải và phím tắt
- `frontend/src/app/positions/[id]/applicants/`: `by-criterion`, `compare`
- 13 file test mới (`criterion-queue`, `duplicate-compare`, `review-loop-metrics`,
  `sticky-bar-height`, `prefetch-next-profile`, …)
- Migration: **không có file nào mới**. Dừng ở `00037`.

### 3.2. Ta đi trước `freebuff` ở đâu

| Ta có, `freebuff` không |
|---|
| `00038`–`00041` (scan state, lịch PV, scorecard, thông báo) |
| `interviews.py`, `notifications.py` |
| `scorecards.py` **505 dòng** (freebuff: 264) |
| Bug fix hôm nay: `criteria.py` thêm `version_number` vào `SELECT` |

⚠️ **`freebuff` KHÔNG có bug fix `version_number`**. Nó có đúng lỗi 500 khi duyệt
bộ tiêu chí thứ hai. Nếu gộp theo hướng "lấy freebuff làm chuẩn" thì bug quay lại.

## 4. Bốn file conflict

| File | Bản chất | Cách xử |
|---|---|---|
| `frontend/package.json` | Cả hai cùng thêm tên file test vào `test:unit` | **Hợp cả hai**: union danh sách, không chọn bên nào |
| `frontend/src/i18n/en.json` | Ta 1941 key, freebuff 1897. **81 key chỉ freebuff có, 125 key chỉ ta có, 0 key trùng mà khác bản dịch** | **Union** → 2022 key. Không key nào đá nhau, nên gộp an toàn |
| `frontend/src/app/positions/[id]/page.tsx` | freebuff viết lại (267+/276−) — tối ưu tải, prefetch, phím tắt | **Khó nhất.** Lấy freebuff làm nền, áp lại phần lịch PV của ta |
| `doc/NHAT_KY_THAY_DOI.md` | Nhật ký hai bên, 1669+ dòng | Nối cả hai, sắp theo ngày |

### 4.1. Một vấn đề có sẵn, gộp sẽ làm nó to hơn

Sau khi union `en.json` thành 2022 key, có **30 giá trị tiếng Anh bị trùng** — ví dụ
`'Đang chờ'` và `'Chờ xử lý'` cùng dịch là `Pending`.

`translate()` dựng **bảng nghịch** (Anh → Việt) bằng `Object.fromEntries`, nên khoá
sau **ghi đè** khoá trước: dịch ngược `Pending` → `'Chờ xử lý'`, và `'Đang chờ'`
không bao giờ dịch ngược ra được.

Đây **không phải lỗi do gộp** — đã có sẵn. Nhưng gộp làm số cặp trùng tăng, và
không ai đang đếm nó. Đề xuất: thêm một test đếm số cặp trùng và chặn tăng thêm
(không sửa 30 cặp cũ ngay — sửa chúng là đổi nhãn người dùng đang thấy).

## 5. Điều đáng lo nhất — và nó không nằm ở 4 file conflict

**20 file backend khác nhau, và 12 file là code sản phẩm.** Nhưng khi đo bằng
`git merge-tree`, phần lớn **tự gộp được**. Cái không tự gộp được là **ngữ nghĩa**:

`freebuff` sửa `positions/[id]/page.tsx`, `api.ts`, `types/index.ts`, `Sidebar.tsx`
— đúng bốn **file nóng** mà `AGENTS.md` đã cảnh báo. Mà ta vừa thêm lịch PV,
thông báo, scorecard vào đúng bốn file đó. Merge tự động sẽ ra code **biên dịch
được nhưng sai**: ví dụ `Sidebar` có mục "Phỏng vấn" nhưng `types/index.ts` lấy
bản freebuff thì mất kiểu `InterviewNotification`.

**Đây là loại lỗi không có conflict marker.** Nó chỉ lộ khi chạy build + test thật.

## 6. Đề xuất: gộp theo 4 bước, có cổng kiểm từng bước

Không gộp một lần. Không `git merge`. Làm từng lớp, mỗi lớp CI xanh mới sang lớp sau.

| Bước | Việc | Cổng kiểm |
|---|---|---|
| **1** | Gộp phần **thuần thêm** của freebuff: 31 file mới + 13 test | `npm run test:unit` xanh với test mới; build xanh |
| **2** | Hợp `package.json` (union danh sách) + `en.json` (union key) | `test:i18n` xanh; `test-manifest` không báo file mồ côi |
| **3** | Gộp `lib/` của freebuff (`criterionQueue`, `idle`, `meCache`, `rubricCache`…) + nối vào chỗ dùng | test của chính freebuff xanh; đo lại số request |
| **4** | `positions/[id]/page.tsx` — lấy freebuff làm nền, áp lại phần lịch PV | **Chạy tay** cả hai đường: mở hồ sơ, và xem lịch PV. Test tự động không đủ |

Sau 4 bước: chạy `bash scripts/test-db.sh` + full test (671 backend / 163 FE),
rồi mới tính chuyện deploy.

### 6.1. Ba việc phải làm trước bước 1

1. **Chốt: `freebuff` có phải nhánh cần gộp không?** Nó không có migration nào,
   nên gộp nó **không** đổi DB. Nhưng nó cũng không có gì ta đang thiếu về nghiệp
   vụ — toàn là tối ưu UX. Nếu mục tiêu là "xong tính năng trước 2 tuần" thì gộp
   nó là **hoãn** mục tiêu đó.
2. **Xác nhận `freebuff` không còn ai đang làm.** Commit cuối: **2026-11-25 16:02**
   (`8fc5f0b`, "phím f hoàn tất hồ sơ"). Tính tới hôm nay là **5 ngày im lặng**.
   Có vẻ đã dừng, nhưng cần người xác nhận — repo không tự biết được.
3. **Kiểm fork có chạy CI** (câu hỏi A0 #1, vẫn chưa trả lời).

### 6.2. Điều tôi khuyên

**Chưa gộp `freebuff` ngay.** Lý do:

- Nó không mang tính năng nào ta thiếu, chỉ là tối ưu UX.
- Nó **không có** bug fix `version_number` — gộp sai hướng là đưa bug trở lại.
- Gộp nó đụng đúng 4 file nóng, ngay lúc 4 agent sắp sửa song song.

Trình tự an toàn hơn: **deploy lần đầu trước** (phiếu A2, đang chờ), rồi gộp
`freebuff` sau khi CI + E2E đã chứng minh bản hiện tại chạy được. Gộp vào một bản
chưa từng chạy là hai rủi ro chồng lên nhau, không tách được cái nào gây lỗi.

Nếu ngược lại, muốn gộp ngay: **bắt buộc** làm đủ 4 bước ở §6, không tắt cổng nào.
