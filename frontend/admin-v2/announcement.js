// ===== KOMUNIKATY SYSTEMOWE (#59) =====

const ANNOUNCEMENT_TYPE_STYLES = {
  info:    { bg: '#1a3a5c', border: '#2a6496', color: '#add4f7', icon: 'ℹ️' },
  warning: { bg: '#3a2e00', border: '#a07800', color: '#f5d76e', icon: '⚠️' },
  danger:  { bg: '#3a0a0a', border: '#a02020', color: '#f79090', icon: '🚨' },
};

function updateAnnouncementPreview(message, type) {
  const preview      = document.getElementById('announcement-preview');
  const previewEmpty = document.getElementById('announcement-preview-empty');
  if (!preview || !previewEmpty) return;

  if (!message) {
    preview.style.display = 'none';
    previewEmpty.style.display = '';
    return;
  }

  const s = ANNOUNCEMENT_TYPE_STYLES[type] || ANNOUNCEMENT_TYPE_STYLES.info;
  preview.style.display       = 'flex';
  preview.style.alignItems    = 'center';
  preview.style.gap           = '0.6rem';
  preview.style.background    = s.bg;
  preview.style.border        = `1px solid ${s.border}`;
  preview.style.color         = s.color;
  preview.style.borderRadius  = '6px';
  preview.style.padding       = '0.55rem 1rem';
  preview.style.fontSize      = '0.88rem';
  preview.innerHTML = `<span>${s.icon}</span><span>${message}</span>`;
  previewEmpty.style.display  = 'none';
}

async function loadAnnouncement() {
  try {
    const res = await fetch('/admin/api/system-message');
    if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
    if (!res.ok) return;
    const data = await res.json();

    const textEl   = document.getElementById('announcement-text');
    const typeEl   = document.getElementById('announcement-type');
    const statusEl = document.getElementById('announcement-status');

    if (textEl) textEl.value = data.message || '';
    if (typeEl) typeEl.value = data.type || 'info';

    if (statusEl) {
      if (data.message) {
        statusEl.textContent = '🟢 Aktywny';
        statusEl.className = 'badge success';
      } else {
        statusEl.textContent = '⚪ Nieaktywny';
        statusEl.className = 'badge';
      }
    }

    updateAnnouncementPreview(data.message || '', data.type || 'info');
  } catch (e) {
    console.error('loadAnnouncement error:', e);
  }
}

async function saveAnnouncement() {
  const text = document.getElementById('announcement-text')?.value?.trim();
  const type = document.getElementById('announcement-type')?.value || 'info';

  if (!text) {
    toast('Wpisz treść komunikatu', '#e55');
    return;
  }

  try {
    const res = await fetch('/admin/api/system-message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, type }),
    });
    if (!res.ok) throw new Error(await res.text());
    toast('✅ Komunikat opublikowany', '#4c4');
    loadAnnouncement();
  } catch (e) {
    toast('Błąd: ' + e.message, '#e55');
  }
}

async function clearAnnouncement() {
  const ok = await adminConfirm(
    '🗑️ Usuń komunikat',
    'Czy na pewno chcesz usunąć aktywny komunikat systemowy?',
    'Usuń'
  );
  if (!ok) return;
  try {
    const res = await fetch('/admin/api/system-message', { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    document.getElementById('announcement-text').value = '';
    toast('🗑️ Komunikat usunięty', '#aaa');
    loadAnnouncement();
  } catch (e) {
    toast('Błąd: ' + e.message, '#e55');
  }
}

// Stare funkcje modalowe zachowane jako no-op dla kompatybilności wstecznej
function closeClearAnnouncementModal() {}
function confirmClearAnnouncement()   {}
