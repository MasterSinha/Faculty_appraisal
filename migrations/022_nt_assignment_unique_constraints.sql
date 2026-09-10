-- Migration 022: add unique constraints on nt_workflow_assignments
-- The in-code duplicate check was the only guard, and it had a bug (missing
-- staff_email filter) that caused MultipleResultsFound in production.
-- These constraints prevent duplicate assignments at the DB level regardless
-- of race conditions or future code changes.
--
-- PostgreSQL unique constraints ignore NULL values, so each constraint only
-- fires when the relevant column is non-null — exactly the semantics we want.

-- Deduplicate existing rows if any
DELETE FROM public.nt_workflow_assignments
WHERE id NOT IN (
    SELECT DISTINCT ON (template_id, appraisal_role) id
    FROM public.nt_workflow_assignments
    WHERE appraisal_role IS NOT NULL
    ORDER BY template_id, appraisal_role, updated_at DESC NULLS LAST
) AND appraisal_role IS NOT NULL;

DELETE FROM public.nt_workflow_assignments
WHERE id NOT IN (
    SELECT DISTINCT ON (template_id, department) id
    FROM public.nt_workflow_assignments
    WHERE department IS NOT NULL
    ORDER BY template_id, department, updated_at DESC NULLS LAST
) AND department IS NOT NULL;

ALTER TABLE public.nt_workflow_assignments
    DROP CONSTRAINT IF EXISTS uq_ntwfa_template_role;
ALTER TABLE public.nt_workflow_assignments
    ADD CONSTRAINT uq_ntwfa_template_role
        UNIQUE (template_id, appraisal_role);

ALTER TABLE public.nt_workflow_assignments
    DROP CONSTRAINT IF EXISTS uq_ntwfa_template_dept;
ALTER TABLE public.nt_workflow_assignments
    ADD CONSTRAINT uq_ntwfa_template_dept
        UNIQUE (template_id, department);
