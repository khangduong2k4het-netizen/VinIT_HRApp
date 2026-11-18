-- Retention becomes 5 years (60 months) after the position closes.
-- Candidates now must grant data-use consent to apply, so applications are
-- kept for 5 years instead of 12 months. The old policy row is kept for the
-- history of cases created under it, but is no longer selected.
--
-- Open cases created under the 12-month policy are cancelled by the retention
-- cycle (cancel_cases_of_superseded_policy), with audit, and re-created later
-- with the 5-year due date. Legal holds (ON_HOLD) are not touched here.

-- New cancel reason for those cases.
ALTER TABLE app_private.application_retention_cases
    DROP CONSTRAINT IF EXISTS application_retention_cases_cancel_reason_check;
ALTER TABLE app_private.application_retention_cases
    ADD CONSTRAINT application_retention_cases_cancel_reason_check
    CHECK (cancel_reason IS NULL OR cancel_reason IN ('MANUAL', 'POSITION_REOPENED', 'POLICY_EXTENDED'));

INSERT INTO app_private.retention_policy_versions (policy_version, retention_months, trigger_event, status)
VALUES ('v2.0-60month', 60, 'POSITION_CLOSED', 'APPROVED')
ON CONFLICT (policy_version) DO NOTHING;

UPDATE app_private.retention_policy_versions
SET status = 'SUPERSEDED'
WHERE policy_version <> 'v2.0-60month' AND status = 'APPROVED';
