// Run: node supabase/tests/five-o-clock-song.mjs /path/to/node_modules/@electric-sql/pglite/dist/index.js
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import vm from 'node:vm';
const { PGlite } = await import(process.argv[2]);
const db = new PGlite();
const read = name => readFileSync(new URL(`../migrations/${name}`, import.meta.url), 'utf8');
const base = read('0002_clean_rebuild.sql');
await db.exec('create role anon; create role authenticated; create function public.is_admin() returns boolean language sql as $$select true$$;');
await db.exec(base.slice(base.indexOf('create table public.content_items'), base.indexOf('create or replace function public.handle_new_user')));
await db.exec(base.slice(base.indexOf('create or replace function public.fmh_solar_seconds'), base.indexOf('alter table public.profiles enable')));
await db.exec(read('0012_replace_solar_approximation_with_naoj_calendar.sql').replace('select public.cron_regenerate_schedule();', ''));
await db.exec(read('0014_replace_sunset_camera.sql'));
await db.exec("insert into content_items(family_code,youtube_id,title,duration_secs) values ('music','music000001','Music',420),('hachijo_taiko','taiko000001','Taiko',7200),('power_push','power000001','Power',240),('sports','sport000001','Sports',3600),('hachijo_picks','picks000001','Picks',360);");
await db.exec("select regenerate_schedule('2026-02-09T03:00:00+09:00');");
const before = (await db.query('select * from schedule_items order by start_at')).rows;
await db.exec(read('0015_add_five_o_clock_song.sql'));
assert.deepEqual((await db.query('select * from schedule_items order by start_at')).rows, before, 'migration must not regenerate');
await db.exec("insert into content_items(family_code,youtube_id,title,duration_secs) values ('five_o_clock_song','song0000001','PRIVATE SONG / ARTIST',300);");
let checked=0;
for (const duration of [1,300,600]) {
  await db.exec(`update content_items set duration_secs=${duration} where family_code='five_o_clock_song'`);
  let skipped=0;
  for(let day=0;day<365;day++) {
    const date=new Date(Date.UTC(2026,0,1+day)).toISOString().slice(0,10);
    await db.exec(`truncate schedule_items; select regenerate_schedule('${date}T03:00:00+09:00');`);
    const rows=(await db.query('select *, extract(epoch from end_at-start_at)::integer as seconds from schedule_items order by start_at')).rows;
    for(let i=1;i<rows.length;i++) assert.equal(+rows[i-1].end_at,+rows[i].start_at,`gap/overlap ${date}`);
    const start=new Date(`${date}T17:00:00+09:00`), end=new Date(+start+duration*1000);
    const song=rows.filter(r=>r.family_code==='five_o_clock_song'&&+r.start_at===+start);
    assert.equal(song.length,1,date); assert.equal(song[0].seconds,duration); assert.equal(song[0].title,'5時のうた');
    const following=rows.find(r=>+r.start_at===+end); assert.ok(following,date);
    assert.notEqual(following.family_code,'five_o_clock_song');
    const previous=rows.find(r=>+r.end_at===+start); assert.ok(previous); assert.notEqual(previous.family_code,'five_o_clock_song');
    const solar=(await db.query(`select sunset_seconds from solar_calendar where month_day='${date.slice(5)}'`)).rows[0].sunset_seconds;
    const overlap=solar-600<61800&&solar+600>61200;
    const sunset=rows.filter(r=>r.title==='SUNSET'&&+r.start_at>=+new Date(`${date}T00:00:00+09:00`)&&+r.start_at<+new Date(`${date}T23:59:59+09:00`));
    assert.equal(sunset.length,overlap?0:1,date); if(overlap)skipped++;
    if(sunset.length) assert.equal(sunset[0].youtube_id,'f8sGmJ67Z04');
    const relay=rows.find(r=>+r.start_at===+new Date(`${date}T22:30:00+09:00`));
    assert.equal(relay?.family_code,'tokyo_relay'); assert.equal(relay.seconds,1200);
    checked++;
  }
  assert.equal(skipped,56); console.log(`365 days passed: ${duration}s songs, 56 SUNSET omissions`);
}
// Three candidates must each occur once in the generated three-day schedule.
await db.exec("insert into content_items(family_code,youtube_id,title,duration_secs) values ('five_o_clock_song','song0000002','B',240),('five_o_clock_song','song0000003','C',180); truncate schedule_items; select regenerate_schedule('2026-02-09T03:00:00+09:00');");
const songs=(await db.query("select youtube_id from schedule_items where family_code='five_o_clock_song'")).rows;
assert.equal(songs.length,3);assert.equal(new Set(songs.map(r=>r.youtube_id)).size,3);
await assert.rejects(db.exec("update content_items set duration_secs=601 where family_code='five_o_clock_song'"));
// Rendering never exposes the source title; NOW and NEXT share the same renderer.
const app=readFileSync(new URL('../../app.js',import.meta.url),'utf8');
const nodes={};const context={document:{querySelector:s=>nodes[s]??={}},Intl,Date};vm.createContext(context);
vm.runInContext(app.slice(0,app.indexOf('const sb ='))+app.slice(app.indexOf('const familyName'),app.indexOf('const desktopAudioUI')),context);
for(const prefix of ['now','next']) {
 context.prefix=prefix;vm.runInContext("showProgram(prefix,{family_code:'five_o_clock_song',title:'PRIVATE SONG / ARTIST'})",context);
 assert.equal(nodes[`#${prefix}-family`].textContent,'5時のうた');assert.equal(nodes[`#${prefix}-title`].textContent,'');
}
console.log(`${checked} generated schedules passed; migration preservation, one-pass selection, duration limit, NOW/NEXT passed`);
await db.close();
