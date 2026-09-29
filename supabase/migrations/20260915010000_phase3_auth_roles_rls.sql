-- Phase 3: Supabase Auth profiles, application roles, and least-privilege RLS.
-- Public signup may create learner or business profiles, never admin profiles.

alter table public.users
  add column role text not null default 'learner'
    check (role in ('learner', 'business', 'admin'));

alter table public.users
  add constraint users_auth_id_fk
  foreign key (id) references auth.users(id) on delete cascade;

create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  requested_role text := new.raw_user_meta_data ->> 'role';
  safe_role text := case
    when requested_role = 'business' then 'business'
    else 'learner'
  end;
begin
  insert into public.users (id, email, display_name, role)
  values (
    new.id,
    new.email,
    nullif(new.raw_user_meta_data ->> 'display_name', ''),
    safe_role
  )
  on conflict (id) do update
    set email = excluded.email,
        updated_at = timezone('utc', now());

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_auth_user();

create or replace function public.current_app_role()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select role from public.users where id = auth.uid();
$$;

create or replace function public.can_view_project(target_project_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.projects p
    where p.id = target_project_id
      and (
        public.current_app_role() = 'admin'
        or p.created_by = auth.uid()
        or p.status = 'active'
      )
  );
$$;

create or replace function public.can_manage_project(target_project_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.projects p
    where p.id = target_project_id
      and (
        public.current_app_role() = 'admin'
        or (public.current_app_role() = 'business' and p.created_by = auth.uid())
      )
  );
$$;

revoke all on function public.current_app_role() from public;
revoke all on function public.can_view_project(uuid) from public;
revoke all on function public.can_manage_project(uuid) from public;
grant execute on function public.current_app_role() to authenticated;
grant execute on function public.can_view_project(uuid) to authenticated;
grant execute on function public.can_manage_project(uuid) to authenticated;

create policy users_select_own_or_admin
on public.users for select to authenticated
using (id = auth.uid() or public.current_app_role() = 'admin');

create policy users_update_own_or_admin
on public.users for update to authenticated
using (id = auth.uid() or public.current_app_role() = 'admin')
with check (
  public.current_app_role() = 'admin'
  or (id = auth.uid() and role = public.current_app_role())
);

create policy projects_select_allowed
on public.projects for select to authenticated
using (
  public.current_app_role() = 'admin'
  or created_by = auth.uid()
  or (public.current_app_role() = 'learner' and status = 'active')
);

create policy projects_insert_business_or_admin
on public.projects for insert to authenticated
with check (
  public.current_app_role() = 'admin'
  or (public.current_app_role() = 'business' and created_by = auth.uid())
);

create policy projects_update_owner_or_admin
on public.projects for update to authenticated
using (public.can_manage_project(id))
with check (
  public.current_app_role() = 'admin'
  or (public.current_app_role() = 'business' and created_by = auth.uid())
);

create policy projects_delete_owner_or_admin
on public.projects for delete to authenticated
using (public.can_manage_project(id));

create policy datasets_select_allowed
on public.datasets for select to authenticated
using (public.can_view_project(project_id));

create policy datasets_insert_owner_or_admin
on public.datasets for insert to authenticated
with check (public.can_manage_project(project_id));

create policy datasets_update_owner_or_admin
on public.datasets for update to authenticated
using (public.can_manage_project(project_id))
with check (public.can_manage_project(project_id));

create policy datasets_delete_owner_or_admin
on public.datasets for delete to authenticated
using (public.can_manage_project(project_id));

create policy modules_select_allowed
on public.modules for select to authenticated
using (public.can_view_project(project_id));

create policy modules_insert_owner_or_admin
on public.modules for insert to authenticated
with check (public.can_manage_project(project_id));

create policy modules_update_owner_or_admin
on public.modules for update to authenticated
using (public.can_manage_project(project_id))
with check (public.can_manage_project(project_id));

create policy modules_delete_owner_or_admin
on public.modules for delete to authenticated
using (public.can_manage_project(project_id));

create policy competencies_select_allowed
on public.competencies for select to authenticated
using (exists (
  select 1 from public.modules m
  where m.id = module_id and public.can_view_project(m.project_id)
));

create policy competencies_insert_owner_or_admin
on public.competencies for insert to authenticated
with check (exists (
  select 1 from public.modules m
  where m.id = module_id and public.can_manage_project(m.project_id)
));

create policy competencies_update_owner_or_admin
on public.competencies for update to authenticated
using (exists (
  select 1 from public.modules m
  where m.id = module_id and public.can_manage_project(m.project_id)
))
with check (exists (
  select 1 from public.modules m
  where m.id = module_id and public.can_manage_project(m.project_id)
));

create policy competencies_delete_owner_or_admin
on public.competencies for delete to authenticated
using (exists (
  select 1 from public.modules m
  where m.id = module_id and public.can_manage_project(m.project_id)
));

create policy concepts_select_allowed
on public.concepts for select to authenticated
using (exists (
  select 1
  from public.competencies c
  join public.modules m on m.id = c.module_id
  where c.id = competency_id and public.can_view_project(m.project_id)
));

create policy concepts_insert_owner_or_admin
on public.concepts for insert to authenticated
with check (exists (
  select 1
  from public.competencies c
  join public.modules m on m.id = c.module_id
  where c.id = competency_id and public.can_manage_project(m.project_id)
));

create policy concepts_update_owner_or_admin
on public.concepts for update to authenticated
using (exists (
  select 1
  from public.competencies c
  join public.modules m on m.id = c.module_id
  where c.id = competency_id and public.can_manage_project(m.project_id)
))
with check (exists (
  select 1
  from public.competencies c
  join public.modules m on m.id = c.module_id
  where c.id = competency_id and public.can_manage_project(m.project_id)
));

create policy concepts_delete_owner_or_admin
on public.concepts for delete to authenticated
using (exists (
  select 1
  from public.competencies c
  join public.modules m on m.id = c.module_id
  where c.id = competency_id and public.can_manage_project(m.project_id)
));

create policy tasks_select_allowed
on public.tasks for select to authenticated
using (public.can_view_project(project_id));

create policy tasks_insert_owner_or_admin
on public.tasks for insert to authenticated
with check (public.can_manage_project(project_id));

create policy tasks_update_owner_or_admin
on public.tasks for update to authenticated
using (public.can_manage_project(project_id))
with check (public.can_manage_project(project_id));

create policy tasks_delete_owner_or_admin
on public.tasks for delete to authenticated
using (public.can_manage_project(project_id));

create policy task_competencies_select_allowed
on public.task_competencies for select to authenticated
using (exists (
  select 1 from public.tasks t
  where t.id = task_id and public.can_view_project(t.project_id)
));

create policy task_competencies_manage_owner_or_admin
on public.task_competencies for all to authenticated
using (exists (
  select 1 from public.tasks t
  where t.id = task_id and public.can_manage_project(t.project_id)
))
with check (exists (
  select 1 from public.tasks t
  where t.id = task_id and public.can_manage_project(t.project_id)
));

create policy task_concepts_select_allowed
on public.task_concepts for select to authenticated
using (exists (
  select 1 from public.tasks t
  where t.id = task_id and public.can_view_project(t.project_id)
));

create policy task_concepts_manage_owner_or_admin
on public.task_concepts for all to authenticated
using (exists (
  select 1 from public.tasks t
  where t.id = task_id and public.can_manage_project(t.project_id)
))
with check (exists (
  select 1 from public.tasks t
  where t.id = task_id and public.can_manage_project(t.project_id)
));

create policy rubrics_select_allowed
on public.rubrics for select to authenticated
using (exists (
  select 1 from public.tasks t
  where t.id = task_id and public.can_view_project(t.project_id)
));

create policy rubrics_manage_owner_or_admin
on public.rubrics for all to authenticated
using (exists (
  select 1 from public.tasks t
  where t.id = task_id and public.can_manage_project(t.project_id)
))
with check (exists (
  select 1 from public.tasks t
  where t.id = task_id and public.can_manage_project(t.project_id)
));

create policy simulations_select_own_or_admin
on public.simulations for select to authenticated
using (learner_id = auth.uid() or public.current_app_role() = 'admin');

create policy simulations_insert_own_or_admin
on public.simulations for insert to authenticated
with check (
  public.current_app_role() = 'admin'
  or (public.current_app_role() = 'learner' and learner_id = auth.uid())
);

create policy simulations_update_own_or_admin
on public.simulations for update to authenticated
using (learner_id = auth.uid() or public.current_app_role() = 'admin')
with check (learner_id = auth.uid() or public.current_app_role() = 'admin');

create policy simulations_delete_own_or_admin
on public.simulations for delete to authenticated
using (learner_id = auth.uid() or public.current_app_role() = 'admin');

create policy submissions_select_own_or_admin
on public.submissions for select to authenticated
using (learner_id = auth.uid() or public.current_app_role() = 'admin');

create policy submissions_insert_own_or_admin
on public.submissions for insert to authenticated
with check (
  public.current_app_role() = 'admin'
  or (
    public.current_app_role() = 'learner'
    and learner_id = auth.uid()
    and exists (
      select 1 from public.simulations s
      where s.id = simulation_id and s.learner_id = auth.uid()
    )
  )
);

create policy submissions_update_own_or_admin
on public.submissions for update to authenticated
using (learner_id = auth.uid() or public.current_app_role() = 'admin')
with check (learner_id = auth.uid() or public.current_app_role() = 'admin');

create policy submissions_delete_own_or_admin
on public.submissions for delete to authenticated
using (learner_id = auth.uid() or public.current_app_role() = 'admin');

create policy evaluations_select_submission_owner_or_admin
on public.evaluations for select to authenticated
using (
  public.current_app_role() = 'admin'
  or exists (
    select 1
    from public.submissions s
    where s.id = submission_id and s.learner_id = auth.uid()
  )
);

create policy evaluations_manage_admin
on public.evaluations for all to authenticated
using (public.current_app_role() = 'admin')
with check (public.current_app_role() = 'admin');

create policy user_skills_select_own_or_admin
on public.user_skills for select to authenticated
using (learner_id = auth.uid() or public.current_app_role() = 'admin');

create policy user_skills_manage_admin
on public.user_skills for all to authenticated
using (public.current_app_role() = 'admin')
with check (public.current_app_role() = 'admin');

comment on column public.users.role is 'Application role: learner, business, or admin. Public signup cannot create admin profiles.';
comment on function public.current_app_role() is 'Returns the authenticated application role for RLS decisions.';
