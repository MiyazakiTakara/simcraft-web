async function loadLimits() {
  const res = await fetch('/admin/api/limits');
  if (!res.ok) { toast('Błąd ładowania limitów', '#e88'); return; }
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
    result.textContent = 'Limity zapisane (nie trwałe w demo).';
    result.style.color = '#4c4';
  } else {
    result.textContent = 'Błąd zapisu limitów.';
    result.style.color = '#e55';
  }
}

async function deleteOldSims() {
  const days = parseInt(document.getElementById('delete-days').value);
  if (!days || days < 1) { toast('Podaj liczbę dni!', '#e88'); return; }
  if (!confirm(`Na pewno usunąć wszystkie symulacje starsze niż ${days} dni?`)) return;
  const res  = await fetch(`/admin/api/simulations?older_than_days=${days}`, { method: 'DELETE' });
  const data = await res.json();
  const el   = document.getElementById('delete-result');
  el.textContent = `Usunięto ${data.deleted} symulacji.`;
  el.style.color = '#4c4';
  loadDashboard();
}

async function deleteAllSims() {
  if (!confirm('Na pewno usunąć WSZYSTKIE symulacje? To nieodwracalne!')) return;
  if (!confirm('Jesteś PEWNY? Wszystkie dane zostaną utracone!')) return;
  const res  = await fetch('/admin/api/simulations', { method: 'DELETE' });
  const data = await res.json();
  const el   = document.getElementById('delete-result');
  el.textContent = `Usunięto ${data.deleted} symulacji.`;
  el.style.color = '#e55';
  loadDashboard();
}
