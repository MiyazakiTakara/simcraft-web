function settingsMixin() {
  return {
    loading:    true,
    isLoggedIn: false,
    error:      null,
    saving:     false,
    saveMsg:    '',
    saveMsgOk:  true,
    characters: [],
    form: {
      main_character_name:  '',
      main_character_realm: '',
      profile_private:      false,
      manualEntry:          false,
    },

    onCharSelect() {
      const ch = this.characters.find(c => c.name === this.form.main_character_name);
      if (ch) {
        this.form.main_character_realm = ch.realm;
      }
    },

    onManualToggle() {
      if (this.form.manualEntry) {
        this.form.main_character_name = '';
        this.form.main_character_realm = '';
      }
    },

    _getSession() {
      return window.__alpineApp?.sessionId || localStorage.getItem('simcraft_session');
    },

    _waitForSession() {
      return new Promise((resolve) => {
        const session = this._getSession();
        if (session) { resolve(session); return; }
        // __alpineApp może jeszcze nie być gotowy — czekamy max 2s
        let tries = 0;
        const interval = setInterval(() => {
          const s = this._getSession();
          if (s || ++tries > 40) {
            clearInterval(interval);
            resolve(s || null);
          }
        }, 50);
      });
    },

    async init() {
      this.loading    = true;
      this.error      = null;
      this.isLoggedIn = false;

      const session = await this._waitForSession();
      if (!session) {
        this.loading = false;
        return;
      }

      try {
        const res = await fetch(`/auth/session/settings?session=${session}`);
        if (res.status === 401) {
          this.loading = false;
          return;
        }
        if (res.status === 404) {
          this.error   = this.$store.i18n.t('errors.not_found');
          this.loading = false;
          return;
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          this.error   = this.$store.i18n.t('common.error_prefix') + (data.detail || res.status);
          this.loading = false;
          return;
        }
        const data = await res.json();
        this.form.main_character_name  = data.main_character_name  || '';
        this.form.main_character_realm = data.main_character_realm || '';
        this.form.profile_private      = !!data.profile_private;
        this.isLoggedIn = true;

        // Ładuj listę postaci
        try {
          const charsRes = await fetch(`/api/characters?session=${session}`);
          if (charsRes.ok) {
            const chars = await charsRes.json();
            this.characters = chars.sort((a, b) => (b.level ?? 0) - (a.level ?? 0));
          }
        } catch (e) {
          console.warn('Failed to load characters for picker', e);
        }
      } catch (e) {
        this.error = this.$store.i18n.t('errors.network');
      } finally {
        this.loading = false;
      }
    },

    async save() {
      this.saving  = true;
      this.saveMsg = '';
      const session = this._getSession();

      const name  = this.form.main_character_name.trim();
      const realm = this.form.main_character_realm.trim();
      if (name && !realm) {
        this.saveMsg   = this.$store.i18n.t('settings.realm_required');
        this.saveMsgOk = false;
        this.saving    = false;
        return;
      }

      try {
        const res = await fetch(`/auth/session/settings?session=${session}`, {
          method:  'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({
            main_character_name:  name  || null,
            main_character_realm: realm || null,
            profile_private:      this.form.profile_private,
          }),
        });

        if (res.status === 400) {
          const data = await res.json().catch(() => ({}));
          this.saveMsg   = this.$store.i18n.t('common.error_prefix') + (data.detail || '400');
          this.saveMsgOk = false;
          return;
        }
        if (res.status === 401) {
          this.saveMsg   = this.$store.i18n.t('errors.session_expired');
          this.saveMsgOk = false;
          return;
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          this.saveMsg   = this.$store.i18n.t('common.error_prefix') + (data.detail || res.status);
          this.saveMsgOk = false;
          return;
        }

        const data = await res.json();
        if (window.__alpineApp) {
          window.__alpineApp.mainChar = data.main_character_name
            ? { name: data.main_character_name, realm: data.main_character_realm }
            : null;
        }
        this.saveMsg   = this.$store.i18n.t('settings.saved');
        this.saveMsgOk = true;
        setTimeout(() => { this.saveMsg = ''; }, 4000);

      } catch (e) {
        this.saveMsg   = this.$store.i18n.t('errors.network');
        this.saveMsgOk = false;
      } finally {
        this.saving = false;
      }
    },

    setTheme(theme) {
      if (window.__alpineApp?.toggleTheme && theme !== window.__alpineApp.theme) {
        window.__alpineApp.toggleTheme();
      } else {
        localStorage.setItem('simcraft_theme', theme);
        document.documentElement.setAttribute('data-theme', theme);
      }
    },
  };
}
