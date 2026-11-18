-- Keep an application for 5 years only while the candidate's Talent Pool
-- (reuse) consent is in force; otherwise keep it 12 months after the position
-- closes, as before 00022.
--
-- 00022 applied 60 months to every application, including CVs that HR uploaded
-- or received by email, where nobody gave consent, and it kept that period even
-- after a candidate withdrew consent. This adds the period for applications
-- without consent to the policy row. For an application with an active
-- TALENT_POOL consent the due date is the later of
--   position closed + retention_months_without_consent, and
--   consent granted + retention_months,
-- which matches "kept up to 5 years" counted from when the candidate ticked
-- consent. NULL keeps the old rule (retention_months after closing for all).
ALTER TABLE app_private.retention_policy_versions
    ADD COLUMN IF NOT EXISTS retention_months_without_consent INTEGER
    CHECK (retention_months_without_consent IS NULL OR retention_months_without_consent > 0);

INSERT INTO app_private.retention_policy_versions
    (policy_version, retention_months, retention_months_without_consent, trigger_event, status)
VALUES ('v2.1-consent-60month', 60, 12, 'POSITION_CLOSED', 'APPROVED')
ON CONFLICT (policy_version) DO NOTHING;

UPDATE app_private.retention_policy_versions
SET status = 'SUPERSEDED'
WHERE policy_version <> 'v2.1-consent-60month' AND status = 'APPROVED';
