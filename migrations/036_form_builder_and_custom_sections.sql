-- Migration 036: Form Builder dynamic form schema, custom section persistence, and custom_fields JSONB

-- 1. Ensure columns on form_section_definitions
ALTER TABLE IF EXISTS public.form_section_definitions
    ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS "order" INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS table_order JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Ensure part is varchar / text without restrictive enum check
ALTER TABLE IF EXISTS public.form_section_definitions
    ALTER COLUMN part TYPE VARCHAR(255);

-- 2. Create generic custom_section_rows table for dynamic/custom sections
CREATE TABLE IF NOT EXISTS public.custom_section_rows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    faculty_email VARCHAR(255) NOT NULL,
    academic_year VARCHAR(50) NOT NULL,
    form_family VARCHAR(100),
    section_code VARCHAR(100) NOT NULL,
    section_title VARCHAR(255),
    row_no INTEGER DEFAULT 1,
    score NUMERIC NOT NULL DEFAULT 0,
    hod_score NUMERIC,
    director_score NUMERIC,
    dean_score NUMERIC,
    vc_score NUMERIC,
    custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_custom_section_rows_lookup 
    ON public.custom_section_rows (faculty_email, academic_year, section_code);

-- 3. Add custom_fields JSONB to all physical section tables
ALTER TABLE IF EXISTS public.teaching_process ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.course_files ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.innovative_teaching ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.projects_guided ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.qualification_enhancement ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.student_feedback ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.department_activities ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.university_activities ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.social_contributions ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.industry_connect ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.acr_scores ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.event_organisation ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.alumni_engagement ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.placement_mentoring ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.journal_publications ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.popular_writings ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.book_publications ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.ict_pedagogy ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.research_guidance ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.research_projects ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.external_research_projects ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.ipr_records ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.patents ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.awards ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.conferences ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.research_proposals ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.products_developed ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.self_development ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE IF EXISTS public.industrial_training ADD COLUMN IF NOT EXISTS custom_fields JSONB NOT NULL DEFAULT '{}'::jsonb;
