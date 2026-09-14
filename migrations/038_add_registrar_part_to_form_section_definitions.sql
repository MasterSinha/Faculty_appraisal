-- Migration 038: Add registrar_part to form_section_definitions

ALTER TABLE IF EXISTS public.form_section_definitions
    ADD COLUMN IF NOT EXISTS registrar_part BOOLEAN NOT NULL DEFAULT false;
