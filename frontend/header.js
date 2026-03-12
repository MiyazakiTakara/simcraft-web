function header() {
  return {
    appearance: { emoji: '⚔️', header_title: 'SimCraft Web' },
    sessionId: localStorage.getItem('simcraft_session'),
    mainChar: null,
    theme: localStorage.getItem('simcraft_theme') || 'dark',

    async init() {
      const isIndex = window.location.pathname === '/';

      if (isIndex) {
        const waitForApp = (resolve) => {
          if (window.__alpineApp) {
            resolve(window.__alpineApp);
          } else {
            setTimeout(() => waitForApp(resolve), 50);
          }
        };
        const appInstance = await new Promise(waitForApp);

        const sync = () => {
          const a = appInstance.appearance;
          if (
            a.header_title     !== this.appearance.header_title ||
            a.hero_title       !== this.appearance.hero_title ||
            a.emoji            !== this.appearance.emoji ||
            a.hero_custom_text !== this.appearance.hero_custom_text
          ) {
            this.appearance = { ...a };
          }

          const newSession = appInstance.sessionId;
          if (newSession !== this.sessionId) this.sessionId = newSession;

          const mc = appInstance.mainChar;
          const newName = mc ? mc.name : null;
          if (newName !== (this.mainChar ? this.mainChar.name : null)) {
            this.mainChar = mc ? { ...mc } : null;
          }

          const newTheme = appInstance.theme;
          if (newTheme !== this.theme) this.theme = newTheme;
        };

        sync();
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
