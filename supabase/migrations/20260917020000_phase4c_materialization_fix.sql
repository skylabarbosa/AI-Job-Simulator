-- Phase 4C fix: avoid PL/pgSQL variable ambiguity with tasks.module_id.

create or replace function public.materialize_approved_blueprint(
  target_project_id uuid,
  target_blueprint_id uuid
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  blueprint_record record;
  module_json jsonb;
  competency_json jsonb;
  concept_json jsonb;
  task_json jsonb;
  materialized_module_id uuid;
  materialized_competency_id uuid;
  materialized_concept_id uuid;
  materialized_task_id uuid;
  task_competency_name text;
  task_concept_name text;
  module_position integer := 0;
  competency_position integer;
  concept_position integer;
  task_position integer := 0;
  rubric_criteria jsonb;
  difficulty_value text;
  task_type_value text;
  modules_created integer := 0;
  competencies_created integer := 0;
  concepts_created integer := 0;
  tasks_created integer := 0;
  task_competencies_created integer := 0;
  task_concepts_created integer := 0;
  rubrics_created integer := 0;
  row_inserted boolean;
begin
  select * into blueprint_record
  from public.project_blueprints
  where id = target_blueprint_id
    and project_id = target_project_id
    and status = 'approved';

  if not found then
    raise exception 'Only an approved blueprint for this project can be materialized';
  end if;

  for module_json in select value from jsonb_array_elements(blueprint_record.blueprint_json -> 'modules') loop
    insert into public.modules (project_id, name, slug, description, position, status)
    values (
      target_project_id,
      module_json ->> 'name',
      lower(regexp_replace(trim(module_json ->> 'name'), '[^a-zA-Z0-9]+', '-', 'g')),
      module_json ->> 'description',
      module_position,
      'active'
    )
    on conflict (project_id, slug) do update
      set name = excluded.name,
          description = excluded.description,
          position = excluded.position,
          status = 'active',
          updated_at = timezone('utc', now())
    returning id, (xmax = 0) into materialized_module_id, row_inserted;
    if row_inserted then modules_created := modules_created + 1; end if;

    competency_position := 0;
    for competency_json in select value from jsonb_array_elements(module_json -> 'competencies') loop
      insert into public.competencies (module_id, name, slug, description, position, status)
      values (
        materialized_module_id,
        competency_json ->> 'name',
        lower(regexp_replace(trim(competency_json ->> 'name'), '[^a-zA-Z0-9]+', '-', 'g')),
        competency_json ->> 'description',
        competency_position,
        'active'
      )
      on conflict (module_id, slug) do update
        set name = excluded.name,
            description = excluded.description,
            position = excluded.position,
            status = 'active',
            updated_at = timezone('utc', now())
      returning id, (xmax = 0) into materialized_competency_id, row_inserted;
      if row_inserted then competencies_created := competencies_created + 1; end if;

      concept_position := 0;
      for concept_json in select value from jsonb_array_elements(competency_json -> 'concepts') loop
        insert into public.concepts (competency_id, name, slug, description, position, status)
        values (
          materialized_competency_id,
          concept_json ->> 'name',
          lower(regexp_replace(trim(concept_json ->> 'name'), '[^a-zA-Z0-9]+', '-', 'g')),
          concept_json ->> 'description',
          concept_position,
          'active'
        )
        on conflict (competency_id, slug) do update
          set name = excluded.name,
              description = excluded.description,
              position = excluded.position,
              status = 'active',
              updated_at = timezone('utc', now())
        returning id, (xmax = 0) into materialized_concept_id, row_inserted;
        if row_inserted then concepts_created := concepts_created + 1; end if;
        concept_position := concept_position + 1;
      end loop;
      competency_position := competency_position + 1;
    end loop;
    module_position := module_position + 1;
  end loop;

  for task_json in select value from jsonb_array_elements(blueprint_record.blueprint_json -> 'tasks') loop
    select case task_json ->> 'difficulty'
      when 'easy' then 'beginner'
      when 'medium' then 'intermediate'
      when 'hard' then 'advanced'
    end into difficulty_value;
    task_type_value := coalesce(task_json ->> 'task_kind', 'other');
    insert into public.tasks (project_id, module_id, title, description, instructions, task_type, difficulty, expected_outcome, reference_solution, position, status)
    select target_project_id, m.id, task_json ->> 'title', task_json ->> 'workplace_context', task_json ->> 'instruction', task_type_value,
      difficulty_value, task_json ->> 'expected_outcome', jsonb_build_object('dataset_fields', coalesce(task_json -> 'dataset_fields', '[]'::jsonb), 'sql_tables', coalesce(task_json -> 'sql_tables', '[]'::jsonb), 'sql_concepts', coalesce(task_json -> 'sql_concepts', '[]'::jsonb)), task_position, 'active'
    from public.modules m
    where m.project_id = target_project_id
      and m.slug = lower(regexp_replace(trim(task_json ->> 'related_module'), '[^a-zA-Z0-9]+', '-', 'g'))
    on conflict (project_id, title) do update
      set module_id = excluded.module_id,
          description = excluded.description,
          instructions = excluded.instructions,
          task_type = excluded.task_type,
          difficulty = excluded.difficulty,
          expected_outcome = excluded.expected_outcome,
          reference_solution = excluded.reference_solution,
          position = excluded.position,
          status = 'active',
          updated_at = timezone('utc', now())
    returning id, (xmax = 0) into materialized_task_id, row_inserted;
    if not found then raise exception 'Task references an unknown module: %', task_json ->> 'related_module'; end if;
    if row_inserted then tasks_created := tasks_created + 1; end if;

    for task_competency_name in select jsonb_array_elements_text(task_json -> 'related_competencies') loop
      insert into public.task_competencies (task_id, competency_id)
      select materialized_task_id, c.id
      from public.competencies c
      join public.modules m on m.id = c.module_id
      where m.project_id = target_project_id
        and m.slug = lower(regexp_replace(trim(task_json ->> 'related_module'), '[^a-zA-Z0-9]+', '-', 'g'))
        and c.slug = lower(regexp_replace(trim(task_competency_name), '[^a-zA-Z0-9]+', '-', 'g'))
      on conflict do nothing;
      if found then task_competencies_created := task_competencies_created + 1; end if;
    end loop;

    for task_concept_name in select jsonb_array_elements_text(task_json -> 'related_concepts') loop
      insert into public.task_concepts (task_id, concept_id)
      select materialized_task_id, co.id
      from public.concepts co
      join public.competencies c on c.id = co.competency_id
      join public.modules m on m.id = c.module_id
      where m.project_id = target_project_id
        and co.slug = lower(regexp_replace(trim(task_concept_name), '[^a-zA-Z0-9]+', '-', 'g'))
        and c.slug in (select lower(regexp_replace(trim(value), '[^a-zA-Z0-9]+', '-', 'g')) from jsonb_array_elements_text(task_json -> 'related_competencies'));
      if found then task_concepts_created := task_concepts_created + 1; end if;
    end loop;

    select coalesce(jsonb_agg(jsonb_build_object('name', value ->> 'name', 'description', value ->> 'description', 'what_should_be_checked', value ->> 'what_should_be_checked', 'evaluation_type', value ->> 'evaluation_type')), '[]'::jsonb)
      into rubric_criteria from jsonb_array_elements(task_json -> 'evaluation_criteria');
    insert into public.rubrics (task_id, version, criteria, scoring_guidance, max_score, status)
    values (materialized_task_id, 1, rubric_criteria, null, 100, 'active')
    on conflict (task_id, version) do update
      set criteria = excluded.criteria,
          status = 'active'
    returning (xmax = 0) into row_inserted;
    if row_inserted then rubrics_created := rubrics_created + 1; end if;
    task_position := task_position + 1;
  end loop;

  return jsonb_build_object('status', 'materialized', 'blueprint_version', blueprint_record.version, 'modules_created', modules_created, 'competencies_created', competencies_created, 'concepts_created', concepts_created, 'tasks_created', tasks_created, 'task_competencies_created', task_competencies_created, 'task_concepts_created', task_concepts_created, 'rubrics_created', rubrics_created);
end;
$$;

revoke all on function public.materialize_approved_blueprint(uuid, uuid) from public;
grant execute on function public.materialize_approved_blueprint(uuid, uuid) to authenticated;