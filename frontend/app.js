// SPEC -> rola (mirror z backendu, używane do auto-detect przed symulacją)
const SPEC_ROLE = {
  'Holy Priest':          'healer',
  'Discipline Priest':    'healer',
  'Holy Paladin':         'healer',
  'Restoration Druid':    'healer',
  'Restoration Shaman':   'healer',
  'Mistweaver Monk':      'healer',
  'Preservation Evoker':  'healer',
};

const ROLE_ICON = { dps: '⚔️', healer: '💚' };
const ROLE_LABEL = { dps: 'DPS', healer: 'Healer' };

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
    simRole: "auto",   // auto | dps | healer | tank
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
    historyPerPage: 5,

    profileTab: "chars",

    newsPage: 1,
    newsPerPage: 5,
    expandedNews: null,
    activeTab: "symulacje",
    currentView: "home",

    newsTeaser(body) {
      if (!body) return "";
      return body.length > 150 ? body.slice(0, 150) + "..." : body;
    },

    charEquipment: [],
    charTalents: [],
    loadingCharDetails: false,
    charDetailsError: null,

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

    appearance: {
      header_title: "SimCraft Web",
      hero_title: "World of Warcraft",
      emoji: "⚔️",
      hero_custom_text: ""
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

    // Zwraca rolę wynikającą z aktualnie wybranego chara (dla auto-detect)
    detectedRole() {
      if (!this.selectedChar) return 'dps';
      const spec = this.selectedChar.spec || '';
      return SPEC_ROLE[spec] || 'dps';
    },

    // Efektywna rola: jeśli simRole==='auto' — detect po speccu, inaczej override
    effectiveRole() {
      return this.simRole === 'auto' ? this.detectedRole() : this.simRole;
    },

    roleIcon(role) { return ROLE_ICON[role] || '⚔️'; },
    roleLabel(role) { return ROLE_LABEL[role] || 'DPS'; },

    // Gdy user wybiera postać — resetuj simRole do auto (żeby auto-detect zadziałał)
    selectChar(ch) {
      this.selectedChar = ch;
      this.simResult = null;
      this.job = null;
      this.simRole = 'auto';
      this.currentView = "symulacje";
      this.activeTab = "symulacje";
      localStorage.setItem("simcraft_last_char", ch.name);
    },

    // Główna metryka do pokazania w wyniku
    resultMetric(result) {
      if (!result) return { value: 0, std: 0, label: 'DPS' };
      const role = result._role || this.effectiveRole();
      if (role === 'healer') return { value: result.hps ?? 0, std: result.hps_std ?? 0, label: 'HPS' };
      return { value: result.dps ?? 0, std: result.dps_std ?? 0, label: 'DPS' };
    },

    async loadNews() {
      try {
        const res = await fetch('/admin/api/news/public');
        console.log('loadNews response:', res.status, res.ok);
        if (res.ok) {
          this.news = await res.json();
          this.newsPage = 1;
          console.log('news loaded:', this.news.length);
        } else {
          console.error('News API error:', res.status);
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
        const data = await API.getHistory(this.sessionId, this.historyPage, this.historyPerPage);
        this.history = data.items || [];
      } catch (e) { console.error("Failed to load history", e); }
    },

    async loadPublicHistory() {
      try {
        const data = await API.getPublicHistory(this.historyPage, this.historyPerPage);
        this.history = data.items || [];
      } catch (e) { console.error("Failed to load public history", e); }
    },

    async loadCharDetails(char) {
      this.loadingCharDetails = true;
      this.charDetailsError = null;
      this.charEquipment = [];
      this.charTalents = [];
      try {
        const [eq, talents] = await Promise.all([
          API.getCharacterEquipment(this.sessionId, char.realm_slug, char.name),
          API.getCharacterTalents(this.sessionId, char.realm_slug, char.name),
        ]);
        this.charEquipment = eq.equipment || [];
        this.charTalents = talents.talents || [];
      } catch (e) {
        this.charDetailsError = e.message;
        console.error("Failed to load char details", e);
      } finally {
        this.loadingCharDetails = false;
        this.$nextTick(() => this.drawDpsTrendChart(char));
      }
    },

    async drawDpsTrendChart(char) {
      const chartDiv = document.getElementById('dps-trend-chart');
      if (!chartDiv) return;

      try {
        const params = new URLSearchParams({
          session: this.sessionId,
          character_name: char.name,
          character_realm_slug: char.realm_slug,
          fight_style: 'Patchwerk',
          limit: 100
        });

        const response = await fetch(`/api/history/trend?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        if (!data.points || data.points.length === 0) {
          Plotly.purge(chartDiv);
          chartDiv.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted)">Brak danych do wykresu</div>';
          return;
        }

        const x = data.points.map(p => new Date(p.timestamp * 1000));
        const y = data.points.map(p => p.dps);

        const trace = {
          x, y,
          mode: 'lines+markers',
          type: 'scatter',
          name: 'DPS',
          line: { color: '#f4a01c', width: 2 },
          marker: { size: 6, color: '#f4a01c' },
          hovertemplate: 'Czas: %{x}<br>DPS: %{y:.0f}<extra></extra>'
        };

        const layout = {
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          margin: { l: 50, r: 20, t: 20, b: 50 },
          xaxis: { gridcolor: 'rgba(255,255,255,0.1)', color: '#aaa', tickformat: '%H:%M<br>%d.%m' },
          yaxis: { gridcolor: 'rgba(255,255,255,0.1)', color: '#aaa', title: 'DPS' },
          showlegend: false
        };

        Plotly.newPlot(chartDiv, [trace], layout, { responsive: true, displayModeBar: false });
      } catch (e) {
        console.error("Failed to load DPS trend", e);
        Plotly.purge(chartDiv);
        chartDiv.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#f66">Błąd ładowania danych</div>';
      }
    },

    getItemQualityColor(quality) {
      const colors = {
        "Poor": "#9d9d9d",
        "Common": "#ffffff",
        "Uncommon": "#1eff00",
        "Rare": "#0070dd",
        "Epic": "#a335ee",
        "Legendary": "#ff8000",
        "Artifact": "#e6cc80",
        "Heirloom": "#00ccff",
      };
      return colors[quality] || "#fff";
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
        if (entry?.role) this.simResult._role = entry.role;
        this.job = {
          id:        jobId,
          charName:  charName !== 'Addon Export' ? charName : null,
          realmSlug: charObj?.realm_slug || entry?.character_realm_slug || null,
          charClass: charClass || null,
          charSpec:  charSpec || charObj?.spec || null,
          role:      entry?.role || 'dps',
        };
      } catch (e) {
        alert("Nie udało się załadować wyniku: " + e.message);
      }
    },

    openResultPage(jobId) {
      window.open('/result/' + jobId, '_blank');
    },

    async loadPubResult(jobId) {
      try {
        const [result, meta] = await Promise.all([
          API.getResultJson(jobId),
          API.getResultMeta(jobId),
        ]);
        result._source = meta?.character_name === 'Addon Export' ? 'addon' : 'history';
        if (meta?.role) result._role = meta.role;
        this.pubResult = result;
        this.pubJob = {
          id:        jobId,
          charName:  meta?.character_name !== 'Addon Export' ? (meta?.character_name || null) : null,
          realmSlug: meta?.character_realm_slug || null,
          charClass: meta?.character_class || null,
          charSpec:  meta?.character_spec  || null,
          role:      meta?.role || 'dps',
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
              const guestRole = result.hps > 100 ? 'healer' : 'dps';
              this.pubJob = { id: guestJobId, charName: null, realmSlug: null, charClass: null, charSpec: null, role: guestRole };
              await API.saveToHistory({
                job_id:               guestJobId,
                character_name:       "Addon Export",
                character_class:      "",
                character_spec:       "",
                character_realm_slug: "",
                dps:                  result.dps,
                hps:                  result.hps || 0,
                role:                 guestRole,
                fight_style:          this.guestSimOptions.fight_style,
                user_id:              null,
              });
              this.loadPublicHistory();
              this.guestLoadingSim = false;
            } else if (status.status === "error") {
              clearInterval(this._guestPollInterval);
              this.guestSimError = "Błąd symulacji: " + (status.error || "Nieznany błąd");
              this.guestLoadingSim = false;
            }
          } catch (e) {
            clearInterval(this._guestPollInterval);
            this.guestLoadingSim = false;
          }
        }, 3000);
      } catch (e) {
        this.guestSimError = "Błąd: " + e.message;
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

    charDetailsModal: null,

    openCharDetails(ch) {
      this.charDetailsModal = ch;
      this.loadCharDetails(ch);
    },

    closeCharDetails() {
      this.charDetailsModal = null;
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
          role:      this.effectiveRole(),
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
          this.simResult._role = this.job.role;
          await API.saveToHistory({
            job_id:               this.job.id,
            character_name:       this.selectedChar?.name || "Addon Export",
            character_class:      this.selectedChar?.class || "",
            character_spec:       this.selectedChar?.spec || "",
            character_realm_slug: this.selectedChar?.realm_slug || "",
            dps:                  this.simResult.dps,
            hps:                  this.simResult.hps || 0,
            role:                 this.effectiveRole(),
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
      const sortedSims = charSims.sort((a, b) => a.created_at - b.created_at);
      const dpsList = sortedSims.map(h => h.dps);
      const latest = dpsList[dpsList.length - 1];
      const first = dpsList[0];
      const diff = latest - first;
      const trend = dpsList.length > 1
        ? (diff > 0 ? '↑' : '↓') + ' ' + Math.abs(Math.round(diff))
        : '1 symulacja';
      return {
        latest, first, diff, trend,
        count: dpsList.length,
        lastSim: charSims.reduce((max, h) => h.created_at > max ? h.created_at : max, 0),
        dpsList,
        chartData: sortedSims.map(h => ({
          x: new Date(h.created_at * 1000),
          y: h.dps,
          job_id: h.job_id
        }))
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

    showItemTooltip(event, item) {
      const tooltip = document.getElementById('item-tooltip');
      if (!tooltip) return;

      let html = `
        <div class="item-tooltip-slot">${item.slot}</div>
        <div class="item-tooltip-title" style="color:${this.getItemQualityColor(item.quality)}">${item.name}</div>
        <div style="color:var(--muted);font-size:.75rem;margin-bottom:.5rem">ilvl ${item.level}</div>
      `;
      if (item.description) html += `<div style="font-size:.8rem;color:var(--muted);margin-bottom:.5rem;font-style:italic">${item.description}</div>`;
      if (item.stats && item.stats.length > 0) {
        html += '<div class="item-tooltip-stats">';
        item.stats.forEach(stat => {
          html += `<div class="item-tooltip-stat"><span>${stat.type}</span><span>${stat.value > 0 ? '+' : ''}${stat.value}</span></div>`;
        });
        html += '</div>';
      }
      if (item.enchant) html += `<div class="item-tooltip-enchant">✓ ${item.enchant}</div>`;
      if (item.gem)     html += `<div class="item-tooltip-gem">♦ ${item.gem}</div>`;
      if (item.spells && item.spells.length > 0) {
        item.spells.forEach(spell => {
          html += `<div class="item-tooltip-spell"><div class="item-tooltip-spell-name">${spell.name}</div><div class="item-tooltip-spell-desc">${spell.description}</div></div>`;
        });
      }

      tooltip.innerHTML = html;
      tooltip.style.display = 'block';

      const rect = event.target.getBoundingClientRect();
      let top  = rect.top - tooltip.offsetHeight - 10;
      let left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2);
      if (top < 10) top = rect.bottom + 10;
      if (left < 10) left = 10;
      if (left + tooltip.offsetWidth > window.innerWidth - 10) left = window.innerWidth - tooltip.offsetWidth - 10;
      tooltip.style.top  = top + 'px';
      tooltip.style.left = left + 'px';
    },

    hideItemTooltip() {
      const tooltip = document.getElementById('item-tooltip');
      if (tooltip) tooltip.style.display = 'none';
    },
  };
}
