// admin-v2/traffic.js
// Nadpisuje loadTraffic() z admin/traffic.js dodając:
//   - auto-refresh co 60s
//   - pause gdy inna zakładka lub karta ukryta
//   - fade na liczbach + odliczanie w topbarze

(function () {
  const INTERVAL_MS = 60_000;
  const FADE_MS     = 350;

  let _timer    = null;
  let _isActive = false;
  let _isVisible = true;
  let _isLoading = false;

  // ----- Publiczne API (wywoływane przez tabs.js) -----

  const _origLoad = window.loadTraffic;   // zachowaj oryginał do renderowania

  window.loadTraffic = function () {
    _isActive = true;
    _schedulePoll();
    _startTimer();
  };

  window.pauseTraffic = function () {
    _isActive = false;
    _stopTimer();
  };

  // ----- Page Visibility -----

  document.addEventListener('visibilitychange', () => {
    _isVisible = !document.hidden;
    if (_isVisible && _isActive) {
      _schedulePoll();
      _startTimer();
    } else {
      _stopTimer();
    }
  });

  // ----- Timer -----

  function _startTimer() {
    _stopTimer();
    if (!_isActive || !_isVisible) return;
    _timer = setInterval(() => _schedulePoll(), INTERVAL_MS);
  }

  function _stopTimer() {
    if (_timer) { clearInterval(_timer); _timer = null; }
  }

  // ----- Fetch -----

  async function _schedulePoll() {
    if (_isLoading) return;
    _isLoading = true;
    _setIndicator('loading');

    try {
      const res = await fetch('/admin/api/traffic/stats');
      if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      _renderStats(data.summary);
      setTimeout(() => {
        if (typeof renderTrafficCharts === 'function') renderTrafficCharts(data);
      }, 0);
      _setIndicator('ok');
    } catch (err) {
      console.error('[traffic] fetch error', err);
      _setIndicator('error');
    } finally {
      _isLoading = false;
    }
  }

  // ----- Wskaźnik w topbarze -----

  function _setIndicator(state) {
    const el = document.getElementById('refresh-label-traffic');
    if (!el) return;
    if (state === 'loading') {
      el.style.color = '#666';
      el.textContent = '🔄 ładowanie...';
    } else if (state === 'error') {
      el.style.color = '#e55';
      el.textContent = '⚠️ błąd odświeżania';
    } else {
      el.style.color = '#4c4';
      const now = new Date().toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      el.textContent = `• odświeżono ${now}`;
      // Odliczanie co 15s
      let rem = INTERVAL_MS / 1000;
      const tick = setInterval(() => {
        rem -= 15;
        const cur = document.getElementById('refresh-label-traffic');
        if (!cur || rem <= 0) { clearInterval(tick); return; }
        const t = new Date().toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        cur.textContent = `• odświeżono ${t} — następne za ${rem}s`;
      }, 15_000);
    }
  }

  // ----- Render statystyk z fade -----

  function _renderStats(s) {
    const fields = {
      'tr-today':        s.today_visits?.toLocaleString()  ?? '—',
      'tr-unique-today': s.unique_today?.toLocaleString()  ?? '—',
      'tr-week':         s.week_visits?.toLocaleString()   ?? '—',
      'tr-month':        s.month_visits?.toLocaleString()  ?? '—',
      'tr-unique-30d':   s.unique_30d?.toLocaleString()    ?? '—',
      'tr-total':        s.total_visits?.toLocaleString()  ?? '—',
    };
    for (const [id, val] of Object.entries(fields)) {
      const el = document.getElementById(id);
      if (!el) continue;
      if (el.textContent === String(val)) continue;
      el.style.transition = `opacity ${FADE_MS}ms`;
      el.style.opacity = '0';
      setTimeout(() => { el.textContent = val; el.style.opacity = '1'; }, FADE_MS / 2);
    }
  }

})();
