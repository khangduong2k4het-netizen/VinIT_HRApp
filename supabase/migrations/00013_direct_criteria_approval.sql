-- Allow the supplementary Admin/HR Lead direct-approval path to be recorded
-- distinctly in the criteria approval trail. The normal HR -> HM workflow
-- keeps using APPROVE with HR_RECRUITER/HIRING_MANAGER reviewer roles.

DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    FOR constraint_name IN
        SELECT con.conname
        FROM pg_constraint con
        WHERE con.conrelid = 'app_private.criteria_approval_events'::regclass
          AND con.contype = 'c'
          AND pg_get_constraintdef(con.oid) LIKE '%reviewer_role%'
    LOOP
        EXECUTE format(
            'ALTER TABLE app_private.criteria_approval_events DROP CONSTRAINT %I',
            constraint_name
        );
    END LOOP;

    FOR constraint_name IN
        SELECT con.conname
        FROM pg_constraint con
        WHERE con.conrelid = 'app_private.criteria_approval_events'::regclass
          AND con.contype = 'c'
          AND pg_get_constraintdef(con.oid) LIKE '%decision%'
    LOOP
        EXECUTE format(
            'ALTER TABLE app_private.criteria_approval_events DROP CONSTRAINT %I',
            constraint_name
        );
    END LOOP;
END $$;

ALTER TABLE app_private.criteria_approval_events
    ADD CONSTRAINT criteria_approval_events_reviewer_role_check
    CHECK (reviewer_role IN ('HR_RECRUITER', 'HIRING_MANAGER', 'HR_LEAD', 'ADMIN'));

ALTER TABLE app_private.criteria_approval_events
    ADD CONSTRAINT criteria_approval_events_decision_check
    CHECK (decision IN ('APPROVE', 'DIRECT_APPROVE', 'REJECT', 'REQUEST_CHANGES'));
