-- Phase 4B: learners may read approved blueprints for active projects only.

drop policy if exists project_blueprints_select_allowed on public.project_blueprints;
create policy project_blueprints_select_allowed
on public.project_blueprints for select to authenticated
using (
  public.can_manage_project(project_id)
  or (status = 'approved' and public.can_view_project(project_id))
);