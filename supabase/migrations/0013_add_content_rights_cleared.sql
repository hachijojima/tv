alter table public.content_items
  add column if not exists rights_cleared boolean null;
