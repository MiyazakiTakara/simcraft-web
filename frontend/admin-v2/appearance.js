// admin-v2/appearance.js — zakładka Wygląd
(function () {

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.emoji-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.emoji-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
      });
    });
  });

  window.loadAppearance = async function () {
    try {
      const res = await fetch('/admin/api/appearance');
      if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
      if (!res.ok) {
        console.error('loadAppearance: HTTP', res.status);
        return;
      }
      const data = await res.json();

      const headerEl = document.getElementById('appearance-header-title');
      const heroEl   = document.getElementById('appearance-hero-title');
      const customEl = document.getElementById('appearance-hero-custom');

      if (headerEl) headerEl.value = data.header_title || '';
      if (heroEl)   heroEl.value   = data.hero_title   || '';
      if (customEl) customEl.value = data.hero_custom_text || '';

      const selectedEmoji = data.emoji || '⚔️';
      document.querySelectorAll('.emoji-btn').forEach(btn => {
        btn.classList.toggle('selected', btn.dataset.emoji === selectedEmoji);
      });
    } catch (e) {
      console.error('loadAppearance error:', e);
    }
  };

  window.saveAppearance = async function () {
    const headerTitle      = document.getElementById('appearance-header-title')?.value || '';
    const heroTitle        = document.getElementById('appearance-hero-title')?.value   || '';
    const selectedEmojiBtn = document.querySelector('.emoji-btn.selected');
    const emoji            = selectedEmojiBtn ? selectedEmojiBtn.dataset.emoji : '⚔️';
    const customEl         = document.getElementById('appearance-hero-custom');
    const heroCustomText   = customEl ? customEl.value : '';

    const resultEl = document.getElementById('appearance-result');

    try {
      const res = await fetch('/admin/api/appearance', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          header_title:    headerTitle,
          hero_title:      heroTitle,
          emoji,
          hero_custom_text: heroCustomText,
        }),
      });
      const result = await res.json();
      if (res.ok) {
        if (resultEl) { resultEl.textContent = 'Zapisano!'; resultEl.style.color = '#4c4'; }
        if (typeof adminToast === 'function') adminToast('Wygląd zapisany', '#4c4');
      } else {
        if (resultEl) {
          resultEl.textContent = 'Błąd: ' + (result.detail || 'Nieznany błąd');
          resultEl.style.color = '#e55';
        }
      }
    } catch (e) {
      if (resultEl) { resultEl.textContent = 'Błąd połączenia'; resultEl.style.color = '#e55'; }
    }
  };

})();
