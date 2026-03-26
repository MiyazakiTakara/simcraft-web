// ========== GDPR / RODO (#71) ==========

let _gdprUsers = [];        // cache listy użytkowników
let _gdprUsersLoaded = false;

// ---------- Ładowanie zakładki ----------

async function loadGdpr() {
  await _loadGdprUsers();
}

async function _loadGdprUsers() {
  if (_gdprUsersLoaded) return;
  try {
    const resp = await fetch('/admin/api/users?limit=500');
    if (!resp.ok) return;
    _gdprUsers = await resp.json();
    _gdprUsersLoaded = true;
  } catch (_) {}
}

// ---------- Autocomplete ----------

function _buildGdprAutocomplete(inputId, dropdownId, hiddenId) {
  const input    = document.getElementById(inputId);
  const dropdown = document.getElementById(dropdownId);
  const hidden   = document.getElementById(hiddenId);
  if (!input || !dropdown) return;

  function renderDropdown(q) {
    const lq = q.toLowerCase();
    const matches = _gdprUsers.filter(u =>
      (u.user_id        || '').toLowerCase().includes(lq) ||
      (u.character_name || '').toLowerCase().includes(lq)
    ).slice(0, 8);

    if (!matches.length || !q) {
      dropdown.classList.add('hidden');
      dropdown.innerHTML = '';
      return;
    }

    dropdown.innerHTML = matches.map(u => {
      const cls  = u.character_class ? ` <span class="gdpr-ac-class">(${u.character_class})</span>` : '';
      const sims = `<span class="gdpr-ac-sims">${u.sim_count} sim</span>`;
      return `<div class="gdpr-ac-item" data-id="${u.user_id}">
        <span class="gdpr-ac-name">${u.character_name || '—'}${cls}</span>
        <span class="gdpr-ac-id">${u.user_id}</span>
        ${sims}
      </div>`;
    }).join('');

    dropdown.classList.remove('hidden');
  }

  input.addEventListener('input', () => {
    if (hidden) hidden.value = '';
    renderDropdown(input.value);
  });

  input.addEventListener('focus', () => {
    if (input.value) renderDropdown(input.value);
  });

  dropdown.addEventListener('mousedown', e => {
    const item = e.target.closest('.gdpr-ac-item');
    if (!item) return;
    e.preventDefault();
    const id = item.dataset.id;
    input.value  = `${id}`;
    if (hidden) hidden.value = id;
    dropdown.classList.add('hidden');
    dropdown.innerHTML = '';
    input.dataset.selectedId = id;
  });

  document.addEventListener('click', e => {
    if (!input.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.classList.add('hidden');
    }
  });
}

// Inicjalizacja autocomplete po załadowaniu DOM
document.addEventListener('DOMContentLoaded', () => {
  _buildGdprAutocomplete('gdpr-user-id',   'gdpr-export-dropdown', 'gdpr-export-hidden');
  _buildGdprAutocomplete('gdpr-delete-id', 'gdpr-delete-dropdown', 'gdpr-delete-hidden');
});

function _getGdprUserId(inputId, hiddenId) {
  const hidden = document.getElementById(hiddenId);
  if (hidden?.value) return hidden.value.trim();
  return document.getElementById(inputId)?.value?.trim() || '';
}

// ---------- Art. 15 — Eksport danych ----------

async function exportUserData() {
  const userId = _getGdprUserId('gdpr-user-id', 'gdpr-export-hidden');
  if (!userId) {
    adminToast('⚠️ Wybierz lub wpisz BNet ID użytkownika.', '#fa0');
    return;
  }

  const btn = document.getElementById('gdpr-export-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Eksportowanie...'; }

  try {
    const resp = await fetch(`/admin/api/users/${encodeURIComponent(userId)}/export`);

    if (resp.status === 404) {
      adminToast('❌ Użytkownik nie znaleziony.', '#e55');
      return;
    }
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      adminToast(`❌ Błąd: ${err.detail || resp.status}`, '#e55');
      return;
    }

    const disposition = resp.headers.get('Content-Disposition') || '';
    const fnMatch     = disposition.match(/filename="([^"]+)"/);
    const filename    = fnMatch ? fnMatch[1] : `gdpr_export_${userId}.json`;

    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    adminToast(`✅ Eksport pobrany: ${filename}`, '#4c4');

  } catch (e) {
    adminToast(`❌ Błąd sieci: ${e.message}`, '#e55');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Pobierz dane (JSON)'; }
  }
}

// ---------- Art. 17 — Usunięcie konta ----------

async function deleteUserAccount() {
  const userId = _getGdprUserId('gdpr-delete-id', 'gdpr-delete-hidden');
  if (!userId) {
    adminToast('⚠️ Wybierz lub wpisz BNet ID użytkownika.', '#fa0');
    return;
  }

  const confirmed = await showConfirm(
    '⚠️ Usuń konto użytkownika (RODO)',
    `Czy na pewno chcesz trwale usunąć konto:\n\n${userId}\n\nUnięte zostaną:\n• profil użytkownika\n• cała historia symulacji\n• pliki wyników (.json)\n• wpisy kolejki zadań\n\nKonto Keycloak należy usunąć ręcznie.\n\nTej operacji nie można cofać.`
  );
  if (!confirmed) return;

  const btn = document.getElementById('gdpr-delete-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Usuwanie...'; }

  try {
    const resp = await fetch(`/admin/api/users/${encodeURIComponent(userId)}`, {
      method: 'DELETE',
    });

    if (resp.status === 404) {
      adminToast('❌ Użytkownik nie znaleziony.', '#e55');
      return;
    }
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      adminToast(`❌ Błąd: ${err.detail || resp.status}`, '#e55');
      return;
    }

    const data = await resp.json();
    adminToast(
      `✅ Konto usunięte: ${userId} | Symulacje: ${data.deleted_simulations} | Pliki: ${data.deleted_files}`,
      '#4c4'
    );

    document.getElementById('gdpr-delete-id').value    = '';
    document.getElementById('gdpr-delete-hidden').value = '';
    _gdprUsersLoaded = false;

    if (typeof loadUsers === 'function') loadUsers();

  } catch (e) {
    adminToast(`❌ Błąd sieci: ${e.message}`, '#e55');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Usuń konto'; }
  }
}
