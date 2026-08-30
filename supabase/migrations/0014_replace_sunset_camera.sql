-- Replace only the SUNSET ISLAND VIEW feed.  Do not regenerate or reset
-- the existing schedule: future SUNSET rows retain their original times.
do $$
declare
  function_sql text;
begin
  select pg_get_functiondef('public.regenerate_schedule(timestamptz)'::regprocedure)
    into function_sql;

  function_sql := replace(
    function_sql,
    '''island_view'',''7IygrRRgXYQ'',''SUNSET'',cursor_at,sunset_end',
    '''island_view'',''f8sGmJ67Z04'',''SUNSET'',cursor_at,sunset_end'
  );

  if position('''island_view'',''f8sGmJ67Z04'',''SUNSET'',cursor_at,sunset_end' in function_sql) = 0 then
    raise exception 'sunset camera scheduler update failed';
  end if;

  execute function_sql;
end;
$$;

update public.schedule_items
set youtube_id = 'f8sGmJ67Z04'
where family_code = 'island_view'
  and title = 'SUNSET'
  and youtube_id = '7IygrRRgXYQ'
  and start_at > now();
