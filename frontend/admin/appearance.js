document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.emoji-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.emoji-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
    });
  });
});

async function loadAppearance() {
  try {
    const res = await fetch('/admin/api/appearance');
    if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
    const data = await res.json();
    document.getElementById('appearance-header-title').value = data.header_title || '';
    document.getElementById('appearance-hero-title').value   = data.hero_title   || '';
    const customEl = document.getElementById('appearance-hero-custom');
    if (customEl) customEl.value = data.hero_custom_text || '';
    const selectedEmoji = data.emoji || '⚔️';
    document.querySelectorAll('.emoji-btn').forEach(btn => {
      btn.classList.toggle('selected', btn.dataset.emoji === selectedEmoji);
    });
  } catch (e) {
    console.error('Error loading appearance:', e);
  }
}

async function saveAppearance() {
  const headerTitle      = document.getElementById('appearance-header-title').value;
  const heroTitle        = document.getElementById('appearance-hero-title').value;
  const selectedEmojiBtn = document.querySelector('.emoji-btn.selected');
  const emoji            = selectedEmojiBtn ? selectedEmojiBtn.dataset.emoji : '⚔️';
  const customEl         = document.getElementById('appearance-hero-custom');
  const heroCustomText   = customEl ? customEl.value : '';
  try {
    const res = await fetch('/admin/api/appearance', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ header_title: headerTitle, hero_title: heroTitle, emoji, hero_custom_text: heroCustomText }),
    });
    const result = await res.json();
    const el     = document.getElementById('appearance-result');
    if (res.ok) {
      el.textContent = 'Zapisano!';
      el.style.color = '#4c4';
      toast('Wygląd zapisany', '#4c4');
    } else {
      el.textContent = 'Błąd: ' + (result.detail || 'Nieznany błąd');
      el.style.color = '#e55';
    }
  } catch (e) {
    const el = document.getElementById('appearance-result');
    el.textContent = 'Błąd połączenia';
    el.style.color = '#e55';
  }
}
