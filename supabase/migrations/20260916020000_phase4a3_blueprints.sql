-- Phase 4A.3: validated AI project understanding drafts.

create table public.project_blueprints (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  version integer not null check (version > 0),
  status text not null default 'draft' check (status in ('draft', 'approved', 'rejected')),
  source_dataset_ids jsonb not null default '[]'::jsonb,
  blueprint_json jsonb not null,
  provider text,
  model text,
  prompt_version text,
  generated_by uuid references public.users(id) on delete set null,
  approved_by uuid references public.users(id) on delete set null,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  approved_at timestamptz,
  unique (project_id, version)
);

create index project_blueprints_project_id_idx on public.project_blueprints(project_id);
create index project_blueprints_status_idx on public.project_blueprints(status);

create trigger project_blueprints_set_updated_at
before update on public.project_blueprints
for each row execute function public.set_updated_at();

alter table public.project_blueprints enable row level security;

create policy project_blueprints_select_allowed
on public.project_blueprints for select to authenticated
using (public.can_manage_project(project_id));

create policy project_blueprints_insert_allowed
on public.project_blueprints for insert to authenticated
with check (public.can_manage_project(project_id));

create policy project_blueprints_update_draft
on public.project_blueprints for update to authenticated
using (status = 'draft' and public.can_manage_project(project_id))
with check (status in ('draft', 'approved') and public.can_manage_project(project_id));
