-- Migration 031: Create schools table and seed initial legacy schools catalog

CREATE TABLE IF NOT EXISTS public.schools (
    code VARCHAR(50) PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    track VARCHAR(50) NOT NULL CHECK (track IN ('engineering', 'non_engineering')),
    has_hod BOOLEAN NOT NULL DEFAULT FALSE,
    has_director BOOLEAN NOT NULL DEFAULT TRUE,
    approval_chain JSONB NOT NULL DEFAULT '["director", "dean", "vc"]'::jsonb,
    departments JSONB NOT NULL DEFAULT '[]'::jsonb,
    default_form VARCHAR(50) NOT NULL DEFAULT 'standard' CHECK (default_form IN ('standard', 'creative')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    "order" INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_schools_active ON public.schools(active);
CREATE INDEX IF NOT EXISTS idx_schools_track ON public.schools(track);

-- Seed verified legacy institutions and forms
INSERT INTO public.schools (code, full_name, track, has_hod, has_director, approval_chain, departments, default_form, active, "order")
VALUES
('SoCSEA', 'School of Computer Science & Applications', 'engineering', FALSE, TRUE, '["director", "dean", "vc"]'::jsonb, '[]'::jsonb, 'standard', TRUE, 1),
('SoBB', 'School of Bio-Engineering & Bio Science', 'engineering', FALSE, TRUE, '["director", "dean", "vc"]'::jsonb, '[]'::jsonb, 'standard', TRUE, 2),
('SoCE', 'School of Continual Education', 'engineering', FALSE, TRUE, '["director", "dean", "vc"]'::jsonb, '[]'::jsonb, 'standard', TRUE, 3),
('SoEMR', 'School of Engineering, Management & Research', 'engineering', TRUE, TRUE, '["hod", "director", "dean", "vc"]'::jsonb, '["Mechanical Engineering", "Civil Engineering", "Chemical Engineering", "Semiconductor Engineering"]'::jsonb, 'standard', TRUE, 4),
('SoCM', 'School of Commerce & Management', 'non_engineering', FALSE, TRUE, '["director", "dean", "vc"]'::jsonb, '[]'::jsonb, 'standard', TRUE, 5),
('SoMCS', 'School of Media & Communication Studies', 'non_engineering', FALSE, TRUE, '["director", "dean", "vc"]'::jsonb, '[]'::jsonb, 'creative', TRUE, 6),
('SoHSS', 'School of Humanities and Social Sciences', 'non_engineering', FALSE, TRUE, '["director", "dean", "vc"]'::jsonb, '[]'::jsonb, 'creative', TRUE, 7),
('SoD', 'School of Design', 'non_engineering', FALSE, TRUE, '["director", "dean", "vc"]'::jsonb, '[]'::jsonb, 'creative', TRUE, 8),
('SoAA', 'School of Applied Arts', 'non_engineering', FALSE, TRUE, '["director", "dean", "vc"]'::jsonb, '[]'::jsonb, 'creative', TRUE, 9),
('CISR', 'Center for Interdisciplinary Studies & Research', 'engineering', FALSE, FALSE, '["vc"]'::jsonb, '[]'::jsonb, 'standard', TRUE, 10)
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
