-- HR's own review of what the matcher concluded, per criterion.
--
-- Why a separate table instead of updating evidence_items.verification_status:
-- that column records what the *system* did (it searched the CV for the quote and
-- either found it or did not). If HR wrote into the same field, nobody could tell
-- afterwards whether a quote was verified by the machine or waved through by a
-- person — and the audit trail would be worth nothing. HR's decision is a second,
-- attributable layer on top, with an author, a time and an optional reason.
--
-- This is what lets the "needs verification" queue actually close. Until now the
-- only way an application left that queue was a recruiting decision (reject, or
-- move to interview), because SHORTLIST is still a screening status. That forced
-- HR to make a hiring call just to clear a technical to-do list.
CREATE TABLE app_private.hr_criterion_reviews (
    review_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- One row per assessment criterion result. Reviews are append-only: a second
    -- look at the same criterion is a new row, never an overwrite, so "who changed
    -- their mind, and when" stays answerable.
    result_id UUID NOT NULL REFERENCES app_private.criterion_assessment_results(result_id) ON DELETE CASCADE,
    app_position_id UUID NOT NULL REFERENCES app_private.positions(position_id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK (decision IN ('CONFIRMED', 'REJECTED')),
    comment TEXT,
    reviewed_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The queue only ever asks "is there a latest review for this result", and the
-- profile page asks for every review of one assessment.
CREATE INDEX hr_criterion_reviews_result_idx
    ON app_private.hr_criterion_reviews (result_id, created_at DESC);
CREATE INDEX hr_criterion_reviews_position_idx
    ON app_private.hr_criterion_reviews (app_position_id);

-- A rejection must say why. Enforced here as well as in the API because a row
-- without a reason is not a review, it is a click.
ALTER TABLE app_private.hr_criterion_reviews
    ADD CONSTRAINT hr_criterion_reviews_rejected_needs_reason
    CHECK (decision = 'CONFIRMED' OR (comment IS NOT NULL AND length(btrim(comment)) > 0));

ALTER TABLE app_private.hr_criterion_reviews ENABLE ROW LEVEL SECURITY;
-- Same posture as app_settings: the backend holds the only key. Who may review is
-- decided per position in the API (HR_RECRUITER / HR_LEAD), not by a table policy.
REVOKE ALL ON app_private.hr_criterion_reviews FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT, INSERT ON app_private.hr_criterion_reviews TO service_role;
