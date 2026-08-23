const $d = selector => document.querySelector(selector);
const cfg = window.FM_HACHIJO_SUPABASE;
const sb = window.supabase.createClient(cfg.url, cfg.publishableKey);
let families = [];
let items = [];

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

async function saveContent() {
  const urls = $d('#urls').value.split(/\n+/).map(value => value.trim()).filter(Boolean);
  const duration = Number($d('#duration').value);
  if (!urls.length || !Number.isFinite(duration) || duration < 1) return void ($d('#save-status').textContent = 'URLと秒単位の再生時間を入力してください。');
  const parsed = urls.map(url => ({ url, youtubeId: idFrom(url) }));
  if (parsed.some(item => !item.youtubeId)) return void ($d('#save-status').textContent = 'YouTube動画URLを1行ずつ入力してください。');
  $d('#save').disabled = true;
  $d('#save-status').textContent = `YouTube情報を確認中…（${parsed.length}件）`;
  const records = await Promise.all(parsed.map(async item => {
    const metadata = await youtubeMetadata(item.url, item.youtubeId);
    return { family_code: $d('#family-code').value, youtube_id: item.youtubeId, source_url: item.url, source_title: metadata.source_title || item.youtubeId, source_channel: metadata.source_channel || null, public_title: metadata.source_title || item.youtubeId, duration_seconds: duration, content_type: 'vod', atomic: true, enabled: true, verified: metadata.verified };
  }));
  const { error } = await sb.from('content_items').upsert(records, { onConflict: 'youtube_id' });
  $d('#save').disabled = false;
  if (error) return void ($d('#save-status').textContent = error.message);
  $d('#urls').value = '';
  $d('#duration').value = '';
  $d('#save-status').textContent = `${records.length}件を保存しました。CHECKEDはoEmbed応答の一次確認済みです。`;
  await loadLibrary();
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
  await loadLibrary();
}

async function start() {
  $d('#auth-submit').onclick = async () => { const { error } = await sb.auth.signInWithPassword({ email: $d('#auth-email').value, password: $d('#auth-password').value }); $d('#auth-status').textContent = error?.message || 'ログインしました。'; if (!error) await auth(); };
  $d('#auth-logout').onclick = async () => { await sb.auth.signOut(); location.reload(); };
  $d('#save').onclick = saveContent;
  $d('#library-search').oninput = renderItems;
  $d('#library-list').onclick = handleItemAction;
  await auth();
}
start();
