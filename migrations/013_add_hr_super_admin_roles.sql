-- Migration 013: Add 'hr' and 'super_admin' to appraisal_role CHECK constraint
-- Safe to run on live data — CHECK constraints do not affect existing rows.

ALTER TABLE public.faculty_profiles
DROP CONSTRAINT IF EXISTS faculty_profiles_appraisal_role_check;

ALTER TABLE public.faculty_profiles
ADD CONSTRAINT faculty_profiles_appraisal_role_check
CHECK (appraisal_role IN (
    'faculty', 'non_teaching_staff', 'staff', 'hod', 'reporting_officer',
    'section_head', 'director', 'center_head', 'dean', 'registrar', 'vc',
    'admin', 'hr', 'super_admin'
));
