-- Add the daily song without regenerating the currently published schedule.
-- The existing 03:00 JST cron will select songs from the new Library family.
alter table public.content_items drop constraint content_items_family_code_check;
alter table public.content_items add constraint content_items_family_code_check
  check (family_code in ('music','hachijo_taiko','power_push','sports','hachijo_picks','five_o_clock_song'));
alter table public.content_items add constraint five_o_clock_song_duration_check
  check (family_code <> 'five_o_clock_song' or duration_secs <= 600);
alter table public.schedule_items drop constraint schedule_items_family_code_check;
alter table public.schedule_items add constraint schedule_items_family_code_check
  check (family_code in ('music','hachijo_taiko','power_push','sports','hachijo_picks','island_view','tokyo_relay','five_o_clock_song'));

-- Patch only the relevant branches, preserving previously deployed changes.
do $$
declare
  function_sql text;
  old_fragment text;
  new_fragment text;
begin
  select pg_get_functiondef('public.regenerate_schedule(timestamptz)'::regprocedure) into function_sql;

  old_fragment := $old$  current_family text$old$;
  new_fragment := $new$  song_start timestamptz; song_pos integer := 1;
  current_family text$new$;
  if position(old_fragment in function_sql) = 0 then
    raise exception 'five o clock song scheduler patch target missing';
  end if;
  function_sql := replace(function_sql, old_fragment, new_fragment);

  old_fragment := $old$  insert into fmh_queue select 'music',$old$;
  new_fragment := $new$  insert into fmh_queue select 'five_o_clock_song', row_number() over (order by random()), youtube_id, title, duration_secs, null from public.content_items where family_code='five_o_clock_song';
  insert into fmh_queue select 'music',$new$;
  if position(old_fragment in function_sql) = 0 then
    raise exception 'five o clock song scheduler patch target missing';
  end if;
  function_sql := replace(function_sql, old_fragment, new_fragment);

  old_fragment := $old$    relay_start :=$old$;
  new_fragment := $new$    song_start := public.fmh_jst_at(local_day, 61200);
    -- Reserve 17:00–17:10 only for deciding whether SUNSET runs.
    if sunset_start < song_start + interval '10 minutes' and sunset_end > song_start then
      sunset_start := null;
      sunset_end := null;
    end if;
    relay_start :=$new$;
  if position(old_fragment in function_sql) = 0 then
    raise exception 'five o clock song scheduler patch target missing';
  end if;
  function_sql := replace(function_sql, old_fragment, new_fragment);

  old_fragment := $old$    if current_family='music' then$old$;
  new_fragment := $new$    if cursor_at = song_start then
      select * into selected from fmh_queue where family_code='five_o_clock_song' order by ord offset song_pos-1 limit 1;
      if not found then
        update fmh_queue set ord=floor(random()*1000000) where family_code='five_o_clock_song';
        song_pos := 1;
        select * into selected from fmh_queue where family_code='five_o_clock_song' order by ord limit 1;
      end if;
      if not found then raise exception '5時のうたのLibraryに曲を追加してください'; end if;
      song_pos := song_pos + 1;
      natural_end := cursor_at + make_interval(secs=>selected.duration_secs);
      insert into public.schedule_items(family_code,youtube_id,title,start_at,end_at)
        values ('five_o_clock_song',selected.youtube_id,'5時のうた',cursor_at,natural_end);
      cursor_at := natural_end;
      continue;
    end if;
    if current_family='music' then$new$;
  if position(old_fragment in function_sql) = 0 then
    raise exception 'five o clock song scheduler patch target missing';
  end if;
  function_sql := replace(function_sql, old_fragment, new_fragment);

  old_fragment := $old$    next_special := least($old$;
  new_fragment := $new$    next_special := least(case when song_start > cursor_at then song_start else 'infinity'::timestamptz end, $new$;
  if position(old_fragment in function_sql) = 0 then
    raise exception 'five o clock song scheduler patch target missing';
  end if;
  function_sql := replace(function_sql, old_fragment, new_fragment);

  execute function_sql;
end;
$$;
