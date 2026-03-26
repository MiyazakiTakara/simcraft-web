// admin-v2/tabs.js — obsługa nawigacji sidebar + topbar title + mobile
(function () {
  const TITLES = {
    dashboard:    'Dashboard',
    traffic:      'Ruch',
    health:       'Health Check',
    news:         'Newsy',
    appearance:   'Wygląd',
    announcement: 'Komunikaty',
    users:        'Użytkownicy',
    roles:        'Role',
    gdpr:         'RODO',
    tasks:        'Zadania',
    logs:         'Logi',
    'js-errors':  'JS Errors',
    audit:        'Audit log',
    limits:       'Limity',
    config:       'Konfiguracja',
    maintenance:  'Maintenance',
    results:      'Pliki wyników',
    search:       'Wyszukiwarka',
    docs:         'Dokumentacja',
  };

  const ON_DEACTIVATE = {
    dashboard: () => typeof pauseDashboard === 'function' && pauseDashboard(),
    traffic:   () => typeof pauseTraffic   === 'function' && pauseTraffic(),
    audit:     () => typeof pauseAudit     === 'function' && pauseAudit(),
  };

  const ON_ACTIVATE = {
    dashboard:    () => typeof loadDashboard    === 'function' && loadDashboard(),
    traffic:      () => typeof loadTraffic      === 'function' && loadTraffic(),
    health:       () => typeof loadHealth       === 'function' && loadHealth(),
    news:         () => typeof loadNews         === 'function' && loadNews(),
    users:        () => typeof loadUsers        === 'function' && loadUsers(),
    logs:         () => typeof loadLogs         === 'function' && loadLogs(),
    'js-errors':  () => typeof loadJsErrors     === 'function' && loadJsErrors(),
    audit:        () => typeof loadAudit        === 'function' && loadAudit(),
    tasks:        () => typeof loadTasks        === 'function' && loadTasks(),
    maintenance:  () => typeof loadMaintenance  === 'function' && loadMaintenance(),
    limits:       () => typeof loadLimits       === 'function' && loadLimits(),
    appearance:   () => typeof loadAppearance   === 'function' && loadAppearance(),
    config:       () => typeof loadConfig       === 'function' && loadConfig(),
    announcement: () => typeof loadAnnouncement === 'function' && loadAnnouncement(),
    docs:         () => typeof loadDocs         === 'function' && loadDocs(),
    results:      () => typeof loadResultsStats === 'function' && loadResultsStats(),
    gdpr:         () => typeof loadGdpr         === 'function' && loadGdpr(),
  };

  let _currentTab = null;
  let _initialized = false;

  // eksponuj aktualną zakładkę dla autorefresh.js
  window.adminCurrentTab = () => _currentTab;

  function activateTab(tab) {
    if (_currentTab && _currentTab !== tab && ON_DEACTIVATE[_currentTab]) {
      ON_DEACTIVATE[_currentTab]();
    }

    document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + tab));

    const titleEl = document.getElementById('topbar-title');
    if (titleEl) titleEl.textContent = TITLES[tab] || tab;

    _currentTab = tab;

    if (ON_ACTIVATE[tab]) ON_ACTIVATE[tab]();

    try { sessionStorage.setItem('adminV2Tab', tab); } catch (_) {}
  }

  function init() {
    if (_initialized) return;
    _initialized = true;

    document.querySelectorAll('.nav-item').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        if (tab) activateTab(tab);
        if (window.innerWidth <= 768) {
          document.getElementById('sidebar')?.classList.remove('mobile-open');
        }
      });
    });

    document.getElementById('mobile-toggle')?.addEventListener('click', () => {
      document.getElementById('sidebar')?.classList.toggle('mobile-open');
    });

    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        openGlobalSearch();
      }
      if (e.key === 'Escape') {
        document.getElementById('search-modal')?.classList.add('hidden');
      }
    });

    let lastTab = 'dashboard';
    try { lastTab = sessionStorage.getItem('adminV2Tab') || 'dashboard'; } catch (_) {}
    activateTab(lastTab);

    const timeEl = document.getElementById('topbar-time');
    function updateTime() {
      if (timeEl) timeEl.textContent = new Date().toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
    }
    updateTime();
    setInterval(updateTime, 60_000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.activateAdminTab = activateTab;
})();

function openGlobalSearch() {
  const modal = document.getElementById('search-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  setTimeout(() => document.getElementById('search-input')?.focus(), 50);
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('search-modal')?.addEventListener('click', function (e) {
    if (e.target === this) this.classList.add('hidden');
  });
});
