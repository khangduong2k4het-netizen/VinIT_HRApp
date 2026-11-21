-- Trạng thái quét virus của tệp hồ sơ.
--
-- Vì sao cần cột này: đường nhận CV (careers_intake.py) fail-closed khi ClamAV
-- không chạy — đúng, vì tệp được lưu lại và đẩy vào hàng xử lý. Nhưng khi bật
-- PUBLIC_CAREERS_UNSCANNED_FILES_ENABLED (chỉ ở vòng thử nghiệm), hồ sơ vẫn
-- được nhận và tệp vẫn được lưu mà **chưa ai quét**. Không có dấu vết nào trên
-- bản ghi thì HR mở hồ sơ ra không biết điều đó, và về sau cũng không ai đối
-- soát được hồ sơ nào đã vào hệ thống trong lúc máy quét chết.
--
-- Vì sao là cột trên application_documents chứ không phải bảng riêng: một tệp
-- có đúng một trạng thái quét. Bảng riêng chỉ thêm một phép join cho mọi câu
-- đọc tài liệu mà không thêm khả năng gì.
--
-- Vì sao mặc định SCANNED: mọi tệp đang có trong hệ thống đều đã đi qua đường
-- fail-closed (hoặc đã được quét sạch), nên gán nhãn cũ cho chúng là đúng. Nếu
-- để NULL rồi suy diễn thì mỗi chỗ đọc phải tự quyết NULL nghĩa là gì.
ALTER TABLE app_private.application_documents
    ADD COLUMN scan_state TEXT NOT NULL DEFAULT 'SCANNED'
    CHECK (scan_state IN ('SCANNED', 'UNSCANNED', 'INFECTED'));

-- Tệp INFECTED không bao giờ được ghi vào bảng này (đường nhận tệp chặn trước
-- khi tạo dòng), nhưng giữ giá trị trong CHECK để schema nói đúng ý định: nếu
-- sau này có nơi ghi lại tệp bẩn thì nó có chỗ để ghi, thay vì bị nhồi thành
-- 'UNSCANNED' và mất thông tin.

-- Truy vấn cần: "hồ sơ nào có tệp chưa quét" cho bảng đối soát của HR.
CREATE INDEX idx_application_documents_unscanned
    ON app_private.application_documents (application_id)
    WHERE scan_state <> 'SCANNED';

COMMENT ON COLUMN app_private.application_documents.scan_state IS
    'SCANNED: đã quét sạch. UNSCANNED: nhận trong lúc ClamAV không chạy (chỉ khi bật cờ thử nghiệm). INFECTED: phát hiện mã độc — hiện không ghi được qua đường nhận tệp.';
