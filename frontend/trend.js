// trend.js — mixin DPS Trend chart (wydzielony z app.js, issue #40)
const TrendMixin = {
  trendCharName:   '',
  trendFightStyle: 'Patchwerk',
  trendPoints:     [],
  trendLoading:    false,
  _trendChart:     null,

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
      this.trendPoints = (data.trend || data.points || []).map(p => ({
        ...p,
        timestamp: p.created_at || p.timestamp,
      }));
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

    const isDark   = (this.theme || 'dark') !== 'light';
    const textClr  = isDark ? '#cccccc' : '#333333';
    const gridClr  = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.08)';
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
            callbacks: { label: ctx => ' DPS: ' + Utils.formatDps(ctx.parsed.y) },
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
            ticks: { color: textClr, callback: v => Utils.formatDps(v), font: { size: 11 } },
            grid:  { color: gridClr },
          },
        },
      },
    });
  },
};
