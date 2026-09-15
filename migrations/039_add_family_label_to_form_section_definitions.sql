-- Migration 039: Add family_label to form_section_definitions

ALTER TABLE IF EXISTS public.form_section_definitions
    ADD COLUMN IF NOT EXISTS family_label TEXT;
