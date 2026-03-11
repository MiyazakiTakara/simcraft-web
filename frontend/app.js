// Glowny Alpine.js store — laczy wszystkie mixiny
function app() {
  return {
    // Stan
    sessionId:    localStorage.getItem('simcraft_session'),
    theme:        localStorage.getItem('simcraft_theme') || 'dark',
    currentView:  'home',
    appearance:   { emoji: '\u2694\ufe0f', header_title: 'SimCraft Web' },

    // Pierwsza sesja / main char
    isFirstLogin:         false,
    showMainCharModal:    false,
    mainChar:             null,   // { name, realm }
    savingMainChar:       false,
    mainCharSaved:        false,

    // Postacie
    characters:       [],
    selectedChar:     null,
    charFilter:       '',
    loadingChars:     false,
    errorChars:       null,
    charDetailsModal: null,
    loadingCharDetails: false,
    charDetailsError: null,
    charEquipment:    [],
    charTalents:      [],

    // Symulacja
    addonText:    '',
    simMode:      'armory',
    simRole:      'auto',
    fightStyle:   'Patchwerk',
    iterations:   1000,
    targetError:  0.5,
    job:          null,
    simResult:    null,
    simError:     null,
    pollTimer:    null,
    chartModal:   null,
    copiedShare:  null,

    // Historia
    history:        [],
    historyPage:    1,
    historyPerPage: 5,
    news:           [],
    newsPage:       1,
    newsPerPage:    3,
    expandedNews:   null,

    ...SimMixin,
    ...CharsMixin,
    ...HistoryMixin,

    async init() {
      this.applyTheme();
      if (this.sessionId) {
        await this.loadCharacters();
        await this.loadHistory();
        await this.checkFirstLogin();
      } else {
        await this.loadPublicHistory();
      }
      await this.loadNews();
      await this.loadAppearance();
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
          body:    JSON.stringify({ name: char.name, realm: char.realm_slug }),
        });
        if (res.ok) {
          this.mainChar          = { name: char.name, realm: char.realm_slug };
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

    navigateTo(view) { this.currentView = view; },

    logout() {
      const s = this.sessionId;
      localStorage.removeItem('simcraft_session');
      localStorage.removeItem('simcraft_last_char');
      this.sessionId  = null;
      this.characters = [];
      this.history    = [];
      window.location.href = '/auth/logout' + (s ? '?session=' + s : '');
    },

    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('simcraft_theme', this.theme);
      this.applyTheme();
    },
    applyTheme() {
      document.documentElement.setAttribute('data-theme', this.theme === 'light' ? 'light' : 'dark');
    },

    getItemQualityColor(q) { return Utils.getItemQualityColor(q); },

    async loadAppearance() {
      try {
        const res = await fetch('/admin/api/appearance');
        if (res.ok) this.appearance = await res.json();
      } catch (e) {}
    },
  };
}
