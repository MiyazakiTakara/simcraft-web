// admin-v2/tasks.js — #64: testowa symulacja z panelu admina

(function () {

  // ───────────────────────────────────────
  // State
  // ───────────────────────────────────────
  let _polling = null;
  let _pendingJobId = null;

  // ───────────────────────────────────────
  // Publiczne API
  // ───────────────────────────────────────
  window.runTestSim = async function () {
    const textarea  = document.getElementById('test-sim-profile');
    const fightSel  = document.getElementById('test-sim-fight-style');
    const iterInput = document.getElementById('test-sim-iterations');
    const btn       = document.getElementById('test-sim-btn');
    const resultEl  = document.getElementById('test-sim-result');

    const profile    = (textarea?.value || '').trim();
    const fightStyle = fightSel?.value || 'Patchwerk';
    const iterations = parseInt(iterInput?.value || '1000', 10);

    if (!profile) {
      _setResult('error', '⚠️ Wklej profil .simc przed uruchomieniem.');
      textarea?.focus();
      return;
    }

    btn.disabled = true;
    btn.textContent = '⏳ Uruchamianie...';
    _setResult('info', '⏳ Wysyłanie żądania...');

    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          addon_text:  profile,
          fight_style: fightStyle,
          iterations:  Math.min(iterations, 10000),
        }),
      });

      if (res.status === 429) {
        _setResult('error', '🚫 Serwer zajęty lub rate limit. Spróbuj za chwilę.');
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        _setResult('error', `❌ Błąd: ${err.detail || res.statusText}`);
        return;
      }

      const data = await res.json();
      const jobId = data.job_id;
      _pendingJobId = jobId;

      _setResult('info',
        `✅ Symulacja uruchomiona — <code>${escHtml(jobId)}</code><br>` +
        `<small style="color:#888">Monitoruję status...</small>`
      );

      // Przełącz na zakładkę Zadania
      if (typeof switchTab === 'function') {
        switchTab('tasks');
      }
      if (typeof loadTasks === 'function') {
        loadTasks();
      }

      // Polling statusu
      _startPolling(jobId);

    } catch (err) {
      _setResult('error', `❌ Błąd sieci: ${escHtml(err.message)}`);
    } finally {
      btn.disabled = false;
      btn.textContent = '▶ Uruchom symulację';
    }
  };

  // ───────────────────────────────────────
  // Polling statusu joba
  // ───────────────────────────────────────
  function _startPolling(jobId) {
    _stopPolling();
    let attempts = 0;
    const MAX_ATTEMPTS = 120; // maks 120 * 3s = 6 min

    _polling = setInterval(async () => {
      attempts++;
      if (attempts > MAX_ATTEMPTS) {
        _stopPolling();
        _setResult('error', `⏱️ Timeout monitorowania — sprawdź zadania ręcznie.`);
        return;
      }

      try {
        const res = await fetch(`/api/job/${encodeURIComponent(jobId)}`);
        if (!res.ok) { _stopPolling(); return; }
        const job = await res.json();

        if (job.status === 'done') {
          _stopPolling();
          _setResult('success',
            `✅ Symulacja zakończona — ` +
            `<a href="/result/${escHtml(jobId)}" target="_blank" ` +
            `style="color:#e8c57a;font-weight:600">Otwórz wynik ↗</a>`
          );
          if (typeof loadTasks === 'function') loadTasks();
        } else if (job.status === 'error') {
          _stopPolling();
          _setResult('error',
            `❌ Symulacja zakończyła się błędem: <br>` +
            `<small style="color:#e55;font-family:monospace">${escHtml(job.error || 'nieznany błąd')}</small>`
          );
          if (typeof loadTasks === 'function') loadTasks();
        }
        // status 'running' — czekamy dalej
      } catch (_) {
        // ignoruj pojedyncze błędy sieci
      }
    }, 3000);
  }

  function _stopPolling() {
    if (_polling) { clearInterval(_polling); _polling = null; }
  }

  // ───────────────────────────────────────
  // Helpers
  // ───────────────────────────────────────
  function _setResult(type, html) {
    const el = document.getElementById('test-sim-result');
    if (!el) return;
    const colors = { info: '#888', success: '#4c9', error: '#e55' };
    el.style.color   = colors[type] || '#888';
    el.style.display = 'block';
    el.innerHTML     = html;
  }

  // Wyeksportuj escHtml jeśli nie istnieje globalnie
  if (typeof window.escHtml !== 'function') {
    window.escHtml = function (s) {
      return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    };
  }

})();
