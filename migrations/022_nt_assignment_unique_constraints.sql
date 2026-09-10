-- Migration 022: add unique constraints on nt_workflow_assignments
-- The in-code duplicate check was the only guard, and it had a bug (missing
-- staff_email filter) that caused MultipleResultsFound in production.
-- These constraints prevent duplicate assignments at the DB level regardless
-- of race conditions or future code changes.
--
-- PostgreSQL unique constraints ignore NULL values, so each constraint only
-- fires when the relevant column is non-null — exactly the semantics we want.

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
