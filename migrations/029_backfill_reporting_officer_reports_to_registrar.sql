-- Migration 029: Backfill existing reporting_officer profiles to reports_to_registrar = true
-- Legacy Reporting Officers route through the Registrar by default (RO -> Registrar -> VC)
UPDATE public.faculty_profiles
SET reports_to_registrar = true
WHERE appraisal_role = 'reporting_officer';
