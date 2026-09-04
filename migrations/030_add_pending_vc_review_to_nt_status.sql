-- Migration 030: Add 'Pending VC Review' to non_teaching_appraisals status check
-- Required when a Reporting Officer whose reports_to_registrar = false submits their self-appraisal,
-- as their form routes directly to the Vice Chancellor (Pending VC Review).

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
