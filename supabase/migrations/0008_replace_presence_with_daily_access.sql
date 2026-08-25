drop function if exists public.increment_presence();
drop function if exists public.presence_total();
drop table if exists public.daily_presence;

create table public.daily_access (
  day date primary key,
  count bigint not null default 0 check (count >= 0)
);

alter table public.daily_access enable row level security;
revoke all on public.daily_access from anon, authenticated;

create function public.access_total() returns bigint language sql stable security definer set search_path=public as $$
  select coalesce(sum(count), 0)::bigint
  from public.daily_access
  where day between ((now() at time zone 'Asia/Tokyo')::date - 6) and (now() at time zone 'Asia/Tokyo')::date
$$;

create function public.record_access() returns bigint language plpgsql security definer set search_path=public as $$
declare today_jst date := (now() at time zone 'Asia/Tokyo')::date;
begin
  insert into public.daily_access(day, count) values (today_jst, 1)
  on conflict (day) do update set count = public.daily_access.count + 1;
  return public.access_total();
end;
$$;

revoke all on function public.access_total() from public;
revoke all on function public.record_access() from public;
grant execute on function public.access_total() to anon, authenticated;
grant execute on function public.record_access() to anon, authenticated;
