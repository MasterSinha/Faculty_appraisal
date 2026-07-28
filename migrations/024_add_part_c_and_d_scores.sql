-- migration 024: Add part c and d scores to declarations and appraisal_reviews
ALTER TABLE public.declarations
  ADD COLUMN IF NOT EXISTS part_c_total numeric not null default 0,
  ADD COLUMN IF NOT EXISTS part_d_total numeric not null default 0;

ALTER TABLE public.appraisal_reviews
  ADD COLUMN IF NOT EXISTS part_c_score numeric not null default 0,
  ADD COLUMN IF NOT EXISTS part_d_score numeric not null default 0;
