function app() {
  return {
    sessionId: null,
    characters: [],
    charFilter: "",
    selectedChar: null,
    job: null,
    simResult: null,
    simMode: "addon",
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

    init() {
      const params = new URLSearchParams(window.location.search);
      const session = params.get("session");
      const resultId = params.get("result");
      
      if (session) {
        this.sessionId = session;
        history.replaceState({}, "", "/");
        this.loadCharacters();
        this.loadHistory();
      } else {
        this.loadPublicHistory();
      }
      
      // Load shared result if provided
      if (resultId) {
        this.loadHistoryResult(resultId);
      }
    },

    async loadCharacters() {
      this.loadingChars = true;
      this.errorChars = null;
      try {
        const chars = await API.getCharacters(this.sessionId);
        this.characters = chars;
        // load avatars async
        for (const ch of this.characters) {
          API.getCharacterMedia(this.sessionId, ch.realm_slug, ch.name.toLowerCase())
            .then((m) => { ch.avatar = m.avatar; })
            .catch(() => {});
        }
      } catch (e) {
        this.errorChars = e.message;
      } finally {
        this.loadingChars = false;
      }
    },

    async loadHistory() {
      try {
        this.history = await API.getHistory();
      } catch (e) {
        console.error("Failed to load history", e);
      }
    },

    async loadPublicHistory() {
      try {
        this.history = await API.getPublicHistory();
      } catch (e) {
        console.error("Failed to load public history", e);
      }
    },

    async loadHistoryResult(jobId) {
      try {
        this.simResult = await API.getResultJson(jobId);
        this.job = { id: jobId };  // Set job so share button works
        this.selectedHistory = jobId;
      } catch (e) {
        alert("Nie udało się załadować wyniku: " + e.message);
      }
    },

    get filteredChars() {
      const q = this.charFilter.toLowerCase();
      return this.characters.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.realm.toLowerCase().includes(q)
      );
    },

    selectChar(ch) {
      this.selectedChar = ch;
      this.simResult = null;
      this.job = null;
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

      if (this.simMode === "addon" && this.addonText.trim()) {
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
          // Save to history
          await API.saveToHistory({
            job_id: this.job.id,
            character_name: this.selectedChar?.name || "Addon Export",
            dps: this.simResult.dps,
            fight_style: this.simOptions.fight_style,
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
      this.sessionId = null;
      this.characters = [];
      this.selectedChar = null;
      this.simResult = null;
      window.location.href = API.logoutUrl();
    },

    formatDps(v) {
      if (!v && v !== 0) return "—";
      if (v >= 1_000_000) return (v / 1_000_000).toFixed(2) + "M";
      if (v >= 1_000)     return (v / 1_000).toFixed(1) + "k";
      return String(v);
    },

    pctBarWidth(dps, maxDps) {
      return maxDps > 0 ? Math.round((dps / maxDps) * 100) + "%" : "0%";
    },

    formatStatName(key) {
      return key;
    },

    formatStatValue(key, val) {
      if (typeof val === "number") return Math.round(val).toLocaleString();
      return val;
    },

    formatTime(timestamp) {
      if (!timestamp) return "—";
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

    copyToClipboard(text) {
      navigator.clipboard.writeText(text).then(() => {
        alert("Link skopiowany do schowka!");
      }).catch(() => {
        alert("Nie udało się skopiować linku");
      });
    },
  };
}
