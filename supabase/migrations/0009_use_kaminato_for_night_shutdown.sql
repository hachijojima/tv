-- Keep the 22:30 TOKYO RELAY untouched.  Only the post-NIGHT PROGRAM
-- overnight relay becomes ISLAND VIEW with the Kaminato live camera.
do $$
declare
  function_sql text;
begin
  select pg_get_functiondef('public.regenerate_schedule(timestamptz)'::regprocedure)
    into function_sql;

  function_sql := replace(
    function_sql,
    '''tokyo_relay'',''_k-5U7IeK8g'',null,cursor_at,dawn_start',
    '''island_view'',''ciBuVo8Sozk'',''放送休止'',cursor_at,dawn_start'
  );

  if position('''island_view'',''ciBuVo8Sozk'',''放送休止'',cursor_at,dawn_start' in function_sql) = 0 then
    raise exception 'night shutdown scheduler update failed';
  end if;

  execute function_sql;
end;
$$;
