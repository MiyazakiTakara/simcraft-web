// ---------- Logs (server) ----------

let _logsOffset = 0;
let _logsLimit  = 50;
let _logsTotal  = 0;
let _logsLevel  = '';

async function loadLogs() {
  _logsOffset = 0;
  _logsLevel  = document.getElementById('log-level')?.value || '';
  await _fetchLogs();
  markRefreshed('logs');
}

async function _fetchLogs() {
  const params = new URLSearchParams({ limit: _logsLimit, offset: _logsOffset });
  if (_logsLevel) params.set('level', _logsLevel);

  const list    = document.getElementById('log-list');
  const info    = document.getElementById('logs-pagination-info');
  const btnPrev = document.getElementById('logs-btn-prev');
  const btnNext = document.getElementById('logs-btn-next');

  try {
    const res = await fetch(`/admin/api/logs?${params}`);
    if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
    const data = await res.json();

    _logsTotal = data.total;

    if (!data.items.length) {
      list.innerHTML = `<p class="empty">Brak logów dla wybranych filtrów.</p>`;
    } else {
      list.innerHTML = data.items.map(l => `
        <div class="log-entry">
          <span class="time">${l.created_at ? l.created_at.replace('T',' ').slice(0,19) : ''}</span>
          <span class="level ${l.level}">${l.level}</span>
          <span class="msg">${escHtml(l.message)}</span>
          ${l.context ? `<div class="ctx">${escHtml(l.context)}</div>` : ''}
        </div>
      `).join('');
    }

    const from = _logsTotal === 0 ? 0 : _logsOffset + 1;
    const to   = Math.min(_logsOffset + _logsLimit, _logsTotal);
    if (info)    info.textContent    = `${from}–${to} z ${_logsTotal}`;
    if (btnPrev) btnPrev.disabled    = _logsOffset === 0;
    if (btnNext) btnNext.disabled    = _logsOffset + _logsLimit >= _logsTotal;

  } catch (e) {
    list.innerHTML = `<p class="empty" style="color:var(--error)">Błąd ładowania: ${escHtml(String(e))}</p>`;
  }
}

function logsPrev() {
  if (_logsOffset < _logsLimit) return;
  _logsOffset -= _logsLimit;
  _fetchLogs();
}

function logsNext() {
  if (_logsOffset + _logsLimit >= _logsTotal) return;
  _logsOffset += _logsLimit;
  _fetchLogs();
}

async function clearLogs(olderThanDays) {
  const label = olderThanDays ? `starsze niż ${olderThanDays} dni` : 'WSZYSTKIE';
  const ok = await showConfirm(
    'Usuń logi',
    `Czy na pewno chcesz usunąć logi (${label})? Operacja jest nieodwracalna.`,
  );
  if (!ok) return;

  const url = '/admin/api/logs' + (olderThanDays ? `?older_than_days=${olderThanDays}` : '');
  const res = await fetch(url, { method: 'DELETE' });
  if (!res.ok) { showToast('Błąd usuwania logów', 'error'); return; }
  const data = await res.json();
  showToast(`Usunięto ${data.deleted} logów`, 'success');
  loadLogs();
}
