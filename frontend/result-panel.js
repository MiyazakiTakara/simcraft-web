window.ResultPanel = function(jobId, opts) {
  const options = Object.assign({
    showReactions: true,
    showFooter:    true,
    showChart:     false,
  }, opts || {});

  return {
    jobId,
    options,
    result:    null,
    meta:      null,
    loading:   true,
    error:     null,
    spellSort: 'total_dmg',
    copied:            false,
    talentsCopied:     false,
    talentsGameCopied: false,
    ts:           Date.now(),
    timelineOpen: false,
    sessionId:    localStorage.getItem('simcraft_session'),
    tooltipCache: {},
    activeTooltip: null,
    tooltipX: 0,
    tooltipY: 0,
    reactionKeys:   ['fire', 'strong', 'sad', 'skull', 'rofl'],
    emojiMap:       { fire: '\ud83d\udd25', strong: '\ud83d\udcaa', sad: '\ud83d\ude22', skull: '\ud83d\udc80', rofl: '\ud83e\udd23' },
    reactionCounts: { fire: 0, strong: 0, sad: 0, skull: 0, rofl: 0 },
    myReaction:     null,
    reactionLoading: false,

    // Chart modal
    chartModal: null,

    formatDps(v)                  { return Utils.formatDps(v); },
    formatDmg(v)                  { return Utils.formatDmg(v); },
    formatStatName(k)             { return Utils.formatStatName(k); },
    formatStatValue(k, v)         { return Utils.formatStatValue(k, v); },
    pctBarWidth(val, spells, key) { return Utils.pctBarWidth(val, spells, key); },
    classColor(c)                 { return Utils.classColor(c); },
    classTextColor(c)             { return Utils.classTextColor(c); },

    async init() {
      if (!this.jobId) {
        this.error = Alpine.store('i18n').t('errors.sim_failed');
        this.loading = false;
        return;
      }

      try {
        const [result, meta] = await Promise.all([
          API.getResultJson(this.jobId),
          API.getResultMeta(this.jobId),
        ]);
        this.result = result;
        this.meta   = meta;
      } catch (e) {
        console.error('[ResultPanel] fetch error:', e);
        this.error = Alpine.store('i18n').t('result.not_found_error');
      } finally {
        this.loading = false;
      }

      await this.$nextTick();
      if (window.WH?.Tooltips?.refreshLinks) window.WH.Tooltips.refreshLinks();
      if (this.options.showReactions) await this.loadReactions();
    },

    showTooltipAt(spellId, event) {
      if (!spellId || spellId <= 0) return;
      const rect = event.currentTarget.getBoundingClientRect();
      this.tooltipX = Math.min(rect.left, window.innerWidth - 300);
      this.tooltipY = rect.bottom + 8;
      this.activeTooltip = spellId;
      this.fetchTooltip(spellId);
    },
    hideTooltip() { this.activeTooltip = null; },
    async fetchTooltip(spellId) {
      if (this.tooltipCache[spellId] !== undefined) return;
      this.tooltipCache[spellId] = 'loading';
      try {
        const r = await fetch(`/api/spell-tooltip/${spellId}`);
        this.tooltipCache[spellId] = r.ok ? await r.json() : null;
      } catch (e) {
        this.tooltipCache[spellId] = null;
      }
    },

    openChartModal(src) {
      this.chartModal = src || null;
    },

    async loadReactions() {
      try {
        const params = this.sessionId ? `?session=${encodeURIComponent(this.sessionId)}` : '';
        const res = await fetch(`/api/reactions/${this.jobId}${params}`);
        if (!res.ok) return;
        const data = await res.json();
        this.reactionCounts = data.counts || this.reactionCounts;
        this.myReaction     = data.my_reaction || null;
        if (data.emoji_map) this.emojiMap = data.emoji_map;
      } catch (e) { console.error('loadReactions:', e); }
    },
    async react(key) {
      if (!this.sessionId || this.reactionLoading) return;
      this.reactionLoading = true;
      try {
        const res = await fetch(`/api/reactions/${this.jobId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session: this.sessionId, emoji: key }),
        });
        if (!res.ok) return;
        const data = await res.json();
        this.reactionCounts = data.counts || this.reactionCounts;
        this.myReaction     = data.my_reaction || null;
      } catch (e) { console.error('react:', e); }
      finally { this.reactionLoading = false; }
    },

    armoryUrl() {
      const name      = this.meta?.character_name;
      const realmSlug = this.meta?.character_realm_slug;
      if (!name || !realmSlug || name === 'Addon Export') return null;
      const authorBnetId = this.meta?.author_bnet_id;
      if (authorBnetId) return `/u/${encodeURIComponent(authorBnetId)}/character/${realmSlug}/${name.toLowerCase()}`;
      return `https://worldofwarcraft.blizzard.com/en-gb/character/eu/${realmSlug}/${name.toLowerCase()}`;
    },
    armoryLabel() {
      return this.meta?.author_bnet_id ? 'SimCraft' : 'Armory \u2197';
    },

    copyTalents() {
      const t = this.meta?.talents;
      if (!t) return;
      navigator.clipboard.writeText(t).then(() => {
        this.talentsCopied = true;
        setTimeout(() => { this.talentsCopied = false; }, 2000);
      });
    },

    copyTalentsForGame() {
      const t = this.meta?.talents;
      if (!t) return;
      navigator.clipboard.writeText(t).then(() => {
        this.talentsGameCopied = true;
        setTimeout(() => { this.talentsGameCopied = false; }, 4000);
      });
    },

    get sortedSpells() {
      if (!this.result?.spells) return [];
      return [...this.result.spells].sort((a, b) => (b[this.spellSort] ?? 0) - (a[this.spellSort] ?? 0));
    },
    resultMetric() {
      if (!this.result) return { value: 0, std: 0 };
      return { value: this.result.dps ?? 0, std: this.result.dps_std ?? 0 };
    },

    copyShare() {
      navigator.clipboard.writeText(window.location.href)
        .then(() => { this.copied = true; setTimeout(() => { this.copied = false; }, 2000); });
    },
    copyShareById() {
      const url = `${window.location.origin}/result/${this.jobId}`;
      navigator.clipboard.writeText(url)
        .then(() => { this.copied = true; setTimeout(() => { this.copied = false; }, 2000); });
    },
  };
};
