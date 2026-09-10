-- Migration 014: add 'Pending Registrar Review' to non_teaching_appraisals status check
-- Required for staff whose reports_to_registrar = true; their forms skip the RO step
-- and land directly in the registrar's queue with this status.

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
