// Audit Log (#67) — kto, kiedy i co zmienił w panelu admina

let _auditOffset   = 0;
let _auditLimit    = 50;
let _auditTotal    = 0;
let _auditUsername = '';
let _auditAction   = '';
let _auditInterval = null;

const AUDIT_REFRESH_MS = 30_000;

async function loadAudit() {
  _auditOffset   = 0;
  _auditUsername = document.getElementById('audit-filter-username')?.value.trim() || '';
  _auditAction   = document.getElementById('audit-filter-action')?.value.trim() || '';
  await _fetchAudit();
  markRefreshed('audit');
  _startAuditRefresh();
}

function _startAuditRefresh() {
  if (_auditInterval) return;
  _auditInterval = setInterval(async () => {
    await _fetchAudit();
    markRefreshed('audit');
  }, AUDIT_REFRESH_MS);
}

function pauseAudit() {
  if (_auditInterval) {
    clearInterval(_auditInterval);
    _auditInterval = null;
  }
}

async function _fetchAudit() {
  const params = new URLSearchParams({
    limit:  _auditLimit,
    offset: _auditOffset,
  });
  if (_auditUsername) params.set('username', _auditUsername);
  if (_auditAction)   params.set('action',   _auditAction);

  const tbody   = document.getElementById('audit-tbody');
  const info    = document.getElementById('audit-pagination-info');
  const btnPrev = document.getElementById('audit-btn-prev');
  const btnNext = document.getElementById('audit-btn-next');

  try {
    const res  = await fetch(`/admin/api/audit-log?${params}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    _auditTotal = data.total;

    tbody.innerHTML = '';
    if (!data.items.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;opacity:.5">Brak wpisów</td></tr>';
    } else {
      data.items.forEach(row => {
        const tr = document.createElement('tr');
        const ts = row.created_at
          ? new Date(row.created_at + 'Z').toLocaleString('pl-PL')
          : '—';
        let details = '';
        if (row.details) {
          try {
            const parsed = JSON.parse(row.details);
            details = Object.entries(parsed)
              .map(([k, v]) => `<span class="audit-detail-key">${k}:</span> ${String(v).slice(0, 80)}`)
              .join('<br>');
          } catch {
            details = String(row.details).slice(0, 200);
          }
        }
        tr.innerHTML = `
          <td>${ts}</td>
          <td><strong>${row.username}</strong></td>
          <td><code class="audit-action">${row.action}</code></td>
          <td class="audit-details">${details}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    const from = _auditTotal === 0 ? 0 : _auditOffset + 1;
    const to   = Math.min(_auditOffset + _auditLimit, _auditTotal);
    if (info) info.textContent = `${from}–${to} z ${_auditTotal}`;
    if (btnPrev) btnPrev.disabled = _auditOffset === 0;
    if (btnNext) btnNext.disabled = _auditOffset + _auditLimit >= _auditTotal;

  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4" style="color:var(--error)">Błąd: ${e.message}</td></tr>`;
  }
}

function auditPrev() {
  if (_auditOffset < _auditLimit) return;
  _auditOffset -= _auditLimit;
  _fetchAudit();
}

function auditNext() {
  if (_auditOffset + _auditLimit >= _auditTotal) return;
  _auditOffset += _auditLimit;
  _fetchAudit();
}

function auditResetFilters() {
  const fu = document.getElementById('audit-filter-username');
  const fa = document.getElementById('audit-filter-action');
  if (fu) fu.value = '';
  if (fa) fa.value = '';
  loadAudit();
}
