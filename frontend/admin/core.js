// ---- Helpers ----

function toast(msg, color = '#eee') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.color = color;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

function fmt(ts) {
  if (!ts) return '\u2014';
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
  return d.toLocaleString('pl-PL');
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function setRefreshLabel(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

// Stub — nadpisywany przez tabs.js gdy jest dostępny.
function markRefreshed(tab) {
  const el = document.getElementById('refresh-label-' + tab);
  if (!el) return;
  const now = new Date().toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  el.textContent = now;
}

// ---- Generic Confirm Dialog ----
function adminConfirm(title = 'Potwierdź', message = '', confirmLabel = 'Potwierdź', dangerous = true) {
  return new Promise((resolve) => {
    const modal   = document.getElementById('confirm-modal');
    const titleEl = document.getElementById('confirm-modal-title');
    const msgEl   = document.getElementById('confirm-modal-message');
    const btnOk   = document.getElementById('confirm-modal-ok');
    const btnCancel = document.getElementById('confirm-modal-cancel');

    if (!modal) { resolve(window.confirm(message)); return; }

    if (titleEl) titleEl.textContent = title;
    if (msgEl)   msgEl.textContent   = message;
    if (btnOk) {
      btnOk.textContent = confirmLabel;
      btnOk.className   = 'btn ' + (dangerous ? 'danger' : 'primary');
    }

    modal.classList.remove('hidden');

    function cleanup() {
      modal.classList.add('hidden');
      btnOk.removeEventListener('click', onOk);
      btnCancel.removeEventListener('click', onCancel);
      modal.removeEventListener('click', onOverlay);
      document.removeEventListener('keydown', onKey);
    }

    function onOk()      { cleanup(); resolve(true);  }
    function onCancel()  { cleanup(); resolve(false); }
    function onOverlay(e){ if (e.target === modal) { cleanup(); resolve(false); } }
    function onKey(e)    { if (e.key === 'Escape')   { cleanup(); resolve(false); } }

    btnOk.addEventListener('click', onOk);
    btnCancel.addEventListener('click', onCancel);
    modal.addEventListener('click', onOverlay);
    document.addEventListener('keydown', onKey);
  });
}

// ---- WoW Class Colors ----

const CLASS_COLORS = {
  'Death Knight':  '#C41E3A',
  'Demon Hunter':  '#A330C9',
  'Druid':         '#FF7C0A',
  'Evoker':        '#33937F',
  'Hunter':        '#AAD372',
  'Mage':          '#3FC7EB',
  'Monk':          '#00FF98',
  'Paladin':       '#F48CBA',
  'Priest':        '#FFFFFF',
  'Rogue':         '#FFF468',
  'Shaman':        '#0070DD',
  'Warlock':       '#8788EE',
  'Warrior':       '#C69B3A',
};

const PLOTLY_LAYOUT_BASE = {
  paper_bgcolor: 'transparent',
  plot_bgcolor:  'transparent',
  font:          { color: '#aaa', size: 11 },
  margin:        { t: 10, r: 10, b: 40, l: 40 },
  xaxis: { gridcolor: '#222', linecolor: '#333', tickcolor: '#444', type: 'linear' },
  yaxis: { gridcolor: '#222', linecolor: '#333', tickcolor: '#444', rangemode: 'tozero' },
  showlegend: false,
};

const PLOTLY_CONFIG = { displayModeBar: false, responsive: true };

// ---- Global Error Handler ----

(function initAdminErrorHandler() {
  function sendError(payload) {
    try {
      fetch('/admin/api/client-error', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      }).catch(() => {});
    } catch (_) {}
  }

  window.addEventListener('error', (e) => {
    const payload = {
      type:    'uncaught_error',
      message: e.message || String(e),
      source:  e.filename || '',
      line:    e.lineno  || null,
      col:     e.colno   || null,
      stack:   e.error?.stack || null,
      url:     location.href,
      ts:      new Date().toISOString(),
    };
    console.error('[AdminErrorHandler]', payload);
    sendError(payload);
    toast('\u26a0\ufe0f B\u0142\u0105d JS: ' + (e.message || 'nieznany').slice(0, 60), '#e55');
  });

  window.addEventListener('unhandledrejection', (e) => {
    const reason  = e.reason;
    const message = reason instanceof Error ? reason.message : String(reason ?? 'unhandled rejection');
    const payload = {
      type:    'unhandled_rejection',
      message,
      stack:   reason instanceof Error ? reason.stack : null,
      url:     location.href,
      ts:      new Date().toISOString(),
    };
    console.error('[AdminErrorHandler]', payload);
    sendError(payload);
    toast('\u26a0\ufe0f Promise error: ' + message.slice(0, 60), '#e55');
  });
}());

// ---- Alert Badge (#58) ----

let _alertBadgeTimer = null;

async function refreshAlertBadge() {
  try {
    const res = await fetch('/admin/api/alerts/count');
    if (!res.ok) return;
    const { active_count } = await res.json();
    const hasAlerts = active_count > 0;

    const sidebarBadge = document.getElementById('badge-health');
    if (sidebarBadge) {
      if (hasAlerts) {
        sidebarBadge.textContent = active_count;
        sidebarBadge.style.display = 'inline-flex';
      } else {
        sidebarBadge.style.display = 'none';
      }
    }

    const topbarAlerts = document.getElementById('topbar-alerts');
    if (topbarAlerts) {
      topbarAlerts.style.display = hasAlerts ? 'inline-flex' : 'none';
    }

    const alertCount = document.getElementById('alert-count');
    if (alertCount) {
      alertCount.textContent = active_count;
    }
  } catch (_) {}
}

function startAlertBadgePolling(intervalMs = 60_000) {
  refreshAlertBadge();
  if (_alertBadgeTimer) clearInterval(_alertBadgeTimer);
  _alertBadgeTimer = setInterval(refreshAlertBadge, intervalMs);
}

// ---- Global Search (#62) ----
//
// label          = dokładna nazwa z nav-label w admin-v2.html
// group          = nazwa grupy z nav-group-label
// keywords       = dodatkowe synonimy / angielskie odpowiedniki
//
// Filtrowanie szuka w: label + group + keywords (case-insensitive)

const ADMIN_NAV_TABS = [
  // --- Przeżrój ---
  { tab: 'dashboard',    icon: '\ud83d\udcca', label: 'Dashboard',            group: 'Przeżrój',      keywords: ['statystyki', 'stats', 'wykresy', 'przegl\u0105d', 'dps', 'top', 'klasy'] },
  { tab: 'traffic',      icon: '\ud83d\udcc8', label: '\ud83d\udcc8 Ruch',              group: 'Przeżrój',      keywords: ['ruch na stronie', 'traffic', 'wizyty', 'odwiedziny', 'visitors', 'unikalni'] },
  { tab: 'health',       icon: '\ud83c\udfe5', label: 'Health',               group: 'Przeżrój',      keywords: ['health check', 'zdrowie', 'status', 'serwisy', 'alerty', 'baza', 'simc'] },
  // --- Treści ---
  { tab: 'news',         icon: '\ud83d\udcf0', label: 'Newsy',                group: 'Treści',        keywords: ['news', 'artykuły', 'wpisy', 'ogłoszenia'] },
  { tab: 'appearance',   icon: '\ud83c\udfa8', label: 'Wygląd',               group: 'Treści',        keywords: ['appearance', 'wygląd strony', 'hero', 'ikona', 'header', 'emoji'] },
  { tab: 'announcement', icon: '\ud83d\udce3', label: 'Komunikaty',            group: 'Treści',        keywords: ['komunikaty systemowe', 'announcement', 'banner', 'globalny', 'przerwa'] },
  // --- Użytkownicy ---
  { tab: 'users',        icon: '\ud83d\udc65', label: 'Użytkownicy',            group: 'Użytkownicy',   keywords: ['users', 'gracze', 'konta', 'bnet', 'battle.net'] },
  { tab: 'gdpr',         icon: '\ud83d\udee1\ufe0f', label: 'RODO',                  group: 'Użytkownicy',   keywords: ['gdpr', 'eksport', 'prywatność', 'usunięcie konta', 'art. 15', 'art. 17'] },
  // --- System ---
  { tab: 'tasks',        icon: '\ud83d\udd27', label: 'Zadania',               group: 'System',        keywords: ['zadania', 'tasks', 'joby', 'kolejka', 'zarządzanie zadaniami'] },
  { tab: 'logs',         icon: '\ud83d\udccb', label: 'Logi',                  group: 'System',        keywords: ['logi', 'logs', 'błędy', 'errors', 'warning', 'info', 'logi systemowe'] },
  { tab: 'js-errors',    icon: '\ud83d\udc1b', label: 'JS Errors',             group: 'System',        keywords: ['js', 'javascript', 'frontend', 'błędy js', 'błędy frontendu'] },
  { tab: 'audit',        icon: '\ud83d\udd50', label: 'Audit log',             group: 'System',        keywords: ['audit', 'historia', 'zmiany', 'admin actions', 'kto co zrobił'] },
  { tab: 'limits',       icon: '\u2699\ufe0f',  label: 'Limity',                group: 'System',        keywords: ['limity', 'limits', 'rate', 'timeout', 'concurrent', 'zarządzanie limitami'] },
  { tab: 'config',       icon: '\ud83d\uddc2\ufe0f', label: 'Konfiguracja',         group: 'System',        keywords: ['config', 'konfiguracja aplikacji', 'ustawienia', 'settings', 'goście'] },
  { tab: 'maintenance',  icon: '\ud83d\udea7', label: 'Utrzymanie',            group: 'System',        keywords: ['maintenance', 'utrzymanie', 'konserwacja', 'stare symulacje', 'tryb konserwacji'] },
  { tab: 'results',      icon: '\ud83d\uddd1\ufe0f', label: 'Pliki wyników',        group: 'System',        keywords: ['wyniki', 'results', 'pliki', 'dysk', 'cleanup'] },
  // --- Inne ---
  { tab: 'search',       icon: '\ud83d\udd0d', label: 'Wyszukiwarka',          group: 'Inne',          keywords: ['search', 'szukaj', 'global', 'ctrl+k'] },
  { tab: 'docs',         icon: '\ud83d\udcda', label: 'Dokumentacja',          group: 'Inne',          keywords: ['docs', 'dokumentacja', 'markdown', 'readme'] },
];

let _searchDebounce = null;

function openGlobalSearch() {
  const modal = document.getElementById('search-modal');
  const input = document.getElementById('search-input');
  if (!modal || !input) return;
  modal.classList.remove('hidden');
  input.value = '';
  _renderNavTabs('');
  setTimeout(() => input.focus(), 50);
}

function closeGlobalSearch() {
  const modal = document.getElementById('search-modal');
  if (modal) modal.classList.add('hidden');
}

// Renderuje listę zakładek (Spotlight) filtrowanych przez q.
// Przeszukuje: label, group, keywords.
function _renderNavTabs(q) {
  const el = document.getElementById('search-results');
  if (!el) return null;

  const lower = q.toLowerCase();
  const tabs = lower
    ? ADMIN_NAV_TABS.filter(t =>
        t.label.toLowerCase().includes(lower) ||
        t.group.toLowerCase().includes(lower) ||
        t.keywords.some(k => k.includes(lower))
      )
    : ADMIN_NAV_TABS;

  if (!tabs.length) return null;

  let html = '<div class="search-group"><div class="search-group-label">\ud83d\udd17 Przejdź do</div>';
  for (const t of tabs) {
    const labelHtml = _highlight(t.label, q);
    const groupHtml = '<span style="color:#666;font-size:0.78rem;margin-left:0.4rem">' + escHtml(t.group) + '</span>';
    html += `<div class="search-item" style="cursor:pointer"
             onclick="closeGlobalSearch();typeof switchTab!=='undefined'&&switchTab('${t.tab}')">
      <span>${t.icon} ${labelHtml}${groupHtml}</span>
    </div>`;
  }
  html += '</div>';
  return html;
}

async function _doSearch(q) {
  const resultsEl = document.getElementById('search-results');
  if (!resultsEl) return;

  if (q.length < 2) {
    const nav = _renderNavTabs(q);
    resultsEl.innerHTML = nav || '<p class="empty">Wpisz frazę aby wyszukać.</p>';
    return;
  }

  resultsEl.innerHTML = '<p class="empty">Szukam…</p>';

  try {
    const res  = await fetch('/admin/api/search?q=' + encodeURIComponent(q));
    const data = await res.json();
    _renderSearchResults(data, q);
  } catch (e) {
    resultsEl.innerHTML = '<p class="empty" style="color:#e55">Błąd wyszukiwania.</p>';
  }
}

function _highlight(text, q) {
  if (!q || !text) return escHtml(text || '');
  const re = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
  return escHtml(text).replace(re, '<mark>$1</mark>');
}

function _renderSearchResults(data, q) {
  const el = document.getElementById('search-results');
  if (!el) return;

  let html = '';

  const navHtml = _renderNavTabs(q);
  if (navHtml) html += navHtml;

  if (data.simulations.length) {
    html += '<div class="search-group"><div class="search-group-label">\ud83d\udcca Symulacje</div>';
    for (const s of data.simulations) {
      const name  = _highlight(s.character_name, q);
      const cls   = escHtml(s.character_class || '');
      const spec  = escHtml(s.character_spec  || '');
      const realm = _highlight(s.realm, q);
      const dps   = s.dps ? Math.round(s.dps).toLocaleString('pl-PL') : '?';
      const color = CLASS_COLORS[s.character_class] || '#aaa';
      html += `<div class="search-item" style="cursor:pointer"
               onclick="closeGlobalSearch();window.open('/sim/${escHtml(s.job_id)}','_blank')"
               title="${escHtml(s.job_id)}">
        <span style="color:${color};font-weight:600">${name}</span>
        <span class="search-item-meta">${cls} ${spec} \u2022 ${realm} \u2022 ${dps} DPS</span>
      </div>`;
    }
    html += '</div>';
  }

  if (data.users.length) {
    html += '<div class="search-group"><div class="search-group-label">\ud83d\udc65 Użytkownicy</div>';
    for (const u of data.users) {
      const tag = _highlight(u.battle_tag || u.bnet_id, q);
      html += `<div class="search-item" style="cursor:pointer"
               onclick="closeGlobalSearch();typeof switchTab!=='undefined'&&switchTab('users');setTimeout(()=>{const s=document.getElementById('user-search');if(s){s.value=${JSON.stringify(u.battle_tag||u.bnet_id)};typeof filterUsers!=='undefined'&&filterUsers();}},300)">
        <span>\ud83d\udc64 ${tag}</span>
        <span class="search-item-meta">${escHtml(u.bnet_id)}</span>
      </div>`;
    }
    html += '</div>';
  }

  if (data.news.length) {
    html += '<div class="search-group"><div class="search-group-label">\ud83d\udcf0 Newsy</div>';
    for (const n of data.news) {
      const title = _highlight(n.title, q);
      const pub   = n.published ? '\u2705' : '\ud83d\udd34';
      html += `<div class="search-item" style="cursor:pointer"
               onclick="closeGlobalSearch();typeof switchTab!=='undefined'&&switchTab('news')">
        <span>${pub} ${title}</span>
      </div>`;
    }
    html += '</div>';
  }

  const totalData = data.simulations.length + data.users.length + data.news.length;
  if (!navHtml && totalData === 0) {
    html = '<p class="empty">Brak wyników dla <strong>' + escHtml(q) + '</strong>.</p>';
  }

  el.innerHTML = html || '<p class="empty">Brak wyników dla <strong>' + escHtml(q) + '</strong>.</p>';
}

// Keyboard shortcut Ctrl+K / Cmd+K
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    const modal = document.getElementById('search-modal');
    if (modal && modal.classList.contains('hidden')) {
      openGlobalSearch();
    } else {
      closeGlobalSearch();
    }
  }
  if (e.key === 'Escape') {
    closeGlobalSearch();
  }
});

// Input handler — debounce 300ms (nawigacja bez debounce)
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('search-input');
  if (input) {
    input.addEventListener('input', () => {
      clearTimeout(_searchDebounce);
      const q = input.value.trim();
      if (q.length < 2) {
        _doSearch(q);
      } else {
        _searchDebounce = setTimeout(() => _doSearch(q), 300);
      }
    });
  }

  const modal = document.getElementById('search-modal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeGlobalSearch();
    });
  }
});
