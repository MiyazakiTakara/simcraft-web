async function loadLimits() {
  const res = await fetch('/admin/api/limits');
  if (!res.ok) { toast(adminT('admin.toast.limits_error'), '#e88'); return; }
  const data = await res.json();
  document.getElementById('limit-concurrent').value = data.max_concurrent_sims;
  document.getElementById('limit-rate').value       = data.rate_limit_per_minute;
  document.getElementById('limit-timeout').value    = data.job_timeout;
}

async function saveLimits() {
  const payload = {
    max_concurrent_sims:   parseInt(document.getElementById('limit-concurrent').value),
    rate_limit_per_minute: parseInt(document.getElementById('limit-rate').value),
    job_timeout:           parseInt(document.getElementById('limit-timeout').value),
  };
  const res    = await fetch('/admin/api/limits', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = document.getElementById('limits-result');
  if (res.ok) {
    result.textContent = adminT('admin.toast.limits_saved');
    result.style.color = '#4c4';
  } else {
    result.textContent = adminT('admin.toast.error_generic');
    result.style.color = '#e55';
  }
}

async function deleteOldSims() {
  const days = parseInt(document.getElementById('delete-days').value);
  if (!days || days < 1) { toast(adminT('admin.toast.days_required'), '#e88'); return; }
  if (!confirm(adminT('admin.confirm.delete_older') + ` ${days}?`)) return;
  const res  = await fetch(`/admin/api/simulations?older_than_days=${days}`, { method: 'DELETE' });
  const data = await res.json();
  const el   = document.getElementById('delete-result');
  el.textContent = adminT('admin.toast.deleted_count').replace('{{n}}', data.deleted);
  el.style.color = '#4c4';
  loadDashboard();
}

async function deleteAllSims() {
  if (!confirm(adminT('admin.confirm.delete_all_1'))) return;
  if (!confirm(adminT('admin.confirm.delete_all_2'))) return;
  const res  = await fetch('/admin/api/simulations', { method: 'DELETE' });
  const data = await res.json();
  const el   = document.getElementById('delete-result');
  el.textContent = adminT('admin.toast.deleted_count').replace('{{n}}', data.deleted);
  el.style.color = '#e55';
  loadDashboard();
}
