-- Migration 032: Add form_variant, form_type, and form_label to schools table

ALTER TABLE public.schools 
ADD COLUMN IF NOT EXISTS form_variant VARCHAR(50) NOT NULL DEFAULT 'standard',
ADD COLUMN IF NOT EXISTS form_type VARCHAR(50) NOT NULL DEFAULT 'FORM_A',
ADD COLUMN IF NOT EXISTS form_label VARCHAR(255) NOT NULL DEFAULT 'Standard Appraisal';

-- Explicitly backfill legacy creative schools to the correct form variant
UPDATE public.schools
SET form_variant = 'mediaCommunication',
    form_type = 'FORM_B',
    form_label = 'Creative Appraisal - Media Communication'
WHERE UPPER(code) IN ('SOMCS', 'SOHSS');

UPDATE public.schools
SET form_variant = 'designArts',
    form_type = 'FORM_C',
    form_label = 'Creative Appraisal - Design Arts'
WHERE UPPER(code) IN ('SOD', 'SOAA');

UPDATE public.schools
SET form_variant = 'standard',
    form_type = 'FORM_A',
    form_label = 'Standard Appraisal'
WHERE default_form = 'standard';
