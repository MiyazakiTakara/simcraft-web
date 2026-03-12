async function loadTraffic() {
  const res = await fetch('/admin/api/traffic/stats');
  if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
  if (!res.ok) { toast('Błąd ładowania ruchu', '#e55'); return; }
  const data = await res.json();
  const s = data.summary;

  document.getElementById('tr-today').textContent        = s.today_visits.toLocaleString();
  document.getElementById('tr-unique-today').textContent = s.unique_today.toLocaleString();
  document.getElementById('tr-week').textContent         = s.week_visits.toLocaleString();
  document.getElementById('tr-month').textContent        = s.month_visits.toLocaleString();
  document.getElementById('tr-unique-30d').textContent   = s.unique_30d.toLocaleString();
  document.getElementById('tr-total').textContent        = s.total_visits.toLocaleString();

  markRefreshed('traffic');
  setTimeout(() => renderTrafficCharts(data), 0);
}

function renderTrafficCharts(data) {
  const daily = data.daily_trend || [];
  if (daily.length) {
    Plotly.newPlot('chart-traffic-daily', [
      {
        x: daily.map(d => d.day), y: daily.map(d => d.total),
        name: 'Wyświetlenia', type: 'scatter', mode: 'lines+markers',
        line: { color: '#3FC7EB', width: 2 }, marker: { color: '#3FC7EB', size: 4 },
        hovertemplate: '%{x}<br><b>%{y} wyświetleń</b><extra></extra>',
      },
      {
        x: daily.map(d => d.day), y: daily.map(d => d.unique),
        name: 'Unikalni', type: 'scatter', mode: 'lines+markers',
        line: { color: '#f4a01c', width: 2, dash: 'dot' }, marker: { color: '#f4a01c', size: 4 },
        hovertemplate: '%{x}<br><b>%{y} unikalnych</b><extra></extra>',
      },
    ], {
      ...PLOTLY_LAYOUT_BASE,
      showlegend: true,
      legend: { font: { color: '#aaa', size: 11 }, bgcolor: 'transparent' },
      margin: { t: 10, r: 10, b: 50, l: 45 },
      xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, type: 'date' },
      yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, tickformat: 'd' },
    }, PLOTLY_CONFIG);
  } else {
    document.getElementById('chart-traffic-daily').innerHTML = '<p style="color:#555;text-align:center;padding:4rem 0">Brak danych</p>';
  }

  const hourly = data.hourly || [];
  if (hourly.length) {
    const hourMap = {};
    hourly.forEach(h => { hourMap[h.hour] = h.count; });
    const hours  = Array.from({ length: 24 }, (_, i) => i);
    const counts = hours.map(h => hourMap[h] || 0);
    Plotly.newPlot('chart-traffic-hourly', [{
      x: hours.map(h => String(h).padStart(2, '0') + ':00'),
      y: counts, type: 'bar',
      marker: { color: counts.map(c => c > 0 ? '#3FC7EB' : '#222') },
      hovertemplate: '<b>%{x}</b><br>%{y} wizyt<extra></extra>',
    }], {
      ...PLOTLY_LAYOUT_BASE,
      margin: { t: 10, r: 10, b: 50, l: 40 },
      xaxis: { ...PLOTLY_LAYOUT_BASE.xaxis, type: 'category' },
      yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, tickformat: 'd' },
    }, PLOTLY_CONFIG);
  } else {
    document.getElementById('chart-traffic-hourly').innerHTML = '<p style="color:#555;text-align:center;padding:4rem 0">Brak danych</p>';
  }

  const pages = data.top_pages || [];
  const el = document.getElementById('traffic-top-pages');
  if (!pages.length) { el.innerHTML = '<p style="color:#555;text-align:center;padding:1.5rem 0">Brak danych</p>'; return; }
  const maxCount = pages[0].count;
  el.innerHTML = `
    <table style="width:100%;border-collapse:collapse">
      <thead>
        <tr style="color:#666;font-size:0.75rem;text-transform:uppercase;border-bottom:1px solid #2a2a2a">
          <th style="text-align:left;padding:0.3rem 0.5rem">#</th>
          <th style="text-align:left;padding:0.3rem 0.5rem">Podstrona</th>
          <th style="text-align:right;padding:0.3rem 0.5rem">Wizyty</th>
          <th style="padding:0.3rem 0.5rem;width:30%"></th>
        </tr>
      </thead>
      <tbody>
        ${pages.map((p, i) => `
          <tr style="border-bottom:1px solid #1e1e1e">
            <td style="padding:0.3rem 0.5rem;color:#555">${i + 1}</td>
            <td style="padding:0.3rem 0.5rem;font-family:monospace;font-size:0.85rem;color:#ccc">${escHtml(p.path)}</td>
            <td style="padding:0.3rem 0.5rem;text-align:right;font-weight:700;color:#3FC7EB">${p.count.toLocaleString()}</td>
            <td style="padding:0.3rem 0.5rem">
              <div style="height:6px;background:#222;border-radius:3px;overflow:hidden">
                <div style="height:100%;width:${Math.round((p.count/maxCount)*100)}%;background:#3FC7EB;border-radius:3px"></div>
              </div>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>`;
}
