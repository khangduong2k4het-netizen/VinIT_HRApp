# Việc có thể làm ngay — rà soát phần treo các phase trước

Ngày rà: 2026-11-21. HEAD lúc rà: `9e0933b`. Nhánh `arena/ea6e2570-vinit-hrapp`.

**Cách rà.** Đọc lại bốn tài liệu treo (`VIEC_CHO_LAM.md`,
`PHASE1_PRODUCTION_DEFERRED_REPORT.md`, `TONG_HOP_DONG_PHASE_UIUX.md`,
`PHASE2_IMPLEMENTATION_PLAN.md`) rồi **đối chiếu từng mục với code hiện tại** —
không tin trạng thái ghi trong tài liệu, vì ba trong bốn lần rà trước đều phát
hiện tài liệu ghi "chưa làm" trong khi code đã xong.

**Tiêu chí "làm được ngay".** Chỉ nhận việc thoả **cả ba**:

1. Không cần quyết định nghiệp vụ/pháp lý của người khác (Privacy, Legal, DevOps, HR).
2. Không cần môi trường ngoài sandbox (VPS, staging, Chromium, dữ liệu thật).
3. Không cần migration chưa được duyệt — hoặc migration đó chỉ thêm bảng/cột
   mới, không đụng dữ liệu đang có.

Việc không thoả thì xếp vào phần C (chờ), kèm lý do cụ thể.

---

## A. Làm được ngay — 6 việc

| # | Việc | Ưu tiên | Ước lượng | Vì sao làm được ngay |
|---|---|---|---|---|
| A1 | ~~Nối `retention execute/recover` vào giao diện~~ | **ĐÃ CHỐT: rút** | — | Anh chọn *giữ nguyên* ngày 2026-11-21: không đưa nút xoá dữ liệu thật vào UI |
| A2 | Đưa ClamAV vào `/health/ready` | ✅ **Xong** `93a9120` | 1 giờ | 8 test; báo `connected`/`unavailable`/`disabled`, không trả 503 khi thiếu máy quét |
| A3 | Bảng `ux_events` + endpoint tổng hợp số đo UX | Trung bình | 4–6 giờ | Dữ liệu đã có sẵn ở client, chỉ thiếu chỗ lưu và chỗ cộng |
| A4 | Cờ "hồ sơ chưa quét virus" cho luồng nộp CV | Trung bình | 3–4 giờ + migration | Hướng đã thống nhất trong `VIEC_CHO_LAM.md` HANG-01 |
| A5 | 3.8 — sửa tiêu chí tại chỗ (cách B) | Thấp | 2–3 giờ | API và `criteriaApi.updateItem` đã có sẵn |
| A6 | Dọn tài liệu treo sai trạng thái | ✅ **Xong** (cùng commit) | 30 phút | Đã sửa `VIEC_CHO_LAM` mục 3 và `TONG_HOP §3` |

## B. Chi tiết từng việc

### A1 — Nối `retention execute/recover` vào giao diện

**Hiện trạng đã kiểm trong code.**

- `backend/app/api/retention.py:161` — `POST /retention/cases/{case_id}/execute`.
- `backend/app/api/retention.py:175` — `POST /retention/cases/{case_id}/recover`
  (nhận `RetentionRecoveryRequest`, có xác nhận).
- `frontend/src/lib/api.ts:302` — `retentionApi` **chỉ có 4 hàm**: `listCases`,
  `generateCases`, `confirmCase`, `cancelCase`. **Thiếu `execute` và `recover`.**
- `frontend/src/app/data-retention/page.tsx:116` — nút hành động chỉ gọi
  `confirmCase`/`cancelCase`.

Nghĩa là tài liệu ghi "chờ làm" là **đúng một nửa**: backend xong, giao diện chưa
nối. Muốn xoá dữ liệu thật hiện vẫn phải gọi API bằng tay.

**Nhưng đọc kỹ comment cạnh `retentionApi` (`api.ts:300`) thì đây là quyết định,
không phải thiếu sót:** *"liệt kê, tạo, xác nhận, huỷ; bước thực thi nằm ngoài
màn hình này"*. Ai đó đã cố ý không đặt nút xoá dữ liệu thật vào giao diện.

Vì vậy tôi **hạ ưu tiên A1 và không coi đây là việc hiển nhiên nên làm**. Có hai
đường, và anh đã chọn **giữ nguyên (2026-11-21)** — A1 rút khỏi danh sách.
Ghi lại hai đường để lần sau không mở lại mà không có lý do mới:

- **Giữ nguyên quyết định cũ** → A1 rút khỏi danh sách; chỉ còn A6 (sửa câu chữ
  tài liệu cho khớp sự thật). Cách này an toàn nhất.
- **Đưa vào UI nhưng có rào** → nút chỉ hiện cho HR Lead/Admin, xác nhận hai bước
  bằng cách gõ lại mã vị trí, và không tự retry khi storage lỗi (đúng A3).

Tôi nghiêng về **giữ nguyên**: thao tác này xoá dữ liệu không hoàn tác được, và
một nút bấm được luôn dễ bấm nhầm hơn một lệnh gọi API có chủ đích.

**Phạm vi.**

1. `retentionApi.execute(caseId)` và `retentionApi.recover(caseId, body)`.
2. Nút "Thực thi" chỉ hiện khi case đã `CONFIRMED`; bấm mở dialog xác nhận hai
   bước, gõ lại đúng mã vị trí để bật nút — không dùng "OK/Cancel".
3. Nút "Phục hồi" cho case `FAILED`/`IN_PROGRESS`, có ô nhập lý do bắt buộc.
4. Hiện kết quả từng phần (xoá DB / xoá storage) vì chúng không atomic — đúng
   ghi chú A3 trong `PHASE1_PRODUCTION_DEFERRED_REPORT.md`.

**Rủi ro phải chặn.** Đây là thao tác phá huỷ. Không làm nút này cho người
không phải HR Lead/Admin; không tự retry khi storage lỗi (A3 đã chốt là **không
tự retry**). Test phải khoá cả hai điều đó.

**Đã chốt:** giữ nguyên, không nối vào UI. Muốn mở lại thì cần lý do mới, không
phải chỉ vì "backend có sẵn".

---

### A2 — Đưa ClamAV vào `/health/ready`

**Hiện trạng.** `backend/app/main.py:57` — `/health/ready` **chỉ** kiểm DB. Tài
liệu HANG-01/HANG-03 ghi đúng: scanner chết mà health vẫn báo `ready`.

Hệ quả cụ thể: `careers_intake.py:39` chặn cứng khi `CLAMAV_UNIX_SOCKET` rỗng →
ứng viên nhận 503, nhưng không có cảnh báo nào cho người vận hành.

**Phạm vi.**

1. `/health/ready` trả thêm `clamav: "connected" | "unavailable" | "disabled"`.
2. **Không** đổi HTTP status thành 503 khi ClamAV chết — làm vậy sẽ khiến load
   balancer rút backend khỏi vòng phục vụ chỉ vì thiếu scanner, trong khi phần
   lớn chức năng vẫn chạy được. Chỉ báo trạng thái, để giám sát bắt.
3. Thêm cờ `readiness_require_clamav` (mặc định `false`) cho ai muốn siết.
4. Test: socket không tồn tại → `unavailable` mà vẫn 200; socket có → `connected`.

**Vì sao tách khỏi A4.** A2 là quan sát, không đổi hành vi nghiệp vụ. A4 mới là
đổi cách nhận hồ sơ.

---

### A3 — Bảng `ux_events` + endpoint tổng hợp số đo UX

**Hiện trạng.** `frontend/src/lib/uxMetrics.ts` ghi 4 loại event vào
**localStorage** của chính trình duyệt; chú thích trong file nói rõ số đo "chỉ
nói về trình duyệt này". Backend **không có** bảng hay endpoint nào
(grep `ux_event|ux_metric|telemetry` trong `backend/app` = 0 kết quả).

**Phạm vi.**

1. Migration mới `00038_ux_events.sql`: bảng chỉ-thêm
   `(event_id, actor_user_id, event_type, application_id, position_id, duration_ms,
   records, failed, occurred_at, received_at)`. Không lưu nội dung hồ sơ — giữ
   đúng nguyên tắc đã ghi trong `uxMetrics.ts`.
2. `POST /ux-events` nhận lô ≤ 50 event, kiểm `event_type` theo whitelist, cắt
   `duration_ms` bất thường (> 30 phút, đúng ngưỡng đã dùng ở client).
3. `GET /admin/ux-metrics?from&to&group_by=week|position|actor` trả trung vị
   dwell, số lượt, tỉ lệ hoàn tất, thời gian/lô. Chỉ HR Lead/Admin.
4. Client gửi bù: đọc localStorage, gửi, xoá sau khi thành công. Gửi **sau** khi
   rời trang, không chặn thao tác.

**Cần quyết trước khi code:** có. Đây là dữ liệu hành vi đo trên người dùng thật
— cần HR/Privacy xác nhận lưu ở máy chủ (dù không có PII, vẫn là dữ liệu quan
sát nhân viên). **Đề xuất: làm phần backend + test trước, giữ cờ
`UX_METRICS_SERVER_ENABLED=false`, chỉ bật khi có xác nhận.** Như vậy không phải
chờ để bắt đầu.

---

### A4 — Cờ "hồ sơ chưa quét virus"

**Hiện trạng.** `careers_intake.py:39` chặn 503 khi thiếu socket. Cờ
`PUBLIC_CAREERS_UNSCANNED_FILES_ENABLED` **đã có** trong
`config.py:48` và đã dùng ở `careers.py:90` + `jd_import.py:75,98` — nhưng
**chưa** dùng ở đường nhận CV. Tức là hướng đã thống nhất chỉ mới áp cho đường
nhập JD.

**Phạm vi.**

1. `careers_intake.py`: khi cờ bật và không có socket → vẫn nhận hồ sơ, đánh dấu
   `unscanned`.
2. Migration `00038` (gộp với A3 hoặc tách): thêm cột
   `application_documents.scan_state text` với `CHECK IN ('SCANNED','UNSCANNED','INFECTED')`,
   mặc định `'SCANNED'` cho dữ liệu cũ.
3. Hiện nhãn cảnh báo trong danh sách hồ sơ cho HR.
4. **Giữ fail-closed khi tệp bẩn** và khi cờ tắt — đúng như A4/HANG-01 đã chốt.

**Cần quyết trước khi code:** có, nhưng nhỏ — chỗ lưu cờ. Đề xuất cột trên
`application_documents` thay vì bảng riêng: một tệp một trạng thái, bảng riêng
chỉ thêm một phép join.

---

### A5 — 3.8 sửa tiêu chí tại chỗ (cách B)

**Hiện trạng đã kiểm.** Backend `PATCH /criteria/{version_id}/items/{criterion_id}`
có ở `criteria.py:566`, chỉ cho sửa khi version chưa duyệt. Frontend đã nối
`criteriaApi.updateItem` (`api.ts:100`). Hiện sửa một tiêu chí = mở dialog.

**Phạm vi (cách B, đã cân nhắc trong `TONG_HOP_DONG_PHASE_UIUX.md` §6.1).**
Inline **chỉ** `name` + `description`; các trường còn lại (`category`,
`weight_in_group`, `expected_evidence_keywords`, `requirement_spec`) vẫn qua
dialog. Trên UI phải nói rõ cái nào sửa tại chỗ được, nếu không sẽ thành hai kiểu
sửa khó hiểu.

**Cần quyết trước khi code:** khuyến nghị cũ là **chờ dữ liệu usability** trả lời
"HR có sửa nhiều tiêu chí liên tiếp không". Nếu sửa 1–2 tiêu chí mỗi lần thì
việc này gần như vô giá trị. Đây là quyết định của anh, không phải của tôi —
nên tôi để A5 ở cuối bảng.

---

### A6 — Dọn tài liệu treo sai trạng thái

Lần rà này tìm được **hai chỗ sai**:

1. `VIEC_CHO_LAM.md` mục 3 ghi "Retention `execute`/`recover` (UI + xác nhận hai
   bước) — Chờ làm" → backend **đã xong**; chỉ UI còn.
2. `TONG_HOP_DONG_PHASE_UIUX.md` §3 ghi "Migration chưa áp lên VPS: `00033`,
   `00034`" → **đã áp thật**; đối chiếu `list_migrations` của project
   `myrymlqdbyqmpynesiwk` thấy `app_settings_00033` (`20261119093753`) và
   `hr_criterion_reviews_00034` (`20261119093801`), cộng `00035`, `00036`,
   `00037` sau đó. Migration mới nhất trên DB là `00037` (`20261120093000`),
   khớp với repo — **không còn migration nào chưa áp**.

Sửa để lần rà sau không mất thời gian dò lại. Rẻ, làm cùng lúc với việc khác.

---

## C. KHÔNG làm được ngay — và vì sao

| Việc | Chặn bởi | Cần ai |
|---|---|---|
| **Lịch phỏng vấn & scorecard** (mục 1 `VIEC_CHO_LAM.md`) | 4 câu hỏi nghiệp vụ chưa trả lời: ai được tạo lịch, một buổi có nhiều người phỏng vấn không, múi giờ, ứng viên có nhận thông báo không | Anh/HR |
| Deploy lên VPS | Cần chạy `deploy.sh` trên máy chủ, không phải sandbox | DevOps/Anh |
| E2E Playwright, usability staging | Không có Chromium trong sandbox; usability cần HR thật | Anh + HR |
| DEP-01…DEP-08 | Chờ DevOps/Privacy/Legal/HR, phần lớn là kiểm chứng môi trường | Nhiều bên |
| Sinh tiêu chí chạy nền (HANG-04 B) | Điều kiện kích hoạt là "HR thực sự gặp 504" hoặc "cần sinh hàng loạt" — **chưa có dấu hiệu nào** | Anh xác nhận |
| HANG-02 (thử scanner chết trên VPS) | Cần VPS + quyền systemctl | DevOps |
| HANG-03 (cron giám sát) | Cần VPS | DevOps |
| Rà thuật ngữ VI/EN (B7) | "TẠM TREO — CHỜ REPORT" theo yêu cầu của anh | Anh + HR |
| F2.08 SSO, rediscovery, LTR/BGE | Tạm treo có chủ đích, chờ quyết định pháp lý/chất lượng | Anh + Privacy |

---

## D. Thứ tự đề xuất

Xếp theo **rủi ro giảm được trên một giờ công**, không theo độ lớn tính năng.

| Bước | Việc | Vì sao đứng ở đây |
|---|---|---|
| 1 | **A2** ClamAV vào health | 1 giờ, biến một lỗi im lặng thành tín hiệu nhìn thấy được. Không phụ thuộc ai. |
| 2 | **A6** dọn tài liệu sai | 30 phút, làm ngay sau A2 vì cùng đụng tài liệu vận hành. |
| 3 | **A1** nối retention UI — **chỉ khi anh chọn đường "có rào"** | Làm được ngay về kỹ thuật, nhưng đang là quyết định cố ý "không đặt nút". Không tự mở lại. |
| 4 | **A4** cờ chưa quét cho CV | Hoàn thiện hướng đã thống nhất; vá đúng chỗ ClamAV chết làm tắc cả form. |
| 5 | **A3** backend số đo UX | Làm phần backend + cờ tắt là được; không phải chờ Privacy để bắt đầu. |
| 6 | **A5** sửa tiêu chí inline | Chỉ làm sau khi anh quyết; xem lý do ở A5. |

**Nếu chỉ có một buổi:** **A2 → A6 → A4**. Cả ba không cần ai quyết và mỗi việc
đóng một lỗ có thể gây hại thật. A1 chỉ vào khi anh trả lời câu hỏi ở mục A1.

**Điều tôi sẽ không làm mà không hỏi lại:** bật `UX_METRICS_SERVER_ENABLED`
(A3), đổi hành vi nhận CV (A4) trên môi trường thật, và mọi thứ trong phần C.
