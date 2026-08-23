begin;
set local role authenticated;
select set_config('request.jwt.claim.sub','9af43f7e-24ce-4c7d-8f99-dc0701a0abee',true);
insert into public.content_items(family_code,youtube_id,source_url,source_title,duration_seconds,content_type,atomic,enabled,verified) values ('long_play','ZZZZZZZZZZZ','https://example.invalid/admin-probe','admin RLS probe',60,'vod',true,false,false);
update public.content_items set public_title='admin RLS probe updated' where youtube_id='ZZZZZZZZZZZ';
delete from public.content_items where youtube_id='ZZZZZZZZZZZ';
rollback;
