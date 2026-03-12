// Główny moduł Alpine — stan + init + nawigacja
// Metody biznesowe są w: utils.js, sim.js, chars.js, history.js

function mergeMixins(target, ...mixins) {
  for (const mixin of mixins) {
    const descs = Object.getOwnPropertyDescriptors(mixin);
    Object.defineProperties(target, descs);
  }
  return target;
}

function app() {
  const state = {
    sessionId: localStorage.getItem('simcraft_session'),
    characters: [],
    charFilter: "",
    selectedChar: null,
    job: null,
    simResult: null,
    pubResult: null,
    pubJob: null,
    simMode: "armory",
    simRole: "auto",
    addonText: "",
    guestAddonText: "",
    guestSimOptions: { fight_style: "Patchwerk", iterations: 1000, target_error: 0.5 },
    guestLoadingSim: false,
    guestSimError: null,
    _guestPollInterval: null,
    simOptions: { fight_style: "Patchwerk", iterations: 1000, target_error: 0.5 },
    loadingChars: false,
    charsLoading: false,   // alias używany przez skeleton w profil.html
    loadingSim: false,
    errorChars: null,
    _pollInterval: null,
    history: [],
    news: [],
    loadingHistory: false,
    historyLoading: false, // alias używany przez skeleton w profil.html i home.html
    spellSort: "total_dmg",
    copiedJobId: null,
    chartModal: null,
    hoveredSpell: null,
    historyPage: 1,
    historyPerPage: 5,
    profileTab: "chars",
    newsPage: 1,
    newsPerPage: 5,
    expandedNews: null,
    activeTab: "home",
    currentView: "home",
    charEquipment: [],
    charTalents: [],
    loadingCharDetails: false,
    charDetailsError: null,
    charDetailsModal: null,
    _viewCache: {},
    appearance: {
      header_title: "SimCraft Web",
      hero_title: "World of Warcraft",
      emoji: "⚔️",
      hero_custom_text: ""
    },
    theme: localStorage.getItem("simcraft_theme") || "dark",

    // Main char modal
    isFirstLogin:      false,
    showMainCharModal: false,
    mainChar:          null,
    savingMainChar:    false,
    mainCharSaved:     false,

    // DPS Trend
    trendCharName:   "",
    trendFightStyle: "Patchwerk",
    trendPoints:     [],
    trendLoading:    false,
    _trendChart:     null,

    // Utils — delegaty
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

    // Gettery (deskryptory) — Alpine widzi je przez mergeMixins
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

    // Role
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
    roleIcon(role)  {
      const r = role || this.effectiveRole();
      if (r === 'heal') return '💚';
      if (r === 'tank') return '🛡️';
      return '⚔️';
    },
    roleLabel(role) {
      const r = role || this.effectiveRole();
      if (r === 'heal') return 'Heal';
      if (r === 'tank') return 'Tank';
      return 'DPS';
    },

    // DPS Trend
    selectTrendChar(char) {
      this.trendCharName = char.name + '|' + (char.realm_slug || char.realm);
    },

    initTrendTab() {
      if (!this.trendCharName && this.characters.length > 0) {
        const c = this.characters[0];
        this.trendCharName = c.name + '|' + (c.realm_slug || c.realm);
      }
      if (this.trendCharName) this.loadTrend();
    },

    async loadTrend() {
      if (!this.trendCharName || !this.sessionId) return;
      const [name, realm] = this.trendCharName.split('|');
      this.trendLoading = true;
      this.trendPoints  = [];
      this.destroyTrendChart();
      try {
        const url = `/api/history/trend?session=${encodeURIComponent(this.sessionId)}&character_name=${encodeURIComponent(name)}&character_realm_slug=${encodeURIComponent(realm)}&fight_style=${encodeURIComponent(this.trendFightStyle)}&limit=50`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('trend fetch failed');
        const data = await res.json();
        this.trendPoints = data.points || [];
      } catch (e) {
        console.error('loadTrend:', e);
      } finally {
        this.trendLoading = false;
        if (this.trendPoints.length > 0) {
          this.$nextTick(() => this.renderTrendChart());
        }
      }
    },

    destroyTrendChart() {
      if (this._trendChart) {
        this._trendChart.destroy();
        this._trendChart = null;
      }
    },

    renderTrendChart() {
      const canvas = document.getElementById('trendChartCanvas');
      if (!canvas || typeof Chart === 'undefined') return;
      this.destroyTrendChart();

      const labels = this.trendPoints.map(p => {
        const d = new Date(p.timestamp);
        return d.toLocaleDateString('pl-PL', { month: 'short', day: 'numeric' }) + ' ' +
               d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
      });
      const values = this.trendPoints.map(p => p.dps);
      const jobIds = this.trendPoints.map(p => p.job_id);

      const isDark  = this.theme !== 'light';
      const textClr = isDark ? '#cccccc' : '#333333';
      const gridClr = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.08)';
      const accentClr = '#7c6fcd';

      this._trendChart = new Chart(canvas, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'DPS',
            data: values,
            borderColor: accentClr,
            backgroundColor: 'rgba(124,111,205,0.15)',
            pointBackgroundColor: accentClr,
            pointRadius: 5,
            pointHoverRadius: 7,
            tension: 0.3,
            fill: true,
          }],
        },
        options: {
          responsive: true,
          interaction: { mode: 'index', intersect: false },
          onClick: (_e, elements) => {
            if (elements.length > 0) {
              const idx = elements[0].index;
              window.open('/result/' + jobIds[idx], '_blank');
            }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: ctx => ' DPS: ' + Utils.formatDps(ctx.parsed.y),
              },
              backgroundColor: isDark ? '#1a1b2e' : '#ffffff',
              titleColor: textClr,
              bodyColor: textClr,
              borderColor: gridClr,
              borderWidth: 1,
            },
          },
          scales: {
            x: {
              ticks: { color: textClr, maxRotation: 45, font: { size: 11 } },
              grid:  { color: gridClr },
            },
            y: {
              ticks: {
                color: textClr,
                callback: v => Utils.formatDps(v),
                font: { size: 11 },
              },
              grid: { color: gridClr },
            },
          },
        },
      });
    },

    // View loader
    async loadView(name) {
      const container = document.getElementById('view-container');
      if (!container) return;

      // Reset animacji
      container.classList.remove('view-enter');

      if (this._viewCache[name]) {
        container.innerHTML = this._viewCache[name];
      } else {
        try {
          const res = await fetch('/views/' + name + '.html?v=5');
          if (!res.ok) throw new Error('View not found: ' + name);
          const html = await res.text();
          this._viewCache[name] = html;
          container.innerHTML = html;
        } catch (e) {
          console.error('loadView failed:', e);
          container.innerHTML = '<p style="color:#f66;padding:2rem">Błąd ładowania widoku: ' + name + '</p>';
          return;
        }
      }

      // Uruchom animację wejścia
      void container.offsetWidth; // reflow wymuszający restart animacji
      container.classList.add('view-enter');

      this.$nextTick(() => Alpine.initTree(container));
    },

    navigateTo(name) {
      this.currentView = name;
      this.activeTab = name;
      window.location.hash = name === 'home' ? '' : name;
      this.loadView(name);
    },

    handleHash() {
      const hash = window.location.hash.slice(1);
      const validViews = ['symulacje', 'profil', 'ustawienia'];
      if (validViews.includes(hash)) {
        this.navigateTo(hash);
      } else {
        this.navigateTo('home');
      }
    },

    toggleTheme() {
      this.theme = this.theme === "dark" ? "light" : "dark";
      localStorage.setItem("simcraft_theme", this.theme);
      document.documentElement.setAttribute("data-theme", this.theme === "light" ? "light" : "dark");
    },

    logout() {
      localStorage.removeItem("simcraft_session");
      localStorage.removeItem("simcraft_last_char");
      this.sessionId = null;
      this.characters = [];
      this.selectedChar = null;
      this.simResult = null;
      window.location.href = API.logoutUrl();
    },

    async loadAppearance() {
      try {
        const res = await fetch('/api/appearance');
        if (res.ok) {
          const data = await res.json();
          this.appearance.header_title     = data.header_title     ?? this.appearance.header_title;
          this.appearance.hero_title       = data.hero_title       ?? this.appearance.hero_title;
          this.appearance.emoji            = data.emoji            ?? this.appearance.emoji;
          this.appearance.hero_custom_text = data.hero_custom_text ?? "";
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

    init() {
      // Udostępnij instancję app() globalnie dla header partial
      window.__alpineApp = this;

      document.documentElement.setAttribute("data-theme", this.theme === "light" ? "light" : "dark");
      this.loadAppearance();

      const params = new URLSearchParams(window.location.search);
      const sessionFromUrl = params.get("session");
      if (sessionFromUrl) {
        this.sessionId = sessionFromUrl;
        localStorage.setItem("simcraft_session", sessionFromUrl);
        history.replaceState({}, "", "/");
      } else {
        const saved = localStorage.getItem("simcraft_session");
        if (saved) this.sessionId = saved;
      }

      if (this.sessionId) {
        this.loadCharacters();
        this.loadHistory();
        this.loadNews();
        this.checkFirstLogin();
      } else {
        this.loadPublicHistory();
        this.loadNews();
      }

      // Persist active view via URL hash
      this.handleHash();
      window.addEventListener('hashchange', () => this.handleHash());
    },
  };

  // Kopiuj gettery z miksinów zachowując deskryptory property
  mergeMixins(state, SimMixin, CharsMixin, HistoryMixin);

  return state;
}
