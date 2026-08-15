-- Migration 027: Dynamic departments, HOD assignments, and Registrar-Gated Part D Review
-- Adds dynamic departments and HOD assignments per academic year,
-- and tracking columns to implement Registrar gating of Part D scores.

CREATE TABLE IF NOT EXISTS public.departments (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    school_code VARCHAR     NOT NULL, -- SoCSEA, SoBB, SoCE, SoEMR, SoCM, SoMCS, SoHSS, SoD, SoAA
    name        VARCHAR     NOT NULL,
    status      VARCHAR     NOT NULL DEFAULT 'active',
    created_by  UUID        NOT NULL REFERENCES public.faculty_profiles(id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.hod_assignments (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    faculty_id    UUID        NOT NULL REFERENCES public.faculty_profiles(id) ON DELETE CASCADE,
    department_id UUID        NOT NULL REFERENCES public.departments(id) ON DELETE CASCADE,
    academic_year VARCHAR     NOT NULL,
    created_by    UUID        NOT NULL REFERENCES public.faculty_profiles(id) ON DELETE RESTRICT,
    assigned_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE (department_id, academic_year)
);

-- Add Part D gating tracking columns to declarations table
ALTER TABLE public.declarations ADD COLUMN IF NOT EXISTS part_d_status VARCHAR NOT NULL DEFAULT 'pending';
ALTER TABLE public.declarations ADD COLUMN IF NOT EXISTS part_d_released_at TIMESTAMPTZ;
ALTER TABLE public.declarations ADD COLUMN IF NOT EXISTS part_d_released_by UUID REFERENCES public.faculty_profiles(id) ON DELETE SET NULL;

-- Add Registrar Part D score override to appraisal_reviews table
ALTER TABLE public.appraisal_reviews ADD COLUMN IF NOT EXISTS registrar_part_d_score NUMERIC;
