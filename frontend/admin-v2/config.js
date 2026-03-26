// admin-v2/config.js — zakładka Konfiguracja (#56)
(function () {
  const FIELDS = [
    'max_concurrent_sims',
    'job_timeout',
    'guest_sims_enabled',
    'history_limit_per_user',
    'rate_limit_per_minute',
    'one_button_mode_enabled',
    'public_history_limit',
    'user_history_limit',
    'char_cache_ttl_minutes',
  ];

  // Pola obsługiwane przez toggle (nie checkbox)
  const TOGGLE_FIELDS = ['one_button_mode_enabled'];

  function getToggleState(key) {
    const btn = document.getElementById('config-toggle-' + key.replaceAll('_', '-'));
    return btn ? btn.classList.contains('active') : false;
  }

  function setToggleState(key, value) {
    const btn = document.getElementById('config-toggle-' + key.replaceAll('_', '-'));
    if (!btn) return;
    if (value) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  }

  function showToast(msg, ok = true) {
    const t = document.getElementById('config-toast');
    if (!t) return;
    t.textContent = msg;
    t.className = 'toast ' + (ok ? 'toast-ok' : 'toast-err');
    t.classList.remove('hidden');
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.add('hidden'), 3500);
  }

  async function loadConfig() {
    const statusEl = document.getElementById('config-status');
    try {
      const res = await fetch('/admin/api/config', { credentials: 'include' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      FIELDS.forEach(key => {
        if (TOGGLE_FIELDS.includes(key)) {
          setToggleState(key, data[key] === true || data[key] === 'true');
          return;
        }
        const el = document.getElementById('config-' + key.replaceAll('_', '-'));
        if (!el) return;
        if (el.type === 'checkbox') {
          el.checked = data[key] === true || data[key] === 'true';
        } else {
          el.value = data[key] ?? '';
        }
      });

      if (statusEl) {
        statusEl.textContent = `Wczytano — ${new Date().toLocaleTimeString('pl-PL')}`;
        statusEl.className = 'badge badge-ok';
      }
    } catch (e) {
      console.error('[config] loadConfig error', e);
      if (statusEl) {
        statusEl.textContent = 'Błąd wczytywania';
        statusEl.className = 'badge badge-err';
      }
    }
  }

  async function saveConfig() {
    const btn = document.getElementById('config-save-btn');
    if (btn) btn.disabled = true;

    const payload = {};
    FIELDS.forEach(key => {
      if (TOGGLE_FIELDS.includes(key)) {
        payload[key] = getToggleState(key);
        return;
      }
      const el = document.getElementById('config-' + key.replaceAll('_', '-'));
      if (!el) return;
      if (el.type === 'checkbox') {
        payload[key] = el.checked;
      } else if (el.type === 'number') {
        payload[key] = Number(el.value);
      } else {
        payload[key] = el.value;
      }
    });

    try {
      const res = await fetch('/admin/api/config', {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showToast('✅ Konfiguracja zapisana');
      await loadConfig();
    } catch (e) {
      console.error('[config] saveConfig error', e);
      showToast('❌ Błąd zapisu: ' + e.message, false);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  window.loadConfig = loadConfig;
  window.saveConfig = saveConfig;
})();
