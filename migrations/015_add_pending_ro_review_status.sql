-- Migration 015: add 'Pending RO Review' to non_teaching_appraisals status check
-- The frontend sends this value when a staff member submits their form for RO review.
-- Also retains 'Pending Registrar Review' added in migration 014.

ALTER TABLE public.non_teaching_appraisals
  DROP CONSTRAINT IF EXISTS non_teaching_appraisals_status_check;

ALTER TABLE public.non_teaching_appraisals
  ADD CONSTRAINT non_teaching_appraisals_status_check
  CHECK (status IN (
    'Draft',
    'Submitted',
    'Pending RO Review',
    'Pending Registrar Review',
    'Pending VC Review',
    'Reporting Officer Reviewed',
    'Registrar Reviewed',
    'VC Approved',
    'Reviewed',
    'Rejected'
  ));
