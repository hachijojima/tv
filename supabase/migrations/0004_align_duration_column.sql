-- The clean beta3 contract names this source duration field duration_secs.
alter table public.content_items rename column duration_seconds to duration_secs;
