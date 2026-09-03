const $ = selector => document.querySelector(selector);
const sb = window.supabase.createClient(window.FM_HACHIJO_SUPABASE.url, window.FM_HACHIJO_SUPABASE.publishableKey);
const audioPreferenceKey = 'fm8jo_audio_preference';
function getAudioPreference() { try { const value = localStorage.getItem(audioPreferenceKey); return value === 'on' || value === 'off' ? value : null; } catch { return null; } }
function setAudioPreference(value) { try { localStorage.setItem(audioPreferenceKey, value); } catch {} }
const state = { player: null, current: null, key: '', boundaryTimer: null, accessRetryTimer: null, accessAttempts: 0, soundOn: false, audioPreference: getAudioPreference(), showAudioOverlay: false, awaitingAudibleAutoplay: false, initialising: false };
function trackEvent(name, parameters = {}) { if (typeof window.gtag === 'function') window.gtag('event', name, parameters); }
const familyName = { music: 'MUSIC', hachijo_taiko: 'HACHIJO TAIKO', power_push: 'POWER PLAY', sports: 'SPORTS', hachijo_picks: 'HACHIJO PICKS', island_view: 'ISLAND VIEW', tokyo_relay: 'TOKYO RELAY' };
const formatTime = value => new Intl.DateTimeFormat('ja-JP', { timeZone: 'Asia/Tokyo', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value));
const message = value => { $('#player-message').textContent = value; $('#player-message').hidden = !value; };
function showProgram(prefix, program) { const isDeparture = program?.family_code === 'tokyo_relay' && formatTime(program.start_at) === '22:30' && formatTime(program.end_at) === '22:50'; const showTitle = ['music', 'power_push', 'hachijo_picks', 'island_view'].includes(program?.family_code); const displayTitle = program?.family_code === 'tokyo_relay' ? (isDeparture ? 'DEPARTURE' : '放送休止') : (showTitle ? (program.title || '') : ''); $(`#${prefix}-family`).textContent = program ? familyName[program.family_code] : '—'; $(`#${prefix}-title`).textContent = displayTitle; }
const desktopAudioUI = () => window.matchMedia('(min-width: 1366px)').matches;
const speakerIcon = 'M4 9v6h4l5 4V5L8 9H4Zm12.59 3 2.7-2.7-1.41-1.41-2.7 2.7-2.71-2.71-1.41 1.41 2.71 2.71-2.7 2.7 1.41 1.41 2.7-2.71 2.71 2.71 1.41-1.41L16.59 12Z';
const mutedSpeakerIcon = 'M4 9v6h4l5 4V5L8 9H4Zm12.5 3c0-1.77-1-3.29-2.5-4.03v8.05A4.49 4.49 0 0 0 16.5 12ZM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.5 7-8.77s-2.99-7.86-7-8.77Z';
function soundLabel() { const button = $('#sound-toggle'); const label = state.soundOn ? '音を消す' : '音を出す'; button.querySelector('span').textContent = label; button.querySelector('path').setAttribute('d', state.soundOn ? speakerIcon : mutedSpeakerIcon); button.setAttribute('aria-label', label); button.setAttribute('aria-pressed', String(state.soundOn)); button.classList.toggle('is-audible', state.soundOn); const overlay = $('#audio-unmute-overlay'); overlay.hidden = !(desktopAudioUI() && state.showAudioOverlay && !state.soundOn && state.player); }
const jstDateKey = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const accessTotalCacheKey = 'fmh_access_total';
function showAccessTotal(total) { const count = Number(total); if (!Number.isFinite(count) || count < 0) throw new Error('Invalid access total'); document.querySelector("#presence-count").textContent = `${count}人`; document.querySelector("#presence-status").setAttribute("aria-label", `${count}人がみています`); try { localStorage.setItem(accessTotalCacheKey, String(count)); } catch {} }
function showCachedAccessTotal() { try { const cached = localStorage.getItem(accessTotalCacheKey); if (cached !== null) showAccessTotal(cached); } catch {} }
function retryAccessRecord() { clearTimeout(state.accessRetryTimer); const delay = Math.min(60000, 1500 * 2 ** state.accessAttempts); state.accessAttempts += 1; state.accessRetryTimer = window.setTimeout(recordAccess, delay); }
async function recordAccess() { try { const key = `fmh_access_recorded_${jstDateKey()}`; const { data, error } = sessionStorage.getItem(key) ? await sb.rpc("access_total") : await sb.rpc("record_access"); if (error) throw error; showAccessTotal(data); sessionStorage.setItem(key, '1'); state.accessAttempts = 0; clearTimeout(state.accessRetryTimer); } catch (error) { console.warn('Unable to update viewer count; retrying.', error); retryAccessRecord(); } }
const hot10Weekdays = ['Sun.', 'Mon.', 'Tue.', 'Wed.', 'Thu.', 'Fri.', 'Sat.'];
function hot10MovementLabel(movement) { if (movement === 'NEW') return 'NEW'; if (movement === 'RE') return 'RE'; if (movement === '→') return '順位変動なし'; const match = /^([↑↓])(\d+)$/.exec(movement || ''); return match ? `${match[2]}位${match[1] === '↑' ? '上昇' : '下降'}` : (movement || '順位情報なし'); }
function renderHot10Date(date) { const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date || ''); if (!match) throw new Error('Invalid HOT10 date'); const [year, month, day] = match.slice(1); const weekday = hot10Weekdays[new Date(Date.UTC(Number(year), Number(month) - 1, Number(day))).getUTCDay()]; $('#hot10-date').setAttribute('aria-label', `${Number(year)}年${Number(month)}月${Number(day)}日 ${weekday}`); $('.hot10-month-day').textContent = `${Number(month)}.${day}`; $('.hot10-weekday').textContent = weekday; $('.hot10-year').textContent = year; }
function renderHot10(chart) { const list = $('#hot10-list'); list.replaceChildren(); chart.forEach(item => { const row = document.createElement('li'); const movement = item.movement || '—'; const movementClass = movement === 'NEW' ? ' is-new' : movement === 'RE' ? ' is-re' : movement.startsWith('↑') ? ' is-up' : movement.startsWith('↓') ? ' is-down' : movement === '→' ? ' is-flat' : ''; row.className = 'hot10-row'; const rankGroup = document.createElement('span'); rankGroup.className = 'hot10-rank-block'; const rank = document.createElement('span'); rank.className = 'hot10-rank'; rank.textContent = String(item.rank).padStart(2, '0'); const move = document.createElement('span'); move.className = `hot10-movement${movementClass}`; move.textContent = movement; move.setAttribute('aria-label', hot10MovementLabel(movement)); rankGroup.append(rank, move); const title = document.createElement('span'); title.className = 'hot10-title'; title.textContent = item.title || '—'; const artist = document.createElement('span'); artist.className = 'hot10-artist'; artist.textContent = item.artist || '—'; row.append(rankGroup, title, artist); list.append(row); }); }
function hot10ChartDate(now = new Date()) { const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23' }).formatToParts(now).reduce((value, part) => ({ ...value, [part.type]: part.value }), {}); const atMidnightUtc = Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day)); const chartDay = new Date(atMidnightUtc - (Number(parts.hour) < 3 ? 86400000 : 0)); return chartDay.toISOString().slice(0, 10); }
async function loadHot10() { const section = $('#hachijo-hot10'); const load = async path => { const url = new URL(path, document.baseURI); url.searchParams.set('v', Date.now().toString()); const response = await fetch(url, { cache: 'no-store' }); if (!response.ok) throw new Error(`HOT10 fetch failed: ${response.status}`); return response.json(); }; try { let data; try { data = await load(`hachijo_hot10/hot10_output/${hot10ChartDate()}.json`); } catch { data = await load('hachijo_hot10/hot10_output/latest.json'); } if (!data?.date || !Array.isArray(data.chart) || data.chart.length !== 10) throw new Error('Invalid HOT10 payload'); renderHot10Date(data.date); renderHot10(data.chart); } catch (error) { console.error('Unable to load HACHIJO HOT 10', error); $('#hot10-list').replaceChildren(Object.assign(document.createElement('li'), { className: 'hot10-error', textContent: 'ランキングを読み込めませんでした' })); } finally { section.setAttribute('aria-busy', 'false'); } }
function scheduleHot10BoundaryRefresh() { const now = new Date(); const boundary = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 18, 0, 0)); if (boundary <= now) boundary.setUTCDate(boundary.getUTCDate() + 1); window.setTimeout(() => { loadHot10(); scheduleHot10BoundaryRefresh(); }, boundary.getTime() - now.getTime() + 200); }
async function readTimeline() { const now = new Date().toISOString(); const { data: current, error } = await sb.from('schedule_items').select('*').lte('start_at', now).gt('end_at', now).order('start_at', { ascending: false }).limit(1).maybeSingle(); if (error) throw error; if (!current) return { current: null, next: null }; const { data: next, error: nextError } = await sb.from('schedule_items').select('*').gte('start_at', current.end_at).order('start_at').limit(1).maybeSingle(); if (nextError) throw nextError; return { current, next }; }
function scheduleBoundary(current) { clearTimeout(state.boundaryTimer); const delay = Math.max(1000, new Date(current.end_at).getTime() - Date.now() + 200); state.boundaryTimer = setTimeout(() => sync(true), delay); }
function startSecondsFor(current) { const elapsed = Math.max(0, Math.floor((Date.now() - new Date(current.start_at).getTime()) / 1000)); return ['island_view', 'tokyo_relay'].includes(current.family_code) ? 0 : (current.start_offset_seconds || 0) + elapsed; }
function startMutedPlayback(showOverlay = false) { if (!state.player) return; state.awaitingAudibleAutoplay = false; state.player.mute(); state.player.playVideo(); state.soundOn = false; state.showAudioOverlay = Boolean(showOverlay && desktopAudioUI()); soundLabel(); }
function enableAudio({ remember = false, showOverlayOnFailure = desktopAudioUI(), source = 'control' } = {}) { if (!state.player) return; state.player.unMute(); state.player.playVideo(); window.setTimeout(() => { const enabled = !state.player.isMuted(); state.soundOn = enabled; state.showAudioOverlay = !enabled && Boolean(showOverlayOnFailure && desktopAudioUI()); if (enabled && remember) { state.audioPreference = 'on'; setAudioPreference('on'); trackEvent('audio_enable', { audio_source: source }); } soundLabel(); }, 150); }
function disableAudio() { if (state.player) state.player.mute(); state.awaitingAudibleAutoplay = false; state.soundOn = false; state.showAudioOverlay = false; state.audioPreference = 'off'; setAudioPreference('off'); soundLabel(); }
function beginInitialAudioPlayback() { const tryAudible = desktopAudioUI() && state.audioPreference === 'on'; if (!tryAudible) { startMutedPlayback(desktopAudioUI() && state.audioPreference === null); return; } state.awaitingAudibleAutoplay = true; state.showAudioOverlay = false; state.soundOn = false; soundLabel(); state.player.unMute(); state.player.playVideo(); window.setTimeout(() => { if (!state.awaitingAudibleAutoplay) return; state.awaitingAudibleAutoplay = false; state.soundOn = !state.player.isMuted(); state.showAudioOverlay = !state.soundOn && desktopAudioUI(); soundLabel(); }, 450); }
function handleAutoplayBlocked() { if (!state.awaitingAudibleAutoplay) return; startMutedPlayback(desktopAudioUI()); }
function loadCurrent(current, force = false) { const key = `${current.id}:${current.start_at}`; if (!force && key === state.key) return; const keepSound = state.soundOn; state.key = key; state.current = current; state.awaitingAudibleAutoplay = false; state.player.mute(); state.soundOn = false; state.showAudioOverlay = false; soundLabel(); state.player.loadVideoById({ videoId: current.youtube_id, startSeconds: startSecondsFor(current) }); state.player.playVideo(); if (keepSound) window.setTimeout(() => enableAudio({ showOverlayOnFailure: false }), 150); }
function renderTimeline({ current, next }, force = false) { if (!current) { message('現在の編成を準備中です。'); $('#now-start').textContent = ''; $('#next-start').textContent = ''; showProgram('now', null); showProgram('next', null); return; } message(''); $('#now-start').textContent = ` ${formatTime(current.start_at)}から`; $('#next-start').textContent = next ? ` ${formatTime(next.start_at)}から` : ''; showProgram('now', current); showProgram('next', next); if (state.player) loadCurrent(current, force); scheduleBoundary(current); }
async function sync(force = false) { try { renderTimeline(await readTimeline(), force); } catch { message('編成を読み込めませんでした。'); } }
const isIPhone = () => /iPhone|iPod/.test(navigator.userAgent);
function fullscreenLabel(active) { const button = $('#fullscreen-toggle'); button.querySelector('span').textContent = active ? '全画面を閉じる' : '全画面'; button.setAttribute('aria-label', active ? '全画面を閉じる' : '全画面'); button.setAttribute('aria-pressed', String(active)); }
function unlockOrientation() { globalThis.screen?.orientation?.unlock?.(); }
function fullscreen() { const container = $('.screen'); if (isIPhone()) { const active = container.classList.toggle('ios-immersive'); document.body.classList.toggle('ios-immersive', active); fullscreenLabel(active); trackEvent('fullscreen_toggle', { fullscreen_state: active ? 'open' : 'close' }); if (active) { globalThis.screen?.orientation?.lock?.('landscape')?.catch?.(() => {}); window.scrollTo(0, 0); } else unlockOrientation(); return; } const active = document.fullscreenElement || document.webkitFullscreenElement; if (active) return (document.exitFullscreen || document.webkitExitFullscreen).call(document); const request = container.requestFullscreen || container.webkitRequestFullscreen; return request?.call(container)?.then?.(() => globalThis.screen?.orientation?.lock?.('landscape')).catch?.(() => {}); }
const startupTimeline = readTimeline();
function createInitialPlayer(current) { const key = `${current.id}:${current.start_at}`, startSeconds = startSecondsFor(current), playerVars = { autoplay: 1, controls: 0, playsinline: 1, rel: 0, origin: location.origin }; state.key = key; state.current = current; if (startSeconds) playerVars.start = startSeconds; state.player = new YT.Player('player', { width: '100%', height: '100%', videoId: current.youtube_id, playerVars, events: { onReady: beginInitialAudioPlayback, onEnded: () => sync(true), onError: () => sync(true), onAutoplayBlocked: handleAutoplayBlocked } }); }
async function startInitialPlayback() { if (state.player || state.initialising) return; state.initialising = true; try { const timeline = await startupTimeline; renderTimeline(timeline); if (timeline.current) createInitialPlayer(timeline.current); } catch { state.initialising = false; message('編成を読み込めませんでした。'); } }
window.onYouTubeIframeAPIReady = startInitialPlayback;
if (window.YT?.Player) startInitialPlayback();
$('#sound-toggle').addEventListener('click', () => { if (state.soundOn) disableAudio(); else enableAudio({ remember: true, source: 'control' }); });
$('#audio-unmute-overlay').addEventListener('click', () => enableAudio({ remember: true, source: 'overlay' }));
$('#fullscreen-toggle').addEventListener('click', fullscreen); ['fullscreenchange', 'webkitfullscreenchange'].forEach(type => document.addEventListener(type, () => { const active = Boolean(document.fullscreenElement || document.webkitFullscreenElement); if (!active) unlockOrientation(); fullscreenLabel(active); trackEvent('fullscreen_toggle', { fullscreen_state: active ? 'open' : 'close' }); }));
$('.note-link').addEventListener('click', () => trackEvent('note_outbound_click', { link_destination: 'note' }));
const requestForm = $('.hot10-request');
const hot10RequestExamples = ['Adoの唱', 'マツケンサンバ', 'ゆずの夏色', 'ミセスの青と夏', 'スピッツのチェリー', 'サザンの真夏の果実', 'B’zのultra soul', 'ピンク・レディーのUFO', 'あいみょんのマリーゴールド', 'いきものがかりのYELL', '奥山熊雄のいもめとてがめ', '石投げ踊り', '50Aのインドの牛乳屋さん', '畑中葉子のカナダからの手紙'];
const requestInput = $('#hot10-request-input');
if (requestInput) requestInput.placeholder = hot10RequestExamples[Math.floor(Math.random() * hot10RequestExamples.length)];
if (requestForm) requestForm.addEventListener('submit', async event => {
  event.preventDefault();
  const button = requestForm.querySelector('button[type="submit"]');
  const success = $('#hot10-request-success');
  const error = $('#hot10-request-error');
  button.disabled = true;
  button.textContent = '送信中…';
  success.hidden = true;
  error.hidden = true;
  try {
    const response = await fetch('https://formsubmit.co/ajax/ritolab8@gmail.com', { method: 'POST', headers: { Accept: 'application/json' }, body: new FormData(requestForm) });
    if (!response.ok) throw new Error(`Request submit failed: ${response.status}`);
    requestForm.querySelector('[name="request"]').value = '';
    success.hidden = false;
    trackEvent('hot10_request_submit');
  } catch (submitError) {
    console.error('Unable to submit HOT10 request', submitError);
    error.hidden = false;
  } finally {
    button.disabled = false;
    button.textContent = 'リクエストする';
  }
});
if (new URLSearchParams(location.search).get('request') === 'sent') {
  const notice = $('#hot10-request-success');
  if (notice) notice.hidden = false;
  const url = new URL(location.href);
  url.searchParams.delete('request');
  history.replaceState({}, '', url);
}
window.addEventListener('resize', soundLabel); soundLabel(); showCachedAccessTotal(); recordAccess(); loadHot10(); scheduleHot10BoundaryRefresh();
