function app() {
  return {
    sessionId: null,
    characters: [],
    charFilter: "",
    selectedChar: null,
    job: null,
    simResult: null,
    pubResult: null,
    pubJob: null,
    simMode: "armory",
    addonText: "",
    guestAddonText: "",
    guestSimOptions: {
      fight_style: "Patchwerk",
      iterations: 1000,
      target_error: 0.5,
    },
    guestLoadingSim: false,
    guestSimError: null,
    _guestPollInterval: null,
    simOptions: {
      fight_style: "Patchwerk",
      iterations: 1000,
      target_error: 0.5,
    },
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

    historySort: "date",
    historyPage: 1,
    historyPerPage: 10,

    newsPage: 1,
    newsPerPage: 5,
    expandedNews: null,
    activeTab: "symulacje",
    currentView: "home",

    newsTeaser(body) {
      if (!body) return "";
      return body.length > 150 ? body.slice(0, 150) + "..." : body;
    },

    init() {
      document.documentElement.setAttribute("data-theme", this.theme === "light" ? "light" : "dark");

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

      window.addEventListener("hashchange", () => this.handleHash());
      this.handleHash();

      if (this.sessionId) {
        this.loadCharacters();
        this.loadHistory();
      } else {
        this.loadPublicHistory();
        this.loadNews();
      }
    },

    handleHash() {
      const hash = window.location.hash.slice(1);
      if (hash === "symulacje" || hash === "profil") {
        this.currentView = hash;
        this.activeTab = hash;
      } else {
        this.currentView = "home";
      }
    },

    theme: localStorage.getItem("simcraft_theme") || "dark",

    STAT_LABELS: {
      strength:    "Strength",
      agility:     "Agility",
      stamina:     "Stamina",
      intellect:   "Intellect",
      crit:        "Critical Strike",
      haste:       "Haste",
      mastery:     "Mastery",
      versatility: "Versatility",
    },

    CLASS_COLORS: {
      "Death Knight":  "#C41E3A",
      "Demon Hunter":  "#A330C9",
      "Druid":         "#FF7C0A",
      "Evoker":        "#33937F",
      "Hunter":        "#AAD372",
      "Mage":          "#3FC7EB",
      "Monk":          "#00FF98",
      "Paladin":       "#F48CBA",
      "Priest":        "#CCCCCC",
      "Rogue":         "#FFF468",
      "Shaman":        "#0070DD",
      "Warlock":       "#8788EE",
      "Warrior":       "#C69B3A",
    },

    init() {
      document.documentElement.setAttribute("data-theme", this.theme === "light" ? "light" : "dark");

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
      } else {
        this.loadPublicHistory();
        this.loadNews();
      }
    },

    async loadNews() {
      try {
        const res = await fetch('/admin/api/news/public');
        if (res.ok) {
          this.news = await res.json();
          this.newsPage = 1;
        }
      } catch (e) { console.error('Failed to load news', e); }
    },

    get newsPageCount() {
      return Math.max(1, Math.ceil(this.news.length / this.newsPerPage));
    },
    get pagedNews() {
      const start = (this.newsPage - 1) * this.newsPerPage;
      return this.news.slice(start, start + this.newsPerPage);
    },
    newsPages() {
      return Array.from({ length: this.newsPageCount }, (_, i) => i + 1);
    },

    toggleTheme() {
      this.theme = this.theme === "dark" ? "light" : "dark";
      localStorage.setItem("simcraft_theme", this.theme);
      document.documentElement.setAttribute("data-theme", this.theme === "light" ? "light" : "dark");
    },

    get sortedHistory() {
      const arr = [...this.history];
      if (this.historySort === "dps")  arr.sort((a, b) => (b.dps ?? 0) - (a.dps ?? 0));
      else if (this.historySort === "name") arr.sort((a, b) => (a.character_name || "").localeCompare(b.character_name || ""));
      else arr.sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0));
      return arr;
    },
    get historyPageCount() {
      return Math.max(1, Math.ceil(this.sortedHistory.length / this.historyPerPage));
    },
    get pagedHistory() {
      const start = (this.historyPage - 1) * this.historyPerPage;
      return this.sortedHistory.slice(start, start + this.historyPerPage);
    },
    setHistorySort(s) {
      this.historySort = s;
      this.historyPage = 1;
    },
    historyPages() {
      return Array.from({ length: this.historyPageCount }, (_, i) => i + 1);
    },

    async loadCharacters() {
      this.loadingChars = true;
      this.errorChars = null;
      try {
        const chars = await API.getCharacters(this.sessionId);
        this.characters = chars.sort((a, b) => (b.level ?? 0) - (a.level ?? 0));
        const lastCharName = localStorage.getItem("simcraft_last_char");
        if (lastCharName && !this.selectedChar) {
          this.selectedChar = this.characters.find(c => c.name === lastCharName) || this.characters[0];
        } else if (!this.selectedChar && this.characters.length) {
          this.selectedChar = this.characters[0];
        }
        for (const ch of this.characters) {
          API.getCharacterMedia(this.sessionId, ch.realm_slug, ch.name.toLowerCase())
            .then((m) => { ch.avatar = m.avatar; })
            .catch(() => {});
        }
      } catch (e) {
        if (e.message.includes("401") || e.message.includes("403") || e.message.includes("Unauthorized")) {
          localStorage.removeItem("simcraft_session");
          this.sessionId = null;
          this.loadPublicHistory();
          this.loadNews();
        } else {
          this.errorChars = e.message;
        }
      } finally {
        this.loadingChars = false;
      }
    },

    async loadHistory() {
      try {
        this.history = await API.getHistory(this.sessionId);
        this.historyPage = 1;
      } catch (e) { console.error("Failed to load history", e); }
    },

    async loadPublicHistory() {
      try {
        this.history = await API.getPublicHistory();
        this.historyPage = 1;
      } catch (e) { console.error("Failed to load public history", e); }
    },

    async loadHistoryResult(jobId) {
      try {
        this.simResult = await API.getResultJson(jobId);
        this.selectedHistory = jobId;
        let entry = this.history.find(e => e.job_id === jobId);
        if (!entry) entry = await API.getResultMeta(jobId);
        const charName  = entry?.character_name || null;
        const charClass = entry?.character_class || null;
        const charSpec  = entry?.character_spec  || null;
        const charObj   = charName ? this.characters.find(c => c.name === charName) : null;
        this.job = {
          id:        jobId,
          charName:  charName !== 'Addon Export' ? charName : null,
          realmSlug: charObj?.realm_slug || entry?.character_realm_slug || null,
          charClass: charClass || null,
          charSpec:  charSpec || charObj?.spec || null,
        };
      } catch (e) {
        alert("Nie uda\u0142o si\u0119 za\u0142adowa\u0107 wyniku: " + e.message);
      }
    },

    async loadPubResult(jobId) {
      try {
        const [result, meta] = await Promise.all([
          API.getResultJson(jobId),
          API.getResultMeta(jobId),
        ]);
        result._source = meta?.character_name === 'Addon Export' ? 'addon' : 'history';
        this.pubResult = result;
        this.pubJob = {
          id:        jobId,
          charName:  meta?.character_name !== 'Addon Export' ? (meta?.character_name || null) : null,
          realmSlug: meta?.character_realm_slug || null,
          charClass: meta?.character_class || null,
          charSpec:  meta?.character_spec  || null,
        };
      } catch (e) {
        console.error("loadPubResult failed", e);
      }
    },

    async startGuestSim() {
      if (!this.guestAddonText.trim()) {
        this.guestSimError = "Wklej tekst z addona!";
        return;
      }
      this.guestSimError = null;
      this.guestLoadingSim = true;
      this.pubResult = null;
      this.pubJob = null;
      try {
        const { job_id } = await API.startSim({
          addon_text:   this.guestAddonText.trim(),
          fight_style:  this.guestSimOptions.fight_style,
          iterations:   this.guestSimOptions.iterations,
          target_error: this.guestSimOptions.target_error,
        });
        const guestJobId = job_id;
        this._guestPollInterval = setInterval(async () => {
          try {
            const status = await API.getJobStatus(guestJobId);
            if (status.status === "done") {
              clearInterval(this._guestPollInterval);
              const result = await API.getResultJson(guestJobId);
              result._source = 'addon';
              this.pubResult = result;
              this.pubJob = { id: guestJobId, charName: null, realmSlug: null, charClass: null, charSpec: null };
              await API.saveToHistory({
                job_id:               guestJobId,
                character_name:       "Addon Export",
                character_class:      "",
                character_spec:       "",
                character_realm_slug: "",
                dps:                  result.dps,
                fight_style:          this.guestSimOptions.fight_style,
                user_id:              null,
              });
              this.loadPublicHistory();
              this.guestLoadingSim = false;
            } else if (status.status === "error") {
              clearInterval(this._guestPollInterval);
              this.guestSimError = "B\u0142\u0105d symulacji: " + (status.error || "Nieznany b\u0142\u0105d");
              this.guestLoadingSim = false;
            }
          } catch (e) {
            clearInterval(this._guestPollInterval);
            this.guestLoadingSim = false;
          }
        }, 3000);
      } catch (e) {
        this.guestSimError = "B\u0142\u0105d: " + e.message;
        this.guestLoadingSim = false;
      }
    },

    get pubSortedSpells() {
      if (!this.pubResult?.spells) return [];
      const key = this.spellSort;
      return [...this.pubResult.spells].sort((a, b) => (b[key] ?? 0) - (a[key] ?? 0));
    },

    get filteredChars() {
      const q = this.charFilter.toLowerCase();
      return this.characters.filter(
        (c) => c.name.toLowerCase().includes(q) || c.realm.toLowerCase().includes(q)
      );
    },

    get sortedSpells() {
      if (!this.simResult?.spells) return [];
      const key = this.spellSort;
      return [...this.simResult.spells].sort((a, b) => (b[key] ?? 0) - (a[key] ?? 0));
    },

    classColor(className) { return this.CLASS_COLORS[className] || "#aaa"; },
    classTextColor(className) {
      const light = ["Hunter", "Mage", "Monk", "Rogue", "Priest"];
      return light.includes(className) ? "#111" : "#fff";
    },
    armoryUrl(realmSlug, name) {
      if (!realmSlug || !name) return null;
      return `https://worldofwarcraft.blizzard.com/en-gb/character/eu/${realmSlug}/${name.toLowerCase()}`;
    },

    selectChar(ch) {
      this.selectedChar = ch;
      this.simResult = null;
      this.job = null;
      this.currentView = "symulacje";
      this.activeTab = "symulacje";
      localStorage.setItem("simcraft_last_char", ch.name);
    },

    async startSim() {
      this.loadingSim = true;
      this.simResult = null;
      this.job = null;
      const payload = {
        session:      this.sessionId,
        fight_style:  this.simOptions.fight_style,
        iterations:   this.simOptions.iterations,
        target_error: this.simOptions.target_error,
      };
      if (this.simMode === "addon") {
        if (!this.addonText.trim()) { alert("Wklej addon export!"); this.loadingSim = false; return; }
        payload.addon_text = this.addonText.trim();
      } else if (this.selectedChar) {
        payload.name       = this.selectedChar.name;
        payload.realm_slug = this.selectedChar.realm_slug;
        payload.region     = this.selectedChar.region || "eu";
      } else {
        alert("Wybierz postac lub wklej addon export!"); this.loadingSim = false; return;
      }
      try {
        const { job_id } = await API.startSim(payload);
        this.job = {
          id:        job_id,
          status:    "running",
          charName:  this.selectedChar?.name || null,
          realmSlug: this.selectedChar?.realm_slug || null,
          charClass: this.selectedChar?.class || null,
          charSpec:  this.selectedChar?.spec || null,
        };
        this._pollInterval = setInterval(() => this._pollJob(), 3000);
      } catch (e) {
        alert("Blad startu symulacji: " + e.message);
        this.loadingSim = false;
      }
    },

    async _pollJob() {
      if (!this.job) return;
      try {
        const status = await API.getJobStatus(this.job.id);
        this.job.status = status.status;
        if (status.status === "done") {
          clearInterval(this._pollInterval);
          this.simResult = await API.getResultJson(this.job.id);
          await API.saveToHistory({
            job_id:               this.job.id,
            character_name:       this.selectedChar?.name || "Addon Export",
            character_class:      this.selectedChar?.class || "",
            character_spec:       this.selectedChar?.spec || "",
            character_realm_slug: this.selectedChar?.realm_slug || "",
            dps:                  this.simResult.dps,
            fight_style:          this.simOptions.fight_style,
            user_id:              this.sessionId || null,
          });
          this.loadHistory();
          this.loadingSim = false;
        } else if (status.status === "error") {
          clearInterval(this._pollInterval);
          alert("Blad symulacji:\n" + (status.error || "Nieznany blad"));
          this.loadingSim = false;
        }
      } catch (e) {
        clearInterval(this._pollInterval);
        this.loadingSim = false;
      }
    },

    getCharacterTrends() {
      const charMap = new Map();
      for (const entry of this.history) {
        if (!entry.character_name || entry.character_name === 'Addon Export') continue;
        const key = entry.character_name;
        if (!charMap.has(key)) {
          charMap.set(key, {
            name: entry.character_name,
            charClass: entry.character_class,
            charSpec: entry.character_spec,
            realmSlug: entry.character_realm_slug,
            dps: [],
            fight_style: entry.fight_style,
            created_at: entry.created_at,
          });
        }
        const char = charMap.get(key);
        char.dps.push({ dps: entry.dps, created_at: entry.created_at, fight_style: entry.fight_style });
        if (entry.created_at > char.created_at) char.created_at = entry.created_at;
      }
      return Array.from(charMap.values()).sort((a, b) => b.created_at - a.created_at);
    },

    getCharDps(charName) {
      const charSims = this.history.filter(h => h.character_name === charName);
      if (charSims.length === 0) return null;
      const dpsList = charSims.sort((a, b) => a.created_at - b.created_at).map(h => h.dps);
      const latest = dpsList[dpsList.length - 1];
      const first = dpsList[0];
      const diff = latest - first;
      const trend = dpsList.length > 1 
        ? (diff > 0 ? '↑' : '↓') + ' ' + Math.abs(Math.round(diff))
        : '1 symulacja';
      return {
        latest,
        first,
        diff,
        trend,
        count: dpsList.length,
        lastSim: charSims.reduce((max, h) => h.created_at > max ? h.created_at : max, 0),
        dpsList,
      };
    },

    getCharAvatar(name) {
      const ch = this.characters.find(c => c.name === name);
      return ch ? ch.avatar : null;
    },

    selectCharByName(name) {
      const ch = this.characters.find(c => c.name === name);
      if (ch) {
        this.selectChar(ch);
        this.activeTab = 'symulacje';
      }
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

    formatDps(v) {
      if (!v && v !== 0) return "\u2014";
      if (v >= 1_000_000) return (v / 1_000_000).toFixed(2) + "M";
      if (v >= 1_000)     return (v / 1_000).toFixed(1) + "k";
      return String(v);
    },
    formatDmg(v) {
      if (!v && v !== 0) return "\u2014";
      if (v >= 1_000_000) return (v / 1_000_000).toFixed(2) + "M";
      if (v >= 1_000)     return (v / 1_000).toFixed(0) + "k";
      return String(Math.round(v));
    },
    pctBarWidth(val, spells, key) {
      const max = Math.max(...spells.map(s => s[key] ?? 0));
      return max > 0 ? Math.round((val / max) * 100) + "%" : "0%";
    },
    formatStatName(key) { return this.STAT_LABELS[key] || key; },
    formatStatValue(key, val) {
      if (typeof val === "number") return val.toLocaleString();
      return val;
    },
    formatTime(timestamp) {
      if (!timestamp) return "\u2014";
      const date = new Date(timestamp * 1000);
      const now = new Date();
      const diff = Math.floor((now - date) / 1000);
      if (diff < 60) return "teraz";
      if (diff < 3600) return Math.floor(diff / 60) + "m temu";
      if (diff < 86400) return Math.floor(diff / 3600) + "h temu";
      return date.toLocaleDateString('pl-PL');
    },
    getShareUrl(jobId) { return window.location.origin + "/result/" + jobId; },
    copyToClipboard(text, jobId) {
      navigator.clipboard.writeText(text).then(() => {
        this.copiedJobId = jobId || true;
        setTimeout(() => { this.copiedJobId = null; }, 2000);
      }).catch(() => {});
    },
  };
}
