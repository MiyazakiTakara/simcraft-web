document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    const tabId = 'tab-' + tab.dataset.tab;
    document.getElementById(tabId).classList.add('active');

    if (tab.dataset.tab === 'news')       loadNews();
    if (tab.dataset.tab === 'limits')     loadLimits();
    if (tab.dataset.tab === 'health')     loadHealth();
    if (tab.dataset.tab === 'tasks')      loadTasks();
    if (tab.dataset.tab === 'appearance') loadAppearance();
    if (tab.dataset.tab === 'traffic')    loadTraffic();
  });
});

function toast(msg, color = '#eee') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.color = color;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

function fmt(ts) {
  if (!ts) return '—';
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
  return d.toLocaleString('pl-PL');
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ---------- Kolory klas WoW ----------
const CLASS_COLORS = {
  'Death Knight':    '#C41E3A',
  'Demon Hunter':    '#A330C9',
  'Druid':           '#FF7C0A',
  'Evoker':          '#33937F',
  'Hunter':          '#AAD372',
  'Mage':            '#3FC7EB',
  'Monk':            '#00FF98',
  'Paladin':         '#F48CBA',
  'Priest':          '#FFFFFF',
  'Rogue':           '#FFF468',
  'Shaman':          '#0070DD',
  'Warlock':         '#8788EE',
  'Warrior':         '#C69B3A',
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

// ---------- Dashboard ----------

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

  setTimeout(() => renderCharts(data), 0);
}

function renderCharts(data) {
  const trend = data.monthly_trend || [];
  if (trend.length) {
    Plotly.newPlot('chart-trend', [{
      x:    trend.map(p => p.day),
      y:    trend.map(p => p.count),
      type: 'scatter',
      mode: 'lines+markers',
      line:    { color: '#f4a01c', width: 2 },
      marker:  { color: '#f4a01c', size: 5 },
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
      x:           sorted.map(c => c.count),
      y:           sorted.map(c => c.character_class || 'Unknown'),
      type:        'bar',
      orientation: 'h',
      marker: { color: sorted.map(c => CLASS_COLORS[c.character_class] || '#555') },
      hovertemplate: '<b>%{y}</b><br>%{x} symulacji<extra></extra>',
    }], {
      ...PLOTLY_LAYOUT_BASE,
      margin: { t: 10, r: 20, b: 40, l: 110 },
      xaxis: {
        gridcolor: '#222', linecolor: '#333', tickcolor: '#444',
        type: 'linear', tickformat: 'd', dtick: 1,
      },
      yaxis: { ...PLOTLY_LAYOUT_BASE.yaxis, automargin: true },
    }, PLOTLY_CONFIG);
  } else {
    document.getElementById('chart-classes').innerHTML = '<p style="color:#555;text-align:center;padding:4rem 0">Brak danych</p>';
  }

  const fs = data.fight_style_distribution || [];
  if (fs.length) {
    Plotly.newPlot('chart-fightstyle', [{
      labels:  fs.map(f => f.fight_style || 'Unknown'),
      values:  fs.map(f => f.count),
      type:    'pie',
      marker:  { colors: ['#f4a01c','#3FC7EB','#AAD372','#A330C9','#C41E3A','#8788EE'] },
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
          <tr style="border-bottom:1px solid #1e1e1e;transition:background .15s" onmouseover="this.style.background='#1a1a1a'" onmouseout="this.style.background='transparent'">
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
    </table>
  `;
}

// ---------- Traffic ----------

async function loadTraffic() {
  const res = await fetch('/admin/api/traffic/stats');
  if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
  if (!res.ok) { toast('Błąd ładowania ruchu', '#e55'); return; }
  const data = await res.json();
  const s = data.summary;

  document.getElementById('tr-today').textContent       = s.today_visits.toLocaleString();
  document.getElementById('tr-unique-today').textContent = s.unique_today.toLocaleString();
  document.getElementById('tr-week').textContent        = s.week_visits.toLocaleString();
  document.getElementById('tr-month').textContent       = s.month_visits.toLocaleString();
  document.getElementById('tr-unique-30d').textContent  = s.unique_30d.toLocaleString();
  document.getElementById('tr-total').textContent       = s.total_visits.toLocaleString();

  setTimeout(() => renderTrafficCharts(data), 0);
}

function renderTrafficCharts(data) {
  // Wykres dzienny (linie: total + unique)
  const daily = data.daily_trend || [];
  if (daily.length) {
    Plotly.newPlot('chart-traffic-daily', [
      {
        x: daily.map(d => d.day),
        y: daily.map(d => d.total),
        name: 'Wyświetlenia',
        type: 'scatter',
        mode: 'lines+markers',
        line:   { color: '#3FC7EB', width: 2 },
        marker: { color: '#3FC7EB', size: 4 },
        hovertemplate: '%{x}<br><b>%{y} wyświetleń</b><extra></extra>',
      },
      {
        x: daily.map(d => d.day),
        y: daily.map(d => d.unique),
        name: 'Unikalni',
        type: 'scatter',
        mode: 'lines+markers',
        line:   { color: '#f4a01c', width: 2, dash: 'dot' },
        marker: { color: '#f4a01c', size: 4 },
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

  // Wykres godzinowy (słupki)
  const hourly = data.hourly || [];
  if (hourly.length) {
    // wypełnij brakujące godziny zerami
    const hourMap = {};
    hourly.forEach(h => { hourMap[h.hour] = h.count; });
    const hours  = Array.from({ length: 24 }, (_, i) => i);
    const counts = hours.map(h => hourMap[h] || 0);
    Plotly.newPlot('chart-traffic-hourly', [{
      x:    hours.map(h => String(h).padStart(2, '0') + ':00'),
      y:    counts,
      type: 'bar',
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

  // Tabela top stron
  const pages = data.top_pages || [];
  const el = document.getElementById('traffic-top-pages');
  if (!pages.length) {
    el.innerHTML = '<p style="color:#555;text-align:center;padding:1.5rem 0">Brak danych</p>';
    return;
  }
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
    </table>
  `;
}

// ---------- News ----------

async function loadNews() {
  const res = await fetch('/admin/api/news');
  if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
  const news = await res.json();
  const list = document.getElementById('news-list');
  if (!news.length) { list.innerHTML = '<p class="empty">Brak newsów.</p>'; return; }
  list.innerHTML = news.map(n => `
    <div class="news-card" id="card-${n.id}">
      <div class="info">
        <h3>${escHtml(n.title)}
          <span class="badge ${n.published ? 'published' : 'draft'}">
            ${n.published ? 'opublikowany' : 'szkic'}
          </span>
        </h3>
        <p>${escHtml(n.body)}</p>
        <div class="meta">${fmt(n.created_at)}</div>
      </div>
      <div class="actions">
        <button class="danger" onclick="togglePublish(${n.id}, ${n.published})">
          ${n.published ? 'Ukryj' : 'Publikuj'}
        </button>
        <button class="danger" onclick="deleteNews(${n.id})">Usuń</button>
      </div>
    </div>
  `).join('');
}

async function createNews() {
  const title     = document.getElementById('news-title').value.trim();
  const body      = document.getElementById('news-body').value.trim();
  const published = document.getElementById('news-published').checked;
  if (!title || !body) { toast('Uzupełnij tytuł i treść!', '#e88'); return; }
  const res = await fetch('/admin/api/news', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, body, published }),
  });
  if (res.ok) {
    toast('News dodany!', '#4c4');
    document.getElementById('news-title').value = '';
    document.getElementById('news-body').value  = '';
    loadNews();
  } else {
    toast('Błąd przy dodawaniu.', '#e55');
  }
}

async function deleteNews(id) {
  if (!confirm('Na pewno usunąć?')) return;
  const res = await fetch(`/admin/api/news/${id}`, { method: 'DELETE' });
  if (res.ok) { toast('Usunięto.', '#aaa'); loadNews(); }
  else toast('Błąd.', '#e55');
}

async function togglePublish(id, current) {
  const res = await fetch(`/admin/api/news/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ published: !current }),
  });
  if (res.ok) loadNews();
  else toast('Błąd.', '#e55');
}

// ---------- Logs ----------

async function loadLogs() {
  const level = document.getElementById('log-level').value;
  const url = '/admin/api/logs?limit=100' + (level ? '&level=' + level : '');
  const res = await fetch(url);
  if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
  const logs = await res.json();
  const list = document.getElementById('log-list');
  if (!logs.length) { list.innerHTML = '<p class="empty">Brak logów.</p>'; return; }
  list.innerHTML = logs.map(l => `
    <div class="log-entry">
      <span class="time">${l.created_at ? l.created_at.replace('T',' ').slice(0,19) : ''}</span>
      <span class="level ${l.level}">${l.level}</span>
      <span class="msg">${escHtml(l.message)}</span>
      ${l.context ? `<div class="ctx">${escHtml(l.context)}</div>` : ''}
    </div>
  `).join('');
}

// ---------- Users ----------

let allUsers = [];

async function loadUsers() {
  const res = await fetch('/admin/api/users?limit=50');
  if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
  allUsers = await res.json();
  renderUsers(allUsers);
}

function renderUsers(users) {
  const list = document.getElementById('user-list');
  if (!users.length) { list.innerHTML = '<p class="empty">Brak użytkowników.</p>'; return; }
  list.innerHTML = users.map(u => `
    <div class="news-card" onclick="openUserModal('${escHtml(u.user_id)}')" style="cursor:pointer">
      <div class="info">
        <h3>${escHtml(u.user_id || 'Nieznany')}</h3>
        <p>${escHtml(u.character_name || '—')} ${
          u.character_class
            ? `<span style="color:#f4a01c">${escHtml((u.character_spec ? u.character_spec + ' ' : '') + u.character_class)}</span>`
            : ''
        }</p>
        <div class="meta">
          ${u.sim_count} symulacji · śr. DPS: ${u.avg_dps ? Number(u.avg_dps).toLocaleString() : '—'} ·
          ${u.last_sim ? 'ostatnia: ' + fmt(u.last_sim) : 'brak'}
        </div>
      </div>
    </div>
  `).join('');
}

function filterUsers() {
  const query = document.getElementById('user-search').value.toLowerCase().trim();
  if (!query) { renderUsers(allUsers); return; }
  const filtered = allUsers.filter(u =>
    (u.user_id        && u.user_id.toLowerCase().includes(query)) ||
    (u.character_name && u.character_name.toLowerCase().includes(query))
  );
  renderUsers(filtered);
}

async function openUserModal(userId) {
  const modal = document.getElementById('user-modal');
  const list  = document.getElementById('user-sim-list');
  modal.classList.remove('hidden');
  list.innerHTML = '<p class="empty">Ładowanie...</p>';

  const res = await fetch('/admin/api/users/' + encodeURIComponent(userId) + '/simulations');
  if (!res.ok) { list.innerHTML = '<p class="empty">Błąd ładowania.</p>'; return; }
  const sims = await res.json();

  if (!sims.length) { list.innerHTML = '<p class="empty">Brak symulacji.</p>'; return; }
  list.innerHTML = sims.map(s => `
    <div class="sim-item">
      <div>
        <div style="font-weight:600">${escHtml(s.character_name || '—')}</div>
        <div style="font-size:0.8rem;color:#888">
          ${s.character_class ? `<span style="color:#f4a01c">${escHtml((s.character_spec ? s.character_spec + ' ' : '') + s.character_class)}</span> · ` : ''}
          ${s.fight_style} · ${fmt(s.created_at)}
        </div>
      </div>
      <div style="text-align:right">
        <div style="font-weight:700;color:#f4a01c;font-size:1.1rem">${Number(s.dps).toLocaleString()} DPS</div>
        <a class="sim-link" href="/result/${s.job_id}" target="_blank">Zobacz wynik ↗</a>
      </div>
    </div>
  `).join('');
}

function closeUserModal() {
  document.getElementById('user-modal').classList.add('hidden');
}

document.getElementById('user-modal').addEventListener('click', function(e) {
  if (e.target === this) closeUserModal();
});

// ---------- Maintenance ----------

async function deleteOldSims() {
  const days = parseInt(document.getElementById('delete-days').value);
  if (!days || days < 1) { toast('Podaj liczbę dni!', '#e88'); return; }
  if (!confirm(`Na pewno usunąć wszystkie symulacje starsze niż ${days} dni?`)) return;
  const res  = await fetch(`/admin/api/simulations?older_than_days=${days}`, { method: 'DELETE' });
  const data = await res.json();
  const el   = document.getElementById('delete-result');
  el.textContent = `Usunięto ${data.deleted} symulacji.`;
  el.style.color = '#4c4';
  loadDashboard();
}

async function deleteAllSims() {
  if (!confirm('Na pewno usunąć WSZYSTKIE symulacje? To nieodwracalne!')) return;
  if (!confirm('Jesteś PEWNY? Wszystkie dane zostaną utracone!')) return;
  const res  = await fetch('/admin/api/simulations', { method: 'DELETE' });
  const data = await res.json();
  const el   = document.getElementById('delete-result');
  el.textContent = `Usunięto ${data.deleted} symulacji.`;
  el.style.color = '#e55';
  loadDashboard();
}

// ---------- Limits ----------

async function loadLimits() {
  const res = await fetch('/admin/api/limits');
  if (!res.ok) { toast('Błąd ładowania limitów', '#e88'); return; }
  const data = await res.json();
  document.getElementById('limit-concurrent').value = data.max_concurrent_sims;
  document.getElementById('limit-rate').value       = data.rate_limit_per_minute;
  document.getElementById('limit-timeout').value    = data.job_timeout;
}

async function saveLimits() {
  const payload = {
    max_concurrent_sims:   parseInt(document.getElementById('limit-concurrent').value),
    rate_limit_per_minute: parseInt(document.getElementById('limit-rate').value),
    job_timeout:           parseInt(document.getElementById('limit-timeout').value),
  };
  const res    = await fetch('/admin/api/limits', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = document.getElementById('limits-result');
  if (res.ok) {
    result.textContent = 'Limity zapisane (nie trwałe w demo).';
    result.style.color = '#4c4';
  } else {
    result.textContent = 'Błąd zapisu limitów.';
    result.style.color = '#e55';
  }
}

// ---------- Health ----------

function _renderHealthRow(key, val) {
  if (key === 'simc_version' && val && typeof val === 'object') {
    const v        = val;
    const local    = v.local  || '—';
    const latest   = v.latest || '—';
    const upToDate = v.up_to_date;
    let badge, badgeColor;
    if      (upToDate === true)  { badge = '✓ aktualna';       badgeColor = '#4c4'; }
    else if (upToDate === false) { badge = '✗ nieaktualna';    badgeColor = '#e55'; }
    else                         { badge = '? nie sprawdzono'; badgeColor = '#aaa'; }
    const releaseLink  = v.release_url  ? ` <a href="${escHtml(v.release_url)}" target="_blank" style="color:#7af;font-size:0.8rem">→ release</a>` : '';
    const publishedAt  = v.published_at ? `<span style="color:#666;font-size:0.78rem"> (${v.published_at.slice(0,10)})</span>` : '';
    const cacheAge     = typeof v.cache_age_s === 'number' ? `<span style="color:#555;font-size:0.75rem"> cache: ${v.cache_age_s}s</span>` : '';
    return `
      <div style="padding:0.4rem 0;border-bottom:1px solid #222">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="color:#aaa">simc_version</span>
          <span style="color:${badgeColor};font-weight:600">${badge}</span>
        </div>
        <div style="font-size:0.82rem;color:#888;margin-top:0.2rem;display:flex;flex-wrap:wrap;gap:0.6rem">
          <span>lokalna: <b style="color:#ccc">${escHtml(local)}</b></span>
          <span>najnowsza: <b style="color:#ccc">${escHtml(latest)}</b>${publishedAt}${releaseLink}</span>
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
  container.innerHTML = '<p class="empty">Ładowanie...</p>';
  const res = await fetch('/admin/api/health');
  if (!res.ok) { container.innerHTML = '<p class="empty">Błąd ładowania.</p>'; return; }
  const data = await res.json();
  const html = Object.entries(data).map(([k, v]) => _renderHealthRow(k, v)).join('');
  container.innerHTML = `<div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:0.5rem">${html}</div>`;
}

// ---------- Tasks ----------

async function loadTasks() {
  const container = document.getElementById('tasks-list');
  container.innerHTML = '<p class="empty">Ładowanie...</p>';
  const res = await fetch('/admin/api/tasks');
  if (!res.ok) { container.innerHTML = '<p class="empty">Błąd ładowania.</p>'; return; }
  const data = await res.json();
  if (!data.active_tasks.length) { container.innerHTML = '<p class="empty">Brak aktywnych zadań.</p>'; return; }
  container.innerHTML = `<div class="news-list">${data.active_tasks.map(t => `
    <div class="sim-item">
      <div>
        <div style="font-weight:600">${escHtml(t.job_id)}</div>
        <div style="font-size:0.8rem;color:#888">Status: ${t.status} · ${fmt(t.started_at)}</div>
      </div>
      <button class="danger" onclick="cancelTask('${t.job_id}')">Anuluj</button>
    </div>
  `).join('')}</div>`;
}

async function cancelTask(jobId) {
  if (!confirm(`Na pewno anulować zadanie ${jobId}?`)) return;
  const res = await fetch(`/admin/api/tasks/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
  if (res.ok) { toast('Zadanie anulowane', '#4c4'); loadTasks(); }
  else toast('Błąd anulowania', '#e55');
}

// ---------- Appearance ----------

document.querySelectorAll('.emoji-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.emoji-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
  });
});

async function loadAppearance() {
  try {
    const res = await fetch('/admin/api/appearance');
    if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
    const data = await res.json();
    document.getElementById('appearance-header-title').value = data.header_title || '';
    document.getElementById('appearance-hero-title').value   = data.hero_title   || '';
    const customEl = document.getElementById('appearance-hero-custom');
    if (customEl) customEl.value = data.hero_custom_text || '';
    const selectedEmoji = data.emoji || '⚔️';
    document.querySelectorAll('.emoji-btn').forEach(btn => {
      btn.classList.toggle('selected', btn.dataset.emoji === selectedEmoji);
    });
  } catch (e) {
    console.error('Error loading appearance:', e);
  }
}

async function saveAppearance() {
  const headerTitle      = document.getElementById('appearance-header-title').value;
  const heroTitle        = document.getElementById('appearance-hero-title').value;
  const selectedEmojiBtn = document.querySelector('.emoji-btn.selected');
  const emoji            = selectedEmojiBtn ? selectedEmojiBtn.dataset.emoji : '⚔️';
  const customEl         = document.getElementById('appearance-hero-custom');
  const heroCustomText   = customEl ? customEl.value : '';
  try {
    const res    = await fetch('/admin/api/appearance', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ header_title: headerTitle, hero_title: heroTitle, emoji, hero_custom_text: heroCustomText }),
    });
    const result = await res.json();
    const el     = document.getElementById('appearance-result');
    if (res.ok) {
      el.textContent = 'Zapisano!';
      el.style.color = '#4c4';
      toast('Wygląd zapisany', '#4c4');
    } else {
      el.textContent = 'Błąd: ' + (result.detail || 'Nieznany błąd');
      el.style.color = '#e55';
    }
  } catch (e) {
    const el = document.getElementById('appearance-result');
    el.textContent = 'Błąd połączenia';
    el.style.color = '#e55';
  }
}

// ---------- Init ----------

document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
  loadAppearance();
});
