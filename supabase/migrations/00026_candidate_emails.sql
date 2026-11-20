-- F3.05 phase 1: semi-automatic candidate emails (human in the loop).
-- HR always reviews and presses send; nothing is sent on its own. Until outbound
-- mail is switched on (CANDIDATE_EMAIL_SEND_MODE=smtp), "send" only records the
-- message as RECORDED so the flow can be tried without emailing anyone.

CREATE TABLE IF NOT EXISTS app_private.email_templates (
    template_code TEXT PRIMARY KEY
        CHECK (template_code IN ('ACK_RECEIVED', 'REQUEST_INFO', 'INTERVIEW_INVITE', 'REJECTION', 'POOL_INVITE')),
    name TEXT NOT NULL,
    subject_template TEXT NOT NULL CHECK (length(subject_template) BETWEEN 1 AND 300),
    body_template TEXT NOT NULL CHECK (length(body_template) BETWEEN 1 AND 10000),
    updated_by UUID REFERENCES auth.users(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One row per message HR drafted or sent. Deleting the application (retention purge)
-- deletes its messages too.
CREATE TABLE IF NOT EXISTS app_private.candidate_emails (
    email_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    application_id UUID NOT NULL REFERENCES app_private.applications(application_id) ON DELETE CASCADE,
    position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    template_code TEXT REFERENCES app_private.email_templates(template_code),
    trigger_source TEXT NOT NULL DEFAULT 'MANUAL' CHECK (trigger_source IN ('MANUAL', 'STATUS_CHANGE')),
    from_address TEXT NOT NULL,
    reply_to_address TEXT,
    to_address TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'RECORDED', 'SENT', 'FAILED', 'CANCELLED')),
    error_code TEXT,
    created_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_by UUID REFERENCES auth.users(id),
    sent_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_candidate_emails_application ON app_private.candidate_emails(application_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_candidate_emails_sent_recent ON app_private.candidate_emails(sent_by, sent_at)
    WHERE status IN ('RECORDED', 'SENT');

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['email_templates', 'candidate_emails'] LOOP
        EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON app_private.%I FROM PUBLIC, anon, authenticated', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.%I TO service_role', t);
    END LOOP;
END $$;

-- Default wording. HR Lead can change it from the "Mẫu thư ứng viên" page.
-- Variables: {ho_ten} {vi_tri} {ma_vi_tri} {ngay_nop} {ten_hr} {email_hr} {thoi_gian_pv} {dia_diem_pv}
INSERT INTO app_private.email_templates (template_code, name, subject_template, body_template) VALUES
('ACK_RECEIVED', 'Xác nhận đã nhận hồ sơ',
 '[VinUniversity] Xác nhận đã nhận hồ sơ ứng tuyển vị trí {vi_tri}',
 E'Kính gửi {ho_ten},\n\nCảm ơn bạn đã quan tâm và ứng tuyển vị trí {vi_tri} ({ma_vi_tri}) tại Trường Đại học VinUni. Chúng tôi đã nhận được hồ sơ của bạn ngày {ngay_nop}.\n\nBộ phận Nhân sự sẽ xem xét hồ sơ và liên hệ với bạn nếu hồ sơ phù hợp với yêu cầu của vị trí.\n\nTrân trọng,\n{ten_hr}\nPhòng Nhân sự - Trường Đại học VinUni'),
('REQUEST_INFO', 'Mời bổ sung thông tin',
 '[VinUniversity] Đề nghị bổ sung thông tin hồ sơ - {vi_tri}',
 E'Kính gửi {ho_ten},\n\nCảm ơn bạn đã ứng tuyển vị trí {vi_tri} ({ma_vi_tri}) tại Trường Đại học VinUni.\n\nĐể tiếp tục xem xét hồ sơ, chúng tôi mong bạn bổ sung các thông tin sau:\n- [Nêu thông tin cần bổ sung]\n\nBạn vui lòng phản hồi email này trong vòng 05 ngày làm việc.\n\nTrân trọng,\n{ten_hr}\nPhòng Nhân sự - Trường Đại học VinUni'),
('INTERVIEW_INVITE', 'Mời phỏng vấn',
 '[VinUniversity] Thư mời phỏng vấn vị trí {vi_tri}',
 E'Kính gửi {ho_ten},\n\nCảm ơn bạn đã ứng tuyển vị trí {vi_tri} ({ma_vi_tri}) tại Trường Đại học VinUni. Chúng tôi trân trọng mời bạn tham dự buổi phỏng vấn:\n\n- Thời gian: {thoi_gian_pv}\n- Địa điểm / đường dẫn: {dia_diem_pv}\n\nBạn vui lòng phản hồi email này để xác nhận tham dự. Nếu thời gian trên chưa phù hợp, bạn có thể đề xuất thời gian khác.\n\nTrân trọng,\n{ten_hr}\nPhòng Nhân sự - Trường Đại học VinUni'),
('REJECTION', 'Thông báo chưa phù hợp',
 '[VinUniversity] Kết quả ứng tuyển vị trí {vi_tri}',
 E'Kính gửi {ho_ten},\n\nCảm ơn bạn đã dành thời gian quan tâm và ứng tuyển vị trí {vi_tri} ({ma_vi_tri}) tại Trường Đại học VinUni.\n\nSau khi xem xét kỹ lưỡng, chúng tôi rất tiếc phải thông báo rằng hồ sơ của bạn chưa phù hợp với yêu cầu của vị trí ở thời điểm này. Quyết định này không phản ánh toàn bộ năng lực của bạn, và chúng tôi rất trân trọng sự quan tâm của bạn dành cho VinUni.\n\nChúc bạn nhiều thành công và mong có dịp hợp tác trong tương lai.\n\nTrân trọng,\n{ten_hr}\nPhòng Nhân sự - Trường Đại học VinUni'),
('POOL_INVITE', 'Mời trao đổi (Talent Pool)',
 '[VinUniversity] Mời trao đổi cơ hội tuyển dụng: {vi_tri} ({ma_vi_tri})',
 E'Kính gửi {ho_ten},\n\nTrước đây bạn đã ứng tuyển tại Trường Đại học VinUni và đồng ý để chúng tôi xem xét hồ sơ cho các vị trí phù hợp khác. Hiện chúng tôi đang tuyển vị trí {vi_tri} ({ma_vi_tri}) và nhận thấy kinh nghiệm của bạn phù hợp với yêu cầu công việc.\n\nNếu bạn quan tâm, vui lòng phản hồi email này kèm CV mới nhất để chúng tôi sắp xếp trao đổi.\n\nTrân trọng,\n{ten_hr}\nPhòng Nhân sự - Trường Đại học VinUni')
ON CONFLICT (template_code) DO NOTHING;
