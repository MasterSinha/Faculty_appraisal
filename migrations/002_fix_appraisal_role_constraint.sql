-- Migration 002: Expand appraisal_role CHECK constraint
-- Adds 'admin', 'staff', and 'section_head' which were missing from the original constraint.
-- Safe to run on live data — CHECK constraints do not affect existing rows.

ALTER TABLE faculty_profiles
DROP CONSTRAINT IF EXISTS faculty_profiles_appraisal_role_check;

ALTER TABLE faculty_profiles
ADD CONSTRAINT faculty_profiles_appraisal_role_check
CHECK (appraisal_role IN (
    'faculty', 'non_teaching_staff', 'staff', 'hod', 'reporting_officer',
    'section_head', 'director', 'center_head', 'dean', 'registrar', 'vc', 'admin'
));
