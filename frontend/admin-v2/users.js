// admin-v2/users.js — zakładka Użytkownicy z paginacją i modalem szczegółów
(function () {
  const PAGE_SIZE = 25;

  let _currentOffset = 0;
  let _totalUsers    = 0;
  let _searchQuery   = '';
  let _searchTimer   = null;

  // ───────────────────────────────────────
  // Public API (wywoływane z tabs.js / HTML)
  // ───────────────────────────────────────

  window.loadUsers = function (offset = 0) {
    _currentOffset = offset;
    _fetchUsers();
  };

  window.filterUsers = function () {
    const q = (document.getElementById('user-search') || {}).value || '';
    _searchQuery = q.toLowerCase().trim();
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(() => {
      _currentOffset = 0;
      _fetchUsers();
    }, 300);
  };

  // ───────────────────────────────────────
  // Fetch
  // ───────────────────────────────────────

  async function _fetchUsers() {
    const list = document.getElementById('user-list');
    if (list) list.innerHTML = '<p class="empty" style="color:#555;padding:1rem">Ładowanie...</p>';

    try {
      const params = new URLSearchParams({
        limit:  PAGE_SIZE,
        offset: _currentOffset,
        total:  'true',
      });
      if (_searchQuery) params.set('search', _searchQuery);

      const res = await fetch('/admin/api/users?' + params.toString(), { credentials: 'include' });
      if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
      if (!res.ok) throw new Error('HTTP ' + res.status);

      const data = await res.json();
      const items = Array.isArray(data) ? data : (data.items || []);
      _totalUsers = Array.isArray(data) ? items.length : (data.total || items.length);

      _renderUsers(items);
      _renderPagination();
    } catch (e) {
      if (list) list.innerHTML = `<p class="empty" style="color:#e55;padding:1rem">Błąd: ${escHtml(e.message)}</p>`;
    }
  }

  // ───────────────────────────────────────
  // Render lista
  // ───────────────────────────────────────

  function _fmtDate(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso + (iso.endsWith('Z') ? '' : 'Z'))
        .toLocaleString('pl-PL', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    } catch { return iso.slice(0, 16).replace('T', ' '); }
  }

  function _renderUsers(users) {
    const list = document.getElementById('user-list');
    if (!list) return;

    if (!users.length) {
      list.innerHTML = '<p class="empty" style="color:#555;padding:1.5rem 1rem">Brak użytkowników.</p>';
      return;
    }

    list.innerHTML = `
      <table class="data-table" style="width:100%">
        <thead>
          <tr>
            <th>Użytkownik</th>
            <th>Postać</th>
            <th style="text-align:right">Symulacje</th>
            <th style="text-align:right">Śr. DPS</th>
            <th>Ostatnia sym.</th>
            <th>Dołączył/a</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${users.map(u => `
            <tr>
              <td style="font-size:0.85rem">
                <span style="color:#ccc;font-weight:500">${escHtml(u.user_id || '?')}</span>
                ${u.profile_private ? ' <span style="color:#555;font-size:0.72rem" title="Profil prywatny">🔒</span>' : ''}
              </td>
              <td style="font-size:0.85rem">
                ${u.character_name
                  ? `<span style="color:#f4a01c">${escHtml(u.character_name)}</span>`
                  : '<span style="color:#444">—</span>'}
                ${u.character_class ? `<span style="color:#555;font-size:0.78rem"> · ${escHtml(u.character_class)}</span>` : ''}
              </td>
              <td style="text-align:right">
                <span style="color:${u.sim_count > 0 ? '#ccc' : '#555'};font-weight:600">${u.sim_count}</span>
              </td>
              <td style="text-align:right;color:#aaa;font-size:0.85rem">
                ${u.avg_dps ? Number(u.avg_dps).toLocaleString('pl-PL', { maximumFractionDigits: 0 }) : '<span style="color:#444">—</span>'}
              </td>
              <td style="color:#666;font-size:0.82rem">${_fmtDate(u.last_sim)}</td>
              <td style="color:#555;font-size:0.78rem">${_fmtDate(u.registered_at)}</td>
              <td>
                <button class="btn secondary btn-sm" onclick="openUserDetailModal('${escHtml(u.user_id)}')">
                  Szczegóły
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>`;
  }

  // ───────────────────────────────────────
  // Paginacja
  // ───────────────────────────────────────

  function _renderPagination() {
    let container = document.getElementById('users-pagination');
    if (!container) {
      const card = document.querySelector('#tab-users .card');
      if (card) {
        container = document.createElement('div');
        container.id = 'users-pagination';
        container.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:0.75rem 1rem;border-top:1px solid #1e1e1e';
        card.appendChild(container);
      }
    }
    if (!container) return;

    const page       = Math.floor(_currentOffset / PAGE_SIZE) + 1;
    const totalPages = Math.ceil(_totalUsers / PAGE_SIZE) || 1;
    const hasPrev    = _currentOffset > 0;
    const hasNext    = _currentOffset + PAGE_SIZE < _totalUsers;

    container.innerHTML = `
      <span style="font-size:0.82rem;color:#555">
        Strona ${page} z ${totalPages} · ${_totalUsers} użytkowników
      </span>
      <div style="display:flex;gap:0.4rem">
        <button class="btn secondary btn-sm" onclick="loadUsers(${_currentOffset - PAGE_SIZE})" ${hasPrev ? '' : 'disabled'}>← Poprzednia</button>
        <button class="btn secondary btn-sm" onclick="loadUsers(${_currentOffset + PAGE_SIZE})" ${hasNext ? '' : 'disabled'}>Następna →</button>
      </div>`;
  }

  // ───────────────────────────────────────
  // Modal szczegółów użytkownika
  // z-index: 890 — confirm-modal (#confirm-modal) ma z-index wyższy
  // dzięki czemu adminConfirm() renderuje się ponad tym modalem
  // ───────────────────────────────────────

  let _modalUserId = null;

  window.openUserDetailModal = async function (userId) {
    _modalUserId = userId;

    let modal = document.getElementById('user-detail-modal');
    if (!modal) {
      modal = _createDetailModal();
      document.body.appendChild(modal);
    }

    modal.style.display = 'flex';
    document.getElementById('udm-title').textContent = userId;
    document.getElementById('udm-body').innerHTML = '<p style="color:#555;padding:1rem">Ładowanie...</p>';

    try {
      const res = await fetch('/admin/api/users/' + encodeURIComponent(userId) + '/simulations', { credentials: 'include' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const sims = await res.json();
      _renderModalSims(sims);
    } catch (e) {
      document.getElementById('udm-body').innerHTML = `<p style="color:#e55;padding:1rem">Błąd: ${escHtml(e.message)}</p>`;
    }
  };

  window.closeUserDetailModal = function () {
    const modal = document.getElementById('user-detail-modal');
    if (modal) modal.style.display = 'none';
    _modalUserId = null;
  };

  window.deleteAllSimsFromModal = async function () {
    if (!_modalUserId) return;
    if (typeof adminConfirm === 'function') {
      const ok = await adminConfirm(
        '🗑️ Usuń wszystkie symulacje',
        `Usunąć WSZYSTKIE symulacje użytkownika ${_modalUserId}? Operacja nieodwracalna.`,
        'Usuń wszystkie', true,
      );
      if (!ok) return;
    }
    try {
      const res = await fetch('/admin/api/users/' + encodeURIComponent(_modalUserId) + '/simulations', { method: 'DELETE', credentials: 'include' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      typeof toast === 'function' && toast(`✅ Usunięto ${data.deleted_count} symulacji`, '#7ecf7e');
      window.closeUserDetailModal();
      _fetchUsers();
    } catch (e) {
      typeof toast === 'function' && toast('❌ Błąd: ' + e.message, '#e55');
    }
  };

  // ───────────────────────────────────────
  // Usuwanie pojedynczej symulacji z modalu
  // ───────────────────────────────────────

  async function _deleteSimFromModal(jobId) {
    if (typeof adminConfirm === 'function') {
      const ok = await adminConfirm(
        '🗑️ Usuń symulację',
        `Usunąć symulację ${jobId}?\nOperacja nieodwracalna.`,
        'Usuń', true,
      );
      if (!ok) return;
    }
    try {
      const res = await fetch('/admin/api/simulations/' + encodeURIComponent(jobId), {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);

      // Usuń wiersz z DOM bez przeładowywania całego modalu
      const row = document.getElementById('udm-row-' + jobId);
      if (row) row.remove();

      typeof toast === 'function' && toast('✅ Symulacja usunięta', '#7ecf7e');
      _fetchUsers(); // odśwież liczniki w tabeli użytkowników
    } catch (e) {
      typeof toast === 'function' && toast('❌ Błąd: ' + e.message, '#e55');
    }
  }

  // Eksponuj globalnie — wywoływane z onclick w dynamicznym HTML
  window._deleteSimFromModal = _deleteSimFromModal;

  // ───────────────────────────────────────
  // Render tabeli symulacji w modalu
  // ───────────────────────────────────────

  function _renderModalSims(sims) {
    const body = document.getElementById('udm-body');
    if (!body) return;

    if (!sims.length) {
      body.innerHTML = '<p style="color:#555;font-size:0.85rem;padding:0.75rem 0">Brak symulacji.</p>';
      return;
    }

    const limited = sims.slice(0, 20);
    body.innerHTML = `
      ${sims.length > 20 ? `<p style="color:#666;font-size:0.8rem;margin-bottom:0.5rem">Pokazuję 20 z ${sims.length} symulacji</p>` : ''}
      <table style="width:100%;border-collapse:collapse;font-size:0.82rem">
        <thead>
          <tr style="color:#555;text-transform:uppercase;font-size:0.68rem;border-bottom:1px solid #2a2a2a">
            <th style="text-align:left;padding:0.3rem 0.4rem">Data</th>
            <th style="text-align:left;padding:0.3rem 0.4rem">Postać</th>
            <th style="text-align:left;padding:0.3rem 0.4rem">Spec</th>
            <th style="text-align:right;padding:0.3rem 0.4rem">DPS</th>
            <th style="text-align:left;padding:0.3rem 0.4rem">Build</th>
            <th style="padding:0.3rem 0.4rem"></th>
          </tr>
        </thead>
        <tbody>
          ${limited.map(s => `
            <tr style="border-bottom:1px solid #1a1a1a" id="udm-row-${escHtml(s.job_id)}">
              <td style="padding:0.3rem 0.4rem;color:#555;white-space:nowrap">${_fmtDate(s.created_at)}</td>
              <td style="padding:0.3rem 0.4rem;color:#ccc">
                ${escHtml(s.character_name || '—')}
                ${s.one_button_mode ? ' <span style="color:#f4a01c;font-size:0.72rem">1btn</span>' : ''}
              </td>
              <td style="padding:0.3rem 0.4rem;color:#888;font-size:0.8rem">
                ${escHtml((s.character_spec ? s.character_spec + ' ' : '') + (s.character_class || '—'))}
                ${s.fight_style ? `<span style="color:#555"> · ${escHtml(s.fight_style)}</span>` : ''}
              </td>
              <td style="padding:0.3rem 0.4rem;text-align:right;color:#f4a01c;font-weight:700">
                ${s.dps ? Number(s.dps).toLocaleString('pl-PL', { maximumFractionDigits: 0 }) : '—'}
              </td>
              <td style="padding:0.3rem 0.4rem;color:#444;font-size:0.75rem">${escHtml(s.wow_build || '—')}</td>
              <td style="padding:0.3rem 0.4rem;display:flex;gap:0.35rem;align-items:center">
                <a href="/#result/${escHtml(s.job_id)}" target="_blank" style="color:#7af;font-size:0.75rem" title="Otwórz wynik">🔗</a>
                <button
                  class="btn danger btn-sm"
                  style="font-size:0.72rem;padding:0.1rem 0.4rem;line-height:1.4"
                  onclick="_deleteSimFromModal('${escHtml(s.job_id)}')"
                  title="Usuń tę symulację"
                >🗑</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>`;
  }

  function _createDetailModal() {
    const overlay = document.createElement('div');
    overlay.id = 'user-detail-modal';
    // z-index 890 — poniżej #confirm-modal (.modal-overlay) który ma z-index wyższy przez CSS
    overlay.style.cssText = 'display:none;position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:890;align-items:center;justify-content:center';
    overlay.addEventListener('click', e => { if (e.target === overlay) window.closeUserDetailModal(); });

    overlay.innerHTML = `
      <div style="background:#111;border:1px solid #2a2a2a;border-radius:10px;padding:1.5rem;max-width:800px;width:95%;max-height:85vh;display:flex;flex-direction:column;gap:1rem">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-shrink:0">
          <div>
            <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:.05em;color:#555;margin-bottom:0.2rem">Użytkownik</div>
            <h3 id="udm-title" style="margin:0;font-size:0.95rem;color:#eee"></h3>
          </div>
          <div style="display:flex;gap:0.5rem;align-items:center">
            <button class="btn danger btn-sm" onclick="deleteAllSimsFromModal()">🗑 Usuń wszystkie</button>
            <button class="modal-close" onclick="window.closeUserDetailModal()">×</button>
          </div>
        </div>
        <div id="udm-body" style="overflow-y:auto;flex:1;min-height:0"></div>
      </div>`;

    return overlay;
  }

})();
