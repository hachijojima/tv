import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

globalThis.window = globalThis;
eval(readFileSync(new URL('../schedule-v3.js', import.meta.url), 'utf8'));
const library = JSON.parse(readFileSync(new URL('../library.json', import.meta.url), 'utf8'));

for (const value of ['2026-06-21', '2026-08-23', '2026-12-21', '2026-08-30']) {
  const [year, month, day] = value.split('-');
  const schedule = HachijoScheduleV3.build(library, { year, month, day });
  const dawn = schedule.items.find(item => item.programLabel === 'DAWN');
  const sunset = schedule.items.find(item => item.programLabel === 'SUNSET');
  const midnight = schedule.items.find(item => item.start === 0);
  const afterMidnight = schedule.items.find(item => item.start === midnight.end);
  assert.equal(schedule.diagnostics.counts['LONG PLAY'], 4, `${value}: LONG PLAY quota`);
  assert.equal(schedule.diagnostics.counts['HACHIJO TAIKO'], 4, `${value}: TAIKO quota`);
  assert.ok(dawn.end - dawn.start >= 900 && dawn.end - dawn.start <= 1500, `${value}: DAWN duration`);
  assert.ok(sunset.end - sunset.start >= 900 && sunset.end - sunset.start <= 1500, `${value}: SUNSET duration`);
  assert.equal(midnight.programLabel, 'LONG PLAY', `${value}: midnight feature`);
  assert.equal(afterMidnight.programLabel, 'TOKYO RELAY', `${value}: midnight relay`);
  assert.equal(schedule.diagnostics.overlaps, 0, `${value}: overlap`);
  assert.ok(schedule.diagnostics.longest_bridge_seconds <= 900, `${value}: bridge duration`);
}
console.log('schedule-v3 tests passed');
