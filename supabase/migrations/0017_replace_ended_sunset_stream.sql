-- Aigae's old stream ended on 2026-11-06. Use the current Yaene port feed.
-- Preserve all published programme times and the normal rotation.
begin;

do $$
declare
  function_sql text;
begin
  select pg_get_functiondef('public.regenerate_schedule(timestamptz)'::regprocedure)
    into function_sql;
  function_sql := replace(
    function_sql,
    '''island_view'',''f8sGmJ67Z04'',''SUNSET'',cursor_at,sunset_end',
    '''island_view'',''SWjwYvrGQYc'',''SUNSET'',cursor_at,sunset_end'
  );
  if position('''island_view'',''SWjwYvrGQYc'',''SUNSET'',cursor_at,sunset_end' in function_sql) = 0 then
    raise exception 'SUNSET scheduler patch target missing';
  end if;
  execute function_sql;
end;
$$;

update public.schedule_items
set youtube_id = 'SWjwYvrGQYc'
where family_code = 'island_view'
  and title = 'SUNSET'
  and youtube_id = 'f8sGmJ67Z04'
  and end_at > now();

commit;
