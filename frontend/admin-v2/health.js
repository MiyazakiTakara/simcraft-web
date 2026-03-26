// admin-v2/health.js
// Obsługuje zakładkę Health w panelu admin-v2:
//   - status serwisów + metryki systemowe
//   - wersja simc vs upstream
//   - WoW build cache
//   - alerty systemowe
//   - ręczny trigger rebuildu simc + polling statusu

(function () {
  const INTERVAL_MS   = 60_000;   // auto-refresh health co 60s
  const REBUILD_POLL_MS = 3_000;  // polling stanu rebuildu co 3s

  let _timer         = null;
  let _rebuildPoller = null;
  let _isActive      = false;
  let _isVisible     = true;
  let _isLoading     = false;

  // ───────────────────────────────────────
  // Publiczne API (wywoływane z tabs.js)
  // ───────────────────────────────────────
  window.loadHealth = function () {
    _isActive = true;
    _fetchHealth();
    _fetchAlerts();
    _startTimer();
    window.loadRebuildLog(0);   // auto-load historii przy wejściu na zakładkę
  };

  window.pauseHealth = function () {
    _isActive = false;
    _stopTimer();
  };

  // ───────────────────────────────────────
  // Page Visibility API
  // ───────────────────────────────────────
  document.addEventListener('visibilitychange', () => {
    _isVisible = !document.hidden;
    if (_isVisible && _isActive) {
      _fetchHealth();
      _startTimer();
    } else {
      _stopTimer();
    }
  });

  // ───────────────────────────────────────
  // Timer
  // ───────────────────────────────────────
  function _startTimer() {
    _stopTimer();
    if (!_isActive || !_isVisible) return;
    _timer = setInterval(() => {
      _fetchHealth();
      _fetchAlerts();
    }, INTERVAL_MS);
  }

  function _stopTimer() {
    if (_timer) { clearInterval(_timer); _timer = null; }
  }

  // ───────────────────────────────────────
  // Health fetch + render
  // ───────────────────────────────────────
  async function _fetchHealth() {
    if (_isLoading) return;
    _isLoading = true;
    _setLiveIndicator('loading');

    try {
      const res = await fetch('/admin/api/health');
      if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      _renderHealth(data);
      _fetchAlerts();
      _setLiveIndicator('ok');
    } catch (err) {
      console.error('[health] fetch error', err);
      _setLiveIndicator('error');
    } finally {
      _isLoading = false;
    }
  }

  function _setLiveIndicator(state) {
    const el = document.getElementById('refresh-label-health');
    if (!el) return;
    el.style.color = { loading: '#666', ok: '#4c4', error: '#e55' }[state] || '#666';
    const now = new Date().toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    if (state === 'ok')      el.textContent = `\u2022 od\u015bwie\u017cono ${now}`;
    else if (state === 'loading') el.textContent = '\ud83d\udd04 ładowanie...';
    else                     el.textContent = '\u26a0\ufe0f b\u0142\u0105d od\u015bwie\u017cania';
  }

  // ───────────────────────────────────────
  // Render health
  // ───────────────────────────────────────
  function _statusBadge(val) {
    const s   = String(val || '');
    const ok  = s.startsWith('ok');
    const col = ok ? '#4c4' : '#e55';
    const ico = ok ? '\u2713' : '\u2717';
    return `<span style="color:${col};font-weight:600">${ico} ${escHtml(s)}</span>`;
  }

  function _pctBar(pct, warnAt = 75, dangerAt = 90) {
    const col = pct >= dangerAt ? '#e55' : pct >= warnAt ? '#f4a01c' : '#4c4';
    return `
      <div style="display:flex;align-items:center;gap:0.5rem;margin-top:0.25rem">
        <div style="flex:1;background:#222;border-radius:3px;height:5px;overflow:hidden">
          <div style="height:100%;width:${Math.min(pct,100)}%;background:${col};transition:width .4s"></div>
        </div>
        <span style="font-size:0.78rem;color:${col};min-width:2.8rem;text-align:right">${pct}%</span>
      </div>`;
  }

  function _card(title, content) {
    return `
      <div class="health-card" style="background:#141414;border:1px solid #2a2a2a;border-radius:8px;
           padding:1rem;margin-bottom:1rem">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.05em;color:#555;
             margin-bottom:0.6rem">${title}</div>
        ${content}
      </div>`;
  }

  function _row(label, valueHtml) {
    return `
      <div style="display:flex;justify-content:space-between;align-items:center;
           padding:0.28rem 0;border-bottom:1px solid #1e1e1e;gap:0.5rem">
        <span style="color:#888;font-size:0.85rem">${escHtml(label)}</span>
        <span style="font-size:0.85rem">${valueHtml}</span>
      </div>`;
  }

  function _renderHealth(d) {
    const wrap = document.getElementById('health-v2-content');
    if (!wrap) return;

    // --- Serwisy ---
    const svcRows = [
      _row('database',    _statusBadge(d.database)),
      _row('simc binary', _statusBadge(d.simc_binary)),
      _row('keycloak',    _statusBadge(d.keycloak)),
    ].join('');

    // --- simc_version ---
    let simcVerContent = '';
    const sv = d.simc_version;
    if (sv && !sv.error) {
      const upToDate  = sv.up_to_date;
      let badge, bcol;
      if      (upToDate === true)  { badge = 'Aktualna';       bcol = '#4c4'; }
      else if (upToDate === false) { badge = 'Nieaktualna';    bcol = '#e55'; }
      else                         { badge = 'Nie sprawdzono'; bcol = '#888'; }
      const commitInfo = sv.last_commit_sha
        ? `<a href="${escHtml(sv.last_commit_url || '#')}" target="_blank"
              style="color:#7af;font-size:0.78rem">${escHtml(sv.last_commit_sha)}</a>
           <span style="color:#555;font-size:0.75rem"> (${(sv.last_commit_date || '').slice(0,10)})</span>`
        : '\u2014';
      const cacheAge = sv.cache_age_s != null
        ? `<span style="color:#444;font-size:0.75rem"> cache: ${sv.cache_age_s}s</span>`
        : '';
      simcVerContent = [
        _row('Lokalna',       `<b style="color:#ccc">${escHtml(sv.local  || '\u2014')}</b>`),
        _row('Upstream',      `<b style="color:#ccc">${escHtml(sv.latest || '\u2014')}</b>`),
        _row('Status',        `<span style="color:${bcol};font-weight:600">${badge}</span>${cacheAge}`),
        _row('Ostatni commit', commitInfo),
      ].join('');
    } else {
      simcVerContent = `<span style="color:#e55;font-size:0.85rem">${escHtml((sv && sv.error) || 'unavailable')}</span>`;
    }

    // --- WoW build ---
    let wowContent = '';
    const wb = d.wow_build;
    if (wb) {
      if (wb.error) {
        wowContent = `<span style="color:#e55;font-size:0.85rem">${escHtml(wb.error)}</span>`;
      } else {
        const age = wb.cache_age_s != null
          ? `<span style="color:#444;font-size:0.75rem"> cache: ${wb.cache_age_s}s</span>`
          : '';
        wowContent = [
          _row('Build',   `<b style="color:#ccc">${escHtml(wb.build || '\u2014')}</b>${age}`),
          _row('Wersja',  `<span style="color:#aaa">${escHtml(wb.version || '\u2014')}</span>`),
        ].join('');
      }
    } else {
      wowContent = `<span style="color:#555;font-size:0.85rem">Brak danych (cache zimny)</span>`;
    }

    // --- System ---
    const sysContent = [
      _row('CPU',  _pctBar(d.cpu_percent    || 0)),
      _row('RAM',  _pctBar(d.memory_percent || 0)),
      d.disk && !d.disk.error ? _row('Dysk',
        _pctBar(d.disk.used_pct || 0, 75, 90) +
        `<span style="color:#555;font-size:0.75rem;display:block;text-align:right;margin-top:0.1rem">
          ${_fmtBytes((d.disk.total_bytes || 0) - (d.disk.free_bytes || 0))} / ${_fmtBytes(d.disk.total_bytes || 0)}
         </span>`,
      ) : _row('Dysk', '<span style="color:#555">unavailable</span>'),
      _row('Aktywne joby', `<b style="color:#ccc">${d.active_jobs ?? '\u2014'}</b>`),
    ].join('');

    // --- Last rebuild summary ---
    const lr = d.last_rebuild;
    let rebuildSummary = `<span style="color:#555;font-size:0.85rem">Brak historii</span>`;
    if (lr) {
      const stCol = lr.status === 'success' ? '#4c4' : lr.status === 'running' ? '#f4a01c' : '#e55';
      rebuildSummary = [
        _row('Status',      `<span style="color:${stCol};font-weight:600">${escHtml(lr.status)}</span>`),
        _row('Trigger',     `<span style="color:#aaa">${escHtml(lr.triggered_by || '\u2014')}</span>`),
        _row('WoW build',   `<span style="color:#aaa">${escHtml(lr.wow_build    || '\u2014')}</span>`),
        _row('simc przed',  `<span style="color:#888">${escHtml(lr.simc_before  || '\u2014')}</span>`),
        _row('simc po',     `<span style="color:#888">${escHtml(lr.simc_after   || '\u2014')}</span>`),
        _row('Start',       `<span style="color:#555;font-size:0.78rem">${escHtml((lr.started_at  || '').replace('T',' ').slice(0,19))}</span>`),
        _row('Koniec',      `<span style="color:#555;font-size:0.78rem">${escHtml((lr.finished_at || '').replace('T',' ').slice(0,19) || '\u2014')}</span>`),
      ].join('');
    }

    // --- Rebuild button + live state ---
    const rs = d.rebuild_state || {};
    const isRunning = rs.status === 'running';
    const rebuildBtnSection = `
      <div style="margin-top:0.8rem;display:flex;gap:0.6rem;align-items:center;flex-wrap:wrap">
        <button class="btn secondary btn-sm" onclick="window.triggerSimcRebuild()"
                ${isRunning ? 'disabled' : ''}>
          ${isRunning ? '\ud83d\udd04 Rebuild w toku\u2026' : '\u26a1 Rebuild simc'}
        </button>
        <span id="rebuild-state-label" style="font-size:0.8rem;color:#555">
          ${isRunning
            ? `Uruchomiony przez ${escHtml(rs.triggered_by || '?')} o ${escHtml((rs.started_at || '').replace('T',' ').slice(0,19))}`
            : (rs.status === 'success' ? '<span style="color:#4c4">\u2713 sukces</span>'
               : rs.status === 'error' ? `<span style="color:#e55">\u2717 ${escHtml(rs.error || 'b\u0142\u0105d')}</span>`
               : '')}
        </span>
      </div>`;

    wrap.innerHTML =
      _card('Serwisy', svcRows) +
      _card('Wersja SimulationCraft', simcVerContent) +
      _card('WoW Retail Build', wowContent) +
      _card('System', sysContent) +
      _card('Ostatni Rebuild SimC',
        rebuildSummary + rebuildBtnSection,
      );
  }

  function _fmtBytes(b) {
    if (!b) return '\u2014';
    if (b >= 1073741824) return (b / 1073741824).toFixed(1) + ' GB';
    if (b >= 1048576)    return (b / 1048576).toFixed(0) + ' MB';
    return (b / 1024).toFixed(0) + ' KB';
  }

  // ───────────────────────────────────────
  // Alerts fetch + render
  // ───────────────────────────────────────
  async function _fetchAlerts(showResolved = false) {
    const section = document.getElementById('alerts-v2-section');
    if (!section) return;
    try {
      const res = await fetch(`/admin/api/alerts?resolved=${showResolved}&limit=50`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      _renderAlerts(data, showResolved);
      _updateAlertBadge(data.active_count || 0);
    } catch (err) {
      console.error('[health] alerts fetch error', err);
    }
  }

  const _ALERT_LABELS = {
    queue_overload:             '\ud83d\udea6 Przeci\u0105\u017cenie kolejki',
    low_disk:                   '\ud83d\udcbe Ma\u0142o miejsca na dysku',
    error_rate:                 '\ud83d\udcdb Wysoka stopa b\u0142\u0119d\u00f3w',
    'service_down:database':    '\ud83d\uddc4\ufe0f Baza danych',
    'service_down:simc_binary': '\u2699\ufe0f Binarny simc',
  };

  function _alertLabel(type) {
    return _ALERT_LABELS[type] || ('\u26a0\ufe0f ' + type);
  }

  function _renderAlerts(data, showResolved) {
    const section = document.getElementById('alerts-v2-section');
    if (!section) return;
    const items       = data.items       || [];
    const activeCount = data.active_count || 0;

    const headerBadge = activeCount > 0
      ? `<span style="background:#e55;color:#fff;border-radius:10px;padding:0.1rem 0.5rem;
              font-size:0.78rem;font-weight:700;margin-left:0.4rem">${activeCount}</span>`
      : `<span style="color:#4c4;font-size:0.82rem;margin-left:0.4rem">\u2713 brak aktywnych</span>`;

    const resolveAllBtn = activeCount > 0
      ? `<button class="btn secondary btn-sm" onclick="window.resolveAllAlertsV2()"
             style="font-size:0.78rem">Zignoruj wszystkie</button>`
      : '';

    const toggleBtn = `<button class="btn secondary btn-sm"
      onclick="window._healthToggleAlerts(${!showResolved})"
      style="font-size:0.78rem">${showResolved ? 'Tylko aktywne' : 'Poka\u017c histori\u0119'}</button>`;

    const rows = items.length
      ? items.map(a => {
          const stCol   = a.resolved ? '#555' : '#e5a000';
          const resolveBtn = !a.resolved
            ? `<button class="btn secondary btn-sm" style="padding:0.15rem 0.5rem;font-size:0.75rem"
                 onclick="window.resolveAlertV2(${a.id})">Zignoruj</button>`
            : `<span style="color:#555;font-size:0.78rem">\u2713</span>`;
          return `
            <div style="display:flex;justify-content:space-between;align-items:flex-start;
                        padding:0.45rem 0;border-bottom:1px solid #1e1e1e;gap:0.5rem">
              <div style="flex:1;min-width:0">
                <div style="font-size:0.87rem;color:${stCol};font-weight:600;margin-bottom:0.1rem">
                  ${escHtml(_alertLabel(a.alert_type))}
                </div>
                <div style="font-size:0.8rem;color:#888;word-break:break-word">
                  ${escHtml(a.message)}
                </div>
                <div style="font-size:0.73rem;color:#444;margin-top:0.1rem">
                  od: ${escHtml((a.triggered_at || '').replace('T',' ').slice(0,16))}
                  ${a.resolved && a.resolved_at
                    ? ` &middot; rozwi\u0105zany: ${escHtml((a.resolved_at).replace('T',' ').slice(0,16))}`
                    : ''}
                </div>
              </div>
              <div style="flex-shrink:0">${resolveBtn}</div>
            </div>`;
        }).join('')
      : `<p style="color:#555;font-size:0.85rem;padding:0.5rem 0">
           ${showResolved ? 'Brak alert\u00f3w w historii.' : 'Brak aktywnych alert\u00f3w.'}
         </p>`;

    section.innerHTML = `
      <div style="background:#141414;border:1px solid #2a2a2a;border-radius:8px;padding:1rem;margin-bottom:1rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.7rem;flex-wrap:wrap;gap:0.4rem">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.05em;color:#555">
            Alerty systemowe${headerBadge}
          </div>
          <div style="display:flex;gap:0.4rem">${resolveAllBtn}${toggleBtn}</div>
        </div>
        <div id="alerts-v2-list">${rows}</div>
      </div>`;
  }

  function _updateAlertBadge(count) {
    const badge = document.getElementById('alert-badge-health');
    if (!badge) return;
    badge.textContent  = count > 0 ? String(count) : '';
    badge.style.display = count > 0 ? 'inline-flex' : 'none';
  }

  // ───────────────────────────────────────
  // Public helpers (onclick-friendly)
  // ───────────────────────────────────────
  window._healthToggleAlerts = function (showResolved) {
    _fetchAlerts(showResolved);
  };

  window.resolveAlertV2 = async function (alertId) {
    const res = await fetch(`/admin/api/alerts/${alertId}/resolve`, { method: 'POST' });
    if (!res.ok) { toast && toast('B\u0142\u0105d', '#e55'); return; }
    _fetchAlerts();
    _fetchBadge();
  };

  window.resolveAllAlertsV2 = async function () {
    if (typeof adminConfirm === 'function') {
      const ok = await adminConfirm('\ud83d\udd14 Alerty', 'Zignorowa\u0107 wszystkie aktywne alerty?', 'Zignoruj wszystkie', false);
      if (!ok) return;
    }
    const res = await fetch('/admin/api/alerts/resolve-all', { method: 'POST' });
    if (!res.ok) { toast && toast('B\u0142\u0105d', '#e55'); return; }
    const data = await res.json();
    toast && toast(`\u2705 Zignorowano ${data.resolved_count} alert\u00f3w`, '#7ecf7e');
    _fetchAlerts();
    _fetchBadge();
  };

  // ───────────────────────────────────────
  // Alert badge (globalny refresh)
  // ───────────────────────────────────────
  async function _fetchBadge() {
    try {
      const res = await fetch('/admin/api/alerts/badge');
      if (!res.ok) return;
      const d = await res.json();
      _updateAlertBadge(d.active_count || 0);
    } catch (_) {}
  }

  // Eksportuj do użytku globalnego (np. z dashboard.js / autorefresh)
  window.refreshAlertBadgeV2 = _fetchBadge;

  // ───────────────────────────────────────
  // SimC Rebuild
  // ───────────────────────────────────────
  window.triggerSimcRebuild = async function () {
    if (typeof adminConfirm === 'function') {
      const ok = await adminConfirm(
        '\u26a1 Rebuild SimC',
        'Uruchomi\u0107 r\u0119czny rebuild SimulationCraft? Operacja potrwa kilka minut.',
        'Uruchom rebuild', true,
      );
      if (!ok) return;
    }
    const res = await fetch('/admin/api/simc/rebuild', { method: 'POST' });
    if (!res.ok) { toast && toast('B\u0142\u0105d uruchamiania rebuildu', '#e55'); return; }
    const data = await res.json();
    if (data.status === 'already_running') {
      toast && toast('\u26a0\ufe0f Rebuild ju\u017c trwa', '#f4a01c');
    } else {
      toast && toast('\ud83d\udd04 Rebuild uruchomiony', '#7ecf7e');
      _startRebuildPolling();
    }
  };

  function _startRebuildPolling() {
    if (_rebuildPoller) return;
    _rebuildPoller = setInterval(async () => {
      try {
        const res = await fetch('/admin/api/simc/rebuild-state');
        if (!res.ok) return;
        const state = await res.json();
        _updateRebuildStateLabel(state);
        if (state.status !== 'running') {
          clearInterval(_rebuildPoller);
          _rebuildPoller = null;
          // odśwież całe health + historię po zakończeniu rebuildu
          _fetchHealth();
          window.loadRebuildLog(0);   // odśwież tabelę historii
        }
      } catch (_) {}
    }, REBUILD_POLL_MS);
  }

  function _updateRebuildStateLabel(state) {
    const lbl = document.getElementById('rebuild-state-label');
    if (!lbl) return;
    const isRunning = state.status === 'running';
    const btn = lbl.previousElementSibling;
    if (btn) {
      btn.disabled     = isRunning;
      btn.textContent  = isRunning ? '\ud83d\udd04 Rebuild w toku\u2026' : '\u26a1 Rebuild simc';
    }
    if (isRunning) {
      lbl.innerHTML = `Uruchomiony przez ${escHtml(state.triggered_by || '?')}`;
      lbl.style.color = '#f4a01c';
    } else if (state.status === 'success') {
      lbl.innerHTML   = `<span style="color:#4c4">\u2713 sukces \u2014 ${escHtml(state.simc_after || '')}</span>`;
    } else if (state.status === 'error') {
      lbl.innerHTML   = `<span style="color:#e55">\u2717 ${escHtml(state.error || 'b\u0142\u0105d')}</span>`;
    } else {
      lbl.textContent = '';
    }
  }

  // Rebuild log (tabela historii) — wywoływane opcjonalnie z HTML
  window.loadRebuildLog = async function (offset = 0) {
    const container = document.getElementById('rebuild-log-table');
    if (!container) return;
    container.innerHTML = '<p style="color:#555;font-size:0.85rem">\u0141adowanie...</p>';
    try {
      const res = await fetch(`/admin/api/simc/rebuild-log?limit=10&offset=${offset}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      if (!d.items.length) {
        container.innerHTML = '<p style="color:#555;font-size:0.85rem;padding:0.5rem 0">Brak historii rebuild\u00f3w.</p>';
        return;
      }
      const prevBtn = offset > 0
        ? `<button class="btn secondary btn-sm" onclick="loadRebuildLog(${offset - 10})">\u2190 Poprzednie</button>`
        : '';
      const nextBtn = (offset + 10) < d.total
        ? `<button class="btn secondary btn-sm" onclick="loadRebuildLog(${offset + 10})">Nast\u0119pne \u2192</button>`
        : '';
      container.innerHTML = `
        <table style="width:100%;border-collapse:collapse;font-size:0.8rem">
          <thead>
            <tr style="color:#555;text-transform:uppercase;font-size:0.68rem;border-bottom:1px solid #2a2a2a">
              <th style="text-align:left;padding:0.3rem 0.4rem">Data</th>
              <th style="text-align:left;padding:0.3rem 0.4rem">Trigger</th>
              <th style="text-align:left;padding:0.3rem 0.4rem">Status</th>
              <th style="text-align:left;padding:0.3rem 0.4rem">WoW build</th>
              <th style="text-align:left;padding:0.3rem 0.4rem">simc przed \u2192 po</th>
            </tr>
          </thead>
          <tbody>
            ${d.items.map(r => {
              const stCol = r.status === 'success' ? '#4c4' : r.status === 'running' ? '#f4a01c' : '#e55';
              return `<tr style="border-bottom:1px solid #1a1a1a">
                <td style="padding:0.3rem 0.4rem;color:#555">${escHtml((r.started_at || '').replace('T',' ').slice(0,16))}</td>
                <td style="padding:0.3rem 0.4rem;color:#aaa">${escHtml(r.triggered_by || '\u2014')}</td>
                <td style="padding:0.3rem 0.4rem;color:${stCol};font-weight:600">${escHtml(r.status)}</td>
                <td style="padding:0.3rem 0.4rem;color:#888">${escHtml(r.wow_build || '\u2014')}</td>
                <td style="padding:0.3rem 0.4rem;color:#666;font-size:0.75rem">
                  ${escHtml(r.simc_before || '\u2014')} \u2192 ${escHtml(r.simc_after || '\u2014')}
                </td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
        <div style="display:flex;justify-content:space-between;margin-top:0.6rem">
          <span style="color:#555;font-size:0.78rem">\u0141\u0105cznie: ${d.total}</span>
          <div style="display:flex;gap:0.4rem">${prevBtn}${nextBtn}</div>
        </div>`;
    } catch (err) {
      container.innerHTML = `<p style="color:#e55;font-size:0.85rem">B\u0142\u0105d \u0142adowania historii.</p>`;
    }
  };

})();
