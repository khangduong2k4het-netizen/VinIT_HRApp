-- Lịch phỏng vấn (B1) — bảng buổi phỏng vấn + người tham gia.
--
-- Vì sao cần: hệ thống dừng ở sàng lọc. Hồ sơ đi SHORTLIST → INTERVIEW →
-- OFFERED/REJECTED_INTERVIEW, nhưng không có nơi nào ghi MỘT BUỔI phỏng vấn:
-- ai, khi nào, ở đâu, vòng mấy. "Hồ sơ đang ở vòng phỏng vấn" vì thế chỉ là một
-- nhãn, không phải một kế hoạch; HR vẫn giữ lịch ở email/Excel.
--
-- Bốn quyết định đã chốt (xem doc/DE_XUAT_LICH_PHONG_VAN.md §1):
--   Q1 ai tạo lịch   -> HR phụ trách + HR_LEAD (kiểm ở API, không phải ở bảng)
--   Q2 nhiều người   -> CÓ, bảng interview_participants, mỗi người một scorecard
--   Q3 bắt buộc vòng -> CÓ, round_number NOT NULL
--   Q4 gửi thư       -> KHÔNG ở vòng này, nên bảng không có cột trạng thái gửi thư
--
-- Cố ý KHÔNG thêm cột nào cho thông báo/gửi thư. Thêm cột "notified_at" rỗng
-- rồi không ai ghi vào là dấu hiệu tính năng nửa vời; khi làm Q4 sẽ thêm sau,
-- cùng migration với bảng outbox của nó.

CREATE TABLE app_private.interviews (
    interview_id   uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id uuid NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    round_number   smallint NOT NULL DEFAULT 1 CHECK (round_number BETWEEN 1 AND 10),
    status         text NOT NULL DEFAULT 'SCHEDULED'
                   CHECK (status IN ('SCHEDULED', 'DONE', 'CANCELLED', 'NO_SHOW')),
    -- LUÔN lưu UTC. API bắt buộc offset khi nhận, giao diện hiện GMT+7.
    starts_at      timestamptz NOT NULL,
    ends_at        timestamptz NOT NULL,
    location_kind  text NOT NULL CHECK (location_kind IN ('ONSITE', 'ONLINE', 'PHONE')),
    -- Phòng họp / link / số điện thoại. ONSTE để trống được (phòng chưa chốt),
    -- ONLINE và PHONE thì không — hẹn online mà không có link là hẹn suông.
    location_text  text,
    created_by     uuid REFERENCES auth.users(id),
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_at > starts_at),
    CHECK (location_kind = 'ONSITE' OR (location_text IS NOT NULL AND btrim(location_text) <> ''))
);

-- Một hồ sơ không thể có hai buổi cùng vòng còn hiệu lực. Ràng buộc nằm ở DB
-- chứ không ở API: hai HR bấm đặt lịch cùng lúc thì chỉ một người thắng, và
-- người kia nhận lỗi rõ ràng thay vì hai buổi trùng nhau không ai biết.
-- Buổi CANCELLED/NO_SHOW không tính, để huỷ rồi đặt lại cùng vòng vẫn được.
CREATE UNIQUE INDEX uq_interviews_active_round
    ON app_private.interviews (application_id, round_number)
    WHERE status IN ('SCHEDULED', 'DONE');

CREATE INDEX idx_interviews_starts_at ON app_private.interviews (starts_at);
CREATE INDEX idx_interviews_application ON app_private.interviews (application_id);

CREATE TABLE app_private.interview_participants (
    interview_id     uuid NOT NULL REFERENCES app_private.interviews(interview_id) ON DELETE CASCADE,
    user_id          uuid NOT NULL REFERENCES auth.users(id),
    participant_role text NOT NULL DEFAULT 'INTERVIEWER'
                     CHECK (participant_role IN ('INTERVIEWER', 'OBSERVER')),
    added_by         uuid REFERENCES auth.users(id),
    created_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (interview_id, user_id)
);

-- "Lịch của tôi" là truy vấn theo user_id; không có chỉ số này thì mọi lần mở
-- trang lịch đều quét toàn bộ người tham gia.
CREATE INDEX idx_interview_participants_user ON app_private.interview_participants (user_id);

-- Cùng khuôn với 00023: client trực tiếp không được đi vòng qua kiểm tra của API.
DO $$ DECLARE t text; BEGIN
    FOREACH t IN ARRAY ARRAY['interviews', 'interview_participants'] LOOP
        EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON TABLE app_private.%I FROM PUBLIC, anon, authenticated', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE app_private.%I TO service_role', t);
    END LOOP;
END $$;

COMMENT ON TABLE app_private.interviews IS
    'Buổi phỏng vấn của một hồ sơ. Lịch là dữ liệu BỔ SUNG: không phải điều kiện để chuyển trạng thái hồ sơ.';
COMMENT ON COLUMN app_private.interviews.round_number IS
    'Vòng phỏng vấn, 1..10. Bắt buộc vì "vòng mấy" là câu hỏi đầu tiên khi xem lịch, và suy ra từ thứ tự thời gian sẽ sai khi có buổi bị huỷ rồi xếp lại.';
