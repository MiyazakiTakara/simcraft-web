function header() {
  return {
    appearance: { emoji: '⚔️', header_title: 'SimCraft Web' },
    sessionId: localStorage.getItem('simcraft_session'),
    mainChar: null,
    theme: localStorage.getItem('simcraft_theme') || 'dark',

    async init() {
      const isIndex = window.location.pathname === '/';

      // Na index.html — dane pobiera app(), czekamy aż będzie gotowy
      if (isIndex) {
        const waitForApp = (resolve) => {
          if (window.__alpineApp) {
            resolve(window.__alpineApp);
          } else {
            setTimeout(() => waitForApp(resolve), 50);
          }
        };
        const appInstance = await new Promise(waitForApp);

        // Sync reaktywny: obserwuj zmiany w app()
        this.$watch('_tick', () => {});
        const sync = () => {
          this.appearance = appInstance.appearance;
          this.sessionId  = appInstance.sessionId;
          this.mainChar   = appInstance.mainChar
            ? appInstance.mainChar
            : (appInstance.mainCharSaved ? { name: appInstance.mainChar?.name } : null);
          this.theme      = appInstance.theme;
        };
        sync();
        // Polling co 300ms żeby łapać zmiany (mainChar, sesja, theme)
        setInterval(sync, 300);
        return;
      }

      // Na pozostałych stronach (result, rankings) — samodzielnie
      try {
        const r = await fetch('/api/appearance');
        if (r.ok) {
          this.appearance = await r.json();
          window.__appearance = this.appearance;
        }
      } catch(e) {}

      if (this.sessionId) {
        try {
          const r = await fetch(`/auth/session/info?session=${encodeURIComponent(this.sessionId)}`);
          if (r.ok) {
            const data = await r.json();
            const name  = data.main_character_name  || null;
            const realm = data.main_character_realm || null;
            this.mainChar = name ? { name, realm } : null;
          } else {
            this.sessionId = null;
            localStorage.removeItem('simcraft_session');
          }
        } catch(e) {}
      }
    },

    goHome() {
      if (window.__alpineApp?.navigateTo) {
        window.__alpineApp.navigateTo('home');
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
      const h = hash.replace('/#', '');
      const [view, tab] = h.split('-');
      if (window.__alpineApp?.navigateTo) {
        window.__alpineApp.navigateTo(view);
        if (tab && window.__alpineApp) window.__alpineApp.profileTab = tab;
      } else {
        window.location.href = hash;
      }
    },

    async logout() {
      if (window.__alpineApp?.logout) {
        window.__alpineApp.logout();
      } else {
        localStorage.removeItem('simcraft_session');
        window.location.href = '/auth/logout';
      }
    },

    toggleTheme() {
      if (window.__alpineApp?.toggleTheme) {
        window.__alpineApp.toggleTheme();
        this.theme = window.__alpineApp.theme;
      } else {
        this.theme = this.theme === 'dark' ? 'light' : 'dark';
        localStorage.setItem('simcraft_theme', this.theme);
        document.documentElement.setAttribute('data-theme', this.theme);
      }
    },
  };
}
