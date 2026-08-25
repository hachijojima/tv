create table public.daily_presence (
  day date primary key,
  count bigint not null default 0 check (count >= 0)
);

alter table public.daily_presence enable row level security;
revoke all on public.daily_presence from anon, authenticated;

create function public.presence_total() returns bigint language sql stable security definer set search_path=public as $$
  select coalesce(sum(count), 0)::bigint
  from public.daily_presence
  where day between ((now() at time zone 'Asia/Tokyo')::date - 27) and (now() at time zone 'Asia/Tokyo')::date
$$;

create function public.increment_presence() returns bigint language plpgsql security definer set search_path=public as $$
declare today_jst date := (now() at time zone 'Asia/Tokyo')::date;
begin
  insert into public.daily_presence(day, count) values (today_jst, 1)
  on conflict (day) do update set count = public.daily_presence.count + 1;
  return public.presence_total();
end;
$$;

revoke all on function public.presence_total() from public;
revoke all on function public.increment_presence() from public;
grant execute on function public.presence_total() to anon, authenticated;
grant execute on function public.increment_presence() to anon, authenticated;
