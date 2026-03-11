// Zarządzanie postaciami, szczegóły, tooltips
const CharsMixin = {
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

  selectChar(ch) {
    this.selectedChar = ch;
    this.simResult = null;
    this.job = null;
    this.simRole = 'auto';
    this.navigateTo('symulacje');
    localStorage.setItem("simcraft_last_char", ch.name);
  },

  selectCharByName(name) {
    const ch = this.characters.find(c => c.name === name);
    if (ch) this.navigateTo('symulacje');
  },

  getCharAvatar(name) {
    const ch = this.characters.find(c => c.name === name);
    return ch ? ch.avatar : null;
  },

  openCharDetails(ch) {
    this.charDetailsModal = ch;
    this.loadCharDetails(ch);
  },

  closeCharDetails() {
    this.charDetailsModal = null;
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

  // Parsuje created_at niezależnie od formatu (ISO string lub Unix seconds)
  _parseDate(created_at) {
    if (!created_at && created_at !== 0) return null;
    if (typeof created_at === "string") {
      const s = created_at.endsWith("Z") || created_at.includes("+") ? created_at : created_at + "Z";
      const d = new Date(s);
      return isNaN(d.getTime()) ? null : d;
    }
    if (typeof created_at === "number") {
      return new Date(created_at < 1e10 ? created_at * 1000 : created_at);
    }
    return null;
  },

  async drawDpsTrendChart(char) {
    const chartDiv = document.getElementById('dps-trend-chart');
    if (!chartDiv) return;
    const charData = this.getCharDps(char.name);
    if (!charData || !charData.chartData || charData.chartData.length === 0) {
      Plotly.purge(chartDiv);
      chartDiv.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted)">Brak danych do wykresu</div>';
      return;
    }
    const x    = charData.chartData.map(p => p.x);
    const dpsY = charData.chartData.map(p => +(p.dps / 1000).toFixed(2));
    const hpsY = charData.chartData.map(p => +(p.hps / 1000).toFixed(2));
    const hasHps = hpsY.some(v => v > 0);
    const traceDps = {
      x, y: dpsY, mode: 'lines+markers', type: 'scatter', name: 'DPS',
      line: { color: '#f4a01c', width: 2 }, marker: { size: 6, color: '#f4a01c' },
      hovertemplate: '%{y:.2f}k DPS<extra></extra>'
    };
    const traces = [traceDps];
    if (hasHps) {
      traces.push({
        x, y: hpsY, mode: 'lines+markers', type: 'scatter', name: 'HPS',
        line: { color: '#3399ff', width: 2 }, marker: { size: 6, color: '#3399ff' },
        hovertemplate: '%{y:.2f}k HPS<extra></extra>'
      });
    }
    Plotly.newPlot(chartDiv, traces, {
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      margin: { l: 55, r: 20, t: 20, b: 50 },
      xaxis: { gridcolor: 'rgba(255,255,255,0.1)', color: '#aaa', tickformat: '%H:%M<br>%d.%m' },
      yaxis: {
        gridcolor: 'rgba(255,255,255,0.1)', color: '#aaa',
        title: hasHps ? 'DPS / HPS' : 'DPS',
        ticksuffix: 'k',
        tickformat: ',.2f',
        exponentformat: 'none',
      },
      showlegend: true,
      legend: { orientation: 'h', y: 1.1, x: 0.5, xanchor: 'center', font: { color: '#aaa' } }
    }, { responsive: true, displayModeBar: false });
  },

  getCharDps(charName) {
    const charSims = this.history.filter(h => h.character_name === charName);
    if (charSims.length === 0) return null;
    const sortedSims = charSims.sort((a, b) => {
      const da = this._parseDate(a.created_at);
      const db = this._parseDate(b.created_at);
      return (da?.getTime() ?? 0) - (db?.getTime() ?? 0);
    });
    const dpsList = sortedSims.map(h => h.dps);
    const hpsList = sortedSims.map(h => h.hps || 0);
    const latest = dpsList[dpsList.length - 1];
    const latestHps = hpsList[hpsList.length - 1];
    const first = dpsList[0];
    const diff = latest - first;
    const lastSimEntry = sortedSims[sortedSims.length - 1];
    const lastSim = lastSimEntry?.created_at ?? null;
    const trend = dpsList.length > 1
      ? (diff > 0 ? '↑' : '↓') + ' ' + Math.abs(Math.round(diff))
      : '1 symulacja';
    return {
      latest, latestHps, first, diff, trend,
      count: dpsList.length, lastSim, dpsList, hpsList,
      chartData: sortedSims.map(h => ({
        x: this._parseDate(h.created_at),
        dps: h.dps,
        hps: h.hps || 0,
        job_id: h.job_id
      })).filter(p => p.x !== null)
    };
  },

  getCharacterTrends() {
    const charMap = new Map();
    for (const entry of this.history) {
      if (!entry.character_name || entry.character_name === 'Addon Export') continue;
      const key = entry.character_name;
      if (!charMap.has(key)) {
        charMap.set(key, {
          name: entry.character_name, charClass: entry.character_class,
          charSpec: entry.character_spec, realmSlug: entry.character_realm_slug,
          dps: [], fight_style: entry.fight_style, created_at: entry.created_at,
        });
      }
      const char = charMap.get(key);
      char.dps.push({ dps: entry.dps, created_at: entry.created_at, fight_style: entry.fight_style });
      const da = this._parseDate(entry.created_at);
      const db = this._parseDate(char.created_at);
      if (da && db && da > db) char.created_at = entry.created_at;
    }
    return Array.from(charMap.values()).sort((a, b) => {
      const da = this._parseDate(a.created_at);
      const db = this._parseDate(b.created_at);
      return (db?.getTime() ?? 0) - (da?.getTime() ?? 0);
    });
  },

  showItemTooltip(event, item) {
    const tooltip = document.getElementById('item-tooltip');
    if (!tooltip) return;
    let html = `
      <div class="item-tooltip-slot">${item.slot}</div>
      <div class="item-tooltip-title" style="color:${Utils.getItemQualityColor(item.quality)}">${item.name}</div>
      <div style="color:var(--muted);font-size:.75rem;margin-bottom:.5rem">ilvl ${item.level}</div>
    `;
    if (item.description) html += `<div style="font-size:.8rem;color:var(--muted);margin-bottom:.5rem;font-style:italic">${item.description}</div>`;
    if (item.stats?.length) {
      html += '<div class="item-tooltip-stats">';
      item.stats.forEach(stat => {
        html += `<div class="item-tooltip-stat"><span>${stat.type}</span><span>${stat.value > 0 ? '+' : ''}${stat.value}</span></div>`;
      });
      html += '</div>';
    }
    if (item.enchant) html += `<div class="item-tooltip-enchant">✓ ${item.enchant}</div>`;
    if (item.gem)     html += `<div class="item-tooltip-gem">♦ ${item.gem}</div>`;
    if (item.spells?.length) {
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
