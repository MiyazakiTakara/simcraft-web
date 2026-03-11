document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
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
  return new Date(ts * 1000).toLocaleString('pl-PL');
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function loadDashboard() {
  const res = await fetch('/admin/api/dashboard');
  if (res.status === 302 || res.redirected) {
    window.location = '/admin/login'; return;
  }
  const data = await res.json();
  
  document.getElementById('stat-total-sims').textContent = data.stats.total_simulations.toLocaleString();
  document.getElementById('stat-total-users').textContent = data.stats.total_users.toLocaleString();
  document.getElementById('stat-today-sims').textContent = data.stats.today_simulations.toLocaleString();
  document.getElementById('stat-active-jobs').textContent = data.stats.active_jobs;
  document.getElementById('stat-cpu').textContent = data.stats.cpu_percent + '%';
  document.getElementById('stat-memory').textContent = data.stats.memory_percent + '%';
  document.getElementById('stat-uptime').textContent = data.stats.uptime;
  
  const recentList = document.getElementById('recent-sims');
  if (!data.recent_sims.length) {
    recentList.innerHTML = '<p class="empty">Brak symulacji.</p>';
  } else {
    recentList.innerHTML = data.recent_sims.map(s => `
      <div class="news-card">
        <div class="info">
          <h3>${escHtml(s.character_name || '—')}</h3>
          <div class="meta">${fmt(s.created_at)}</div>
        </div>
        <div style="text-align:right">
          <div class="stat-value" style="font-size:1rem">${Number(s.dps).toLocaleString()} DPS</div>
          <a class="sim-link" href="/result/${s.job_id}" target="_blank">Zobacz ↗</a>
        </div>
      </div>
    `).join('');
  }
}

async function loadNews() {
  const res = await fetch('/admin/api/news');
  if (res.status === 302 || res.redirected) {
    window.location = '/admin/login'; return;
  }
  const news = await res.json();
  const list = document.getElementById('news-list');
  if (!news.length) {
    list.innerHTML = '<p class="empty">Brak newsów.</p>';
    return;
  }
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
  const title = document.getElementById('news-title').value.trim();
  const body  = document.getElementById('news-body').value.trim();
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
    document.getElementById('news-body').value = '';
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

async function loadLogs() {
  const level = document.getElementById('log-level').value;
  const url = '/admin/api/logs?limit=100' + (level ? '&level=' + level : '');
  const res = await fetch(url);
  if (res.status === 302 || res.redirected) {
    window.location = '/admin/login'; return;
  }
  const logs = await res.json();
  const list = document.getElementById('log-list');
  if (!logs.length) {
    list.innerHTML = '<p class="empty">Brak logów.</p>';
    return;
  }
  list.innerHTML = logs.map(l => `
    <div class="log-entry">
      <span class="time">${l.created_at ? l.created_at.replace('T', ' ').slice(0,19) : ''}</span>
      <span class="level ${l.level}">${l.level}</span>
      <span class="msg">${escHtml(l.message)}</span>
      ${l.context ? `<div class="ctx">${escHtml(l.context)}</div>` : ''}
    </div>
  `).join('');
}

let allUsers = [];

async function loadUsers() {
  const res = await fetch('/admin/api/users?limit=50');
  if (res.status === 302 || res.redirected) {
    window.location = '/admin/login'; return;
  }
  allUsers = await res.json();
  renderUsers(allUsers);
}

function renderUsers(users) {
  const list = document.getElementById('user-list');
  if (!users.length) {
    list.innerHTML = '<p class="empty">Brak użytkowników.</p>';
    return;
  }
  list.innerHTML = users.map(u => `
    <div class="news-card" onclick="openUserModal('${escHtml(u.user_id)}')" style="cursor:pointer">
      <div class="info">
        <h3>${escHtml(u.user_id || 'Nieznany')}</h3>
        <p>${escHtml(u.character_name || '—')} ${u.character_class ? '<span style="color:#f4a01c">' + escHtml((u.character_spec ? u.character_spec + ' ' : '') + u.character_class) + '</span>' : ''}</p>
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
  if (!query) {
    renderUsers(allUsers);
    return;
  }
  const filtered = allUsers.filter(u => 
    (u.user_id && u.user_id.toLowerCase().includes(query)) ||
    (u.character_name && u.character_name.toLowerCase().includes(query))
  );
  renderUsers(filtered);
}

async function openUserModal(userId) {
  const modal = document.getElementById('user-modal');
  const list = document.getElementById('user-sim-list');
  modal.classList.remove('hidden');
  list.innerHTML = '<p class="empty">Ładowanie...</p>';
  
  const res = await fetch('/admin/api/users/' + encodeURIComponent(userId) + '/simulations');
  if (!res.ok) { list.innerHTML = '<p class="empty">Błąd ładowania.</p>'; return; }
  const sims = await res.json();
  
  if (!sims.length) {
    list.innerHTML = '<p class="empty">Brak symulacji.</p>';
    return;
  }
  list.innerHTML = sims.map(s => `
    <div class="sim-item">
      <div>
        <div style="font-weight:600">${escHtml(s.character_name || '—')}</div>
        <div style="font-size:0.8rem;color:#888">
          ${s.character_class ? '<span style="color:#f4a01c">' + escHtml((s.character_spec ? s.character_spec + ' ' : '') + s.character_class) + '</span> · ' : ''}
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

loadDashboard();
