-- Retention reminders now distinguish due dates within the same closed position.
-- Under migration 00023, applications without Talent Pool consent are due 12 months
-- after closing while consented applications are due up to 5 years after consent.
-- Keying reminders only by (position_id, position_closed_at, milestone_days) would
-- silence the 30/15/7-day reminders for the later 5-year Talent Pool cases once the
-- earlier 12-month cases fired those milestones.

ALTER TABLE app_private.retention_notifications
    ADD COLUMN IF NOT EXISTS due_on DATE;

UPDATE app_private.retention_notifications
SET due_on = (due_date AT TIME ZONE 'UTC')::date
WHERE due_on IS NULL;

ALTER TABLE app_private.retention_notifications
    ALTER COLUMN due_on SET NOT NULL;

DO $$
DECLARE c RECORD;
BEGIN
    FOR c IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'app_private.retention_notifications'::regclass
          AND contype = 'u'
          AND pg_get_constraintdef(oid) NOT ILIKE '%due_on%'
    LOOP
        EXECUTE format('ALTER TABLE app_private.retention_notifications DROP CONSTRAINT %I', c.conname);
    END LOOP;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_retention_notifications_due_on
    ON app_private.retention_notifications (position_id, position_closed_at, due_on, milestone_days, recipient_user_id, channel);
