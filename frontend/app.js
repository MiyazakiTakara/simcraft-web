function app() {
  return {
    sessionId: null,
    characters: [],
    charFilter: "",
    selectedChar: null,
    job: null,
    simResult: null,
    simMode: "armory",
    addonText: "",
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
    loadingHistory: false,
    spellSort: "total_dmg",
    copiedJobId: null,

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
      "Priest":        "#FFFFFF",
      "Rogue":         "#FFF468",
      "Shaman":        "#0070DD",
      "Warlock":       "#8788EE",
      "Warrior":       "#C69B3A",
    },

    init() {
      const params = new URLSearchParams(window.location.search);
      const sessionFromUrl = params.get("session");
      const resultId = params.get("result");

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
      }

      if (resultId) {
        this.loadHistoryResult(resultId);
      }
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
        } else {
          this.errorChars = e.message;
        }
      } finally {
        this.loadingChars = false;
      }
    },

    async loadHistory() {
      try { this.history = await API.getHistory(); }
      catch (e) { console.error("Failed to load history", e); }
    },

    async loadPublicHistory() {
      try { this.history = await API.getPublicHistory(); }
      catch (e) { console.error("Failed to load public history", e); }
    },

    async loadHistoryResult(jobId) {
      try {
        this.simResult = await API.getResultJson(jobId);
        this.job = { id: jobId };
        this.selectedHistory = jobId;
      } catch (e) {
        alert("Nie uda\u0142o si\u0119 za\u0142adowa\u0107 wyniku: " + e.message);
      }
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

    classColor(className) {
      return this.CLASS_COLORS[className] || "var(--muted)";
    },

    selectChar(ch) {
      this.selectedChar = ch;
      this.simResult = null;
      this.job = null;
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
        if (!this.addonText.trim()) {
          alert("Wklej addon export!");
          this.loadingSim = false;
          return;
        }
        payload.addon_text = this.addonText.trim();
      } else if (this.selectedChar) {
        payload.name       = this.selectedChar.name;
        payload.realm_slug = this.selectedChar.realm_slug;
        payload.region     = this.selectedChar.region || "eu";
      } else {
        alert("Wybierz postac lub wklej addon export!");
        this.loadingSim = false;
        return;
      }

      try {
        const { job_id } = await API.startSim(payload);
        this.job = { id: job_id, status: "running" };
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
            job_id:           this.job.id,
            character_name:   this.selectedChar?.name || "Addon Export",
            character_class:  this.selectedChar?.class || "",
            dps:              this.simResult.dps,
            fight_style:      this.simOptions.fight_style,
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

    formatStatName(key) {
      return this.STAT_LABELS[key] || key;
    },

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

    getShareUrl(jobId) {
      return window.location.origin + "/?result=" + jobId;
    },

    copyToClipboard(text, jobId) {
      navigator.clipboard.writeText(text).then(() => {
        this.copiedJobId = jobId || true;
        setTimeout(() => { this.copiedJobId = null; }, 2000);
      }).catch(() => {});
    },
  };
}
