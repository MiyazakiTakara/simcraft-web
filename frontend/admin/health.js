function _renderHealthRow(key, val) {
  if (key === 'simc_version' && val && typeof val === 'object') {
    const v = val;
    const local  = v.local  || '—';
    const latest = v.latest || '—';
    const upToDate = v.up_to_date;
    let badge, badgeColor;
    if      (upToDate === true)  { badge = adminT('admin.health.up_to_date');   badgeColor = '#4c4'; }
    else if (upToDate === false) { badge = adminT('admin.health.outdated');      badgeColor = '#e55'; }
    else                         { badge = adminT('admin.health.not_checked');   badgeColor = '#aaa'; }
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
          <span>${adminT('admin.health.local')}: <b style="color:#ccc">${escHtml(local)}</b></span>
          <span>${adminT('admin.health.latest')}: <b style="color:#ccc">${escHtml(latest)}</b>${publishedAt}${releaseLink}</span>
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
  container.innerHTML = `<p class="empty">${adminT('common.loading')}</p>`;
  const res = await fetch('/admin/api/health');
  if (!res.ok) { container.innerHTML = `<p class="empty">${adminT('admin.toast.error_generic')}</p>`; return; }
  const data = await res.json();
  const html = Object.entries(data).map(([k, v]) => _renderHealthRow(k, v)).join('');
  container.innerHTML = `<div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:0.5rem">${html}</div>`;
  markRefreshed('health');
  // odśwież badge po health checku (health check wyzwala evaluate_alerts)
  refreshAlertBadge();
  // załaduj sekcję alertów
  loadAlerts();
}

// ---------- Results Cleanup ----------

function _fmtBytes(bytes) {
  if (bytes === null || bytes === undefined) return '—';
  if (bytes >= 1024 ** 3) return (bytes / 1024 ** 3).toFixed(2) + ' GB';
  if (bytes >= 1024 ** 2) return (bytes / 1024 ** 2).toFixed(1) + ' MB';
  if (bytes >= 1024)      return (bytes / 1024).toFixed(1) + ' KB';
  return bytes + ' B';
}

function _diskBarColor(freeBytes, totalBytes) {
  if (!totalBytes) return '#555';
  const usedPct = (totalBytes - freeBytes) / totalBytes;
  if (usedPct >= 0.9) return '#e55';
  if (usedPct >= 0.75) return '#e5a000';
  return '#4c4';
}

async function loadResultsStats() {
  const section = document.getElementById('results-cleanup-section');
  if (!section) return;
  section.innerHTML = `<p class="empty">${adminT('common.loading')}</p>`;

  const res = await fetch('/admin/api/results/stats');
  if (!res.ok) { section.innerHTML = `<p class="empty">${adminT('admin.toast.error_generic')}</p>`; return; }
  const d = await res.json();

  const usedBytes  = d.total_disk_bytes && d.free_bytes != null ? d.total_disk_bytes - d.free_bytes : null;
  const usedPct    = d.total_disk_bytes ? Math.round((usedBytes / d.total_disk_bytes) * 100) : null;
  const barColor   = _diskBarColor(d.free_bytes, d.total_disk_bytes);

  const diskBar = d.total_disk_bytes ? `
    <div style="margin:0.5rem 0 0.8rem">
      <div style="display:flex;justify-content:space-between;font-size:0.8rem;color:#888;margin-bottom:0.3rem">
        <span>Dysk: ${_fmtBytes(usedBytes)} / ${_fmtBytes(d.total_disk_bytes)} (${usedPct}% zajęte)</span>
        <span style="color:#aaa">Wolne: <b style="color:#ccc">${_fmtBytes(d.free_bytes)}</b></span>
      </div>
      <div style="background:#222;border-radius:4px;height:6px;overflow:hidden">
        <div style="height:100%;width:${usedPct}%;background:${barColor};transition:width 0.4s"></div>
      </div>
    </div>` : '';

  section.innerHTML = `
    <div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:1rem;margin-top:1rem">
      <div style="font-weight:600;margin-bottom:0.7rem;color:#f4a01c">🗂️ Pliki wyników symulacji</div>

      <div style="display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:0.6rem">
        <div style="text-align:center">
          <div style="font-size:1.5rem;font-weight:700;color:#ccc">${d.file_count.toLocaleString()}</div>
          <div style="font-size:0.78rem;color:#666">plików .json</div>
        </div>
        <div style="text-align:center">
          <div style="font-size:1.5rem;font-weight:700;color:#ccc">${_fmtBytes(d.total_bytes)}</div>
          <div style="font-size:0.78rem;color:#666">zajmowane</div>
        </div>
      </div>

      ${diskBar}

      <div style="display:flex;gap:0.6rem;flex-wrap:wrap;margin-bottom:1rem">
        <button class="btn secondary btn-sm" onclick="cleanupResults('errors')">
          ⚠️ Usuń błędne
        </button>
        <button class="btn secondary btn-sm" onclick="cleanupResults('30')">
          🗑️ Starsze niż 30 dni
        </button>
        <button class="btn secondary btn-sm" onclick="cleanupResults('90')">
          🗑️ Starsze niż 90 dni
        </button>
        <button class="btn secondary btn-sm" onclick="promptCleanupCustom()">
          ⚙️ Niestandardowe…
        </button>
      </div>

      <div style="border-top:1px solid #2a2a2a;padding-top:0.8rem">
        <div style="font-size:0.85rem;color:#aaa;margin-bottom:0.4rem">Auto-cleanup (dni; 0 = wyłączony)</div>
        <div style="display:flex;gap:0.5rem;align-items:center">
          <input type="number" id="auto-cleanup-days" min="0" max="365"
            value="${d.auto_cleanup_days}"
            style="width:80px;background:#111;border:1px solid #333;color:#ccc;padding:0.3rem 0.5rem;border-radius:4px;font-size:0.9rem">
          <button class="btn secondary btn-sm" onclick="saveAutoCleanup()">Zapisz</button>
          <span style="font-size:0.78rem;color:#555">(uruchamiane co 24h przy starcie)</span>
        </div>
      </div>
    </div>
  `;
}

async function cleanupResults(mode, customDays) {
  let confirmMsg, params;

  if (mode === 'errors') {
    confirmMsg = 'Czy na pewno chcesz usunąć wszystkie symulacje z błędem? Operacji nie można cofnąć.';
    params = 'errors_only=true';
  } else if (mode === 'custom') {
    confirmMsg = `Czy na pewno chcesz usunąć symulacje starsze niż ${customDays} dni?`;
    params = `older_than_days=${customDays}`;
  } else {
    const days = parseInt(mode);
    confirmMsg = `Czy na pewno chcesz usunąć symulacje starsze niż ${days} dni?`;
    params = `older_than_days=${days}`;
  }

  const ok = await adminConfirm('🗑️ Cleanup wyników', confirmMsg, 'Usuń', true);
  if (!ok) return;

  const res = await fetch(`/admin/api/results/cleanup?${params}`, { method: 'POST' });
  if (!res.ok) { toast(adminT('admin.toast.error_generic'), '#e55'); return; }
  const data = await res.json();
  toast(`✅ Usunięto ${data.deleted_count} symulacji (${data.deleted_files} plików)`, '#7ecf7e');
  loadResultsStats();
}

async function promptCleanupCustom() {
  const val = prompt('Usuń symulacje starsze niż ile dni?', '60');
  if (!val) return;
  const days = parseInt(val);
  if (isNaN(days) || days < 1) { toast('Podaj liczbę dni ≥ 1', '#e55'); return; }
  await cleanupResults('custom', days);
}

async function saveAutoCleanup() {
  const input = document.getElementById('auto-cleanup-days');
  const days  = parseInt(input?.value ?? '0');
  if (isNaN(days) || days < 0 || days > 365) {
    toast('Wartość musi być w zakresie 0–365', '#e55');
    return;
  }
  const res = await fetch('/admin/api/config', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auto_cleanup_days: days }),
  });
  if (res.ok) {
    toast(days === 0 ? '✅ Auto-cleanup wyłączony' : `✅ Auto-cleanup: co ${days} dni`, '#7ecf7e');
  } else {
    toast(adminT('admin.toast.error_generic'), '#e55');
  }
}

// ---------- Alerts Section (#58) ----------

const _ALERT_TYPE_LABELS = {
  queue_overload:              '🚦 Przeciążenie kolejki',
  low_disk:                    '💾 Mało miejsca na dysku',
  error_rate:                  '📛 Wysoka stopa błędów',
  'service_down:database':     '🗄️ Baza danych',
  'service_down:simc_binary':  '⚙️ Binarny simc',
};

function _alertTypeLabel(type) {
  return _ALERT_TYPE_LABELS[type] || ('⚠️ ' + type);
}

function _alertRowHtml(alert) {
  const since = fmt(alert.triggered_at);
  const resolvedInfo = alert.resolved
    ? `<span style="color:#555;font-size:0.75rem"> · rozwiązany ${fmt(alert.resolved_at)}</span>`
    : '';
  const resolveBtn = !alert.resolved
    ? `<button class="btn secondary btn-sm" style="padding:0.15rem 0.6rem;font-size:0.78rem"
         onclick="resolveAlert(${alert.id})">Zignoruj</button>`
    : `<span style="color:#555;font-size:0.78rem">✓</span>`;
  return `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;
                padding:0.5rem 0;border-bottom:1px solid #1e1e1e;gap:0.5rem">
      <div style="flex:1;min-width:0">
        <div style="font-size:0.88rem;color:#e5a000;font-weight:600;margin-bottom:0.15rem">
          ${escHtml(_alertTypeLabel(alert.alert_type))}
        </div>
        <div style="font-size:0.82rem;color:#aaa;word-break:break-word">
          ${escHtml(alert.message)}
        </div>
        <div style="font-size:0.75rem;color:#555;margin-top:0.15rem">
          od: ${escHtml(since)}${resolvedInfo}
        </div>
      </div>
      <div style="flex-shrink:0">${resolveBtn}</div>
    </div>`;
}

async function loadAlerts(showResolved = false) {
  const section = document.getElementById('alerts-section');
  if (!section) return;

  const url = `/admin/api/alerts?resolved=${showResolved}&limit=50`;
  const res = await fetch(url);
  if (!res.ok) {
    section.innerHTML = `<p class="empty" style="color:#e55">Błąd ładowania alertów.</p>`;
    return;
  }
  const data = await res.json();
  const items = data.items || [];
  const activeCount = data.active_count || 0;

  const headerBadge = activeCount > 0
    ? `<span style="background:#e55;color:#fff;border-radius:10px;padding:0.1rem 0.5rem;
                   font-size:0.78rem;font-weight:700;margin-left:0.4rem">${activeCount}</span>`
    : `<span style="color:#4c4;font-size:0.82rem;margin-left:0.4rem">✓ brak aktywnych</span>`;

  const resolveAllBtn = activeCount > 0
    ? `<button class="btn secondary btn-sm" onclick="resolveAllAlerts()"
         style="font-size:0.78rem">Zignoruj wszystkie</button>`
    : '';

  const toggleLabel = showResolved ? 'Pokaż tylko aktywne' : 'Pokaż historię';
  const toggleBtn = `<button class="btn secondary btn-sm"
    onclick="loadAlerts(${!showResolved})" style="font-size:0.78rem">${toggleLabel}</button>`;

  const rows = items.length
    ? items.map(_alertRowHtml).join('')
    : `<p class="empty" style="color:#555;font-size:0.85rem;padding:0.5rem 0">
         ${showResolved ? 'Brak alertów w historii.' : 'Brak aktywnych alertów.'}
       </p>`;

  section.innerHTML = `
    <div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:1rem;margin-bottom:1rem">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.7rem;flex-wrap:wrap;gap:0.4rem">
        <div style="font-weight:600;color:#f4a01c">
          🔔 Alerty systemowe${headerBadge}
        </div>
        <div style="display:flex;gap:0.4rem">
          ${resolveAllBtn}
          ${toggleBtn}
        </div>
      </div>
      <div id="alerts-list">${rows}</div>
    </div>`;
}

async function resolveAlert(alertId) {
  const res = await fetch(`/admin/api/alerts/${alertId}/resolve`, { method: 'POST' });
  if (!res.ok) { toast(adminT('admin.toast.error_generic'), '#e55'); return; }
  toast('✅ Alert zignorowany', '#7ecf7e');
  loadAlerts();
  refreshAlertBadge();
}

async function resolveAllAlerts() {
  const ok = await adminConfirm('🔔 Alerty', 'Oznaczyć wszystkie aktywne alerty jako zignorowane?', 'Zignoruj wszystkie', false);
  if (!ok) return;
  const res = await fetch('/admin/api/alerts/resolve-all', { method: 'POST' });
  if (!res.ok) { toast(adminT('admin.toast.error_generic'), '#e55'); return; }
  const data = await res.json();
  toast(`✅ Zignorowano ${data.resolved_count} alertów`, '#7ecf7e');
  loadAlerts();
  refreshAlertBadge();
}
