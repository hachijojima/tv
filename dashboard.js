const $d = selector => document.querySelector(selector);
const cfg = window.FM_HACHIJO_SUPABASE;
const sb = window.supabase.createClient(cfg.url, cfg.publishableKey);
let families = [];
let items = [];
let pendingRecords = null;
let youtubeApiPromise = null;

const escapeHtml = value => String(value || '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
const idFrom = value => (value.match(/(?:youtu\.be\/|[?&]v=|\/embed\/)([\w-]{11})/) || [])[1];
const secondsLabel = seconds => `${Math.floor(seconds / 3600) ? `${Math.floor(seconds / 3600)}h ` : ''}${Math.floor((seconds % 3600) / 60)}m`;

function renderFamilies() {
  $d('#family-code').innerHTML = families.map(family => `<option value="${escapeHtml(family.code)}">${escapeHtml(family.display_name)}</option>`).join('');
  $d('#family-list').innerHTML = families.map(family => `<article class="candidate"><div><p class="candidate-kicker">${escapeHtml(family.code)} · ${family.enabled ? 'ENABLED' : 'DISABLED'}</p><h3>${escapeHtml(family.display_name)}</h3><p class="candidate-meta">${escapeHtml(family.schedule_role)} · ${family.daily_min}–${family.daily_max} / DAY</p></div></article>`).join('') || '<p class="candidate-empty">PROGRAM FAMILY がありません。</p>';
}

function renderItems() {
  const query = $d('#library-search').value.trim().toLocaleLowerCase('ja');
  const visible = items.filter(item => [item.family_code, item.public_title, item.source_title, item.source_channel, item.youtube_id].join(' ').toLocaleLowerCase('ja').includes(query));
  $d('#library-list').innerHTML = visible.map(item => `<article class="candidate" data-item="${item.id}"><div><p class="candidate-kicker">${escapeHtml(item.family_code)} · ${item.enabled ? 'ENABLED' : 'DISABLED'} · ${item.verified ? 'CHECKED' : 'UNVERIFIED'}</p><h3>${escapeHtml(item.public_title || item.source_title)}</h3><p class="candidate-meta">${escapeHtml(item.source_channel || 'Unknown channel')} · ${secondsLabel(item.duration_seconds)}</p><p class="candidate-reason">${escapeHtml(item.youtube_id)}</p></div><div class="dashboard-actions"><button data-action="edit">EDIT</button><button data-action="toggle">${item.enabled ? 'DISABLE' : 'ENABLE'}</button><button data-action="delete">DELETE</button></div></article>`).join('') || '<p class="candidate-empty">該当するコンテンツはありません。</p>';
}

async function loadLibrary() {
  const [{ data: familyRows, error: familyError }, { data: itemRows, error: itemError }] = await Promise.all([
    sb.from('program_families').select('*').order('sort_order'),
    sb.from('content_items').select('*').order('created_at', { ascending: false })
  ]);
  if (familyError || itemError) throw familyError || itemError;
  families = familyRows || [];
  items = itemRows || [];
  renderFamilies();
  renderItems();
}

async function youtubeMetadata(url, youtubeId) {
  try {
    const response = await fetch(`https://www.youtube.com/oembed?url=${encodeURIComponent(url)}&format=json`);
    if (!response.ok) return { verified: false };
    const data = await response.json();
    return { source_title: data.title || youtubeId, source_channel: data.author_name || null, verified: true };
  } catch { return { verified: false }; }
}

function loadYouTubeApi() {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (youtubeApiPromise) return youtubeApiPromise;
  youtubeApiPromise = new Promise((resolve, reject) => {
    const previous = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => { previous?.(); resolve(window.YT); };
    const script = document.createElement('script');
    script.src = 'https://www.youtube.com/iframe_api';
    script.onerror = () => reject(new Error('YouTube Player APIを読み込めませんでした。'));
    document.head.append(script);
  });
  return youtubeApiPromise;
}

async function youtubeDuration(youtubeId) {
  const YT = await loadYouTubeApi();
  const mount = document.createElement('div');
  mount.setAttribute('aria-hidden', 'true');
  mount.style.cssText = 'position:fixed;left:-2px;bottom:-2px;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none';
  const playerId = `duration-probe-${youtubeId}-${Date.now()}`;
  mount.id = playerId;
  document.body.append(mount);
  return new Promise(resolve => {
    let settled = false;
    const finish = value => { if (!settled) { settled = true; try { player.destroy(); } catch {} mount.remove(); resolve(value); } };
    const timer = setTimeout(() => finish(null), 12000);
    const player = new YT.Player(playerId, {
      width: '1', height: '1', videoId: youtubeId,
      playerVars: { autoplay: 0, controls: 0, playsinline: 1, rel: 0 },
      events: {
        onReady: event => {
          const read = () => { const duration = Math.round(event.target.getDuration()); if (duration > 0) { clearTimeout(timer); finish(duration); } };
          read(); setTimeout(read, 800); setTimeout(read, 2200);
        },
        onError: () => { clearTimeout(timer); finish(null); }
      }
    });
  });
}

function renderDurationFallbacks(records) {
  const missing = records.filter(record => !record.duration_seconds);
  $d('#duration-fallbacks').innerHTML = missing.map(record => `<label>Duration (seconds) <small>${escapeHtml(record.source_title || record.youtube_id)} — 自動取得できませんでした。</small><input type="number" min="1" data-duration-for="${escapeHtml(record.youtube_id)}" placeholder="seconds"></label>`).join('');
  $d('#duration-fallbacks').hidden = !missing.length;
}

async function persistRecords(records) {
  const missing = records.filter(record => !record.duration_seconds);
  if (missing.length) {
    missing.forEach(record => { record.duration_seconds = Number($d(`[data-duration-for="${record.youtube_id}"]`)?.value); });
    if (missing.some(record => !Number.isFinite(record.duration_seconds) || record.duration_seconds < 1)) {
      $d('#save-status').textContent = '自動取得できなかった動画だけ、秒数を入力してください。';
      return;
    }
  }
  $d('#save').disabled = true;
  const { error } = await sb.from('content_items').upsert(records, { onConflict: 'youtube_id' });
  $d('#save').disabled = false;
  if (error) return void ($d('#save-status').textContent = error.message);
  $d('#urls').value = '';
  $d('#duration-fallbacks').innerHTML = '';
  $d('#duration-fallbacks').hidden = true;
  pendingRecords = null;
  $d('#save-status').textContent = `${records.length}件を、動画ごとの実durationで保存しました。`;
  await loadLibrary();
}

async function saveContent() {
  if (pendingRecords) return persistRecords(pendingRecords);
  const urls = $d('#urls').value.split(/\n+/).map(value => value.trim()).filter(Boolean);
  if (!urls.length) return void ($d('#save-status').textContent = 'YouTube動画URLを1行ずつ入力してください。');
  const parsed = urls.map(url => ({ url, youtubeId: idFrom(url) }));
  if (parsed.some(item => !item.youtubeId)) return void ($d('#save-status').textContent = 'YouTube動画URLを1行ずつ入力してください。');
  $d('#save').disabled = true;
  $d('#save-status').textContent = `YouTube情報・実durationを確認中…（${parsed.length}件）`;
  const records = await Promise.all(parsed.map(async item => {
    const [metadata, duration] = await Promise.all([youtubeMetadata(item.url, item.youtubeId), youtubeDuration(item.youtubeId)]);
    return { family_code: $d('#family-code').value, youtube_id: item.youtubeId, source_url: item.url, source_title: metadata.source_title || item.youtubeId, source_channel: metadata.source_channel || null, public_title: metadata.source_title || item.youtubeId, duration_seconds: duration, content_type: 'vod', atomic: true, enabled: true, verified: metadata.verified && Boolean(duration) };
  }));
  $d('#save').disabled = false;
  pendingRecords = records;
  renderDurationFallbacks(records);
  if (records.some(record => !record.duration_seconds)) {
    $d('#save-status').textContent = '取得不能な動画があります。表示された行だけ秒数を入力して、もう一度SAVEしてください。';
    return;
  }
  await persistRecords(records);
}

async function updateItem(item, changes) {
  const { error } = await sb.from('content_items').update(changes).eq('id', item.id);
  if (error) alert(error.message); else await loadLibrary();
}

async function handleItemAction(event) {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const item = items.find(value => value.id === button.closest('[data-item]').dataset.item);
  if (!item) return;
  if (button.dataset.action === 'toggle') return updateItem(item, { enabled: !item.enabled });
  if (button.dataset.action === 'delete') {
    if (confirm(`「${item.public_title || item.source_title}」を削除します。`)) {
      const { error } = await sb.from('content_items').delete().eq('id', item.id);
      if (error) alert(error.message); else await loadLibrary();
    }
    return;
  }
  const title = prompt('表示タイトル', item.public_title || item.source_title);
  if (title === null) return;
  const duration = Number(prompt('再生時間（秒）', item.duration_seconds));
  if (!Number.isFinite(duration) || duration < 1) return alert('再生時間は1秒以上で入力してください。');
  await updateItem(item, { public_title: title.trim() || item.source_title, duration_seconds: duration });
}

async function auth() {
  const { data: { session } } = await sb.auth.getSession();
  if (!session) { $d('#admin-panel').hidden = true; $d('#library-panel').hidden = true; return; }
  $d('#auth-status').textContent = session.user.email;
  $d('#auth-submit').hidden = true;
  $d('#auth-logout').hidden = false;
  const { data: profile, error } = await sb.from('profiles').select('is_admin').single();
  if (error || !profile?.is_admin) return void ($d('#auth-status').textContent = 'このユーザーは管理者ではありません。');
  $d('#admin-panel').hidden = false;
  $d('#library-panel').hidden = false;
  $d('#generate-week').hidden = false;
  await loadLibrary();
}

function jstDate(offset = 0) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts().filter(part => part.type !== 'literal').map(part => [part.type, part.value]));
  const date = new Date(Date.UTC(+parts.year, +parts.month - 1, +parts.day + offset));
  return { year: String(date.getUTCFullYear()), month: String(date.getUTCMonth() + 1).padStart(2, '0'), day: String(date.getUTCDate()).padStart(2, '0') };
}
const dateKey = date => `${date.year}-${date.month}-${date.day}`;
const timestamp = (date, seconds) => { const value = new Date(Date.UTC(+date.year, +date.month - 1, +date.day + Math.floor(seconds / 86400), 0, 0, seconds % 86400)); return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, '0')}-${String(value.getUTCDate()).padStart(2, '0')}T${String(value.getUTCHours()).padStart(2, '0')}:${String(value.getUTCMinutes()).padStart(2, '0')}:${String(value.getUTCSeconds()).padStart(2, '0')}+09:00`; };

async function loadWeek() {
  const start = dateKey(jstDate());
  const end = dateKey(jstDate(7));
  const { data: schedules, error } = await sb.from('daily_schedules').select('id,broadcast_date,diagnostics,rule_version,schedule_items(start_at,end_at,family_code,detail,content_id,source_id)').gte('broadcast_date', start).lt('broadcast_date', end).order('broadcast_date');
  if (error) { $d('#schedule-status').textContent = error.message; return; }
  $d('#week').innerHTML = (schedules || []).map((schedule, index) => {
    const diagnostics = schedule.diagnostics || {}, counts = diagnostics.counts || {}, warnings = diagnostics.warnings || [];
    const entries = (schedule.schedule_items || []).sort((a, b) => a.start_at.localeCompare(b.start_at)).map(item => `<p><time>${item.start_at.slice(11, 16)}</time><span>${escapeHtml(item.family_code)}</span><small>${escapeHtml(item.detail?.sourceTitle || item.detail?.archiveYear ? `${item.detail?.archiveYear || ''} ${item.detail?.archivePart || ''}` : '')}</small></p>`).join('');
    return `<details ${index ? '' : 'open'}><summary>${schedule.broadcast_date} · score ${diagnostics.diversity_score ?? '—'}</summary><p class="candidate-meta">LONG PLAY ${counts['LONG PLAY'] ?? 0}/4 · TAIKO ${counts['HACHIJO TAIKO'] ?? 0}/4 · SPORTS ${counts.SPORTS ?? 0} · BRIDGE ${Math.round((diagnostics.bridge_total_seconds || 0) / 60)}m</p>${warnings.length ? `<p class="candidate-reason">${escapeHtml(warnings.join(' / '))}</p>` : ''}${entries}</details>`;
  }).join('') || '<p class="candidate-empty">まだ確定済みの番組表はありません。管理者がGENERATEを実行してください。</p>';
}

async function generateWeek() {
  if (!confirm('今後7日分の確定番組表を置き換えます。')) return;
  $d('#generate-week').disabled = true;
  $d('#schedule-status').textContent = 'ライブラリと7日分の編成を読み込み中…';
  const library = await fetch('library.json', { cache: 'no-store' }).then(response => response.json());
  const [{ data: contentRows, error: contentError }, { data: sourceRows, error: sourceError }] = await Promise.all([
    sb.from('content_items').select('id,youtube_id'), sb.from('archive_sources').select('id,youtube_id')
  ]);
  if (contentError || sourceError) { $d('#schedule-status').textContent = (contentError || sourceError).message; $d('#generate-week').disabled = false; return; }
  const contentId = new Map((contentRows || []).map(row => [row.youtube_id, row.id]));
  const sourceId = new Map((sourceRows || []).map(row => [row.youtube_id, row.id]));
  for (let offset = 0; offset < 7; offset++) {
    const date = jstDate(offset), generated = window.HachijoScheduleV3.build(library, date);
    const { data: schedule, error } = await sb.from('daily_schedules').upsert({ broadcast_date: generated.date, rule_version: generated.ruleVersion, diversity_score: generated.diagnostics.diversity_score, diagnostics: generated.diagnostics }, { onConflict: 'broadcast_date' }).select('id').single();
    if (error) { $d('#schedule-status').textContent = error.message; $d('#generate-week').disabled = false; return; }
    const { error: deleteError } = await sb.from('schedule_items').delete().eq('schedule_id', schedule.id);
    if (deleteError) { $d('#schedule-status').textContent = deleteError.message; $d('#generate-week').disabled = false; return; }
    const rows = generated.items.map(program => ({ schedule_id: schedule.id, start_at: timestamp(date, program.start), end_at: timestamp(date, program.end), family_code: ({ 'LONG PLAY': 'long_play', 'HACHIJO TAIKO': 'hachijo_taiko', SPORTS: 'island_league', 'HACHIJO ARCHIVE': 'hachijo_archive', 'HACHIJO NOW': 'island_camera', 'TOKYO RELAY': 'tokyo_relay', DAWN: 'dawn', SUNSET: 'sunset', 'AFTER HOURS': 'after_hours' }[program.programLabel] || 'island_camera'), content_id: contentId.get(program.youtubeId) || null, source_id: sourceId.get(program.youtubeId) || null, start_offset: program.sourceOffset || 0, end_offset: program.sourceOffset ? program.sourceOffset + (program.end - program.start) : null, detail: program }));
    const { error: itemError } = await sb.from('schedule_items').insert(rows);
    if (itemError) { $d('#schedule-status').textContent = itemError.message; $d('#generate-week').disabled = false; return; }
  }
  $d('#schedule-status').textContent = '7日分をDBへ確定保存しました。diagnosticsの警告を確認してください。';
  $d('#generate-week').disabled = false;
  await loadWeek();
}

async function start() {
  $d('#auth-submit').onclick = async () => { const { error } = await sb.auth.signInWithPassword({ email: $d('#auth-email').value, password: $d('#auth-password').value }); $d('#auth-status').textContent = error?.message || 'ログインしました。'; if (!error) await auth(); };
  $d('#auth-logout').onclick = async () => { await sb.auth.signOut(); location.reload(); };
  $d('#save').onclick = saveContent;
  $d('#urls').oninput = () => { pendingRecords = null; $d('#duration-fallbacks').innerHTML = ''; $d('#duration-fallbacks').hidden = true; };
  $d('#library-search').oninput = renderItems;
  $d('#library-list').onclick = handleItemAction;
  $d('#generate-week').onclick = generateWeek;
  await auth();
  await loadWeek();
}
start();
