let allUsers = [];
let _userSimsModified = false;

async function loadUsers() {
  const res = await fetch('/admin/api/users?limit=100');
  if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
  allUsers = await res.json();
  renderUsers(allUsers);
}

function renderUsers(users) {
  const list = document.getElementById('user-list');
  if (!users.length) {
    list.innerHTML = `<p class="empty">${adminT('admin.users.empty')}</p>`;
    return;
  }

  list.innerHTML = `
    <table class="user-table">
      <thead>
        <tr>
          <th>${adminT('admin.users.col.user')}</th>
          <th>${adminT('admin.users.col.character')}</th>
          <th class="num">${adminT('admin.users.col.sims')}</th>
          <th class="num">${adminT('admin.users.col.avg_dps')}</th>
          <th>${adminT('admin.users.col.last_sim')}</th>
          <th>${adminT('admin.users.col.registered')}</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${users.map(u => `
          <tr class="user-row${u.sim_count === 0 ? ' no-sims' : ''}" data-user-id="${escHtml(u.user_id)}">
            <td class="user-id-cell">
              <span class="user-id-text">${escHtml(u.user_id || adminT('common.unknown'))}</span>
              ${u.profile_private ? '<span class="user-private-badge" title="Profil prywatny">🔒</span>' : ''}
            </td>
            <td class="char-cell">
              ${u.character_name
                ? `<span class="char-name">${escHtml(u.character_name)}</span>`
                : '<span class="no-data">—</span>'
              }
            </td>
            <td class="num">
              <span class="sim-count ${u.sim_count === 0 ? 'zero' : ''}">${u.sim_count}</span>
            </td>
            <td class="num">
              ${u.avg_dps ? `<span class="dps-val">${Number(u.avg_dps).toLocaleString()}</span>` : '<span class="no-data">—</span>'}
            </td>
            <td class="date-cell">${u.last_sim ? fmtShort(u.last_sim) : '<span class="no-data">—</span>'}</td>
            <td class="date-cell">${u.registered_at ? fmtShort(u.registered_at) : '<span class="no-data">—</span>'}</td>
            <td class="action-cell">
              ${u.sim_count > 0
                ? `<button class="btn-row" onclick="openUserModal('${escHtml(u.user_id)}')">${adminT('admin.users.view_sims')}</button>`
                : ''
              }
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function fmtShort(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  } catch { return iso.slice(0, 16).replace('T', ' '); }
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

let _currentModalUserId = null;

async function openUserModal(userId) {
  _currentModalUserId = userId;
  _userSimsModified = false;
  const modal = document.getElementById('user-modal');
  const list  = document.getElementById('user-sim-list');
  modal.classList.remove('hidden');
  list.innerHTML = `<p class="empty">${adminT('common.loading')}</p>`;

  const res = await fetch('/admin/api/users/' + encodeURIComponent(userId) + '/simulations');
  if (!res.ok) { list.innerHTML = `<p class="empty">${adminT('admin.toast.error_generic')}</p>`; return; }
  const sims = await res.json();
  if (!sims.length) { list.innerHTML = `<p class="empty">${adminT('admin.users.no_sims')}</p>`; return; }

  list.innerHTML = `
    <div class="sim-actions-bar">
      <label style="display:flex;align-items:center;gap:0.4rem;cursor:pointer;color:#aaa;font-size:0.85rem">
        <input type="checkbox" id="sim-select-all" onchange="toggleSelectAllSims(this.checked)">
        ${adminT('common.select_all') || 'Zaznacz wszystkie'}
      </label>
      <div style="display:flex;gap:0.5rem;margin-left:auto">
        <button class="btn secondary btn-sm" id="btn-delete-selected" onclick="deleteSelectedSims()" disabled>
          ☒ ${adminT('admin.users.delete_selected') || 'Usuń zaznaczone'}
        </button>
        <button class="btn danger btn-sm" onclick="deleteAllUserSims()">
          🗑️ ${adminT('admin.users.delete_all') || 'Usuń wszystkie'}
        </button>
      </div>
    </div>
    ${sims.map(s => `
      <div class="sim-item" data-job-id="${escHtml(s.job_id)}">
        <label style="display:flex;align-items:flex-start;gap:0.6rem;cursor:pointer;width:100%">
          <input type="checkbox" class="sim-checkbox" value="${escHtml(s.job_id)}"
            onchange="onSimCheckboxChange()" style="margin-top:0.3rem;flex-shrink:0">
          <div style="flex:1">
            <div style="font-weight:600">${escHtml(s.character_name || '—')}</div>
            <div style="font-size:0.8rem;color:#888">
              ${s.character_class ? `<span style="color:#f4a01c">${escHtml((s.character_spec ? s.character_spec + ' ' : '') + s.character_class)}</span> · ` : ''}
              ${escHtml(s.fight_style || '')} · ${fmtShort(s.created_at)}
              ${s.wow_build ? `<span style="color:#555"> · ${escHtml(s.wow_build)}</span>` : ''}
            </div>
            ${s.one_button_mode ? '<span class="sim-badge one-button">🕑 1-Button</span>' : ''}
          </div>
          <div style="text-align:right;flex-shrink:0">
            <div style="font-weight:700;color:#f4a01c;font-size:1.05rem">${Number(s.dps).toLocaleString()} DPS</div>
            <a class="sim-link" href="/result/${s.job_id}" target="_blank">${adminT('admin.users.view_result')}</a>
          </div>
        </label>
      </div>
    `).join('')}
  `;
}

function onSimCheckboxChange() {
  const checked = document.querySelectorAll('.sim-checkbox:checked').length;
  const btn = document.getElementById('btn-delete-selected');
  if (btn) btn.disabled = checked === 0;

  const all    = document.querySelectorAll('.sim-checkbox').length;
  const selAll = document.getElementById('sim-select-all');
  if (selAll) {
    selAll.indeterminate = checked > 0 && checked < all;
    selAll.checked = checked === all;
  }
}

function toggleSelectAllSims(checked) {
  document.querySelectorAll('.sim-checkbox').forEach(cb => cb.checked = checked);
  const btn = document.getElementById('btn-delete-selected');
  if (btn) btn.disabled = !checked;
}

async function deleteSelectedSims() {
  const checkboxes = document.querySelectorAll('.sim-checkbox:checked');
  if (!checkboxes.length) return;

  const jobIds = Array.from(checkboxes).map(cb => cb.value);
  const n   = jobIds.length;
  const ok  = await adminConfirm(
    `🗑️ Usuń zaznaczone symulacje`,
    `Czy na pewno chcesz usunąć ${n} zaznaczon${n === 1 ? 'ą' : 'ych'} symulacj${n === 1 ? 'ę' : 'ę'}? Tej operacji nie można cofnąć.`,
    'Usuń'
  );
  if (!ok) return;

  const btn = document.getElementById('btn-delete-selected');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Usuwam…'; }

  let successCount = 0;
  let failCount    = 0;

  for (const jobId of jobIds) {
    const res = await fetch('/admin/api/simulations/' + encodeURIComponent(jobId), { method: 'DELETE' });
    if (res.ok) {
      successCount++;
      _userSimsModified = true;
      const item = document.querySelector(`.sim-item[data-job-id="${jobId}"]`);
      if (item) item.remove();
    } else {
      failCount++;
    }
  }

  if (failCount === 0) {
    toast(`✅ Usunięto ${successCount} symulacji`, '#7ecf7e');
  } else {
    toast(`⚠️ Usunięto ${successCount}, błąd przy ${failCount}`, '#e5a000');
  }

  onSimCheckboxChange();

  const remaining = document.querySelectorAll('.sim-checkbox').length;
  if (remaining === 0) {
    closeUserModal();
  }
}

async function deleteAllUserSims() {
  if (!_currentModalUserId) return;

  const ok = await adminConfirm(
    '🗑️ Usuń wszystkie symulacje',
    `Czy na pewno chcesz usunąć WSZYSTKIE symulacje użytkownika ${_currentModalUserId}? Tej operacji nie można cofnąć.`,
    'Usuń wszystkie'
  );
  if (!ok) return;

  const res = await fetch(
    '/admin/api/users/' + encodeURIComponent(_currentModalUserId) + '/simulations',
    { method: 'DELETE' }
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    toast('❌ Błąd: ' + (err.detail || res.status), '#e55');
    return;
  }

  const data = await res.json();
  _userSimsModified = true;
  toast(`✅ Usunięto ${data.deleted_count} symulacji`, '#7ecf7e');
  closeUserModal();
}

function closeUserModal() {
  document.getElementById('user-modal').classList.add('hidden');
  _currentModalUserId = null;
  if (_userSimsModified) {
    _userSimsModified = false;
    loadUsers();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('user-modal').addEventListener('click', function(e) {
    if (e.target === this) closeUserModal();
  });
});
