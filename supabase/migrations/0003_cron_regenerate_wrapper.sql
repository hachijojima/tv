create or replace function public.cron_regenerate_schedule() returns void language plpgsql security definer set search_path=public as $$
declare admin_id uuid;
begin
  select id into admin_id from public.profiles where is_admin order by created_at limit 1;
  if admin_id is null then raise exception 'no administrator profile'; end if;
  perform set_config('request.jwt.claim.sub', admin_id::text, true);
  perform public.regenerate_schedule(now());
end;
$$;
revoke all on function public.cron_regenerate_schedule() from public, anon, authenticated;
select cron.unschedule(jobid) from cron.job where jobname='fmhachijo-regenerate-0300';
select cron.schedule('fmhachijo-regenerate-0300', '0 18 * * *', $$select public.cron_regenerate_schedule();$$);
