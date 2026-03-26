function header() {
  return {
    appearance: { emoji: '\u2694\ufe0f', header_title: 'SimCraft Web' },
    sessionId: localStorage.getItem('simcraft_session'),
    mainChar: null,
    bnetId: null,
    theme: localStorage.getItem('simcraft_theme') || 'dark',

    async init() {
      // Global session-expired handler
      window.addEventListener('simcraft:session-expired', () => {
        localStorage.removeItem('simcraft_session');
        this.sessionId = null;
        this.mainChar  = null;
        this._injectBanner(Alpine.store('i18n').t('errors.session_expired'), 'warning');
        setTimeout(() => { window.location.href = '/auth/logout'; }, 2000);
      }, { once: true });

      // Appearance
      try {
        const r = await fetch('/api/appearance');
        if (r.ok) {
          this.appearance = await r.json();
          document.title = (this.appearance.emoji || '\u2694\ufe0f') + ' ' + (this.appearance.header_title || 'SimCraft Web');
        }
      } catch(e) {}

      // System message banner
      try {
        const r = await fetch('/api/system-message');
        if (r.ok) {
          const d = await r.json();
          if (d.message) {
            this._injectBanner(d.message, d.type || 'info');
          }
        }
      } catch(e) {}

      // Session
      if (this.sessionId) {
        try {
          const r = await fetch(`/auth/session/info?session=${encodeURIComponent(this.sessionId)}`);
          if (r.ok) {
            const data = await r.json();
            const name  = data.main_character_name  || null;
            const realm = data.main_character_realm || null;
            this.mainChar = name ? { name, realm } : null;
            this.bnetId   = data.bnet_id || null;
          // Proaktywny refresh tokenu BNet
          try {
            const rr = await fetch(`/auth/session/refresh?session=${encodeURIComponent(this.sessionId)}`, { method: 'POST' });
            if (rr.status === 401) {
              window.dispatchEvent(new CustomEvent('simcraft:session-expired'));
              return;
            }
          } catch(e) { /* BNet niedostępny — nie karamy */ }
          } else {
            this.sessionId = null;
            localStorage.removeItem('simcraft_session');
          }
        } catch(e) {}
      }
    },

    _injectBanner(message, type) {
      if (document.getElementById('system-banner')) return;
      const icons = { info: '\u2139\ufe0f', warning: '\u26a0\ufe0f', danger: '\ud83d\udea8' };
      const icon = icons[type] || icons.info;
      const closeLabel = Alpine.store('i18n').t('common.close');
      const banner = document.createElement('div');
      banner.id = 'system-banner';
      banner.className = `system-banner system-banner--${type}`;
      banner.innerHTML = `
        <span class="system-banner__icon">${icon}</span>
        <span class="system-banner__text">${this._esc(message)}</span>
        <button class="system-banner__close" onclick="document.getElementById('system-banner').remove()" aria-label="${closeLabel}">&times;</button>
      `;
      document.body.appendChild(banner);
    },

    _esc(str) {
      return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    },

    goHome() {
      window.location.href = '/';
    },

    goSim() {
      window.location.href = '/sim';
    },

    goTo(path) {
      window.location.href = path;
    },

    goProfile() {
      if (this.bnetId) {
        window.open('/u/' + encodeURIComponent(this.bnetId), '_blank');
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
