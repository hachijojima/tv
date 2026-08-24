alter table public.content_items drop constraint content_items_family_code_check;
alter table public.content_items add constraint content_items_family_code_check check (family_code in ('music','hachijo_taiko','power_push','sports','hachijo_picks'));
alter table public.schedule_items drop constraint schedule_items_family_code_check;
alter table public.schedule_items add constraint schedule_items_family_code_check check (family_code in ('music','hachijo_taiko','power_push','sports','hachijo_picks','island_view','tokyo_relay'));

do $$
declare function_sql text;
begin
  select pg_get_functiondef('public.regenerate_schedule(timestamptz)'::regprocedure) into function_sql;
  function_sql := replace(function_sql, 'duration_seconds', 'duration_secs');
  function_sql := replace(function_sql,
    'music_pos integer := 1; taiko_pos integer := 1; sports_pos integer := 1; picks_pos integer := 1;',
    'music_pos integer := 1; taiko_pos integer := 1; power_pos integer := 1; sports_pos integer := 1; picks_pos integer := 1;');
  function_sql := replace(function_sql,
    'insert into fmh_queue select ''hachijo_picks'', row_number() over (order by random()), youtube_id, title, duration_secs, null from public.content_items where family_code=''hachijo_picks'';',
    'insert into fmh_queue select ''hachijo_picks'', row_number() over (order by random()), youtube_id, title, duration_secs, null from public.content_items where family_code=''hachijo_picks'';' || chr(10) ||
    '  insert into fmh_queue select ''power_push'', row_number() over (order by random()), youtube_id, title, duration_secs, null from public.content_items where family_code=''power_push'';');
  function_sql := replace(function_sql,
    'or not exists(select 1 from fmh_queue where family_code=''sports'') then raise exception ''all four library families require content'';',
    'or not exists(select 1 from fmh_queue where family_code=''power_push'') or not exists(select 1 from fmh_queue where family_code=''sports'') then raise exception ''all five library families require content'';');
  function_sql := replace(function_sql,
    'elsif current_family=''sports'' then select * into selected from fmh_queue where family_code=''sports''',
    'elsif current_family=''power_push'' then select * into selected from fmh_queue where family_code=''power_push'' order by ord offset power_pos-1 limit 1; if not found then update fmh_queue set ord=floor(random()*1000000) where family_code=''power_push''; power_pos:=1; select * into selected from fmh_queue where family_code=''power_push'' order by ord limit 1; end if; power_pos:=power_pos+1;' || chr(10) ||
    '    elsif current_family=''sports'' then select * into selected from fmh_queue where family_code=''sports''');
  function_sql := replace(function_sql,
    'when ''hachijo_taiko'' then ''sports'' when ''sports'' then ''hachijo_picks''',
    'when ''hachijo_taiko'' then ''power_push'' when ''power_push'' then ''sports'' when ''sports'' then ''hachijo_picks''');
  if position('family_code=''power_push''' in function_sql) = 0 or position('duration_seconds' in function_sql) > 0 then
    raise exception 'power push function upgrade failed';
  end if;
  execute function_sql;
end;
$$;
