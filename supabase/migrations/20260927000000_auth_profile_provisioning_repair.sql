create or replace function public.provision_auth_user_profile(
  target_user_id uuid,
  requested_role text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  auth_identity auth.users%rowtype;
  safe_role text;
begin
  if requested_role is null or requested_role not in ('learner', 'business') then
    raise exception 'Only learner and business profiles can be provisioned';
  end if;

  select * into auth_identity
  from auth.users
  where id = target_user_id;

  if not found then
    raise exception 'Auth user does not exist';
  end if;

  safe_role := requested_role;

  insert into public.users (id, email, display_name, role)
  values (
    auth_identity.id,
    auth_identity.email,
    nullif(auth_identity.raw_user_meta_data ->> 'display_name', ''),
    safe_role
  )
  on conflict (id) do update
    set email = excluded.email,
        updated_at = pg_catalog.timezone('utc', pg_catalog.now());

  return auth_identity.id;
end;
$$;

revoke all on function public.provision_auth_user_profile(uuid, text) from public, anon, authenticated;
grant execute on function public.provision_auth_user_profile(uuid, text) to service_role;

create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  safe_role text := case
    when new.raw_user_meta_data ->> 'role' = 'business' then 'business'
    else 'learner'
  end;
begin
  perform public.provision_auth_user_profile(new.id, safe_role);
  return new;
end;
$$;