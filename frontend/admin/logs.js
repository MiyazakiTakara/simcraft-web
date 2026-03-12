async function loadLogs() {
  const level = document.getElementById('log-level').value;
  const url   = '/admin/api/logs?limit=100' + (level ? '&level=' + level : '');
  const res   = await fetch(url);
  if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
  const logs = await res.json();
  const list = document.getElementById('log-list');
  if (!logs.length) { list.innerHTML = '<p class="empty">Brak logów.</p>'; return; }
  list.innerHTML = logs.map(l => `
    <div class="log-entry">
      <span class="time">${l.created_at ? l.created_at.replace('T',' ').slice(0,19) : ''}</span>
      <span class="level ${l.level}">${l.level}</span>
      <span class="msg">${escHtml(l.message)}</span>
      ${l.context ? `<div class="ctx">${escHtml(l.context)}</div>` : ''}
    </div>
  `).join('');
  markRefreshed('logs');
}
