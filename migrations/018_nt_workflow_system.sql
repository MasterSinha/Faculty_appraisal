-- Migration 018: Dynamic NT Workflow System
-- Replaces hardcoded RO→Registrar→VC flow with a fully configurable chain.
-- Run this ONCE on the database before deploying the new API code.

-- ── 1. Designations catalog ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.nt_designations (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR     NOT NULL UNIQUE,
    description VARCHAR,
    is_system   BOOLEAN     NOT NULL DEFAULT false,
    is_active   BOOLEAN     NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- ── 2. Workflow templates ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.nt_workflow_templates (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR     NOT NULL,
    description VARCHAR,
    is_active   BOOLEAN     NOT NULL DEFAULT true,
    is_default  BOOLEAN     NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- ── 3. Workflow template steps ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.nt_workflow_template_steps (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id     UUID        NOT NULL REFERENCES public.nt_workflow_templates(id) ON DELETE CASCADE,
    step_no         INTEGER     NOT NULL,
    designation_id  UUID        NOT NULL REFERENCES public.nt_designations(id),
    is_required     BOOLEAN     NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (template_id, step_no)
);

-- ── 4. Template assignments ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.nt_workflow_assignments (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id     UUID        NOT NULL REFERENCES public.nt_workflow_templates(id),
    staff_email     VARCHAR     UNIQUE,
    appraisal_role  VARCHAR,
    department      VARCHAR,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_one_target CHECK (
        (staff_email IS NOT NULL)::int
      + (appraisal_role IS NOT NULL)::int
      + (department IS NOT NULL)::int = 1
    )
);

-- ── 5. Workflow instances ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.nt_workflow_instances (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    appraisal_id    UUID        NOT NULL REFERENCES public.non_teaching_appraisals(id) ON DELETE CASCADE,
    template_id     UUID        REFERENCES public.nt_workflow_templates(id),
    staff_email     VARCHAR     NOT NULL,
    academic_year   VARCHAR     NOT NULL,
    current_step    INTEGER,
    status          VARCHAR     NOT NULL DEFAULT 'PENDING',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (staff_email, academic_year)
);

-- ── 6. Workflow instance steps ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.nt_workflow_instance_steps (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id     UUID        NOT NULL REFERENCES public.nt_workflow_instances(id) ON DELETE CASCADE,
    step_no         INTEGER     NOT NULL,
    designation     VARCHAR     NOT NULL,
    reviewer_email  VARCHAR,
    status          VARCHAR     NOT NULL DEFAULT 'WAITING',
    score           NUMERIC,
    remarks         TEXT,
    reviewed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (instance_id, step_no)
);

-- ── Seed: system designations ────────────────────────────────────────────────
INSERT INTO public.nt_designations (name, description, is_system) VALUES
('Reporting Officer', 'First approver for non-teaching staff appraisals', true),
('Registrar',         'Reviews after Reporting Officer',                   true),
('VC',                'Final approver — Vice Chancellor',                  true)
ON CONFLICT (name) DO NOTHING;

-- ── Seed: two default workflow templates ────────────────────────────────────
WITH t AS (
    INSERT INTO public.nt_workflow_templates (name, description, is_default)
    SELECT 'Standard NT Flow', 'Reporting Officer → Registrar → VC', true
    WHERE NOT EXISTS (SELECT 1 FROM public.nt_workflow_templates WHERE name = 'Standard NT Flow')
    RETURNING id
)
INSERT INTO public.nt_workflow_template_steps (template_id, step_no, designation_id)
SELECT t.id, s.step_no, d.id
  FROM t,
       (VALUES (1,'Reporting Officer'), (2,'Registrar'), (3,'VC')) AS s(step_no, name)
  JOIN public.nt_designations d ON d.name = s.name;

WITH t AS (
    INSERT INTO public.nt_workflow_templates (name, description, is_default)
    SELECT 'Direct to Registrar', 'Registrar → VC (skips Reporting Officer)', false
    WHERE NOT EXISTS (SELECT 1 FROM public.nt_workflow_templates WHERE name = 'Direct to Registrar')
    RETURNING id
)
INSERT INTO public.nt_workflow_template_steps (template_id, step_no, designation_id)
SELECT t.id, s.step_no, d.id
  FROM t,
       (VALUES (1,'Registrar'), (2,'VC')) AS s(step_no, name)
  JOIN public.nt_designations d ON d.name = s.name;

INSERT INTO public.nt_workflow_assignments (template_id, appraisal_role)
SELECT id, 'non_teaching_staff' FROM public.nt_workflow_templates WHERE name = 'Standard NT Flow'
AND NOT EXISTS (SELECT 1 FROM public.nt_workflow_assignments WHERE appraisal_role = 'non_teaching_staff');

INSERT INTO public.nt_workflow_assignments (template_id, appraisal_role)
SELECT id, 'reporting_officer' FROM public.nt_workflow_templates WHERE name = 'Standard NT Flow'
AND NOT EXISTS (SELECT 1 FROM public.nt_workflow_assignments WHERE appraisal_role = 'reporting_officer');

INSERT INTO public.nt_workflow_assignments (template_id, appraisal_role)
SELECT id, 'registrar' FROM public.nt_workflow_templates WHERE name = 'Standard NT Flow'
AND NOT EXISTS (SELECT 1 FROM public.nt_workflow_assignments WHERE appraisal_role = 'registrar');
