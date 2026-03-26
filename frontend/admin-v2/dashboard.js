// admin-v2/dashboard.js  (#61: +czas trwania, error rate, trendline DPS per klasa)
// Auto-refresh co 30s, pauzuje gdy:
//   - użytkownik nie jest na zakładce dashboard
//   - karta przegladarki jest ukryta (Page Visibility API)

(function () {
  const INTERVAL_MS = 30_000;
  const FADE_MS     = 400;

  let _timer        = null;
  let _lastData     = null;
  let _isActive     = false;
  let _isVisible    = true;
  let _isLoading    = false;

  // ───────────────────────────────────────
  // Publiczne API (wywoływane z tabs.js)
  // ───────────────────────────────────────
  window.loadDashboard = function () {
    _isActive = true;
    _schedulePoll(true);
    _startTimer();
  };

  window.pauseDashboard = function () {
    _isActive = false;
    _stopTimer();
  };

  // ───────────────────────────────────────
  // Page Visibility API
  // ───────────────────────────────────────
  document.addEventListener('visibilitychange', () => {
    _isVisible = !document.hidden;
    if (_isVisible && _isActive) {
      _schedulePoll(true);
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
    _timer = setInterval(() => _schedulePoll(false), INTERVAL_MS);
  }

  function _stopTimer() {
    if (_timer) { clearInterval(_timer); _timer = null; }
  }

  // ───────────────────────────────────────
  // Fetch
  // ───────────────────────────────────────
  async function _schedulePoll(immediate) {
    if (_isLoading) return;
    _isLoading = true;
    _setLiveIndicator('loading');

    try {
      const res = await fetch('/admin/api/dashboard');
      if (res.status === 302 || res.redirected) {
        window.location = '/admin/login';
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      _lastData = data;
      _renderStats(data.stats);
      setTimeout(() => _renderCharts(data), 0);
      _markRefreshed();
      _setLiveIndicator('ok');
    } catch (err) {
      console.error('[dashboard] fetch error', err);
      _setLiveIndicator('error');
    } finally {
      _isLoading = false;
    }
  }

  // ───────────────────────────────────────
  // Wskaźnik live
  // ───────────────────────────────────────
  function _setLiveIndicator(state) {
    const el = document.getElementById('refresh-label-dashboard');
    if (!el) return;
    el.style.color = { loading: '#666', ok: '#4c4', error: '#e55' }[state] || '#666';
    if (state === 'ok') {
      const now = new Date().toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      el.textContent = `\u2022 od\u015bwie\u017cono ${now}`;
    } else if (state === 'loading') {
      el.textContent = '\ud83d\udd04 \u0142adowanie...';
    } else {
      el.textContent = '\u26a0\ufe0f b\u0142\u0105d od\u015bwie\u017cania';
    }
  }

  function _markRefreshed() {
    let remaining = INTERVAL_MS / 1000;
    const tick = setInterval(() => {
      remaining -= 5;
      const el = document.getElementById('refresh-label-dashboard');
      if (!el || remaining <= 0) { clearInterval(tick); return; }
      const now = new Date().toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      el.textContent = `\u2022 od\u015bwie\u017cono ${now} \u2014 nast\u0119pne za ${remaining}s`;
    }, 5000);
  }

  // ───────────────────────────────────────
  // Render statystyk
  // ───────────────────────────────────────
  function _fmtDuration(s) {
    if (s == null) return '\u2014';
    if (s < 60) return Math.round(s) + 's';
    return Math.floor(s / 60) + 'm ' + Math.round(s % 60) + 's';
  }

  function _errorRateColor(pct) {
    if (pct == null) return '';
    if (pct < 5)  return '#4c4';
    if (pct < 15) return '#f4a01c';
    return '#e55';
  }

  function _renderStats(s) {
    const fields = {
      'stat-total-sims':  s.total_simulations?.toLocaleString()  ?? '\u2014',
      'stat-total-users': s.total_users?.toLocaleString()         ?? '\u2014',
      'stat-today-sims':  s.today_simulations?.toLocaleString()   ?? '\u2014',
      'stat-week-sims':   s.week_simulations?.toLocaleString()    ?? '\u2014',
      'stat-month-sims':  s.month_simulations?.toLocaleString()   ?? '\u2014',
      'stat-active-jobs': s.active_jobs        ?? '\u2014',
      'stat-cpu':         s.cpu_percent != null ? s.cpu_percent + '%' : '\u2014',
      'stat-memory':      s.memory_percent != null ? s.memory_percent + '%' : '\u2014',
      'stat-uptime':      s.uptime ?? '\u2014',
      // #61
      'stat-avg-duration':    _fmtDuration(s.avg_sim_duration_s),
      'stat-median-duration': _fmtDuration(s.median_sim_duration_s),
      'stat-error-rate-24h':  s.error_rate_24h != null ? s.error_rate_24h + '%' : '\u2014',
      'stat-error-rate-7d':   s.error_rate_7d  != null ? s.error_rate_7d  + '%' : '\u2014',
    };

    for (const [id, val] of Object.entries(fields)) {
      const el = document.getElementById(id);
      if (!el) continue;
      const oldVal = el.textContent;
      if (oldVal === String(val)) continue;

      el.style.transition = `opacity ${FADE_MS}ms`;
      el.style.opacity = '0';
      setTimeout(() => {
        el.textContent = val;
        el.style.opacity = '1';
        if (oldVal !== '\u2014' && oldVal !== val) {
          el.style.color = '#7ef4a0';
          setTimeout(() => { el.style.color = ''; }, 1500);
        }
      }, FADE_MS / 2);
    }

    // Kolorowanie error rate
    ['stat-error-rate-24h', 'stat-error-rate-7d'].forEach((id, i) => {
      const el = document.getElementById(id);
      const pct = i === 0 ? s.error_rate_24h : s.error_rate_7d;
      if (el && pct != null) setTimeout(() => { el.style.color = _errorRateColor(pct); }, FADE_MS);
    });

    // Alert CPU/RAM
    const alertEl    = document.getElementById('topbar-alerts');
    const alertCount = document.getElementById('alert-count');
    if (alertEl) {
      const alerts = [];
      if (s.cpu_percent > 90)    alerts.push('CPU ' + s.cpu_percent + '%');
      if (s.memory_percent > 90) alerts.push('RAM ' + s.memory_percent + '%');
      alertEl.style.display = alerts.length ? 'flex' : 'none';
      alertEl.title = alerts.length ? 'Wysokie obci\u0105\u017cenie: ' + alerts.join(', ') : '';
      if (alertCount) alertCount.textContent = alerts.length;
    }
  }

  // ───────────────────────────────────────
  // Render wykresów (Plotly)
  // ───────────────────────────────────────
  function _renderCharts(data) {
    if (typeof Plotly === 'undefined') return;

    const noData = '<p style="color:#555;text-align:center;padding:4rem 0">Brak danych</p>';

    // --- Trend 30 dni ---
    const trend = data.monthly_trend || [];
    if (trend.length) {
      Plotly.react('chart-trend', [{
        x: trend.map(p => p.day),
        y: trend.map(p => p.count),
        type: 'scatter', mode: 'lines+markers',
        line:   { color: '#f4a01c', width: 2 },
        marker: { color: '#f4a01c', size: 5 },
        fill:   'tozeroy',
        fillcolor: 'rgba(244,160,28,0.07)',
        hovertemplate: '%{x}<br><b>%{y} symulacji</b><extra></extra>',
      }], {
        ...PLOTLY_LAYOUT_BASE,
        margin: { t: 10, r: 10, b: 50, l: 40 },
        xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, type: 'date' },
        yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, tickformat: 'd' },
      }, PLOTLY_CONFIG);
    } else {
      const el = document.getElementById('chart-trend');
      if (el) el.innerHTML = noData;
    }

    // --- Rozkład klas ---
    const classes = data.class_distribution || [];
    if (classes.length) {
      const sorted = [...classes].sort((a, b) => a.count - b.count);
      Plotly.react('chart-classes', [{
        x: sorted.map(c => c.count),
        y: sorted.map(c => c.character_class || 'Unknown'),
        type: 'bar', orientation: 'h',
        marker: { color: sorted.map(c => CLASS_COLORS[c.character_class] || '#555') },
        hovertemplate: '<b>%{y}</b><br>%{x} symulacji<extra></extra>',
      }], {
        ...PLOTLY_LAYOUT_BASE,
        margin: { t: 10, r: 20, b: 40, l: 110 },
        xaxis: { gridcolor: '#222', linecolor: '#333', tickcolor: '#444', tickformat: 'd', dtick: 1 },
        yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, automargin: true },
      }, PLOTLY_CONFIG);
    } else {
      const el = document.getElementById('chart-classes');
      if (el) el.innerHTML = noData;
    }

    // --- Fight Style (pie) ---
    const fs = data.fight_style_distribution || [];
    if (fs.length) {
      Plotly.react('chart-fightstyle', [{
        labels: fs.map(f => f.fight_style || 'Unknown'),
        values: fs.map(f => f.count),
        type: 'pie',
        marker: { colors: ['#f4a01c','#3FC7EB','#AAD372','#A330C9','#C41E3A','#8788EE'] },
        textinfo: 'percent+label',
        hovertemplate: '<b>%{label}</b><br>%{value} symulacji (%{percent})<extra></extra>',
        textfont: { color: '#ccc', size: 11 },
      }], {
        ...PLOTLY_LAYOUT_BASE,
        margin: { t: 10, r: 10, b: 10, l: 10 },
        showlegend: false,
      }, PLOTLY_CONFIG);
    } else {
      const el = document.getElementById('chart-fightstyle');
      if (el) el.innerHTML = noData;
    }

    // --- Top 10 DPS ---
    const top10 = data.top_dps || [];
    const container = document.getElementById('chart-top10');
    if (container) {
      if (!top10.length) {
        container.innerHTML = '<p style="color:#555;text-align:center;padding:2rem 0">Brak danych</p>';
      } else {
        container.innerHTML = `
          <table style="width:100%;border-collapse:collapse">
            <thead>
              <tr style="color:#555;font-size:0.72rem;text-transform:uppercase;border-bottom:1px solid #2a2a2a">
                <th style="text-align:left;padding:0.3rem 0.4rem;width:1.5rem">#</th>
                <th style="text-align:left;padding:0.3rem 0.4rem">Posta\u0107</th>
                <th style="text-align:left;padding:0.3rem 0.4rem">Klasa / Spec</th>
                <th style="text-align:right;padding:0.3rem 0.4rem">DPS</th>
              </tr>
            </thead>
            <tbody>
              ${top10.map((r, i) => `
                <tr style="border-bottom:1px solid #1a1a1a;transition:background .12s"
                    onmouseover="this.style.background='#1e1e1e'" onmouseout="this.style.background='transparent'">
                  <td style="padding:0.35rem 0.4rem;color:#444">${i + 1}</td>
                  <td style="padding:0.35rem 0.4rem">
                    <a href="/result/${escHtml(r.job_id)}" target="_blank"
                       style="color:#e8c57a;text-decoration:none;font-weight:600">
                      ${escHtml(r.character_name || '\u2014')}
                    </a>
                  </td>
                  <td style="padding:0.35rem 0.4rem;color:${CLASS_COLORS[r.character_class] || '#aaa'}">
                    ${escHtml((r.character_spec ? r.character_spec + ' ' : '') + (r.character_class || ''))}
                  </td>
                  <td style="padding:0.35rem 0.4rem;text-align:right;font-weight:700;color:#f4a01c">
                    ${Number(r.dps).toLocaleString('pl-PL', { maximumFractionDigits: 0 })}
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>`;
      }
    }

    // --- #61: Histogram czasów trwania ---
    const hist = data.duration_histogram;
    if (hist) {
      const buckets = ['<30s', '30-60s', '60-120s', '>120s'];
      const vals    = [hist.lt30, hist.lt60, hist.lt120, hist.gt120];
      Plotly.react('chart-duration-hist', [{
        x: buckets,
        y: vals,
        type: 'bar',
        marker: { color: ['#4c9', '#f4a01c', '#e8a030', '#e55'] },
        hovertemplate: '<b>%{x}</b><br>%{y} symulacji<extra></extra>',
      }], {
        ...PLOTLY_LAYOUT_BASE,
        margin: { t: 10, r: 10, b: 40, l: 40 },
        yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, tickformat: 'd' },
      }, PLOTLY_CONFIG);
    }

    // --- #61: Trendline DPS per klasa ---
    const dpsTrend = data.dps_trend_by_class || [];
    if (dpsTrend.length) {
      // Grupuj po klasie
      const byClass = {};
      for (const row of dpsTrend) {
        if (!byClass[row.class]) byClass[row.class] = { x: [], y: [] };
        byClass[row.class].x.push(row.date);
        byClass[row.class].y.push(row.avg_dps);
      }
      const traces = Object.entries(byClass).map(([cls, pts]) => ({
        x: pts.x,
        y: pts.y,
        type: 'scatter',
        mode: 'lines+markers',
        name: cls,
        line:   { color: CLASS_COLORS[cls] || '#888', width: 2 },
        marker: { color: CLASS_COLORS[cls] || '#888', size: 4 },
        hovertemplate: `<b>${cls}</b><br>%{x}<br>\u0141rednie DPS: <b>%{y:,.0f}</b><extra></extra>`,
      }));
      Plotly.react('chart-dps-trends', traces, {
        ...PLOTLY_LAYOUT_BASE,
        margin: { t: 10, r: 10, b: 50, l: 60 },
        xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, type: 'date' },
        yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, tickformat: ',.0f' },
        showlegend: true,
        legend: { bgcolor: 'transparent', font: { color: '#888', size: 10 } },
      }, PLOTLY_CONFIG);
    } else {
      const el = document.getElementById('chart-dps-trends');
      if (el) el.innerHTML = '<p style="color:#555;text-align:center;padding:4rem 0">Za ma\u0142o danych (min. 3 symulacje / klas\u0119 / dzie\u0144)</p>';
    }
  }

})();
