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

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('user-modal').addEventListener('click', function(e) {
    if (e.target === this) closeUserModal();
  });
});
