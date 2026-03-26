// admin-v2/maintenance.js — Maintenance Mode tab
(function () {

  // ---------- banner ----------

  function updateMaintenanceBanner(enabled) {
    let banner = document.getElementById('maintenance-topbar-banner');
    const topbar = document.querySelector('.topbar');
    if (!topbar) return;

    if (enabled) {
      if (!banner) {
        banner = document.createElement('div');
        banner.id = 'maintenance-topbar-banner';
        banner.style.cssText = [
          'background:#c0392b',
          'color:#fff',
          'font-size:0.78rem',
          'font-weight:600',
          'letter-spacing:0.04em',
          'padding:4px 16px',
          'text-align:center',
          'position:sticky',
          'top:0',
          'z-index:200',
        ].join(';');
        topbar.insertAdjacentElement('afterend', banner);
      }
      banner.textContent = '\u26A0\uFE0F MAINTENANCE MODE AKTYWNY — strona /sim jest zablokowana dla u\u017cytkownik\u00f3w';
    } else {
      banner?.remove();
    }
  }

  // ---------- load ----------

  async function loadMaintenance() {
    const toggle  = document.getElementById('maintenance-toggle');
    const msgArea = document.getElementById('maintenance-message');
    const status  = document.getElementById('maintenance-status');

    if (!toggle) return;

    try {
      const r = await fetch('/admin/api/maintenance', { credentials: 'include' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json();

      toggle.checked = !!d.enabled;
      if (msgArea) msgArea.value = d.message || '';
      if (status) {
        status.textContent = d.enabled ? '\u26A0\uFE0F Maintenance aktywny' : '\u2705 Aplikacja dzia\u0142a normalnie';
        status.className = 'maintenance-status ' + (d.enabled ? 'status-warn' : 'status-ok');
      }
      updateMaintenanceBanner(d.enabled);
    } catch (e) {
      console.error('[maintenance] load error', e);
      if (status) { status.textContent = '\u274C B\u0142\u0105d \u0142adowania'; status.className = 'maintenance-status status-error'; }
    }
  }

  // ---------- save ----------

  async function saveMaintenance() {
    const toggle  = document.getElementById('maintenance-toggle');
    const msgArea = document.getElementById('maintenance-message');
    const btn     = document.getElementById('maintenance-save-btn');

    if (!toggle) return;

    const enabled = toggle.checked;
    const message = msgArea ? msgArea.value.trim() : '';

    if (btn) { btn.disabled = true; btn.textContent = 'Zapisywanie\u2026'; }

    try {
      const r = await fetch('/admin/api/maintenance', {
        method:      'POST',
        credentials: 'include',
        headers:     { 'Content-Type': 'application/json' },
        body:        JSON.stringify({ enabled, message }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);

      updateMaintenanceBanner(enabled);

      const status = document.getElementById('maintenance-status');
      if (status) {
        status.textContent = enabled ? '\u26A0\uFE0F Maintenance aktywny' : '\u2705 Aplikacja dzia\u0142a normalnie';
        status.className = 'maintenance-status ' + (enabled ? 'status-warn' : 'status-ok');
      }

      _toast(enabled ? 'Maintenance mode w\u0142\u0105czony' : 'Maintenance mode wy\u0142\u0105czony', enabled ? 'warn' : 'ok');
    } catch (e) {
      console.error('[maintenance] save error', e);
      _toast('B\u0142\u0105d zapisu: ' + e.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Zapisz'; }
    }
  }

  // ---------- toast ----------

  function _toast(msg, type) {
    // Reuse globalny toast jesli istnieje (zdefiniowany w dashboard.js lub inline)
    if (typeof showAdminToast === 'function') { showAdminToast(msg, type); return; }
    const el = document.createElement('div');
    const colors = { ok: '#27ae60', warn: '#e67e22', error: '#c0392b' };
    el.style.cssText = [
      'position:fixed', 'bottom:24px', 'right:24px', 'z-index:9999',
      'padding:10px 20px', 'border-radius:8px', 'color:#fff', 'font-size:0.9rem',
      'font-weight:600', 'box-shadow:0 4px 16px rgba(0,0,0,.3)',
      'background:' + (colors[type] || '#333'),
    ].join(';');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  // ---------- expose ----------

  window.loadMaintenance = loadMaintenance;
  window.saveMaintenance = saveMaintenance;

})();
