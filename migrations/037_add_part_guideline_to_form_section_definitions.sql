-- Migration 037: Add part_guideline to form_section_definitions

ALTER TABLE IF EXISTS public.form_section_definitions
    ADD COLUMN IF NOT EXISTS part_guideline TEXT;
