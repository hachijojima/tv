// node supabase/tests/sunset-camera.mjs /absolute/path/to/@electric-sql/pglite/dist/index.js
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const { PGlite } = await import(process.argv[2]);
const db = new PGlite();
const read = name => readFileSync(new URL(`../migrations/${name}`, import.meta.url), 'utf8');
const base = read('0002_clean_rebuild.sql');
await db.exec('create role anon; create role authenticated; create function public.is_admin() returns boolean language sql as $$select true$$;');
await db.exec(base.slice(base.indexOf('create table public.content_items'), base.indexOf('create or replace function public.handle_new_user')));
await db.exec(base.slice(base.indexOf('create or replace function public.fmh_solar_seconds'), base.indexOf('alter table public.profiles enable')));
await db.exec(read('0012_replace_solar_approximation_with_naoj_calendar.sql').replace('select public.cron_regenerate_schedule();', ''));
for (const name of ['0014_replace_sunset_camera.sql','0015_add_five_o_clock_song.sql','0016_rename_song_display.sql']) await db.exec(read(name));
await db.exec(`insert into schedule_items(family_code,youtube_id,title,start_at,end_at) values
 ('island_view','f8sGmJ67Z04','SUNSET',now()-interval '2 hours',now()-interval '1 hour'),
 ('island_view','f8sGmJ67Z04','SUNSET',now()-interval '10 minutes',now()+interval '10 minutes'),
 ('island_view','f8sGmJ67Z04','SUNSET',now()+interval '1 day',now()+interval '1 day 20 minutes'),
 ('island_view','SilNYdV2HNs','DAWN',now()+interval '12 hours',now()+interval '12 hours 20 minutes'),
 ('music','f8sGmJ67Z04','Other use',now()+interval '2 hours',now()+interval '3 hours');`);
const before = (await db.query('select *, end_at > now() as still_relevant from schedule_items order by start_at')).rows;
await db.exec(read('0017_replace_ended_sunset_stream.sql'));
const expected = before.map(row => ({...row, youtube_id: row.title === 'SUNSET' && row.still_relevant ? 'SWjwYvrGQYc' : row.youtube_id}));
assert.deepEqual((await db.query('select *, end_at > now() as still_relevant from schedule_items order by start_at')).rows, expected);
await db.exec(read('0017_replace_ended_sunset_stream.sql'));
assert.deepEqual((await db.query('select *, end_at > now() as still_relevant from schedule_items order by start_at')).rows, expected, 'patch is idempotent');
await db.exec(`insert into content_items(family_code,youtube_id,title,duration_secs) values
 ('music','music000001','Music',420),('hachijo_taiko','taiko000001','Taiko',7200),
 ('power_push','power000001','Power',240),('sports','sport000001','Sports',3600),
 ('hachijo_picks','picks000001','Picks',360),('five_o_clock_song','song0000001','Song',300);
 truncate schedule_items; select regenerate_schedule('2030-06-01T03:00:00+09:00');`);
const rows = (await db.query('select * from schedule_items order by start_at')).rows;
const sunsets = rows.filter(r => r.title === 'SUNSET');
assert.equal(sunsets.length, 3);
assert.ok(sunsets.every(r => r.youtube_id === 'SWjwYvrGQYc'));
assert.ok(rows.filter(r => r.title === 'DAWN').every(r => r.youtube_id === 'SilNYdV2HNs'));
for (let i=1;i<rows.length;i++) assert.equal(+rows[i-1].end_at,+rows[i].start_at);
console.log('SUNSET patch passed: active/future feed replacement, history/times/other content preservation, idempotence, regenerated schedule continuity.');
await db.close();
