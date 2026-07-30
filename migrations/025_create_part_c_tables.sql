-- migration 025: Create tables for new Part C sections (event_organisation, alumni_engagement, placement_mentoring)

CREATE TABLE IF NOT EXISTS public.event_organisation (
  id uuid primary key default gen_random_uuid(),
  faculty_email text not null,
  academic_year text not null,
  form_family text,
  section_title text,
  max_marks numeric,
  row_no integer,
  event text,
  role text,
  date text,
  level text,
  score numeric not null default 0,
  hod_score numeric,
  director_score numeric,
  dean_score numeric,
  vc_score numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

CREATE TABLE IF NOT EXISTS public.alumni_engagement (
  id uuid primary key default gen_random_uuid(),
  faculty_email text not null,
  academic_year text not null,
  form_family text,
  section_title text,
  max_marks numeric,
  row_no integer,
  activity text,
  details text,
  date text,
  score numeric not null default 0,
  hod_score numeric,
  director_score numeric,
  dean_score numeric,
  vc_score numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

CREATE TABLE IF NOT EXISTS public.placement_mentoring (
  id uuid primary key default gen_random_uuid(),
  faculty_email text not null,
  academic_year text not null,
  form_family text,
  section_title text,
  max_marks numeric,
  row_no integer,
  type text,
  name text,
  date text,
  score numeric not null default 0,
  hod_score numeric,
  director_score numeric,
  dean_score numeric,
  vc_score numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
