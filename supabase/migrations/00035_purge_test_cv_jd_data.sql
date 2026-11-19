-- ============================================================================
-- 00035_purge_test_cv_jd_data.sql
--
-- MỤC ĐÍCH: làm trống toàn bộ dữ liệu CV / JD / vị trí / chấm điểm / tuyển dụng
-- để chạy lại luồng demo với dữ liệu hợp lệ mới. GIỮ NGUYÊN tài khoản, phòng
-- ban, job family, rubric library, cấu hình AI và bảng cấu hình ngưỡng.
--
-- LOẠI: thao tác XOÁ DỮ LIỆU, không hoàn tác. Chỉ dùng trên project test
--       myrymlqdbyqmpynesiwk. Bản sao lưu trước khi xoá nằm ở schema
--       app_backup_20261119 (63 bảng; đối chiếu khớp từng bảng trước khi xoá).
--
-- VÌ SAO PHẢI TẮT TRIGGER:
--   audit_events có trigger prevent_audit_event_mutation() RAISE EXCEPTION với
--   MỌI DELETE và TRUNCATE, không phân biệt role (kể cả postgres). Trigger được
--   tắt trong đúng phạm vi transaction này rồi bật lại và kiểm tra tgenabled.
--
-- VÌ SAO PHẢI RESET next_sequence:
--   backend/app/services/departments.py:next_position_code() sinh mã từ
--   departments.next_sequence, KHÔNG phải từ max(position_code). IT Department
--   đang là 7; không reset thì vị trí mới sẽ bắt đầu từ IT-0007 chứ không phải
--   IT-0001.
--
-- VÌ SAO RESET CHUỖI AUDIT:
--   chain_sequence có UNIQUE index và DEFAULT nextval(). Nếu để sequence tiếp
--   tục từ giá trị cũ, event đầu tiên của dữ liệu mới sẽ mang số lớn trong khi
--   chain chỉ còn 1 dòng — chuỗi "liền mạch" đứt ngay từ dòng đầu. Reset về 1
--   làm chain mới bắt đầu sạch.
--
-- THỨ TỰ XOÁ: con trước, cha sau. Ba chỗ dễ sai, đã dò từ pg_constraint:
--   * shortlist_share_items -> ranking_items là NO ACTION, nên phải xoá
--     share_items TRƯỚC ranking_items (không thì FK chặn).
--   * audit_events -> positions là NO ACTION, nên audit_events phải xoá TRƯỚC
--     positions.
--   * assessment_runs -> operations là NO ACTION, nên assessment_runs TRƯỚC
--     operations.
-- ============================================================================

BEGIN;

-- Chốt chặn 1: không chạy khi còn operation đang xử lý. Xoá giữa chừng sẽ làm
-- worker ghi vào bảng đã bị xoá dòng và lỗi khó truy.
DO $$
DECLARE n integer;
BEGIN
    SELECT count(*) INTO n FROM app_private.operations
     WHERE status IN ('PENDING', 'PROCESSING');
    IF n > 0 THEN
        RAISE EXCEPTION 'Còn % operation đang chạy — dừng worker hoặc chờ xong rồi purge', n;
    END IF;
END $$;

-- Chốt chặn 2: phải có bản sao lưu khớp số dòng trước khi xoá. Nếu ai đó chạy
-- file này trên môi trường khác (không có schema backup), nó dừng ngay đây.
DO $$
DECLARE live bigint; bk bigint;
BEGIN
    SELECT count(*) INTO live FROM app_private.applications;
    SELECT count(*) INTO bk   FROM app_backup_20261119.applications;
    IF live <> bk THEN
        RAISE EXCEPTION 'Bản sao lưu không khớp (live=%, backup=%) — không xoá', live, bk;
    END IF;
END $$;

ALTER TABLE app_private.audit_events DISABLE TRIGGER audit_events_append_only;

-- ---------------------------------------------------------------------------
-- A. Shortlist (phải xoá trước ranking_items và assessment_runs)
-- ---------------------------------------------------------------------------
DELETE FROM app_private.shortlist_scorecard_criteria;
DELETE FROM app_private.scorecard_reopen_events;
DELETE FROM app_private.shortlist_scorecards;
DELETE FROM app_private.shortlist_feedback;
DELETE FROM app_private.shortlist_share_items;
DELETE FROM app_private.shortlist_shares;

-- ---------------------------------------------------------------------------
-- B. Xếp hạng (items trước runs; items cũng chặn share_items)
-- ---------------------------------------------------------------------------
DELETE FROM app_private.ranking_items;
DELETE FROM app_private.ranking_runs;

-- ---------------------------------------------------------------------------
-- C. Kết quả chấm điểm và bằng chứng (sâu nhất trong cây hồ sơ)
-- ---------------------------------------------------------------------------
DELETE FROM app_private.evidence_items;
DELETE FROM app_private.hr_criterion_reviews;
DELETE FROM app_private.criterion_assessment_results;
DELETE FROM app_private.assessment_runs;

-- ---------------------------------------------------------------------------
-- D. Tài liệu CV / profile
-- ---------------------------------------------------------------------------
DELETE FROM app_private.cv_chunk_embeddings;
DELETE FROM app_private.document_processing_runs;
DELETE FROM app_private.profile_facts;
DELETE FROM app_private.profile_versions;
DELETE FROM app_private.application_documents;

-- ---------------------------------------------------------------------------
-- E. Các bảng vệ tinh của application
-- ---------------------------------------------------------------------------
DELETE FROM app_private.duplicate_signals;
DELETE FROM app_private.gmail_test_messages;
DELETE FROM app_private.careers_intake_receipts;
DELETE FROM app_private.talent_pool_consents;
DELETE FROM app_private.application_private_notes;
DELETE FROM app_private.application_status_events;
DELETE FROM app_private.application_identities;
DELETE FROM app_private.cv_batch_items;
DELETE FROM app_private.cv_batches;
DELETE FROM app_private.deletion_jobs;
DELETE FROM app_private.deletion_events;
DELETE FROM app_private.application_retention_cases;

-- ---------------------------------------------------------------------------
-- F. Hồ sơ và operation
-- ---------------------------------------------------------------------------
DELETE FROM app_private.applications;
DELETE FROM app_private.operation_recovery_events;
DELETE FROM app_private.operations;

-- ---------------------------------------------------------------------------
-- G. Rubric / JD / vị trí (audit_events phải xoá TRƯỚC positions)
-- ---------------------------------------------------------------------------
DELETE FROM app_private.criteria_approval_events;
DELETE FROM app_private.criteria_items;
DELETE FROM app_private.criteria_versions;
DELETE FROM app_private.jd_versions;
DELETE FROM app_private.position_create_requests;
DELETE FROM app_private.position_access_grants;
DELETE FROM app_private.position_assignments;
DELETE FROM app_private.position_status_events;
DELETE FROM app_private.audit_events;
DELETE FROM app_private.positions;

ALTER TABLE app_private.audit_events ENABLE TRIGGER audit_events_append_only;

-- Xác nhận trigger thật sự bật lại. Không im lặng bỏ qua.
DO $$
DECLARE st char;
BEGIN
    SELECT tgenabled INTO st FROM pg_trigger
     WHERE tgname = 'audit_events_append_only'
       AND tgrelid = 'app_private.audit_events'::regclass;
    IF st IS DISTINCT FROM 'O' THEN
        RAISE EXCEPTION 'Trigger audit chưa bật lại (tgenabled=%) — huỷ toàn bộ', st;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Đánh số lại từ đầu cho dữ liệu mới.
-- ---------------------------------------------------------------------------
UPDATE app_private.departments SET next_sequence = 1;
ALTER SEQUENCE app_private.audit_event_chain_seq RESTART WITH 1;

-- ---------------------------------------------------------------------------
-- Hậu điều kiện. Sai một điều là huỷ cả transaction.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    applications_left bigint; documents_left bigint; positions_left bigint;
    jd_left bigint; evidence_left bigint; results_left bigint; audit_left bigint;
    users_left bigint; roles_left bigint; depts_left bigint;
    jobs_left bigint; settings_left bigint; ai_left bigint;
    ops_left bigint; seq_now bigint; seq_called boolean;
BEGIN
    SELECT count(*) INTO applications_left FROM app_private.applications;
    SELECT count(*) INTO documents_left    FROM app_private.application_documents;
    SELECT count(*) INTO positions_left    FROM app_private.positions;
    SELECT count(*) INTO jd_left           FROM app_private.jd_versions;
    SELECT count(*) INTO evidence_left     FROM app_private.evidence_items;
    SELECT count(*) INTO results_left      FROM app_private.criterion_assessment_results;
    SELECT count(*) INTO audit_left        FROM app_private.audit_events;
    SELECT count(*) INTO ops_left          FROM app_private.operations;
    SELECT count(*) INTO users_left        FROM app_private.user_profiles;
    SELECT count(*) INTO roles_left        FROM app_private.user_role_assignments;
    SELECT count(*) INTO depts_left        FROM app_private.departments;
    SELECT count(*) INTO jobs_left         FROM app_private.job_families;
    SELECT count(*) INTO settings_left     FROM app_private.app_settings;
    SELECT count(*) INTO ai_left           FROM app_private.ai_configuration_versions;
    -- Đọc trạng thái sequence TRỰC TIẾP từ sequence, KHÔNG qua pg_sequences
    -- (pg_sequences.last_value trả NULL khi sequence chưa được gọi lần nào kể
    --  từ lần reset — đã gặp đúng lỗi này ở lần dry-run đầu) và KHÔNG dùng
    -- nextval (gọi nextval sẽ tiêu một số và làm sequence luôn khác 1).
    EXECUTE 'SELECT last_value, is_called FROM app_private.audit_event_chain_seq'
       INTO seq_now, seq_called;

    IF applications_left + documents_left + positions_left + jd_left
       + evidence_left + results_left + audit_left + ops_left <> 0 THEN
        RAISE EXCEPTION 'Còn dữ liệu chưa xoá: app=% doc=% pos=% jd=% ev=% res=% audit=% ops=%',
            applications_left, documents_left, positions_left, jd_left,
            evidence_left, results_left, audit_left, ops_left;
    END IF;

    -- Những thứ phải còn nguyên
    IF users_left    <> 5 THEN RAISE EXCEPTION 'user_profiles đổi: % (phải 5)', users_left; END IF;
    IF roles_left    <> 6 THEN RAISE EXCEPTION 'user_role_assignments đổi: % (phải 6)', roles_left; END IF;
    IF depts_left    <> 2 THEN RAISE EXCEPTION 'departments đổi: % (phải 2)', depts_left; END IF;
    IF jobs_left     <> 2 THEN RAISE EXCEPTION 'job_families đổi: % (phải 2)', jobs_left; END IF;
    IF settings_left <> 2 THEN RAISE EXCEPTION 'app_settings đổi: % (phải 2)', settings_left; END IF;
    IF ai_left       <> 4 THEN RAISE EXCEPTION 'ai_configuration_versions đổi: % (phải 4)', ai_left; END IF;
    -- Sau RESTART WITH 1: is_called phải là false, tức là số kế tiếp được
    -- phát sẽ đúng bằng 1. Nếu is_called=true thì số kế tiếp là 2 — sai.
    IF seq_now IS DISTINCT FROM 1 OR seq_called THEN
        RAISE EXCEPTION 'Chuỗi audit không sạch: last_value=% is_called=%', seq_now, seq_called;
    END IF;

    RAISE NOTICE 'PURGE OK — giữ: user=% roles=% dept=% family=% settings=% ai=%',
        users_left, roles_left, depts_left, jobs_left, settings_left, ai_left;
END $$;

COMMIT;
