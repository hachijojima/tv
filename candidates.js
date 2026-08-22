const formatDuration = seconds => `${Math.floor(seconds / 60)} min`;
const escapeHtml = value => String(value).replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' })[char]);
async function startCandidates() {
  const data = await fetch('candidates.json', { cache: 'no-store' }).then(response => response.ok ? response.json() : Promise.reject());
  const ref = document.querySelector('#reference-link');
  ref.textContent = data.editorialReference.title;
  ref.href = data.editorialReference.url;
  document.querySelector('#principles').innerHTML = data.editorialReference.principles.map(item => `<li>${escapeHtml(item)}</li>`).join('');
  const review = data.candidates.filter(item => item.status === 'review');
  document.querySelector('#review-list').innerHTML = review.length ? review.map(item => `<article class="candidate"><div><p class="candidate-kicker">${escapeHtml(item.tags.join(' / '))}</p><h3>${escapeHtml(item.title)}</h3><p class="candidate-meta">${escapeHtml(item.channel)} · ${formatDuration(item.duration)}</p><p class="candidate-reason">${escapeHtml(item.reason)}</p></div><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">YOUTUBE</a></article>`).join('') : '<p class="candidate-empty">候補はありません。</p>';
}
startCandidates().catch(() => { document.querySelector('#review-list').textContent = '候補を読み込めませんでした。'; });
