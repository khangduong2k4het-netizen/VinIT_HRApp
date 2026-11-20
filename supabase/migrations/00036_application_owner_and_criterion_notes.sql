-- Ghi chú HR gắn với từng tiêu chí, và người phụ trách từng hồ sơ.
--
-- Hai thứ này cùng một lý do: khi hai HR làm chung một vị trí, một nhận xét
-- ("tiêu chí 3 nói có chứng chỉ X, tôi thấy không đúng") phải nằm cạnh đúng tiêu
-- chí và phải biết ai đang giữ hồ sơ. Không có hai mốc đó thì ghi chú rời rạc ở
-- cuối trang và công việc bị làm trùng.

ALTER TABLE app_private.applications
    ADD COLUMN IF NOT EXISTS assigned_to UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS applications_assigned_to_idx
    ON app_private.applications (assigned_to);

COMMENT ON COLUMN app_private.applications.assigned_to IS
    'HR đang phụ trách hồ sơ này; NULL nghĩa là chưa ai nhận. Không thay thế position_assignments — đó là quyền, đây là việc đang làm.';

-- Tiêu chí của đúng phiên bản đã đánh giá hồ sơ. FK để một tiêu chí bị xoá
-- không để lại ghi chú trỏ vào hư không; ON DELETE SET NULL biến nó thành ghi
-- chú chung thay vì xoá mất nội dung HR đã viết.
ALTER TABLE app_private.application_private_notes
    ADD COLUMN IF NOT EXISTS criterion_id UUID REFERENCES app_private.criteria_items(criterion_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS application_private_notes_criterion_idx
    ON app_private.application_private_notes (application_id, criterion_id);

COMMENT ON COLUMN app_private.application_private_notes.criterion_id IS
    'NULL = ghi chú chung của hồ sơ; ngược lại là ghi chú cho một tiêu chí cụ thể.';
