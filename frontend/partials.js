/**
 * partials.js — ładuje header i footer jako HTML partiale i inicjuje Alpine na załadowanych drzewach.
 * Użycie: <script src="/partials.js"></script> na każdej stronie.
 * Wymaga: Alpine.js, i18n.js, header.js załadowanych przed lub równocześnie.
 */
(function () {
  async function loadPartial(selector, url) {
    const el = document.querySelector(selector);
    if (!el) return;
    try {
      const r = await fetch(url + '?v=1');
      if (!r.ok) return;
      el.innerHTML = await r.text();
      // Inicjuj Alpine na nowym drzewie (jeśli Alpine już wystartowało)
      if (window.Alpine?.initTree) {
        window.Alpine.initTree(el);
      }
    } catch (e) {
      console.warn('loadPartial failed:', url, e);
    }
  }

  async function loadPartials() {
    await Promise.all([
      loadPartial('#site-header', '/partials/header.html'),
      loadPartial('#site-footer', '/partials/footer.html'),
    ]);
  }

  // Czekaj na DOMContentLoaded + Alpine gotowy
  document.addEventListener('DOMContentLoaded', () => {
    // Alpine może jeszcze nie być załadowane (defer) — poczekaj na alpine:init lub odpali się po nim
    if (window.Alpine) {
      loadPartials();
    } else {
      document.addEventListener('alpine:init', () => loadPartials());
      // Fallback: jeśli alpine:init już minął
      setTimeout(() => {
        if (!document.querySelector('#site-header header')) loadPartials();
      }, 300);
    }
  });
})();
