-- Phase 2: project-agnostic database foundation.
-- Authentication-owned identities and authorization policies belong to Phase 3.

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create table public.users (
  id uuid primary key default gen_random_uuid(),
  email text unique,
  display_name text,
  status text not null default 'active' check (status in ('active', 'inactive', 'suspended')),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table public.projects (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  description text,
  created_by uuid references public.users(id) on delete set null,
  status text not null default 'draft' check (status in ('draft', 'active', 'archived')),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table public.datasets (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  file_name text not null,
  storage_path text not null,
  file_type text not null default 'text/csv',
  schema_metadata jsonb not null default '{}'::jsonb,
  status text not null default 'pending' check (status in ('pending', 'ready', 'failed', 'archived')),
  uploaded_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (project_id, storage_path)
);

create table public.modules (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  name text not null,
  slug text not null,
  description text,
  position integer not null default 0 check (position >= 0),
  status text not null default 'draft' check (status in ('draft', 'active', 'archived')),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (project_id, slug),
  unique (id, project_id)
);

create table public.competencies (
  id uuid primary key default gen_random_uuid(),
  module_id uuid not null references public.modules(id) on delete cascade,
  name text not null,
  slug text not null,
  description text,
  position integer not null default 0 check (position >= 0),
  status text not null default 'active' check (status in ('draft', 'active', 'archived')),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (module_id, slug)
);

create table public.concepts (
  id uuid primary key default gen_random_uuid(),
  competency_id uuid not null references public.competencies(id) on delete cascade,
  name text not null,
  slug text not null,
  description text,
  position integer not null default 0 check (position >= 0),
  status text not null default 'active' check (status in ('draft', 'active', 'archived')),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (competency_id, slug)
);

create table public.tasks (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  module_id uuid,
  title text not null,
  description text,
  instructions text,
  task_type text not null,
  difficulty text not null default 'beginner' check (difficulty in ('beginner', 'intermediate', 'advanced')),
  expected_outcome text,
  reference_solution jsonb,
  position integer not null default 0 check (position >= 0),
  status text not null default 'draft' check (status in ('draft', 'active', 'archived')),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (id, project_id),
  constraint tasks_module_project_fk
    foreign key (module_id, project_id)
    references public.modules(id, project_id)
    on delete set null (module_id)
);

create table public.task_competencies (
  task_id uuid not null references public.tasks(id) on delete cascade,
  competency_id uuid not null references public.competencies(id) on delete cascade,
  primary key (task_id, competency_id)
);

create table public.task_concepts (
  task_id uuid not null references public.tasks(id) on delete cascade,
  concept_id uuid not null references public.concepts(id) on delete cascade,
  primary key (task_id, concept_id)
);

create table public.rubrics (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.tasks(id) on delete cascade,
  version integer not null default 1 check (version > 0),
  criteria jsonb not null default '[]'::jsonb,
  scoring_guidance text,
  max_score numeric(6, 2) not null default 100 check (max_score > 0),
  status text not null default 'draft' check (status in ('draft', 'active', 'archived')),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (task_id, version)
);

create table public.simulations (
  id uuid primary key default gen_random_uuid(),
  learner_id uuid not null references public.users(id) on delete restrict,
  project_id uuid not null references public.projects(id) on delete restrict,
  current_task_id uuid,
  status text not null default 'active' check (status in ('active', 'paused', 'completed', 'abandoned')),
  progress numeric(5, 2) not null default 0 check (progress >= 0 and progress <= 100),
  started_at timestamptz not null default timezone('utc', now()),
  completed_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  check (completed_at is null or completed_at >= started_at),
  constraint simulations_current_task_project_fk
    foreign key (current_task_id, project_id)
    references public.tasks(id, project_id)
    on delete set null (current_task_id)
);

create table public.submissions (
  id uuid primary key default gen_random_uuid(),
  simulation_id uuid not null references public.simulations(id) on delete cascade,
  task_id uuid not null references public.tasks(id) on delete restrict,
  learner_id uuid not null references public.users(id) on delete restrict,
  attempt_number integer not null default 1 check (attempt_number > 0),
  content jsonb not null default '{}'::jsonb,
  status text not null default 'submitted' check (status in ('draft', 'submitted', 'superseded')),
  submitted_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (simulation_id, task_id, attempt_number)
);

create table public.evaluations (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references public.submissions(id) on delete cascade,
  evaluation_type text not null check (evaluation_type in ('deterministic', 'ai')),
  status text not null default 'pending' check (status in ('pending', 'completed', 'failed')),
  score numeric(6, 2) check (score >= 0),
  deterministic_result jsonb,
  ai_result jsonb,
  feedback text,
  evaluated_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (submission_id, evaluation_type)
);

create table public.user_skills (
  id uuid primary key default gen_random_uuid(),
  learner_id uuid not null references public.users(id) on delete cascade,
  competency_id uuid references public.competencies(id) on delete cascade,
  concept_id uuid references public.concepts(id) on delete cascade,
  current_score numeric(6, 2) not null default 0 check (current_score >= 0 and current_score <= 100),
  previous_score numeric(6, 2) check (previous_score >= 0 and previous_score <= 100),
  level text not null default 'developing' check (level in ('novice', 'developing', 'proficient', 'advanced')),
  last_evaluated_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  check ((competency_id is not null) <> (concept_id is not null))
);

create or replace function public.validate_task_competency_project()
returns trigger
language plpgsql
as $$
begin
  if not exists (
    select 1
    from public.tasks t
    join public.competencies c on c.id = new.competency_id
    join public.modules m on m.id = c.module_id
    where t.id = new.task_id
      and t.project_id = m.project_id
  ) then
    raise exception 'Task and competency must belong to the same project';
  end if;

  return new;
end;
$$;

create or replace function public.validate_task_concept_project()
returns trigger
language plpgsql
as $$
begin
  if not exists (
    select 1
    from public.tasks t
    join public.concepts c on c.id = new.concept_id
    join public.competencies co on co.id = c.competency_id
    join public.modules m on m.id = co.module_id
    where t.id = new.task_id
      and t.project_id = m.project_id
  ) then
    raise exception 'Task and concept must belong to the same project';
  end if;

  return new;
end;
$$;

create or replace function public.validate_submission_consistency()
returns trigger
language plpgsql
as $$
declare
  simulation_record record;
  task_project_id uuid;
begin
  select s.learner_id, s.project_id
  into simulation_record
  from public.simulations s
  where s.id = new.simulation_id;

  select t.project_id
  into task_project_id
  from public.tasks t
  where t.id = new.task_id;

  if simulation_record is null
     or task_project_id is null
     or simulation_record.project_id <> task_project_id
     or simulation_record.learner_id <> new.learner_id then
    raise exception 'Submission must match its simulation project and learner';
  end if;

  return new;
end;
$$;

create trigger task_competencies_validate_project
before insert or update on public.task_competencies
for each row execute function public.validate_task_competency_project();

create trigger task_concepts_validate_project
before insert or update on public.task_concepts
for each row execute function public.validate_task_concept_project();

create trigger submissions_validate_consistency
before insert or update on public.submissions
for each row execute function public.validate_submission_consistency();

create unique index user_skills_learner_competency_uidx
  on public.user_skills (learner_id, competency_id)
  where competency_id is not null;
create unique index user_skills_learner_concept_uidx
  on public.user_skills (learner_id, concept_id)
  where concept_id is not null;

create index datasets_project_id_idx on public.datasets (project_id);
create index modules_project_id_idx on public.modules (project_id);
create index competencies_module_id_idx on public.competencies (module_id);
create index concepts_competency_id_idx on public.concepts (competency_id);
create index tasks_project_id_idx on public.tasks (project_id);
create index tasks_module_id_idx on public.tasks (module_id);
create index task_competencies_competency_id_idx on public.task_competencies (competency_id);
create index task_concepts_concept_id_idx on public.task_concepts (concept_id);
create index rubrics_task_id_idx on public.rubrics (task_id);
create index simulations_learner_id_idx on public.simulations (learner_id);
create index simulations_project_id_idx on public.simulations (project_id);
create index submissions_simulation_id_idx on public.submissions (simulation_id);
create index submissions_task_id_idx on public.submissions (task_id);
create index submissions_learner_id_idx on public.submissions (learner_id);
create index evaluations_submission_id_idx on public.evaluations (submission_id);
create index user_skills_learner_id_idx on public.user_skills (learner_id);
create index user_skills_competency_id_idx on public.user_skills (competency_id);
create index user_skills_concept_id_idx on public.user_skills (concept_id);

create trigger users_set_updated_at before update on public.users for each row execute function public.set_updated_at();
create trigger projects_set_updated_at before update on public.projects for each row execute function public.set_updated_at();
create trigger datasets_set_updated_at before update on public.datasets for each row execute function public.set_updated_at();
create trigger modules_set_updated_at before update on public.modules for each row execute function public.set_updated_at();
create trigger competencies_set_updated_at before update on public.competencies for each row execute function public.set_updated_at();
create trigger concepts_set_updated_at before update on public.concepts for each row execute function public.set_updated_at();
create trigger tasks_set_updated_at before update on public.tasks for each row execute function public.set_updated_at();
create trigger rubrics_set_updated_at before update on public.rubrics for each row execute function public.set_updated_at();
create trigger simulations_set_updated_at before update on public.simulations for each row execute function public.set_updated_at();
create trigger submissions_set_updated_at before update on public.submissions for each row execute function public.set_updated_at();
create trigger evaluations_set_updated_at before update on public.evaluations for each row execute function public.set_updated_at();
create trigger user_skills_set_updated_at before update on public.user_skills for each row execute function public.set_updated_at();

-- Keep the schema closed until Phase 3 defines auth-backed policies.
do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'users', 'projects', 'datasets', 'modules', 'competencies', 'concepts',
    'tasks', 'task_competencies', 'task_concepts', 'rubrics', 'simulations',
    'submissions', 'evaluations', 'user_skills'
  ] loop
    execute format('alter table public.%I enable row level security', table_name);
  end loop;
end;
$$;

comment on schema public is 'Phase 2 project-agnostic AI Job Simulator foundation. Add auth-backed RLS policies in Phase 3.';
