function settingsMixin() {
  return {
    loading:    true,
    isLoggedIn: false,
    error:      null,
    saving:     false,
    saveMsg:    '',
    saveMsgOk:  true,
    form: {
      main_character_name:  '',
      main_character_realm: '',
      profile_private:      false,
    },

    async init() {
      this.loading    = true;
      this.error      = null;
      this.isLoggedIn = false;

      const session = window._session;
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
      } catch (e) {
        this.error = this.$store.i18n.t('errors.network');
      } finally {
        this.loading = false;
      }
    },

    async save() {
      this.saving  = true;
      this.saveMsg = '';
      const session = window._session;

      // Walidacja
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
        // Aktualizuj lokalny stan Alpine (main char w headerze)
        if (this.$store && this.$store.session) {
          this.$store.session.main_character_name  = data.main_character_name  || '';
          this.$store.session.main_character_realm = data.main_character_realm || '';
        }
        this.saveMsg   = this.$store.i18n.t('settings.saved');
        this.saveMsgOk = true;

        // Wyczyść komunikat po 4s
        setTimeout(() => { this.saveMsg = ''; }, 4000);

      } catch (e) {
        this.saveMsg   = this.$store.i18n.t('errors.network');
        this.saveMsgOk = false;
      } finally {
        this.saving = false;
      }
    },

    setTheme(theme) {
      if (this.$store && this.$store.theme !== undefined) {
        this.$store.theme = theme;
        localStorage.setItem('simcraft_theme', theme);
        document.documentElement.setAttribute('data-theme', theme);
      }
    },
  };
}
