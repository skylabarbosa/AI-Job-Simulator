-- Phase 5.5: immutable runtime releases.  A release is the explicit link
-- between one approved blueprint and the runtime rows produced from it.
-- Existing rows are deliberately not guessed/backfilled: their provenance is
-- unknown and changing it would rewrite learner history.

create table public.project_releases (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete restrict,
  blueprint_id uuid not null references public.project_blueprints(id) on delete restrict,
  status text not null default 'materialized' check (status in ('materialized', 'published', 'superseded', 'abandoned')),
  created_at timestamptz not null default timezone('utc', now()),
  published_at timestamptz,
  unique (project_id, blueprint_id)
);
create unique index project_releases_one_published_per_project
  on public.project_releases(project_id) where status = 'published';

create unique index simulations_one_resumable_per_learner_project
  on public.simulations(learner_id, project_id)
  where status in ('active', 'paused');

alter table public.projects add column published_release_id uuid references public.project_releases(id) on delete restrict;
alter table public.modules add column release_id uuid references public.project_releases(id) on delete restrict;
alter table public.tasks add column release_id uuid references public.project_releases(id) on delete restrict;

-- A release's definitions are append-only.  The legacy project-level
-- uniqueness is replaced so a revision can use the same human-facing title.
alter table public.modules drop constraint if exists modules_project_id_slug_key;
alter table public.tasks drop constraint if exists tasks_project_title_unique;
create unique index modules_release_slug_uidx on public.modules(release_id, slug) where release_id is not null;
create unique index tasks_release_title_uidx on public.tasks(release_id, title) where release_id is not null;
create index modules_release_id_idx on public.modules(release_id);
create index tasks_release_id_idx on public.tasks(release_id);

create or replace function public.materialize_approved_blueprint(
  target_project_id uuid,
  target_blueprint_id uuid
)
returns jsonb language plpgsql security invoker set search_path = public as $$
declare
  blueprint_record record; release_record record; module_json jsonb; competency_json jsonb;
  concept_json jsonb; task_json jsonb; materialized_module_id uuid; materialized_competency_id uuid;
  materialized_concept_id uuid; materialized_task_id uuid; task_competency_name text; task_concept_name text;
  module_position integer := 0; competency_position integer; concept_position integer; task_position integer := 0;
  difficulty_value text; task_type_value text; rubric_criteria jsonb;
begin
  select * into blueprint_record from public.project_blueprints
    where id = target_blueprint_id and project_id = target_project_id and status = 'approved';
  if not found then raise exception 'Only an approved blueprint for this project can be materialized'; end if;
  select * into release_record from public.project_releases
    where project_id = target_project_id and blueprint_id = target_blueprint_id;
  if found and release_record.status <> 'materialized' then
    raise exception 'Published or superseded releases are immutable; create a new approved blueprint revision';
  end if;
  if not found then
    insert into public.project_releases(project_id, blueprint_id, status)
      values(target_project_id, target_blueprint_id, 'materialized')
      returning * into release_record;
  end if;

  -- Re-materialising the same un-published release is safe and deterministic.
  delete from public.rubrics where task_id in (select id from public.tasks where release_id = release_record.id);
  delete from public.tasks where release_id = release_record.id;
  delete from public.concepts where competency_id in (select c.id from public.competencies c join public.modules m on m.id=c.module_id where m.release_id=release_record.id);
  delete from public.competencies where module_id in (select id from public.modules where release_id=release_record.id);
  delete from public.modules where release_id = release_record.id;

  for module_json in select value from jsonb_array_elements(blueprint_record.blueprint_json -> 'modules') loop
    insert into public.modules(project_id, release_id, name, slug, description, position, status)
      values(target_project_id, release_record.id, module_json->>'name', lower(regexp_replace(trim(module_json->>'name'), '[^a-zA-Z0-9]+', '-', 'g')), module_json->>'description', module_position, 'active')
      returning id into materialized_module_id;
    competency_position := 0;
    for competency_json in select value from jsonb_array_elements(module_json->'competencies') loop
      insert into public.competencies(module_id,name,slug,description,position,status)
        values(materialized_module_id, competency_json->>'name', lower(regexp_replace(trim(competency_json->>'name'), '[^a-zA-Z0-9]+', '-', 'g')), competency_json->>'description', competency_position, 'active') returning id into materialized_competency_id;
      concept_position := 0;
      for concept_json in select value from jsonb_array_elements(competency_json->'concepts') loop
        insert into public.concepts(competency_id,name,slug,description,position,status)
          values(materialized_competency_id, concept_json->>'name', lower(regexp_replace(trim(concept_json->>'name'), '[^a-zA-Z0-9]+', '-', 'g')), concept_json->>'description', concept_position, 'active');
        concept_position := concept_position + 1;
      end loop;
      competency_position := competency_position + 1;
    end loop;
    module_position := module_position + 1;
  end loop;
  for task_json in select value from jsonb_array_elements(blueprint_record.blueprint_json->'tasks') loop
    difficulty_value := case task_json->>'difficulty' when 'easy' then 'beginner' when 'medium' then 'intermediate' when 'hard' then 'advanced' end;
    task_type_value := coalesce(task_json->>'task_kind', 'other');
    insert into public.tasks(project_id,release_id,module_id,title,description,instructions,task_type,difficulty,expected_outcome,reference_solution,position,status)
      select target_project_id, release_record.id, m.id, task_json->>'title', task_json->>'workplace_context', task_json->>'instruction', task_type_value, difficulty_value, task_json->>'expected_outcome', jsonb_build_object('blueprint_task_key', task_json->>'task_key', 'dataset_fields',coalesce(task_json->'dataset_fields','[]'::jsonb),'sql_tables',coalesce(task_json->'sql_tables','[]'::jsonb),'sql_concepts',coalesce(task_json->'sql_concepts','[]'::jsonb)), task_position, 'active'
      from public.modules m where m.release_id=release_record.id and m.slug=lower(regexp_replace(trim(task_json->>'related_module'), '[^a-zA-Z0-9]+', '-', 'g')) returning id into materialized_task_id;
    if not found then raise exception 'Task references an unknown module: %', task_json->>'related_module'; end if;
    for task_competency_name in select jsonb_array_elements_text(task_json->'related_competencies') loop
      insert into public.task_competencies(task_id,competency_id) select materialized_task_id,c.id from public.competencies c join public.modules m on m.id=c.module_id where m.release_id=release_record.id and m.slug=lower(regexp_replace(trim(task_json->>'related_module'),'[^a-zA-Z0-9]+','-','g')) and c.slug=lower(regexp_replace(trim(task_competency_name),'[^a-zA-Z0-9]+','-','g')) on conflict do nothing;
    end loop;
    for task_concept_name in select jsonb_array_elements_text(task_json->'related_concepts') loop
      insert into public.task_concepts(task_id,concept_id) select materialized_task_id,co.id from public.concepts co join public.competencies c on c.id=co.competency_id join public.modules m on m.id=c.module_id where m.release_id=release_record.id and co.slug=lower(regexp_replace(trim(task_concept_name),'[^a-zA-Z0-9]+','-','g')) and c.slug in (select lower(regexp_replace(trim(value),'[^a-zA-Z0-9]+','-','g')) from jsonb_array_elements_text(task_json->'related_competencies')) on conflict do nothing;
    end loop;
    select coalesce(jsonb_agg(jsonb_build_object('name',value->>'name','description',value->>'description','what_should_be_checked',value->>'what_should_be_checked','evaluation_type',value->>'evaluation_type')),'[]'::jsonb) into rubric_criteria from jsonb_array_elements(task_json->'evaluation_criteria');
    insert into public.rubrics(task_id,version,criteria,max_score,status) values(materialized_task_id,1,rubric_criteria,100,'active');
    task_position := task_position + 1;
  end loop;
  return jsonb_build_object('status','materialized','release_id',release_record.id,'blueprint_id',blueprint_record.id,'blueprint_version',blueprint_record.version);
end; $$;

create or replace function public.publish_materialized_release(target_project_id uuid, target_blueprint_id uuid)
returns jsonb language plpgsql security invoker set search_path = public as $$
declare release_record record;
begin
  select r.* into release_record from public.project_releases r join public.project_blueprints b on b.id=r.blueprint_id
    where r.project_id=target_project_id and r.blueprint_id=target_blueprint_id and r.status='materialized' and b.status='approved';
  if not found then raise exception 'The exact approved blueprint must be materialized before publishing'; end if;
  if not exists(select 1 from public.tasks where release_id=release_record.id and status='active') then raise exception 'The release has no active tasks'; end if;
  update public.project_releases set status='superseded'
    where project_id=target_project_id and status='published' and id <> release_record.id;
  update public.project_releases set status='published', published_at=timezone('utc',now()) where id=release_record.id;
  update public.projects set status='active', published_release_id=release_record.id
    where id=target_project_id and status in ('draft','active');
  if not found then raise exception 'Only draft or published projects can release a revision'; end if;
  return jsonb_build_object('release_id',release_record.id,'blueprint_id',target_blueprint_id);
end; $$;

revoke all on function public.materialize_approved_blueprint(uuid,uuid) from public;
revoke all on function public.publish_materialized_release(uuid,uuid) from public;
grant execute on function public.materialize_approved_blueprint(uuid,uuid) to authenticated;
grant execute on function public.publish_materialized_release(uuid,uuid) to authenticated;
