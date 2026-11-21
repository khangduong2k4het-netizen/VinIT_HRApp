-- 00037: thêm trạng thái SUPERSEDED cho criteria_versions.
--
-- Vì sao: một vị trí chỉ được có MỘT bộ tiêu chí đang hiệu lực. Trước đây
-- duyệt bộ mới không hạ bộ cũ, nên vị trí có thể có hai bộ cùng APPROVED cho
-- một JD — người đọc sau không biết ứng viên cũ đã chấm bằng bộ nào.
--
-- Vì sao không dùng lại ARCHIVED/REJECTED: hai trạng thái đó mang nghĩa "bị
-- loại bỏ có chủ ý". Một bộ đã duyệt rồi bị bộ khác thay thế KHÔNG bị loại —
-- nó vẫn là bằng chứng đã duyệt và đã dùng để chấm ứng viên trước đó. Gộp hai
-- nghĩa này vào một nhãn là làm mất đúng thứ tự cần truy khi có khiếu nại.
--
-- Idempotent: chạy lại không hỏng.

BEGIN;

ALTER TABLE app_private.criteria_versions
    DROP CONSTRAINT IF EXISTS criteria_versions_status_check;

ALTER TABLE app_private.criteria_versions
    ADD CONSTRAINT criteria_versions_status_check CHECK (status IN (
        'DRAFT', 'PENDING_HR_REVIEW', 'PENDING_HM_APPROVAL',
        'APPROVED', 'REJECTED', 'SUPERSEDED'
    ));

-- Truy vấn "bộ nào đang hiệu lực của vị trí này" chạy trên mọi lần chấm điểm
-- và mọi lần tải tab Tiêu chí. Index riêng cho trạng thái hiệu lực, một phần
-- để không phình theo số bản nháp/bị thay thế tích tụ theo thời gian.
CREATE INDEX IF NOT EXISTS criteria_versions_effective_idx
    ON app_private.criteria_versions (position_id, jd_version_id, version_number DESC)
    WHERE status IN ('APPROVED', 'PENDING_HR_REVIEW', 'PENDING_HM_APPROVAL', 'DRAFT');

COMMENT ON COLUMN app_private.criteria_versions.status IS
    'DRAFT nháp; PENDING_* đang chờ duyệt; APPROVED đang hiệu lực (tối đa một bộ mỗi vị trí); REJECTED bị từ chối; SUPERSEDED từng duyệt rồi bị bộ mới thay thế.';

COMMIT;
