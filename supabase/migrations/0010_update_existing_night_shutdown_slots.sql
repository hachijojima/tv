-- Update only already-generated overnight slots.  Do not regenerate or reshuffle
-- the rest of the 72-hour schedule; the 22:30 DEPARTURE slot remains TOKYO RELAY.
update public.schedule_items
set
  family_code = 'island_view',
  youtube_id = 'ciBuVo8Sozk',
  title = '放送休止',
  start_offset_seconds = null
where family_code = 'tokyo_relay'
  and (start_at at time zone 'Asia/Tokyo')::time <> time '22:30';
