-- Phase 4A.1: business project context fields.

alter table public.projects
  add column business_problem text,
  add column work_requirements text,
  add column desired_outcome text;
