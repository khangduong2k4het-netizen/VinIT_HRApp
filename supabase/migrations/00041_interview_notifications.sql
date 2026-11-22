-- Thông báo trong ứng dụng cho lịch phỏng vấn (00041).
--
-- Phạm vi đã chốt với người dùng: **trong app trước, email sau**. Vì vậy ở đây
-- KHÔNG có cột email, KHÔNG có trạng thái "đã gửi thư". Thêm một cột như
-- `emailed_at` bây giờ là hứa một việc hệ thống chưa làm, và đúng loại cột mà
-- người đọc sau sẽ tưởng đã chạy — cùng lý do Q4 của đề xuất gốc không thêm cột
-- thông báo ứng viên.
--
-- Thông báo suy ra từ sự kiện trên lịch, không phải bản sao nội dung buổi:
-- `interviews` đã là nguồn sự thật, chép giờ/nơi vào đây sẽ lệch ngay lần sửa
-- lịch đầu tiên. Bảng chỉ giữ "ai cần biết, chuyện gì đã xảy ra, lúc nào".

CREATE TABLE IF NOT EXISTS app_private.interview_notifications (
    notification_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Người nhận. NULL = thông báo hệ thống, hiện không dùng, nhưng để mở đường
    -- cho việc sau này mà không phải đổi kiểu cột (khoá ngoại thêm sau thì rẻ).
    user_id          uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    interview_id     uuid NOT NULL REFERENCES app_private.interviews(interview_id) ON DELETE CASCADE,
    -- Loại sự kiện. Giữ dạng text thay vì enum: thêm loại mới không cần migration
    -- khoá, và màn hình chỉ cần bỏ qua loại nó chưa biết.
    kind             text NOT NULL,
    -- Người gây ra sự kiện, để câu thông báo nói được "ai đổi".
    actor_user_id    uuid REFERENCES auth.users(id),
    -- Nội dung thay đổi có cấu trúc (giờ cũ/mới, người thêm/bớt). jsonb vì mỗi
    -- loại cần một hình dạng khác nhau; ràng buộc chặt ở đây sẽ phải sửa mỗi
    -- lần thêm loại, mà giá trị thật thì không đáng.
    payload          jsonb NOT NULL DEFAULT '{}'::jsonb,
    read_at          timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT interview_notifications_kind_check
        CHECK (kind IN ('INTERVIEW_CREATED', 'INTERVIEW_UPDATED', 'INTERVIEW_CANCELLED',
                        'PARTICIPANTS_CHANGED', 'SCORECARD_DUE_SOON'))
);

-- Truy vấn nóng: "thông báo chưa đọc của tôi", mới nhất trước.
CREATE INDEX IF NOT EXISTS idx_interview_notifications_unread
    ON app_private.interview_notifications (user_id, created_at DESC)
    WHERE read_at IS NULL;

-- Và lịch sử theo buổi, cho màn chi tiết.
CREATE INDEX IF NOT EXISTS idx_interview_notifications_interview
    ON app_private.interview_notifications (interview_id, created_at DESC);

-- Cùng khuôn với 00039: client trực tiếp không đi vòng qua kiểm tra của API.
DO $$ BEGIN
    ALTER TABLE app_private.interview_notifications ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON TABLE app_private.interview_notifications FROM PUBLIC, anon, authenticated;
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE app_private.interview_notifications TO service_role;
END $$;

COMMENT ON TABLE app_private.interview_notifications IS
    'Thông báo lịch phỏng vấn TRONG ỨNG DỤNG. Cố ý không có cột email/đã gửi: email là việc sau, và một cột "đã gửi" ở đây sẽ nói dối.';
COMMENT ON COLUMN app_private.interview_notifications.payload IS
    'Mô tả thay đổi ({from, to}, {added_usernames}, …). Không chép nội dung buổi — interviews là nguồn sự thật duy nhất.';
