-- 028_add_activity_logs.sql
-- Create activity_logs table for persistent activity tracking

CREATE TABLE IF NOT EXISTS activity_logs (
    id UUID PRIMARY KEY,
    type VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    detail VARCHAR NOT NULL,
    meta JSONB NOT NULL DEFAULT '{}',
    academic_year VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed activity_logs with historical submission events
INSERT INTO activity_logs (id, type, title, detail, meta, academic_year, created_at)
SELECT 
    gen_random_uuid(),
    'submission',
    'Appraisal Submitted',
    f.full_name || ' (' || COALESCE(f.school, '') || ') submitted self-appraisal form',
    json_build_object('email', f.email, 'role', f.appraisal_role, 'school', f.school)::jsonb,
    d.academic_year,
    d.submitted_at
FROM declarations d
JOIN faculty_profiles f ON d.faculty_email = f.email
WHERE d.submitted_at IS NOT NULL
ON CONFLICT (id) DO NOTHING;

-- Seed activity_logs with historical reviewer events
INSERT INTO activity_logs (id, type, title, detail, meta, academic_year, created_at)
SELECT 
    gen_random_uuid(),
    'review',
    'Reviewed by ' || CASE 
        WHEN r.reviewer_role = 'hod' THEN 'HOD'
        WHEN r.reviewer_role = 'center_head' THEN 'Center Head'
        WHEN r.reviewer_role = 'director' THEN 'Director'
        WHEN r.reviewer_role = 'dean' THEN 'Dean'
        WHEN r.reviewer_role = 'vc' THEN 'VC'
        WHEN r.reviewer_role = 'registrar' THEN 'Registrar'
        WHEN r.reviewer_role = 'reporting_officer' THEN 'Reporting Officer'
        ELSE UPPER(r.reviewer_role)
    END,
    CASE 
        WHEN r.status = 'Rejected' THEN 
            CASE 
                WHEN r.reviewer_role = 'hod' THEN 'HOD'
                WHEN r.reviewer_role = 'center_head' THEN 'Center Head'
                WHEN r.reviewer_role = 'director' THEN 'Director'
                WHEN r.reviewer_role = 'dean' THEN 'Dean'
                WHEN r.reviewer_role = 'vc' THEN 'VC'
                WHEN r.reviewer_role = 'registrar' THEN 'Registrar'
                WHEN r.reviewer_role = 'reporting_officer' THEN 'Reporting Officer'
                ELSE UPPER(r.reviewer_role)
            END || ' (' || r.reviewer_email || ') rejected ' || f.full_name || '''s appraisal form'
        ELSE 
            CASE 
                WHEN r.reviewer_role = 'hod' THEN 'HOD'
                WHEN r.reviewer_role = 'center_head' THEN 'Center Head'
                WHEN r.reviewer_role = 'director' THEN 'Director'
                WHEN r.reviewer_role = 'dean' THEN 'Dean'
                WHEN r.reviewer_role = 'vc' THEN 'VC'
                WHEN r.reviewer_role = 'registrar' THEN 'Registrar'
                WHEN r.reviewer_role = 'reporting_officer' THEN 'Reporting Officer'
                ELSE UPPER(r.reviewer_role)
            END || ' (' || r.reviewer_email || ') reviewed ' || f.full_name || '''s appraisal form (' || r.status || ')'
    END,
    json_build_object('faculty_email', r.faculty_email, 'reviewer', r.reviewer_email)::jsonb,
    r.academic_year,
    r.reviewed_at
FROM appraisal_reviews r
JOIN faculty_profiles f ON r.faculty_email = f.email
WHERE r.reviewed_at IS NOT NULL
ON CONFLICT (id) DO NOTHING;
