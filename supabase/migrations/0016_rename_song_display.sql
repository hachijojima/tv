-- Rename display text only; retain every scheduling rule and existing time.
do $$
declare function_sql text;
begin
  select pg_get_functiondef('public.regenerate_schedule(timestamptz)'::regprocedure) into function_sql;
  if position('5時のうた' in function_sql) = 0 then
    raise exception 'song display name replacement target missing';
  end if;
  execute replace(function_sql, '5時のうた', 'ごじのうた');
end;
$$;

update public.schedule_items
set title = 'ごじのうた'
where family_code = 'five_o_clock_song' and title = '5時のうた';
