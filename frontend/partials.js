(function () {
  const PARTIAL_VERSION = '9';

  async function loadPartial(selector, url) {
    const el = document.querySelector(selector);
    if (!el) return;
    try {
      const r = await fetch(url + '?v=' + PARTIAL_VERSION);
      if (!r.ok) return;
      const html = await r.text();

      if (window.Alpine && window.Alpine.mutateDom) {
        // mutateDom wylacza MutationObserver Alpine na czas callbacku
        // dzieki temu wstrzykniecie HTML nie triggeruje reinit() zadnego komponentu
        window.Alpine.mutateDom(() => { el.innerHTML = html; });
      } else {
        el.innerHTML = html;
      }

      // initTree tylko na bezposrednich dzieciach z x-data
      if (window.Alpine && window.Alpine.initTree) {
        const roots = el.querySelectorAll(':scope > [x-data]');
        roots.forEach(root => window.Alpine.initTree(root));
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

  function tryLoad() {
    if (window.Alpine) {
      loadPartials();
    } else {
      let done = false;
      const fallback = setTimeout(() => {
        if (!done) { done = true; loadPartials(); }
      }, 5000);
      document.addEventListener('alpine:initialized', () => {
        if (!done) {
          done = true;
          clearTimeout(fallback);
          loadPartials();
        }
      }, { once: true });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tryLoad);
  } else {
    tryLoad();
  }

})();
