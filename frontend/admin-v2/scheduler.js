// admin-v2/scheduler.js — obsługa sekcji Auto-rebuild w zakładce Konfiguracja

async function loadSchedulerConfig() {
  try {
    const r = await fetch('/admin/api/scheduler');
    if (!r.ok) throw new Error(await r.text());
    const d = await r.json();
    _renderSchedulerConfig(d);
  } catch (e) {
    document.getElementById('scheduler-section').innerHTML =
      `<p style="color:#e55">Błąd ładowania schedulera: ${e.message}</p>`;
  }
}

function _renderSchedulerConfig(d) {
  // enabled toggle
  const chk = document.getElementById('scheduler-enabled');
  if (chk) chk.checked = !!d.enabled;

  // interval
  const inp = document.getElementById('scheduler-interval-h');
  if (inp) inp.value = d.interval_h ?? 6;

  // status info
  const statusEl = document.getElementById('scheduler-status-info');
  if (statusEl) {
    const lines = [];
    if (d.running) {
      lines.push(`<span class="badge ok">▶ Działa</span>`);
    } else {
      lines.push(`<span class="badge warn">⏸ Zatrzymany</span>`);
    }
    if (d.next_run) {
      const t = new Date(d.next_run);
      lines.push(`Następny check: <b>${t.toLocaleString('pl-PL')}</b>`);
    }
    if (d.last_check_ts) {
      const t2 = new Date(d.last_check_ts);
      const st = d.last_check_status === 'ok'
        ? '<span style="color:#4c4">✓ ok</span>'
        : `<span style="color:#e55">${_esc(d.last_check_status)}</span>`;
      lines.push(`Ostatni check: ${t2.toLocaleString('pl-PL')} — ${st}`);
    }
    if (d.last_wow_build) {
      lines.push(`Ostatni znany WoW build: <code>${_esc(d.last_wow_build)}</code>`);
    }
    statusEl.innerHTML = lines.join('<br>');
  }
}

async function saveSchedulerConfig() {
  const enabled    = document.getElementById('scheduler-enabled')?.checked ?? true;
  const interval_h = parseInt(document.getElementById('scheduler-interval-h')?.value ?? '6', 10);
  const resultEl   = document.getElementById('scheduler-result');

  if (isNaN(interval_h) || interval_h < 1 || interval_h > 168) {
    resultEl.textContent = 'Interwał musi być między 1 a 168 godzin.';
    resultEl.className   = 'form-result error';
    return;
  }

  try {
    const r = await fetch('/admin/api/scheduler', {
      method:  'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ enabled, interval_h }),
    });
    if (!r.ok) throw new Error(await r.text());
    const d = await r.json();
    _renderSchedulerConfig(d);
    resultEl.textContent = '✓ Zapisano';
    resultEl.className   = 'form-result ok';
    setTimeout(() => { resultEl.textContent = ''; }, 3000);
  } catch (e) {
    resultEl.textContent = 'Błąd: ' + e.message;
    resultEl.className   = 'form-result error';
  }
}

async function schedulerTriggerNow() {
  const btn    = document.getElementById('scheduler-trigger-btn');
  const result = document.getElementById('scheduler-result');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Sprawdzanie...'; }
  try {
    const r = await fetch('/admin/api/scheduler/trigger-now', { method: 'POST' });
    if (!r.ok) throw new Error(await r.text());
    result.textContent = '✓ Sprawdzanie WoW build uruchomione w tle. Odśwież za chwilę.';
    result.className   = 'form-result ok';
    setTimeout(() => loadSchedulerConfig(), 3000);
  } catch (e) {
    result.textContent = 'Błąd: ' + e.message;
    result.className   = 'form-result error';
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🔍 Sprawdź teraz'; }
  }
}

function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
