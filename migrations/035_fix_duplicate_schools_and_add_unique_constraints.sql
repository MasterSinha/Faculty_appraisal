-- Migration 035: Fix duplicate/conflicting school entries (such as duplicate SoEMR) and enforce case-insensitive uniqueness

-- 1. Ensure track constraint allows all valid tracks
ALTER TABLE public.schools DROP CONSTRAINT IF EXISTS schools_track_check;
ALTER TABLE public.schools ADD CONSTRAINT schools_track_check 
    CHECK (track IN ('engineering', 'non_engineering', 'cisr'));

-- 2. Consolidate references pointing to case-variant SoEMR entries
UPDATE public.faculty_profiles 
SET school = 'SoEMR' 
WHERE LOWER(TRIM(school)) = 'soemr' AND school != 'SoEMR';

UPDATE public.departments 
SET school_code = 'SoEMR' 
WHERE LOWER(TRIM(school_code)) = 'soemr' AND school_code != 'SoEMR';

UPDATE public.role_assignments 
SET scope_id = 'SoEMR' 
WHERE LOWER(TRIM(scope_id)) = 'soemr' AND scope_id != 'SoEMR' AND scope_type = 'school';

-- 3. Upsert canonical SoEMR record under engineering track
INSERT INTO public.schools (
    code, full_name, track, has_hod, has_director,
    approval_chain, departments, default_form, form_variant, form_type, form_label, active, "order",
    created_at, updated_at
) VALUES (
    'SoEMR',
    'School of Engineering, Management & Research',
    'engineering',
    true,
    true,
    '["hod", "director", "dean", "vc"]'::jsonb,
    '["Mechanical Engineering", "Civil Engineering", "Chemical Engineering", "Semiconductor Engineering"]'::jsonb,
    'standard',
    'standard',
    'FORM_A',
    'Standard Appraisal',
    true,
    4,
    NOW(),
    NOW()
)
ON CONFLICT (code) DO UPDATE SET
    full_name      = 'School of Engineering, Management & Research',
    track          = 'engineering',
    has_hod        = true,
    has_director   = true,
    approval_chain = '["hod", "director", "dean", "vc"]'::jsonb,
    departments    = '["Mechanical Engineering", "Civil Engineering", "Chemical Engineering", "Semiconductor Engineering"]'::jsonb,
    default_form   = 'standard',
    form_variant   = 'standard',
    form_type      = 'FORM_A',
    form_label     = 'Standard Appraisal',
    active         = true,
    "order"        = 4,
    updated_at     = NOW();

-- 4. Delete duplicate SoEMR entries
DELETE FROM public.schools 
WHERE LOWER(TRIM(code)) = 'soemr' AND code != 'SoEMR';

-- 5. Deduplicate any other case-insensitive duplicate schools
WITH ranked_duplicates AS (
    SELECT 
        code,
        LOWER(TRIM(code)) as lower_code,
        ROW_NUMBER() OVER (
            PARTITION BY LOWER(TRIM(code)) 
            ORDER BY active DESC, updated_at DESC, created_at ASC
        ) as rn,
        FIRST_VALUE(code) OVER (
            PARTITION BY LOWER(TRIM(code)) 
            ORDER BY active DESC, updated_at DESC, created_at ASC
        ) as canonical_code
    FROM public.schools
),
duplicates_to_delete AS (
    SELECT code, canonical_code FROM ranked_duplicates WHERE rn > 1
)
UPDATE public.faculty_profiles fp
SET school = dtd.canonical_code
FROM duplicates_to_delete dtd
WHERE fp.school = dtd.code;

WITH ranked_duplicates AS (
    SELECT 
        code,
        LOWER(TRIM(code)) as lower_code,
        ROW_NUMBER() OVER (
            PARTITION BY LOWER(TRIM(code)) 
            ORDER BY active DESC, updated_at DESC, created_at ASC
        ) as rn,
        FIRST_VALUE(code) OVER (
            PARTITION BY LOWER(TRIM(code)) 
            ORDER BY active DESC, updated_at DESC, created_at ASC
        ) as canonical_code
    FROM public.schools
),
duplicates_to_delete AS (
    SELECT code, canonical_code FROM ranked_duplicates WHERE rn > 1
)
UPDATE public.departments dept
SET school_code = dtd.canonical_code
FROM duplicates_to_delete dtd
WHERE dept.school_code = dtd.code;

WITH ranked_duplicates AS (
    SELECT 
        code,
        LOWER(TRIM(code)) as lower_code,
        ROW_NUMBER() OVER (
            PARTITION BY LOWER(TRIM(code)) 
            ORDER BY active DESC, updated_at DESC, created_at ASC
        ) as rn
    FROM public.schools
),
duplicates_to_delete AS (
    SELECT code FROM ranked_duplicates WHERE rn > 1
)
DELETE FROM public.schools
WHERE code IN (SELECT code FROM duplicates_to_delete);

-- 6. Enforce case-insensitive uniqueness at the database level
CREATE UNIQUE INDEX IF NOT EXISTS idx_schools_lower_code ON public.schools (LOWER(TRIM(code)));
