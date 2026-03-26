// session.js — mixin first-login flow + appearance (wydzielony z app.js, issue #40)
const SessionMixin = {
  isFirstLogin:      false,
  showMainCharModal: false,
  mainChar:          null,
  savingMainChar:    false,
  mainCharSaved:     false,
  bnetId:            null,
  appearance: {
    header_title:     'SimCraft Web',
    hero_title:       'World of Warcraft',
    emoji:            '\u2694\ufe0f',
    hero_custom_text: '',
  },

  async loadAppearance() {
    try {
      const res = await fetch('/api/appearance');
      if (res.ok) {
        const data = await res.json();
        this.appearance.header_title     = data.header_title     ?? this.appearance.header_title;
        this.appearance.hero_title       = data.hero_title       ?? this.appearance.hero_title;
        this.appearance.emoji            = data.emoji            ?? this.appearance.emoji;
        this.appearance.hero_custom_text = data.hero_custom_text ?? '';
        document.title = this.appearance.emoji + ' ' + this.appearance.header_title;
      }
    } catch (e) {
      console.error('Failed to load appearance:', e);
    }
  },

  async checkFirstLogin() {
    if (!this.sessionId) return;
    try {
      const res = await fetch(`/auth/session/info?session=${this.sessionId}`);
      if (!res.ok) return;
      const info = await res.json();
      this.mainChar = info.main_character_name
        ? { name: info.main_character_name, realm: info.main_character_realm }
        : null;
      this.bnetId = info.bnet_id || null;
      if (info.is_first_login) {
        this.isFirstLogin      = true;
        this.showMainCharModal = true;
      }
    } catch (e) {
      console.error('checkFirstLogin failed', e);
    }
  },

  async saveMainChar(char) {
    if (!this.sessionId || this.savingMainChar) return;
    this.savingMainChar = true;
    try {
      const res = await fetch(`/auth/session/main-character?session=${this.sessionId}`, {
        method:  'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ name: char.name, realm: char.realm_slug || char.realm }),
      });
      if (res.ok) {
        this.mainChar          = { name: char.name, realm: char.realm_slug || char.realm };
        this.mainCharSaved     = true;
        this.showMainCharModal = false;
        this.isFirstLogin      = false;
      }
    } catch (e) {
      console.error('saveMainChar failed', e);
    } finally {
      this.savingMainChar = false;
    }
  },

  async skipMainCharModal() {
    this.showMainCharModal = false;
    this.isFirstLogin      = false;
    if (!this.sessionId) return;
    try {
      await fetch(`/auth/session/skip-first-login?session=${this.sessionId}`, { method: 'POST' });
    } catch (e) {}
  },
};
