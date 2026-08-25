-- Restore the audible TOKYO RELAY feed for the overnight shutdown only.
-- The 22:30 DEPARTURE slot and all DAWN / SUNSET rows are left untouched.
do $$
declare
  function_sql text;
begin
  select pg_get_functiondef('public.regenerate_schedule(timestamptz)'::regprocedure)
    into function_sql;

  function_sql := replace(
    function_sql,
    '''island_view'',''ciBuVo8Sozk'',''放送休止'',cursor_at,dawn_start',
    '''tokyo_relay'',''_k-5U7IeK8g'',null,cursor_at,dawn_start'
  );

  if position('''tokyo_relay'',''_k-5U7IeK8g'',null,cursor_at,dawn_start' in function_sql) = 0 then
    raise exception 'night shutdown scheduler restore failed';
  end if;

  execute function_sql;
end;
$$;

update public.schedule_items
set
  family_code = 'tokyo_relay',
  youtube_id = '_k-5U7IeK8g',
  title = null,
  start_offset_seconds = null
where family_code = 'island_view'
  and youtube_id = 'ciBuVo8Sozk'
  and title = '放送休止';
