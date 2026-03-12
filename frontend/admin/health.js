function _renderHealthRow(key, val) {
  if (key === 'simc_version' && val && typeof val === 'object') {
    const v = val;
    const local  = v.local  || '—';
    const latest = v.latest || '—';
    const upToDate = v.up_to_date;
    let badge, badgeColor;
    if      (upToDate === true)  { badge = '✓ aktualna';       badgeColor = '#4c4'; }
    else if (upToDate === false) { badge = '✗ nieaktualna';    badgeColor = '#e55'; }
    else                         { badge = '? nie sprawdzono'; badgeColor = '#aaa'; }
    const releaseLink = v.release_url  ? ` <a href="${escHtml(v.release_url)}" target="_blank" style="color:#7af;font-size:0.8rem">→ release</a>` : '';
    const publishedAt = v.published_at ? `<span style="color:#666;font-size:0.78rem"> (${v.published_at.slice(0,10)})</span>` : '';
    const cacheAge    = typeof v.cache_age_s === 'number' ? `<span style="color:#555;font-size:0.75rem"> cache: ${v.cache_age_s}s</span>` : '';
    return `
      <div style="padding:0.4rem 0;border-bottom:1px solid #222">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="color:#aaa">simc_version</span>
          <span style="color:${badgeColor};font-weight:600">${badge}</span>
        </div>
        <div style="font-size:0.82rem;color:#888;margin-top:0.2rem;display:flex;flex-wrap:wrap;gap:0.6rem">
          <span>lokalna: <b style="color:#ccc">${escHtml(local)}</b></span>
          <span>najnowsza: <b style="color:#ccc">${escHtml(latest)}</b>${publishedAt}${releaseLink}</span>
          ${cacheAge}
        </div>
      </div>`;
  }
  const strVal = String(val);
  const isOk   = strVal === 'ok' || strVal.startsWith('ok');
  const color  = isOk ? '#4c4' : '#e55';
  const icon   = isOk ? '✓' : '✗';
  return `<div style="display:flex;justify-content:space-between;padding:0.3rem 0;border-bottom:1px solid #222">
    <span>${escHtml(key)}</span>
    <span style="color:${color}">${icon} ${escHtml(strVal)}</span>
  </div>`;
}

async function loadHealth() {
  const container = document.getElementById('health-status');
  container.innerHTML = '<p class="empty">Ładowanie...</p>';
  const res = await fetch('/admin/api/health');
  if (!res.ok) { container.innerHTML = '<p class="empty">Błąd ładowania.</p>'; return; }
  const data = await res.json();
  const html = Object.entries(data).map(([k, v]) => _renderHealthRow(k, v)).join('');
  container.innerHTML = `<div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:0.5rem">${html}</div>`;
  markRefreshed('health');
}
