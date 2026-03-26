// admin-v2/autorefresh.js — auto-refresh aktywnej zakładki co 30s
// zatrzymuje się gdy karta przeglądarki jest nieaktywna
(function () {
  const INTERVAL_MS = 30_000;

  const REFRESHABLE = new Set([
    'dashboard', 'traffic', 'health', 'tasks', 'logs', 'audit', 'js-errors',
  ]);

  const LOADERS = {
    dashboard: () => typeof loadDashboard  === 'function' && loadDashboard(),
    traffic:   () => typeof loadTraffic    === 'function' && loadTraffic(),
    health:    () => typeof loadHealth     === 'function' && loadHealth(),
    tasks:     () => typeof loadTasks      === 'function' && loadTasks(),
    logs:      () => typeof loadLogs       === 'function' && loadLogs(),
    audit:     () => typeof loadAudit      === 'function' && loadAudit(),
    'js-errors': () => typeof loadJsErrors === 'function' && loadJsErrors(),
  };

  let _timer = null;
  let _paused = false;

  function currentTab() {
    return typeof window.adminCurrentTab === 'function'
      ? window.adminCurrentTab()
      : null;
  }

  function tick() {
    if (_paused) return;
    const tab = currentTab();
    if (tab && REFRESHABLE.has(tab) && LOADERS[tab]) {
      LOADERS[tab]();
    }
  }

  function start() {
    if (_timer) return;
    _timer = setInterval(tick, INTERVAL_MS);
  }

  function stop() {
    if (_timer) {
      clearInterval(_timer);
      _timer = null;
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      _paused = true;
      stop();
    } else {
      _paused = false;
      tick(); // natychmiastowe odświeżenie po powrocie
      start();
    }
  });

  // start po załadowaniu strony
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
