function header() {
  return {
    appearance: { emoji: '⚔️', header_title: 'SimCraft Web', hero_title: 'WoW DPS Simulator' },
    sessionId: localStorage.getItem('simcraft_session'),
    mainChar: null,
    theme: localStorage.getItem('simcraft_theme') || 'dark',

    async init() {
      // Wczytaj appearance
      try {
        const r = await fetch('/api/appearance');
        if (r.ok) {
          this.appearance = await r.json();
          window.__appearance = this.appearance;
        }
      } catch(e) {}

      // Wczytaj info o sesji (main char)
      if (this.sessionId) {
        try {
          const r = await fetch('/auth/session/info', {
            headers: { 'X-Session-ID': this.sessionId }
          });
          if (r.ok) {
            const data = await r.json();
            this.mainChar = data.main_character || null;
          } else {
            // Sesja wygasła
            this.sessionId = null;
            localStorage.removeItem('simcraft_session');
          }
        } catch(e) {}
      }
    },

    goHome() {
      if (window.location.pathname === '/') {
        // Na index.html — użyj Alpine router jeśli dostępny
        if (window.__alpineApp?.navigateTo) {
          window.__alpineApp.navigateTo('home');
        } else {
          window.location.href = '/';
        }
      } else {
        window.location.href = '/';
      }
    },

    goSim() {
      if (window.__alpineApp?.navigateTo) {
        window.__alpineApp.navigateTo('symulacje');
      } else {
        window.location.href = '/#symulacje';
      }
    },

    goTo(hash) {
      if (window.location.pathname === '/') {
        // Parsuj hash na widok i tab
        const h = hash.replace('/#', '');
        const [view, tab] = h.split('-');
        if (window.__alpineApp?.navigateTo) {
          window.__alpineApp.navigateTo(view);
          if (tab && window.__alpineApp) window.__alpineApp.profileTab = tab;
        } else {
          window.location.hash = view;
        }
      } else {
        window.location.href = hash;
      }
    },

    async logout() {
      localStorage.removeItem('simcraft_session');
      window.location.href = '/auth/logout';
    },

    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('simcraft_theme', this.theme);
      document.documentElement.setAttribute('data-theme', this.theme);
    },
  };
}
