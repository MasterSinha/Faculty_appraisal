ALTER TABLE faculty_profiles
DROP CONSTRAINT IF EXISTS faculty_profiles_appraisal_role_check;

ALTER TABLE faculty_profiles
ADD CONSTRAINT faculty_profiles_appraisal_role_check
CHECK (appraisal_role IN (
    'faculty', 'non_teaching_staff', 'staff', 'hod', 'reporting_officer',
    'section_head', 'director', 'center_head', 'dean', 'registrar', 'vc',
    'admin', 'hr', 'super_admin'
));
