create or replace function public.require_release_task_blueprint_identity()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.release_id is not null
     and coalesce(new.reference_solution ->> 'blueprint_task_key', '') = '' then
    raise exception 'Release tasks require a persisted blueprint task identity; create a new blueprint revision'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger tasks_require_release_blueprint_identity
before insert or update of release_id, reference_solution on public.tasks
for each row execute function public.require_release_task_blueprint_identity();