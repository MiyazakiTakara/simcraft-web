/**
 * partials.js — ładuje header i footer jako HTML partiale i inicjuje Alpine na załadowanych drzewach.
 */
(function () {
  async function loadPartial(selector, url) {
    const el = document.querySelector(selector);
    if (!el) return;
    try {
      const r = await fetch(url + '?v=2');
      if (!r.ok) return;
      el.innerHTML = await r.text();
      if (window.Alpine?.initTree) {
        window.Alpine.initTree(el);
      }
    } catch (e) {
      console.warn('loadPartial failed:', url, e);
    }
  }

  function loadPartials() {
    return Promise.all([
      loadPartial('#site-header', '/partials/header.html'),
      loadPartial('#site-footer', '/partials/footer.html'),
    ]);
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (window.Alpine) {
      // Alpine już załadowane synchronicznie (bez defer)
      loadPartials();
    } else {
      // Alpine z defer — czekamy na alpine:initialized (po init wszystkich komponentów)
      document.addEventListener('alpine:initialized', () => loadPartials(), { once: true });
    }
  });
})();
