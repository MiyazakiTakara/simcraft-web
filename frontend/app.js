// Główny moduł Alpine — home view + stan globalny
// Logika biznesowa w miksinach: sim.js, chars.js, history.js, trend.js, session.js

function mergeMixins(target, ...mixins) {
  for (const mixin of mixins) {
    for (const key of Object.keys(mixin)) {
      if (!(key in target)) {
        const desc = Object.getOwnPropertyDescriptor(mixin, key);
        if (desc) Object.defineProperty(target, key, desc);
      }
    }
  }
  return target;
}

// =====================
// WOWHEAD TOOLTIP OVERRIDE
// =====================
function applyWowheadOverride() {
  if (document.getElementById('simcraft-wh-override')) return;
  const s = document.createElement('style');
  s.id = 'simcraft-wh-override';
  s.textContent = `
    .wowhead-tooltip {
      background:    var(--surface) !important;
      border:        1px solid var(--border) !important;
      border-radius: var(--radius) !important;
      box-shadow:    var(--shadow-lg) !important;
      padding:       0 !important;
      overflow:      hidden !important;
    }
    .wowhead-tooltip > table {
      background:    transparent !important;
      border:        none !important;
      border-spacing: 0 !important;
      border-collapse: collapse !important;
      width:         100% !important;
    }
    .wowhead-tooltip > table th {
      background:    var(--surface) !important;
      background-image: none !important;
      width:         0 !important;
      padding:       0 !important;
      border:        none !important;
    }
    .wowhead-tooltip > table > tbody > tr:first-child > td:first-child {
      background:    var(--surface) !important;
      color:         var(--text)    !important;
      border:        none          !important;
      padding:       .6rem .75rem  !important;
      font-family:   "Segoe UI", system-ui, sans-serif !important;
      font-size:     var(--text-sm) !important;
      line-height:   1.55 !important;
    }
    .wowhead-tooltip table table {
      background:    transparent !important;
      border:        none        !important;
      border-spacing: 0          !important;
    }
    .wowhead-tooltip table table td,
    .wowhead-tooltip table table th {
      background:    transparent !important;
      color:         var(--text) !important;
      border:        none        !important;
      padding:       .1rem 0     !important;
      width:         auto        !important;
      background-image: none     !important;
    }
    .wowhead-tooltip table table:last-of-type td {
      color:         var(--muted) !important;
      font-size:     var(--text-xs) !important;
      padding-top:   .3rem !important;
      border-top:    1px solid var(--border) !important;
    }
    .wowhead-tooltip a            { color: var(--accent)  !important; text-decoration: none !important; }
    .wowhead-tooltip a:hover      { color: var(--accent2) !important; text-decoration: underline !important; }
    .wowhead-tooltip .q0 { color: #9d9d9d !important; }
    .wowhead-tooltip .q1 { color: #ffffff !important; }
    .wowhead-tooltip .q2 { color: #1eff00 !important; }
    .wowhead-tooltip .q3 { color: #0070dd !important; }
    .wowhead-tooltip .q4 { color: #a335ee !important; }
    .wowhead-tooltip .q5 { color: #ff8000 !important; }
    .wowhead-tooltip .q6 { color: #e6cc80 !important; }
    .wowhead-tooltip .q  { font-weight: 700 !important; }
    .wowhead-tooltip .moneygold   { color: var(--accent) !important; }
    .wowhead-tooltip .moneysilver { color: #aaa !important; }
    .wowhead-tooltip .moneycopper { color: #cd7f32 !important; }
    .whtt-tooltip-icon { display: none !important; }
    .wowhead-tooltip-powered { display: none !important; }
    [data-theme="light"] .wowhead-tooltip,
    [data-theme="light"] .wowhead-tooltip > table > tbody > tr:first-child > td:first-child {
      background: var(--surface) !important;
      color:      var(--text)    !important;
    }
    [data-theme="light"] .wowhead-tooltip > table th {
      background: var(--surface) !important;
    }
    [data-theme="light"] .wowhead-tooltip a { color: var(--accent) !important; }
  `;
  document.head.appendChild(s);
}

function watchWowheadInjections() {
  const observer = new MutationObserver(() => {
    const ours = document.getElementById('simcraft-wh-override');
    if (!ours) { applyWowheadOverride(); return; }
    if (document.head.lastElementChild !== ours) {
      document.head.appendChild(ours);
    }
  });
  observer.observe(document.head, { childList: true });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    applyWowheadOverride();
    watchWowheadInjections();
  });
} else {
  applyWowheadOverride();
  watchWowheadInjections();
}

function app() {
  const state = {
    sessionId: localStorage.getItem('simcraft_session'),
    characters: [],
    charFilter: '',
    selectedChar: null,
    job: null,
    simResult: null,
    pubResult: null,
    pubJob: null,
    simMode: 'armory',
    simRole: 'auto',
    addonText: '',
    guestAddonText: '',
    guestSimOptions: { fight_style: 'Patchwerk', iterations: 1000, target_error: 0.5, one_button_mode: false },
    guestLoadingSim: false,
    guestSimError: null,
    _guestPollInterval: null,
    simOptions: { fight_style: 'Patchwerk', iterations: 1000, target_error: 0.5, one_button_mode: false },
    loadingChars: false,
    loadingSim: false,
    errorChars: null,
    _pollInterval: null,
    history: [],
    news: [],
    loadingHistory: false,
    rebuildBanner: null,
    spellSort: 'total_dmg',
    copiedJobId: null,
    chartModal: null,
    hoveredSpell: null,
    simTimelineOpen: false,
    historyPage: 1,
    historyPerPage: 5,
    newsPage: 1,
    newsPerPage: 5,
    expandedNews: null,
    activeTab: 'home',
    currentView: 'home',
    charEquipment: [],
    charTalents: [],
    loadingCharDetails: false,
    charDetailsError: null,
    charDetailsModal: null,
    tooltipCache: {},
    theme: localStorage.getItem('simcraft_theme') || 'dark',
    oneButtonMode: false,
    publicHistoryLimit: 20,
    userHistoryLimit: 20,

    formatDps(v)                  { return Utils.formatDps(v); },
    formatDmg(v)                  { return Utils.formatDmg(v); },
    formatTime(ts)                { return Utils.formatTime(ts); },
    pctBarWidth(val, spells, key) { return Utils.pctBarWidth(val, spells, key); },
    formatStatName(key)           { return Utils.formatStatName(key); },
    formatStatValue(key, val)     { return Utils.formatStatValue(key, val); },
    getShareUrl(jobId)            { return Utils.getShareUrl(jobId); },
    classColor(className)         { return Utils.classColor(className); },
    classTextColor(className)     { return Utils.classTextColor(className); },
    armoryUrl(realmSlug, name)    { return Utils.armoryUrl(realmSlug, name); },
    getItemQualityColor(quality)  { return Utils.getItemQualityColor(quality); },
    copyToClipboard(text, jobId)  { Utils.copyToClipboard(text, jobId, (v) => { this.copiedJobId = v; }); },

    get filteredChars() {
      const q = (this.charFilter || '').toLowerCase();
      return (this.characters || []).filter(
        c => c.name.toLowerCase().includes(q) || c.realm.toLowerCase().includes(q)
      );
    },
    get historyPageCount() {
      return Math.max(1, Math.ceil((this.history || []).length / (this.historyPerPage || 5)));
    },
    get pagedHistory() {
      const start = ((this.historyPage || 1) - 1) * (this.historyPerPage || 5);
      return (this.history || []).slice(start, start + (this.historyPerPage || 5));
    },
    get newsPageCount() {
      return Math.max(1, Math.ceil((this.news || []).length / (this.newsPerPage || 5)));
    },
    get pagedNews() {
      const start = ((this.newsPage || 1) - 1) * (this.newsPerPage || 5);
      return (this.news || []).slice(start, start + (this.newsPerPage || 5));
    },
    get sortedSpells() {
      if (!this.simResult?.spells) return [];
      const key = this.spellSort || 'dps';
      return [...this.simResult.spells].sort((a, b) => (b[key] ?? 0) - (a[key] ?? 0));
    },
    get pubSortedSpells() {
      if (!this.pubResult?.spells) return [];
      const key = this.spellSort || 'dps';
      return [...this.pubResult.spells].sort((a, b) => (b[key] ?? 0) - (a[key] ?? 0));
    },

    detectedRole()  { return 'dps'; },
    effectiveRole() {
      if (this.simRole && this.simRole !== 'auto') return this.simRole;
      if (this.selectedChar?.spec) {
        const s = this.selectedChar.spec.toLowerCase();
        if (s.includes('heal')) return 'heal';
        if (s.includes('tank')) return 'tank';
      }
      return 'dps';
    },
    roleIcon(role) {
      const r = role || this.effectiveRole();
      if (r === 'heal') return '\ud83d\udc9a';
      if (r === 'tank') return '\ud83d\udee1\ufe0f';
      return '\u2694\ufe0f';
    },
    roleLabel(role) {
      const r = role || this.effectiveRole();
      if (r === 'heal') return 'Heal';
      if (r === 'tank') return 'Tank';
      return 'DPS';
    },

    async loadView(name) {
      const container = document.getElementById('view-container');
      if (!container) return;
      container.classList.remove('view-enter');
      try {
        const res = await fetch('/views/' + name + '.html?v=14');
        if (!res.ok) throw new Error('View not found: ' + name);
        container.innerHTML = await res.text();
      } catch (e) {
        console.error('loadView failed:', e);
        container.innerHTML = '<p style="color:#f66;padding:2rem">Błąd ładowania widoku: ' + name + '</p>';
        return;
      }
      void container.offsetWidth;
      container.classList.add('view-enter');
    },

    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('simcraft_theme', this.theme);
      document.documentElement.setAttribute('data-theme', this.theme === 'light' ? 'light' : 'dark');
    },

    logout() {
      localStorage.removeItem('simcraft_session');
      localStorage.removeItem('simcraft_last_char');
      this.sessionId = null;
      this.characters = [];
      this.selectedChar = null;
      this.simResult = null;
      window.location.href = API.logoutUrl();
    },
  };

  if (typeof window.settingsMixin !== 'undefined') {
    mergeMixins(state, window.settingsMixin());
  }
  mergeMixins(state, SimMixin, CharsMixin, HistoryMixin, TrendMixin, SessionMixin);

  state.init = async function() {
    window.__alpineApp = this;
    document.documentElement.setAttribute('data-theme', this.theme === 'light' ? 'light' : 'dark');
    this.loadAppearance();

    // Pobierz konfig zanim załadujesz historię i widok
    try {
      const r = await fetch('/api/config/public');
      if (r.ok) {
        const cfg = await r.json();
        // Zawsze przypisuj — żeby reset z true->false też działał
        const obm = !!cfg.one_button_mode_enabled;
        this.oneButtonMode                    = obm;
        this.guestSimOptions.one_button_mode  = obm;
        this.simOptions.one_button_mode       = obm;
        if (cfg.public_history_limit) this.publicHistoryLimit = cfg.public_history_limit;
        if (cfg.user_history_limit)   this.userHistoryLimit   = cfg.user_history_limit;
      }
    } catch (e) {}

    if (this.sessionId) {
      this.loadCharacters();
      this.checkFirstLogin();
    }

    this.loadNews();
    this.loadPublicHistory();

    this.$nextTick(() => this.loadView('home'));
  };

  return state;
}

window.app = app;
