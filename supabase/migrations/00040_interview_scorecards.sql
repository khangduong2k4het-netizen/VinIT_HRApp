-- Mở khoá scorecard để chấm được theo BUỔI phỏng vấn (B2).
--
-- Vì sao không viết scorecard thứ hai: bảng hiện có đã đủ thứ cần cho một vòng
-- phỏng vấn — criteria_version_id (snapshot rubric đúng lúc), due_at, 4 mức
-- overall_recommendation, strengths/concerns, revision, submit/reopen có event.
-- Nhân bản 8 route của scorecards.py để có thêm một bản sao là cách chắc chắn
-- nhất để hai đường lệch nhau, và mọi báo cáo "điểm theo tiêu chí" sau đó phải
-- hợp hai nguồn.
--
-- Rủi ro duy nhất là nới ràng buộc trên bảng đang có dữ liệu. Ba điều làm nó
-- an toàn:
--   1. DROP NOT NULL chỉ NỚI, không thể làm hỏng dòng cũ.
--   2. Mọi dòng cũ đều còn share_item_id nên vẫn thoả CHECK đúng-một-nguồn.
--   3. Dòng cũ có interview_id = NULL nên không lọt vào unique index mới.

ALTER TABLE app_private.shortlist_scorecards
    ALTER COLUMN share_item_id DROP NOT NULL,
    ADD COLUMN interview_id uuid REFERENCES app_private.interviews(interview_id) ON DELETE CASCADE;

-- Đúng một trong hai nguồn phải có mặt. Không có CHECK này thì một scorecard
-- mồ côi (không share, không buổi) vẫn tồn tại được, và nó sẽ nằm trong mọi
-- báo cáo mà không ai mở ra được.
--
-- Viết dạng (a IS NOT NULL)::int + (b IS NOT NULL)::int = 1 chứ không dùng
-- "a IS NOT NULL <> b IS NOT NULL" để đọc ra ngay ý định: cộng đúng bằng 1.
ALTER TABLE app_private.shortlist_scorecards
    ADD CONSTRAINT scorecard_has_exactly_one_source
    CHECK ((share_item_id IS NOT NULL)::int + (interview_id IS NOT NULL)::int = 1);

-- Một người chấm một buổi đúng một lần. Không có index này thì gọi endpoint
-- sinh scorecard hai lần sẽ tạo hai bản cho cùng người, và người đó thấy hai
-- ô điểm cho một tiêu chí.
CREATE UNIQUE INDEX uq_scorecard_interview_reviewer
    ON app_private.shortlist_scorecards (interview_id, reviewer_user_id)
    WHERE interview_id IS NOT NULL;

CREATE INDEX idx_scorecard_interview ON app_private.shortlist_scorecards (interview_id)
    WHERE interview_id IS NOT NULL;

COMMENT ON COLUMN app_private.shortlist_scorecards.share_item_id IS
    'Đường share shortlist (cũ). NULL khi scorecard thuộc một buổi phỏng vấn.';
COMMENT ON COLUMN app_private.shortlist_scorecards.interview_id IS
    'Buổi phỏng vấn (B2). NULL khi scorecard thuộc đường share. Đúng một trong hai cột có giá trị.';
