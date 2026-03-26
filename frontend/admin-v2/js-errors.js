// admin-v2/js-errors.js — zakładka Błędy JS
(function () {

  let _jsErrors = [];

  function _isJsError(log) {
    const msg = log.message || '';
    return msg.startsWith('[uncaught_error]') || msg.startsWith('[unhandled_rejection]');
  }

  function _formatTs(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleString('pl-PL', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    } catch { return iso; }
  }

  function _stripPrefix(msg) {
    return msg
      .replace(/^\[uncaught_error\]\s*/, '')
      .replace(/^\[unhandled_rejection\]\s*/, '');
  }

  function _badgeType(msg) {
    if (msg.startsWith('[uncaught_error]'))      return '<span class="badge badge-error">Error</span>';
    if (msg.startsWith('[unhandled_rejection]')) return '<span class="badge badge-warn">Promise</span>';
    return '';
  }

  function _renderTable(errors) {
    const tbody = document.getElementById('js-errors-tbody');
    const empty = document.getElementById('js-errors-empty');
    const count = document.getElementById('js-errors-count');

    if (count) count.textContent = errors.length;

    if (!tbody) return;
    if (!errors.length) {
      tbody.innerHTML = '';
      if (empty) empty.style.display = '';
      return;
    }
    if (empty) empty.style.display = 'none';

    tbody.innerHTML = errors.map(e => {
      const badge   = _badgeType(e.message || '');
      const message = _escHtml(_stripPrefix(e.message || ''));
      const context = e.context ? _escHtml(e.context) : '';
      const ts      = _formatTs(e.created_at);
      return `
        <tr>
          <td>${ts}</td>
          <td>${badge}</td>
          <td class="js-error-msg">${message}</td>
          <td>${context ? `<details><summary>stack</summary><pre class="log-pre">${context}</pre></details>` : '—'}</td>
        </tr>`;
    }).join('');
  }

  function _escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  window.loadJsErrors = async function () {
    const loader = document.getElementById('js-errors-loader');
    const err    = document.getElementById('js-errors-fetch-error');
    if (loader) loader.style.display = '';
    if (err)    err.style.display    = 'none';

    try {
      const res = await fetch('/admin/api/logs?level=ERROR&limit=200');
      if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
      if (!res.ok) throw new Error('HTTP ' + res.status);

      const data = await res.json();
      const logs = Array.isArray(data) ? data : (data.items || []);
      _jsErrors = logs.filter(_isJsError);
      _renderTable(_jsErrors);
    } catch (e) {
      console.error('loadJsErrors error:', e);
      if (err) { err.textContent = 'Błąd ładowania: ' + e.message; err.style.display = ''; }
    } finally {
      if (loader) loader.style.display = 'none';
    }
  };

  window.clearJsErrorsView = function () {
    _jsErrors = [];
    _renderTable([]);
    const count = document.getElementById('js-errors-count');
    if (count) count.textContent = '0';
    if (typeof adminToast === 'function') adminToast('Widok wyczyszczony (logi na serwerze bez zmian)', '#aaa');
  };

  window.deleteJsErrorLogs = async function () {
    if (!confirm('Usunąć wszystkie logi ERROR ze serwera?')) return;
    try {
      const res = await fetch('/admin/api/logs', { method: 'DELETE' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (typeof adminToast === 'function')
        adminToast(`Usunięto ${data.deleted ?? '?'} logów`, '#4c4');
      await window.loadJsErrors();
    } catch (e) {
      if (typeof adminToast === 'function') adminToast('Błąd usuwania logów: ' + e.message, '#e55');
    }
  };

  window.filterJsErrors = function (query) {
    if (!query) { _renderTable(_jsErrors); return; }
    const q = query.toLowerCase();
    _renderTable(_jsErrors.filter(e =>
      (e.message  || '').toLowerCase().includes(q) ||
      (e.context  || '').toLowerCase().includes(q)
    ));
  };

})();
