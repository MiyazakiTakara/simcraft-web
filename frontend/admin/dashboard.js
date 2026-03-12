async function loadDashboard() {
  const res = await fetch('/admin/api/dashboard');
  if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
  const data = await res.json();
  const s = data.stats;

  document.getElementById('stat-total-sims').textContent  = s.total_simulations.toLocaleString();
  document.getElementById('stat-total-users').textContent = s.total_users.toLocaleString();
  document.getElementById('stat-today-sims').textContent  = s.today_simulations.toLocaleString();
  document.getElementById('stat-week-sims').textContent   = (s.week_simulations  ?? '—').toLocaleString();
  document.getElementById('stat-month-sims').textContent  = (s.month_simulations ?? '—').toLocaleString();
  document.getElementById('stat-active-jobs').textContent = s.active_jobs;
  document.getElementById('stat-cpu').textContent         = s.cpu_percent + '%';
  document.getElementById('stat-memory').textContent      = s.memory_percent + '%';
  document.getElementById('stat-uptime').textContent      = s.uptime;

  markRefreshed('dashboard');
  setTimeout(() => renderDashboardCharts(data), 0);
}

function renderDashboardCharts(data) {
  const trend = data.monthly_trend || [];
  if (trend.length) {
    Plotly.newPlot('chart-trend', [{
      x: trend.map(p => p.day),
      y: trend.map(p => p.count),
      type: 'scatter', mode: 'lines+markers',
      line:   { color: '#f4a01c', width: 2 },
      marker: { color: '#f4a01c', size: 5 },
      hovertemplate: '%{x}<br><b>%{y} symulacji</b><extra></extra>',
    }], {
      ...PLOTLY_LAYOUT_BASE,
      margin: { t: 10, r: 10, b: 50, l: 40 },
      xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, type: 'date' },
      yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, tickformat: 'd' },
    }, PLOTLY_CONFIG);
  } else {
    document.getElementById('chart-trend').innerHTML = '<p style="color:#555;text-align:center;padding:4rem 0">Brak danych</p>';
  }

  const classes = data.class_distribution || [];
  if (classes.length) {
    const sorted = [...classes].sort((a, b) => a.count - b.count);
    Plotly.newPlot('chart-classes', [{
      x: sorted.map(c => c.count),
      y: sorted.map(c => c.character_class || 'Unknown'),
      type: 'bar', orientation: 'h',
      marker: { color: sorted.map(c => CLASS_COLORS[c.character_class] || '#555') },
      hovertemplate: '<b>%{y}</b><br>%{x} symulacji<extra></extra>',
    }], {
      ...PLOTLY_LAYOUT_BASE,
      margin: { t: 10, r: 20, b: 40, l: 110 },
      xaxis: { gridcolor: '#222', linecolor: '#333', tickcolor: '#444', type: 'linear', tickformat: 'd', dtick: 1 },
      yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, automargin: true },
    }, PLOTLY_CONFIG);
  } else {
    document.getElementById('chart-classes').innerHTML = '<p style="color:#555;text-align:center;padding:4rem 0">Brak danych</p>';
  }

  const fs = data.fight_style_distribution || [];
  if (fs.length) {
    Plotly.newPlot('chart-fightstyle', [{
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
    document.getElementById('chart-fightstyle').innerHTML = '<p style="color:#555;text-align:center;padding:4rem 0">Brak danych</p>';
  }

  const top10 = data.top_dps || [];
  const container = document.getElementById('chart-top10');
  if (!top10.length) {
    container.innerHTML = '<p style="color:#555;text-align:center;padding:2rem 0">Brak danych</p>';
    return;
  }
  container.innerHTML = `
    <table style="width:100%;border-collapse:collapse">
      <thead>
        <tr style="color:#666;font-size:0.75rem;text-transform:uppercase;border-bottom:1px solid #2a2a2a">
          <th style="text-align:left;padding:0.3rem 0.4rem">#</th>
          <th style="text-align:left;padding:0.3rem 0.4rem">Postać</th>
          <th style="text-align:left;padding:0.3rem 0.4rem">Klasa / Spec</th>
          <th style="text-align:right;padding:0.3rem 0.4rem">DPS</th>
        </tr>
      </thead>
      <tbody>
        ${top10.map((r, i) => `
          <tr style="border-bottom:1px solid #1e1e1e;transition:background .15s"
              onmouseover="this.style.background='#1a1a1a'" onmouseout="this.style.background='transparent'">
            <td style="padding:0.35rem 0.4rem;color:#555">${i + 1}</td>
            <td style="padding:0.35rem 0.4rem">
              <a href="/result/${escHtml(r.job_id)}" target="_blank"
                 style="color:#e8c57a;text-decoration:none;font-weight:600">
                ${escHtml(r.character_name || '—')}
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
