// Główny moduł Alpine — stan + init + nawigacja
// Metody biznesowe są w: utils.js, sim.js, chars.js, history.js

function app() {
  return Object.assign(
    // Stan
    {
      sessionId: null,
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
      loadingSim: false,
      errorChars: null,
      _pollInterval: null,
      history: [],
      news: [],
      loadingHistory: false,
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
      activeTab: "symulacje",
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
    },

    // Miksy
    SimMixin,
    CharsMixin,
    HistoryMixin,

    // Metody lokalne (utils delegowane, view loader, init, misc)
    {
      // Utils — delegaty (wymagane przez szablony Alpine)
      formatDps(v)                    { return Utils.formatDps(v); },
      formatDmg(v)                    { return Utils.formatDmg(v); },
      formatTime(ts)                  { return Utils.formatTime(ts); },
      pctBarWidth(val, spells, key)   { return Utils.pctBarWidth(val, spells, key); },
      formatStatName(key)             { return Utils.formatStatName(key); },
      formatStatValue(key, val)       { return Utils.formatStatValue(key, val); },
      getShareUrl(jobId)              { return Utils.getShareUrl(jobId); },
      classColor(className)           { return Utils.classColor(className); },
      classTextColor(className)       { return Utils.classTextColor(className); },
      armoryUrl(realmSlug, name)      { return Utils.armoryUrl(realmSlug, name); },
      getItemQualityColor(quality)    { return Utils.getItemQualityColor(quality); },
      copyToClipboard(text, jobId)    { Utils.copyToClipboard(text, jobId, (v) => { this.copiedJobId = v; }); },

      // Role
      detectedRole()  { return 'dps'; },
      effectiveRole() { return 'dps'; },
      roleIcon()      { return '⚔️'; },
      roleLabel()     { return 'DPS'; },

      // View loader
      async loadView(name) {
        const container = document.getElementById('view-container');
        if (!container) return;
        if (this._viewCache[name]) {
          container.innerHTML = this._viewCache[name];
        } else {
          try {
            const res = await fetch('/views/' + name + '.html?v=1');
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
        this.$nextTick(() => Alpine.initTree(container));
      },

      navigateTo(name) {
        this.currentView = name;
        this.activeTab = name;
        this.loadView(name);
      },

      handleHash() {
        const hash = window.location.hash.slice(1);
        if (hash === "symulacje" || hash === "profil") {
          this.navigateTo(hash);
        } else {
          this.navigateTo("home");
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

      init() {
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
        } else {
          this.loadPublicHistory();
          this.loadNews();
        }

        this.loadView('home');
      },
    }
  );
}
