-- FM八丈島 TV β3 CLEAN REBUILD.  Only Auth itself and the admin profile survive.
drop trigger if exists on_auth_user_created on auth.users;
drop function if exists public.handle_new_user();
drop table if exists public.schedule_items cascade;
drop table if exists public.daily_schedules cascade;
drop table if exists public.playout_history cascade;
drop table if exists public.archive_sources cascade;
drop table if exists public.content_items cascade;
drop table if exists public.program_families cascade;
drop function if exists public.is_admin();

create table if not exists public.profiles (
  id uuid primary key references auth.users on delete cascade,
  is_admin boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.content_items (
  id uuid primary key default gen_random_uuid(),
  family_code text not null check (family_code in ('music','hachijo_taiko','power_push','sports','hachijo_picks')),
  youtube_id text not null unique check (youtube_id ~ '^[A-Za-z0-9_-]{11}$'),
  title text not null,
  channel_name text,
  duration_secs integer not null check (duration_secs > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.schedule_items (
  id uuid primary key default gen_random_uuid(),
  family_code text not null check (family_code in ('music','hachijo_taiko','power_push','sports','hachijo_picks','island_view','tokyo_relay')),
  youtube_id text not null check (youtube_id ~ '^[A-Za-z0-9_-]{11}$'),
  title text,
  start_at timestamptz not null,
  end_at timestamptz not null check (end_at > start_at),
  start_offset_seconds integer check (start_offset_seconds is null or start_offset_seconds >= 0),
  created_at timestamptz not null default now()
);
create index schedule_items_current_idx on public.schedule_items (start_at, end_at);
create index schedule_items_next_idx on public.schedule_items (end_at, start_at);
create index content_items_family_idx on public.content_items (family_code);

create or replace function public.handle_new_user() returns trigger language plpgsql security definer set search_path=public as $$
begin
  insert into public.profiles(id) values (new.id) on conflict do nothing;
  return new;
end;
$$;
create trigger on_auth_user_created after insert on auth.users for each row execute procedure public.handle_new_user();

create or replace function public.is_admin() returns boolean language sql stable security definer set search_path=public as $$
  select exists(select 1 from public.profiles where id = auth.uid() and is_admin)
$$;

-- Hachijojima solar approximation, expressed as a JST timestamp.  The schedule
-- only uses it for the fixed ±10 minute ISLAND VIEW windows.
create or replace function public.fmh_solar_seconds(local_day date, rising boolean) returns integer language plpgsql immutable as $$
declare n integer; seasonal double precision;
begin
  n := extract(doy from local_day)::integer;
  seasonal := sin((n - 80) * pi() * 2 / 365.0);
  return round(case when rising then 21600 - seasonal * 3300 else 64800 + seasonal * 3300 end)::integer;
end;
$$;
create or replace function public.fmh_jst_at(local_day date, seconds_after_midnight integer) returns timestamptz language sql immutable as $$
  select (local_day::timestamp + make_interval(secs => seconds_after_midnight)) at time zone 'Asia/Tokyo'
$$;

create or replace function public.regenerate_schedule(replace_from timestamptz default now()) returns void language plpgsql security definer set search_path=public as $$
declare
  cursor_at timestamptz := replace_from;
  horizon timestamptz := replace_from + interval '72 hours';
  local_day date; dawn_start timestamptz; dawn_end timestamptz; sunset_start timestamptz; sunset_end timestamptz; relay_start timestamptz; relay_end timestamptz; next_special timestamptz;
  current_family text := 'music'; selected record; natural_end timestamptz; night_program boolean := false; force_night_relay boolean := false;
  music_pos integer := 1; taiko_pos integer := 1; power_pos integer := 1; sports_pos integer := 1; picks_pos integer := 1;
begin
  if not public.is_admin() then raise exception 'admin required'; end if;
  create temporary table if not exists fmh_queue (family_code text, ord integer, youtube_id text, title text, duration_secs integer, start_offset_seconds integer) on commit drop;
  truncate fmh_queue;
  insert into fmh_queue select 'music', row_number() over (order by random()), youtube_id, title, duration_secs, null from public.content_items where family_code='music';
  insert into fmh_queue select 'hachijo_picks', row_number() over (order by random()), youtube_id, title, duration_secs, null from public.content_items where family_code='hachijo_picks';
  insert into fmh_queue select 'power_push', row_number() over (order by random()), youtube_id, title, duration_secs, null from public.content_items where family_code='power_push';
  insert into fmh_queue select 'hachijo_taiko', row_number() over (order by random()), youtube_id, title, 3600, duration_secs - part * 3600 from public.content_items cross join lateral generate_series(1, floor(duration_secs / 3600)::integer) part where family_code='hachijo_taiko';
  insert into fmh_queue select 'sports', row_number() over (order by random()), youtube_id, title, 1800, (part - 1) * 1800 from public.content_items cross join lateral generate_series(1, floor(duration_secs / 1800)::integer) part where family_code='sports';
  if not exists(select 1 from fmh_queue where family_code='music') or not exists(select 1 from fmh_queue where family_code='hachijo_picks') or not exists(select 1 from fmh_queue where family_code='hachijo_taiko') or not exists(select 1 from fmh_queue where family_code='power_push') or not exists(select 1 from fmh_queue where family_code='sports') then raise exception 'all five library families require content'; end if;
  update public.schedule_items set end_at=replace_from where start_at < replace_from and end_at > replace_from;
  delete from public.schedule_items where start_at >= replace_from;
  while cursor_at < horizon loop
    local_day := (cursor_at at time zone 'Asia/Tokyo')::date;
    dawn_start := public.fmh_jst_at(local_day, public.fmh_solar_seconds(local_day, true) - 600);
    dawn_end := dawn_start + interval '20 minutes';
    sunset_start := public.fmh_jst_at(local_day, public.fmh_solar_seconds(local_day, false) - 600);
    sunset_end := sunset_start + interval '20 minutes';
    relay_start := public.fmh_jst_at(local_day, 81000);
    relay_end := relay_start + interval '20 minutes';
    if cursor_at >= dawn_start and cursor_at < dawn_end then
      insert into public.schedule_items(family_code,youtube_id,title,start_at,end_at) values ('island_view','SilNYdV2HNs','DAWN',cursor_at,dawn_end); cursor_at := dawn_end; current_family := 'music'; continue;
    end if;
    if cursor_at >= sunset_start and cursor_at < sunset_end then
      insert into public.schedule_items(family_code,youtube_id,title,start_at,end_at) values ('island_view','7IygrRRgXYQ','SUNSET',cursor_at,sunset_end); cursor_at := sunset_end; continue;
    end if;
    if force_night_relay or ((cursor_at at time zone 'Asia/Tokyo')::time >= time '22:30' and cursor_at > relay_end) or ((cursor_at at time zone 'Asia/Tokyo')::time < (dawn_start at time zone 'Asia/Tokyo')::time) then
      if cursor_at >= dawn_end then dawn_start := public.fmh_jst_at(local_day + 1, public.fmh_solar_seconds(local_day + 1, true) - 600); end if;
      insert into public.schedule_items(family_code,youtube_id,title,start_at,end_at) values ('tokyo_relay','_k-5U7IeK8g',null,cursor_at,dawn_start); cursor_at := dawn_start; force_night_relay := false; continue;
    end if;
    if cursor_at >= relay_start and cursor_at < relay_end then
      insert into public.schedule_items(family_code,youtube_id,title,start_at,end_at) values ('tokyo_relay','_k-5U7IeK8g',null,cursor_at,relay_end); cursor_at := relay_end; night_program := true; continue;
    end if;
    if current_family='music' then select * into selected from fmh_queue where family_code='music' order by ord offset music_pos-1 limit 1; if not found then update fmh_queue set ord=floor(random()*1000000) where family_code='music'; music_pos:=1; select * into selected from fmh_queue where family_code='music' order by ord limit 1; end if; music_pos:=music_pos+1;
    elsif current_family='hachijo_taiko' then select * into selected from fmh_queue where family_code='hachijo_taiko' order by ord offset taiko_pos-1 limit 1; if not found then update fmh_queue set ord=floor(random()*1000000) where family_code='hachijo_taiko'; taiko_pos:=1; select * into selected from fmh_queue where family_code='hachijo_taiko' order by ord limit 1; end if; taiko_pos:=taiko_pos+1;
    elsif current_family='power_push' then select * into selected from fmh_queue where family_code='power_push' order by ord offset power_pos-1 limit 1; if not found then update fmh_queue set ord=floor(random()*1000000) where family_code='power_push'; power_pos:=1; select * into selected from fmh_queue where family_code='power_push' order by ord limit 1; end if; power_pos:=power_pos+1;
    elsif current_family='sports' then select * into selected from fmh_queue where family_code='sports' order by ord offset sports_pos-1 limit 1; if not found then update fmh_queue set ord=floor(random()*1000000) where family_code='sports'; sports_pos:=1; select * into selected from fmh_queue where family_code='sports' order by ord limit 1; end if; sports_pos:=sports_pos+1;
    else select * into selected from fmh_queue where family_code='hachijo_picks' order by ord offset picks_pos-1 limit 1; if not found then update fmh_queue set ord=floor(random()*1000000) where family_code='hachijo_picks'; picks_pos:=1; select * into selected from fmh_queue where family_code='hachijo_picks' order by ord limit 1; end if; picks_pos:=picks_pos+1; end if;
    natural_end := cursor_at + make_interval(secs=>selected.duration_secs);
    next_special := least(case when dawn_start > cursor_at then dawn_start else 'infinity'::timestamptz end, case when sunset_start > cursor_at then sunset_start else 'infinity'::timestamptz end, case when relay_start > cursor_at then relay_start else 'infinity'::timestamptz end);
    if next_special = 'infinity'::timestamptz then next_special := public.fmh_jst_at(local_day + 1, public.fmh_solar_seconds(local_day + 1, true) - 600); end if;
    insert into public.schedule_items(family_code,youtube_id,title,start_at,end_at,start_offset_seconds) values (current_family,selected.youtube_id,selected.title,cursor_at,least(natural_end,next_special),selected.start_offset_seconds);
    cursor_at := least(natural_end,next_special);
    if night_program then force_night_relay:=true; night_program:=false; else current_family := case current_family when 'music' then 'hachijo_taiko' when 'hachijo_taiko' then 'power_push' when 'power_push' then 'sports' when 'sports' then 'hachijo_picks' else 'music' end; end if;
  end loop;
end;
$$;

alter table public.profiles enable row level security;
alter table public.content_items enable row level security;
alter table public.schedule_items enable row level security;
drop policy if exists "profile self read" on public.profiles;
create policy "profile self read" on public.profiles for select using (id=auth.uid());
create policy "public read schedule" on public.schedule_items for select using (true);
create policy "admin content" on public.content_items for all using (public.is_admin()) with check (public.is_admin());
create policy "admin schedule" on public.schedule_items for all using (public.is_admin()) with check (public.is_admin());
grant usage on schema public to anon, authenticated;
revoke all on public.content_items, public.schedule_items, public.profiles from anon, authenticated;
grant select on public.schedule_items to anon;
grant select, insert, update, delete on public.content_items, public.schedule_items to authenticated;
grant select on public.profiles to authenticated;
revoke all on function public.is_admin() from public;
grant execute on function public.is_admin() to anon, authenticated;
grant execute on function public.regenerate_schedule(timestamptz) to authenticated;
revoke all on function public.handle_new_user() from public, anon, authenticated;

create extension if not exists pg_cron;
select cron.unschedule(jobid) from cron.job where jobname='fmhachijo-regenerate-0300';
select cron.schedule('fmhachijo-regenerate-0300', '0 18 * * *', $$select public.regenerate_schedule(now());$$);
