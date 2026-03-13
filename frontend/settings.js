function settingsMixin() {
  const result = {
    loading: true,
    isLoggedIn: false,
    error: null,
    saving: false,
    saveMsg: '',
    saveMsgOk: true,
    characters: [],
    charPrivacies: {},
    form_main_character_name: '',
    form_main_character_realm: '',
    form_profile_private: false,
    form_manualEntry: false,
    bnetId: null,
    profileUrlCopied: false,

    classColor(className) {
      const colors = {
        'Death Knight': '#C41E3A', 'Demon Hunter': '#A330C9', 'Druid': '#FF7C0A',
        'Evoker': '#33937F', 'Hunter': '#AAD372', 'Mage': '#3FC7EB', 'Monk': '#00FF98',
        'Paladin': '#F48CBA', 'Priest': '#CCCCCC', 'Rogue': '#FFF468', 'Shaman': '#0070DD',
        'Warlock': '#8788EE', 'Warrior': '#C69B3A',
      };
      return colors[className] || '#888';
    },

    copyProfileUrl() {
      if (!this.bnetId) return;
      const url = 'https://sim.miyazakitakara.ovh/u/' + encodeURIComponent(this.bnetId);
      navigator.clipboard.writeText(url).then(() => {
        this.profileUrlCopied = true;
        setTimeout(() => { this.profileUrlCopied = false; }, 2500);
      }).catch(() => {});
    },

    getCharPrivacy(ch) {
      const key = ch.name + '|' + (ch.realm_slug || ch.realm);
      return this.charPrivacies[key] || false;
    },

    async toggleCharPrivacyDirect(name, realm) {
      const session = this._getSession();
      if (!session) return;
      const key = name + '|' + realm;
      const isPrivate = !this.charPrivacies[key];
      try {
        const res = await fetch(`/auth/session/character-privacy?session=${session}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            character_name: name,
            character_realm: realm,
            is_private: isPrivate,
          }),
        });
        if (res.ok) {
          this.charPrivacies[key] = isPrivate;
        }
      } catch (e) {
        console.error('Failed to toggle char privacy', e);
      }
    },

    async toggleCharPrivacy(ch, event) {
      event.preventDefault();
      event.stopPropagation();
      const session = this._getSession();
      if (!session) return;
      const realm = ch.realm_slug || ch.realm;
      const key = ch.name + '|' + realm;
      const isPrivate = !this.charPrivacies[key];
      try {
        const res = await fetch(`/auth/session/character-privacy?session=${session}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            character_name: ch.name,
            character_realm: realm,
            is_private: isPrivate,
          }),
        });
        if (res.ok) {
          this.charPrivacies[key] = isPrivate;
        }
      } catch (e) {
        console.error('Failed to toggle char privacy', e);
      }
    },

    async loadCharPrivacies() {
      const session = this._getSession();
      if (!session || this.characters.length === 0) return;
      try {
        const res = await fetch(`/auth/session/character-privacy?session=${session}`);
        if (res.ok) {
          const data = await res.json();
          this.charPrivacies = data.privacies || {};
          if (window.__alpineApp) {
            window.__alpineApp.charPrivacies = this.charPrivacies;
          }
        }
      } catch (e) {
        console.warn('Failed to load char privacies', e);
      }
    },

    onCharSelect() {
      const ch = this.characters.find(c => c.name === this.form_main_character_name);
      if (ch) {
        this.form_main_character_realm = ch.realm;
      }
    },

    onManualToggle() {
      if (this.form_manualEntry) {
        this.form_main_character_name = '';
        this.form_main_character_realm = '';
      }
    },

    _getSession() {
      return window.__alpineApp?.sessionId || localStorage.getItem('simcraft_session');
    },

    _waitForSession() {
      return new Promise((resolve) => {
        const session = this._getSession();
        if (session) { resolve(session); return; }
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

    async initSettings() {
      this.loading    = true;
      this.error      = null;
      this.isLoggedIn = false;

      const session = await this._waitForSession();
      if (!session) {
        this.loading = false;
        return;
      }

      try {
        // Pobierz bnet_id z session/info
        const infoRes = await fetch(`/auth/session/info?session=${session}`);
        if (infoRes.ok) {
          const info = await infoRes.json();
          this.bnetId = info.bnet_id || null;
          if (window.__alpineApp) window.__alpineApp.bnetId = this.bnetId;
        }

        const res = await fetch(`/auth/session/settings?session=${session}`);
        if (res.status === 401) { this.loading = false; return; }
        if (res.status === 404) {
          this.error   = 'Nie znaleziono.';
          this.loading = false;
          return;
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          this.error   = 'Błąd: ' + (data.detail || res.status);
          this.loading = false;
          return;
        }
        const data = await res.json();
        this.form_main_character_name  = data.main_character_name  || '';
        this.form_main_character_realm = data.main_character_realm || '';
        this.form_profile_private      = !!data.profile_private;
        this.isLoggedIn = true;

        try {
          const charsRes = await fetch(`/api/characters?session=${session}`);
          if (charsRes.ok) {
            const chars = await charsRes.json();
            this.characters = chars.sort((a, b) => (b.level ?? 0) - (a.level ?? 0));
            if (window.__alpineApp) {
              window.__alpineApp.characters = this.characters;
            }
            await this.loadCharPrivacies();
          }
        } catch (e) {
          console.warn('Failed to load characters for picker', e);
        }
      } catch (e) {
        this.error = 'Błąd sieci.';
      } finally {
        this.loading = false;
      }
    },

    async save() {
      this.saving  = true;
      this.saveMsg = '';
      const session = this._getSession();

      const name  = this.form_main_character_name.trim();
      const realm = this.form_main_character_realm.trim();
      if (name && !realm) {
        this.saveMsg   = 'Realm jest wymagany.';
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
            profile_private:      this.form_profile_private,
          }),
        });

        if (res.status === 400) {
          const data = await res.json().catch(() => ({}));
          this.saveMsg   = 'Błąd: ' + (data.detail || '400');
          this.saveMsgOk = false;
          return;
        }
        if (res.status === 401) {
          this.saveMsg   = 'Sesja wygasła.';
          this.saveMsgOk = false;
          return;
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          this.saveMsg   = 'Błąd: ' + (data.detail || res.status);
          this.saveMsgOk = false;
          return;
        }

        const data = await res.json();
        if (window.__alpineApp) {
          window.__alpineApp.mainChar = data.main_character_name
            ? { name: data.main_character_name, realm: data.main_character_realm }
            : null;
        }
        this.saveMsg   = 'Zapisano!';
        this.saveMsgOk = true;
        setTimeout(() => { this.saveMsg = ''; }, 4000);

      } catch (e) {
        this.saveMsg   = 'Błąd sieci.';
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
  return result;
}

window.toggleCharPrivacyGlobal = async function(name, realm) {
  const app = window.__alpineApp;
  if (!app) return;
  const session = app.sessionId || localStorage.getItem('simcraft_session');
  if (!session) return;
  const key = name + '|' + realm;
  const isPrivate = !app.charPrivacies[key];
  try {
    const res = await fetch(`/auth/session/character-privacy?session=${session}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ character_name: name, character_realm: realm, is_private: isPrivate }),
    });
    if (res.ok) app.charPrivacies[key] = isPrivate;
  } catch (e) {
    console.error('Failed to toggle char privacy', e);
  }
};

window.settingsMixin = settingsMixin;

function registerSettingsMixin() {
  if (typeof Alpine !== 'undefined') {
    Alpine.data('settingsMixin', settingsMixin);
  } else {
    setTimeout(registerSettingsMixin, 100);
  }
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', registerSettingsMixin);
} else {
  registerSettingsMixin();
}
