// admin-v2/results.js — zakładka Pliki wyników
(function () {

  let _allSimulations = [];
  let _selectedUser   = null;

  function _formatTs(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleString('pl-PL', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch { return iso; }
  }

  function _fmtDps(dps) {
    if (!dps) return '—';
    return Number(dps).toLocaleString('pl-PL', { maximumFractionDigits: 0 });
  }

  function _escHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // ── STATS ────────────────────────────────────────────────────────────────

  window.loadResultsStats = async function () {
    const loader   = document.getElementById('results-stats-loader');
    const errEl    = document.getElementById('results-stats-error');
    if (loader) loader.style.display = '';
    if (errEl)  errEl.style.display  = 'none';

    try {
      const res = await fetch('/admin/api/dashboard');
      if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
      if (!res.ok) throw new Error('HTTP ' + res.status);

      const data = await res.json();
      const stats = data.stats || {};

      _setEl('results-total-count',    stats.total_simulations ?? '—');
      _setEl('results-today-count',    stats.today_simulations ?? '—');
      _setEl('results-week-count',     stats.week_simulations  ?? '—');
      _setEl('results-month-count',    stats.month_simulations ?? '—');
      _setEl('results-error-rate-24h', stats.error_rate_24h != null ? stats.error_rate_24h + '%' : '—');

      // Top DPS
      _renderTopDps(data.top_dps || []);

      // Klasy
      _renderClassChart(data.class_distribution || []);

    } catch (e) {
      console.error('loadResultsStats error:', e);
      if (errEl) { errEl.textContent = 'Błąd ładowania statystyk: ' + e.message; errEl.style.display = ''; }
    } finally {
      if (loader) loader.style.display = 'none';
    }
  };

  function _setEl(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function _renderTopDps(rows) {
    const tbody = document.getElementById('results-top-dps-tbody');
    if (!tbody) return;
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty-state">Brak danych</td></tr>'; return; }
    tbody.innerHTML = rows.map((r, i) => `
      <tr>
        <td>${i + 1}</td>
        <td>${_escHtml(r.character_name || '—')}</td>
        <td>${_escHtml(r.character_class || '—')} / ${_escHtml(r.character_spec || '—')}</td>
        <td><strong>${_fmtDps(r.dps)}</strong></td>
        <td>
          <a href="/#result/${_escHtml(r.job_id)}" target="_blank" class="btn-link">🔗</a>
          <button class="btn btn-xs btn-danger" onclick="deleteSimulation('${_escHtml(r.job_id)}')">🗑</button>
        </td>
      </tr>`).join('');
  }

  function _renderClassChart(dist) {
    const container = document.getElementById('results-class-dist');
    if (!container) return;
    if (!dist.length) { container.innerHTML = '<p class="empty-state">Brak danych</p>'; return; }
    const total = dist.reduce((s, d) => s + d.count, 0);
    container.innerHTML = dist.map(d => {
      const pct = total ? Math.round(d.count / total * 100) : 0;
      return `
        <div class="dist-row">
          <span class="dist-label">${_escHtml(d.character_class || 'Unknown')}</span>
          <div class="dist-bar-wrap">
            <div class="dist-bar" style="width:${pct}%"></div>
          </div>
          <span class="dist-val">${d.count} (${pct}%)</span>
        </div>`;
    }).join('');
  }

  // ── USER SIMULATIONS ─────────────────────────────────────────────────────

  window.loadUserSimulations = async function (userId) {
    _selectedUser = userId;
    const modal  = document.getElementById('results-user-modal');
    const tbody  = document.getElementById('results-user-sims-tbody');
    const title  = document.getElementById('results-user-modal-title');
    const errEl  = document.getElementById('results-user-modal-error');

    if (modal)  modal.style.display  = 'flex';
    if (tbody)  tbody.innerHTML      = '<tr><td colspan="5">Ładowanie…</td></tr>';
    if (title)  title.textContent    = `Symulacje użytkownika: ${userId}`;
    if (errEl)  errEl.style.display  = 'none';

    try {
      const res = await fetch(`/admin/api/users/${encodeURIComponent(userId)}/simulations`);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      _allSimulations = await res.json();
      _renderUserSimsTable(_allSimulations);
    } catch (e) {
      if (errEl) { errEl.textContent = 'Błąd: ' + e.message; errEl.style.display = ''; }
      if (tbody) tbody.innerHTML = '';
    }
  };

  function _renderUserSimsTable(sims) {
    const tbody = document.getElementById('results-user-sims-tbody');
    if (!tbody) return;
    if (!sims.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-state">Brak symulacji</td></tr>';
      return;
    }
    tbody.innerHTML = sims.map(s => `
      <tr>
        <td>${_formatTs(s.created_at)}</td>
        <td>${_escHtml(s.character_name || '—')}</td>
        <td>${_escHtml(s.character_class || '—')} / ${_escHtml(s.character_spec || '—')}</td>
        <td><strong>${_fmtDps(s.dps)}</strong></td>
        <td>
          <a href="/#result/${_escHtml(s.job_id)}" target="_blank" class="btn-link">🔗</a>
          <button class="btn btn-xs btn-danger" onclick="deleteSimulation('${_escHtml(s.job_id)}')">🗑</button>
        </td>
      </tr>`).join('');
  }

  window.closeResultsUserModal = function () {
    const modal = document.getElementById('results-user-modal');
    if (modal) modal.style.display = 'none';
    _selectedUser   = null;
    _allSimulations = [];
  };

  window.deleteAllUserSimulations = async function () {
    if (!_selectedUser) return;
    if (!confirm(`Usunąć WSZYSTKIE symulacje użytkownika ${_selectedUser}? Operacja nieodwracalna.`)) return;
    try {
      const res = await fetch(`/admin/api/users/${encodeURIComponent(_selectedUser)}/simulations`, { method: 'DELETE' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (typeof adminToast === 'function')
        adminToast(`Usunięto ${data.deleted_count ?? '?'} symulacji`, '#4c4');
      window.closeResultsUserModal();
      await window.loadResultsStats();
    } catch (e) {
      if (typeof adminToast === 'function') adminToast('Błąd: ' + e.message, '#e55');
    }
  };

  // ── SINGLE SIM DELETE ─────────────────────────────────────────────────────

  window.deleteSimulation = async function (jobId) {
    if (!confirm(`Usunąć symulację ${jobId}?`)) return;
    try {
      const res = await fetch(`/admin/api/simulations/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      if (typeof adminToast === 'function') adminToast('Symulacja usunięta', '#4c4');

      // odśwież widok modal lub statystyki
      if (_selectedUser) {
        _allSimulations = _allSimulations.filter(s => s.job_id !== jobId);
        _renderUserSimsTable(_allSimulations);
      } else {
        await window.loadResultsStats();
      }
    } catch (e) {
      if (typeof adminToast === 'function') adminToast('Błąd: ' + e.message, '#e55');
    }
  };

  // ── SEARCH ────────────────────────────────────────────────────────────────

  window.filterUserSims = function (query) {
    if (!_allSimulations.length) return;
    if (!query) { _renderUserSimsTable(_allSimulations); return; }
    const q = query.toLowerCase();
    _renderUserSimsTable(_allSimulations.filter(s =>
      (s.character_name  || '').toLowerCase().includes(q) ||
      (s.character_class || '').toLowerCase().includes(q) ||
      (s.job_id          || '').toLowerCase().includes(q)
    ));
  };

})();
