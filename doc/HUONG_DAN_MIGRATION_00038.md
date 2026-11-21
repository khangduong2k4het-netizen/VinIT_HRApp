# Migration `00038` — trạng thái quét virus của tệp hồ sơ

> **✅ ĐÃ ÁP ngày 2026-11-21** trên project `myrymlqdqmpynesiwk`
> (migration `document_scan_state_00038`). Hậu kiểm đạt (mục 3). **Không chạy lại.**

## 1. Vì sao cần

Đường nhận CV (`careers_intake.py`) fail-closed khi ClamAV không trả lời. Đúng cho
production — tệp được lưu lại và đẩy vào hàng xử lý. Nhưng ở vòng thử nghiệm nó
làm tắc **toàn bộ** form ứng tuyển vì một dịch vụ phụ, và người nộp chỉ nhận
"Không thể tiếp nhận tệp".

Hướng đã thống nhất (HANG-01 trong `VIEC_CHO_LAM.md`): có cờ rõ ràng thì **vẫn
nhận**, nhưng bản ghi phải mang dấu "chưa quét" và phải có audit.

Cột này là chỗ mang dấu đó. Không có cột thì hồ sơ nhận vào lúc máy quét chết
trông y hệt hồ sơ đã quét sạch — với HR, và với bất kỳ ai đối soát về sau.

## 2. Thay đổi

```sql
ALTER TABLE app_private.application_documents
    ADD COLUMN scan_state TEXT NOT NULL DEFAULT 'SCANNED'
    CHECK (scan_state IN ('SCANNED', 'UNSCANNED', 'INFECTED'));
CREATE INDEX idx_application_documents_unscanned
    ON app_private.application_documents (application_id)
    WHERE scan_state <> 'SCANNED';
```

Ba quyết định:

- **`DEFAULT 'SCANNED'`** — mọi tệp đang có đều đã đi qua đường fail-closed. Để
  `NULL` thì mỗi chỗ đọc phải tự quyết `NULL` nghĩa là gì, và sẽ có chỗ quyết sai.
- **Giữ `INFECTED` trong `CHECK`** dù hiện không đường nào ghi được giá trị này
  (tệp bẩn bị chặn trước khi tạo dòng). Nếu sau này có nơi ghi lại tệp bẩn thì nó
  có chỗ để ghi, thay vì bị nhồi thành `UNSCANNED` và mất thông tin.
- **Chỉ số bộ phận** `WHERE scan_state <> 'SCANNED'` — hồ sơ chưa quét là thiểu
  số; đánh chỉ số toàn bảng là phí cho mọi lần ghi CV.

## 3. Hậu kiểm sau khi áp

| Kiểm | Kết quả |
|---|---|
| Cột tồn tại, kiểu `text` | ✅ |
| `column_default` | `'SCANNED'::text` ✅ |
| `is_nullable` | `NO` ✅ |
| Dòng hiện có bị đổi giá trị | Không — `DEFAULT` chỉ áp cho dòng mới; dòng cũ nhận `'SCANNED'` |

## 4. Không cần áp trước khi deploy — nhưng phải áp cùng lượt

Đây là cột **chỉ thêm**, có `DEFAULT`, nên code cũ chạy trên schema mới vẫn đúng,
và code mới chạy trên schema cũ sẽ lỗi ở `INSERT` (cột không tồn tại). Nghĩa là:

- Áp migration trước rồi deploy sau: an toàn.
- Deploy trước khi áp: **mọi lần nộp CV đều 500** cho tới khi áp.

`scripts/deploy.sh` sẽ `exit 2` vì `supabase/migrations` thay đổi — chạy lại với
`--migrations-verified` sau khi đã áp (đã áp rồi, xem đầu file).
