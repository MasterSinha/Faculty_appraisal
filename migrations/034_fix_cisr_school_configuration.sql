-- Migration 034: Ensure track constraint permits 'cisr' and update canonical CISR configuration

-- 1. Ensure track check constraint permits 'engineering', 'non_engineering', 'cisr'
ALTER TABLE public.schools DROP CONSTRAINT IF EXISTS schools_track_check;
ALTER TABLE public.schools ADD CONSTRAINT schools_track_check 
    CHECK (track IN ('engineering', 'non_engineering', 'cisr'));

-- 2. Correct canonical CISR configuration
INSERT INTO public.schools (
    code, full_name, track, has_hod, has_director, approval_chain, departments, default_form, active, "order"
)
VALUES (
    'CISR',
    'Center for Interdisciplinary Studies & Research',
    'cisr',
    FALSE,
    FALSE,
    '["center_head", "vc"]'::jsonb,
    '[]'::jsonb,
    'standard',
    TRUE,
    10
)
ON CONFLICT (code) DO UPDATE SET
    full_name = EXCLUDED.full_name,
    track = EXCLUDED.track,
    has_hod = EXCLUDED.has_hod,
    has_director = EXCLUDED.has_director,
    approval_chain = EXCLUDED.approval_chain,
    departments = EXCLUDED.departments,
    default_form = EXCLUDED.default_form,
    active = EXCLUDED.active,
    "order" = EXCLUDED."order";
