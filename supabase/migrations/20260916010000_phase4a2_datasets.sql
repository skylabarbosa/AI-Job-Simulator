-- Phase 4A.2: private CSV dataset storage and metadata fields.

alter table public.datasets
  add column file_size bigint,
  add column row_count integer,
  add column column_count integer;

insert into storage.buckets (id, name, public)
values ('project-datasets', 'project-datasets', false)
on conflict (id) do update set public = false;

create policy project_datasets_select
on storage.objects for select to authenticated
using (
  bucket_id = 'project-datasets'
  and exists (
    select 1
    from public.projects p
    where p.id::text = (storage.foldername(name))[1]
      and (p.created_by = auth.uid() or public.current_app_role() = 'admin')
  )
);

create policy project_datasets_insert
on storage.objects for insert to authenticated
with check (
  bucket_id = 'project-datasets'
  and exists (
    select 1
    from public.projects p
    where p.id::text = (storage.foldername(name))[1]
      and (p.created_by = auth.uid() or public.current_app_role() = 'admin')
  )
);

create policy project_datasets_delete
on storage.objects for delete to authenticated
using (
  bucket_id = 'project-datasets'
  and exists (
    select 1
    from public.projects p
    where p.id::text = (storage.foldername(name))[1]
      and (p.created_by = auth.uid() or public.current_app_role() = 'admin')
  )
);
