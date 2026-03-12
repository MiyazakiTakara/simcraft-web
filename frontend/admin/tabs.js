// ---- Auto-refresh ----
// interwaly w ms; null = brak auto-refresh
const TAB_REFRESH = {
  dashboard: 30_000,
  traffic:   60_000,
  tasks:     10_000,
  health:    60_000,
  logs:      15_000,
};

const TAB_LOAD_FN = {
  dashboard:   () => loadDashboard(),
  traffic:     () => loadTraffic(),
  news:        () => loadNews(),
  users:       () => loadUsers(),
  logs:        () => loadLogs(),
  maintenance: null,
  limits:      () => loadLimits(),
  health:      () => loadHealth(),
  tasks:       () => loadTasks(),
  appearance:  () => loadAppearance(),
};

let _activeTab    = null;
let _refreshTimer = null;

function stopAutoRefresh() {
  if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null; }
}

function startAutoRefresh(tab) {
  stopAutoRefresh();
  const fn       = TAB_LOAD_FN[tab];
  const interval = TAB_REFRESH[tab];
  if (!fn) return;
  fn();
  if (interval) _refreshTimer = setInterval(fn, interval);
}

// timestamp ostatniego odswiezenia
function markRefreshed(tab) {
  const el = document.getElementById(`refresh-label-${tab}`);
  if (el) {
    const now = new Date().toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    el.textContent = `ostatnia aktualizacja: ${now}`;
  }
}

// ---- Tab switching ----

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    _activeTab = tab.dataset.tab;
    startAutoRefresh(_activeTab);
  });
});

// ---- Init ----

document.addEventListener('DOMContentLoaded', () => {
  _activeTab = 'dashboard';
  startAutoRefresh('dashboard');
  loadAppearance();
});

// zatrzymaj timer gdy karta przegłądarki nieaktywna
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    stopAutoRefresh();
  } else if (_activeTab) {
    startAutoRefresh(_activeTab);
  }
});
