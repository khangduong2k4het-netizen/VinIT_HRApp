-- Departments (đơn vị/phòng ban) are Admin-managed master data. Each
-- department owns a position-code template such as REQ-IT-{SEQ:000}; creating
-- a position generates REQ-IT-001, REQ-IT-002, ... from that template.
-- Existing positions keep their manual codes and free-text org_unit snapshot.

CREATE TABLE IF NOT EXISTS app_private.departments (
    department_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 160),
    code_format TEXT NOT NULL CHECK (char_length(code_format) BETWEEN 3 AND 80),
    next_sequence INTEGER NOT NULL DEFAULT 1 CHECK (next_sequence >= 1),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_departments_name_lower
    ON app_private.departments ((lower(name)));
CREATE UNIQUE INDEX IF NOT EXISTS idx_departments_code_format
    ON app_private.departments (code_format);

ALTER TABLE app_private.positions
    ADD COLUMN IF NOT EXISTS department_id UUID
        REFERENCES app_private.departments(department_id) ON DELETE RESTRICT;
ALTER TABLE app_private.positions
    ADD COLUMN IF NOT EXISTS department_sequence INTEGER
        CHECK (department_sequence IS NULL OR department_sequence >= 1);
CREATE INDEX IF NOT EXISTS idx_positions_department
    ON app_private.positions (department_id, opened_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_department_sequence
    ON app_private.positions (department_id, department_sequence)
    WHERE department_id IS NOT NULL AND department_sequence IS NOT NULL;

-- Recreate the service-role discovery view with the new department columns.
DROP VIEW IF EXISTS public.positions;
CREATE VIEW public.positions
WITH (security_invoker = true) AS
SELECT * FROM app_private.positions;

CREATE OR REPLACE VIEW public.departments
WITH (security_invoker = true) AS
SELECT department_id, name, code_format, next_sequence, is_active,
       created_by, created_at, updated_at
FROM app_private.departments;

REVOKE ALL ON public.positions FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.departments FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_private.departments TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.departments TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.positions TO service_role;

COMMENT ON TABLE app_private.departments IS
    'Admin-managed departments. code_format is the position-code template and must contain one {SEQ} or {SEQ:000} placeholder, e.g. REQ-IT-{SEQ:000}.';
COMMENT ON VIEW public.departments IS
    'Admin-managed departments. code_format is the position-code template and must contain one {SEQ} or {SEQ:000} placeholder, e.g. REQ-IT-{SEQ:000}.';
COMMENT ON COLUMN app_private.positions.department_id IS
    'Department selected when the position was created; NULL for legacy positions.';
COMMENT ON COLUMN app_private.positions.department_sequence IS
    'Sequence rendered into position_code from the department code_format; NULL for legacy positions.';
COMMENT ON COLUMN app_private.positions.org_unit IS
    'Department name snapshot for new positions; free text for legacy positions.';
