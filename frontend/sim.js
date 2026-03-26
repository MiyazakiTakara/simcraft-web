// Logika symulacji (startSim, polling, guest sim, pubResult)
const SimMixin = {
  // Tooltip cache: spell_id -> 'loading' | null | { name, description, icon, school, cast_time, ... }
  tooltipCache: {},

  async showTooltip(spellId) {
    if (!spellId || spellId <= 0) return;
    if (this.tooltipCache[spellId] !== undefined) return;
    this.tooltipCache[spellId] = 'loading';
    try {
      const r = await fetch(`/api/spell-tooltip/${spellId}`);
      this.tooltipCache[spellId] = r.ok ? await r.json() : null;
    } catch (e) {
      console.warn('tooltip fetch failed', spellId, e);
      this.tooltipCache[spellId] = null;
    }
  },

  resultMetric(result) {
    if (!result) return { value: 0, std: 0, label: 'DPS' };
    return { value: result.dps ?? 0, std: result.dps_std ?? 0, label: 'DPS' };
  },

  async startSim() {
    this.loadingSim = true;
    this.simResult = null;
    this.job = null;
    const payload = {
      session:          this.sessionId,
      fight_style:      this.simOptions.fight_style,
      iterations:       this.simOptions.iterations,
      target_error:     this.simOptions.target_error,
      one_button_mode:  this.simOptions.one_button_mode,
    };
    if (this.simMode === "addon") {
      if (!this.addonText.trim()) { alert(Alpine.store('i18n').t('sim.error_paste_addon')); this.loadingSim = false; return; }
      payload.addon_text = this.addonText.trim();
    } else if (this.selectedChar) {
      payload.name       = this.selectedChar.name;
      payload.realm_slug = this.selectedChar.realm_slug;
      payload.region     = this.selectedChar.region || "eu";
    } else {
      alert(Alpine.store('i18n').t('sim.error_select_or_paste')); this.loadingSim = false; return;
    }
    try {
      const { job_id, source } = await API.startSim(payload);
      const isAddonMode = this.simMode === "addon";
      this.job = {
        id:              job_id,
        source:          source || 'web',
        status:          "running",
        // W trybie addon nie przypisujemy wybranej postaci
        charName:        isAddonMode ? null : (this.selectedChar?.name || null),
        realmSlug:       isAddonMode ? null : (this.selectedChar?.realm_slug || null),
        charClass:       isAddonMode ? null : (this.selectedChar?.class || null),
        charSpec:        isAddonMode ? null : (this.selectedChar?.spec || null),
        charSpecId:      isAddonMode ? null : (this.selectedChar?.spec_id || null),
        role:            this.effectiveRole(),
        one_button_mode: this.simOptions.one_button_mode,
        isAddonMode,
      };
      this._pollInterval = setInterval(() => this._pollJob(), 3000);
    } catch (e) {
      alert(Alpine.store('i18n').t('sim.error_start_prefix') + e.message);
      this.loadingSim = false;
    }
  },

  async _pollJob() {
    if (!this.job) return;
    try {
      const status = await API.getJobStatus(this.job.id);
      this.job.status = status.status;
      if (status.wow_build) this.job.wow_build = status.wow_build;

      // Pokaz baner rebuildu jezeli backend go zwrocil
      if (status.rebuild_banner) {
        this.rebuildBanner = status.rebuild_banner;
      }

      if (status.status === "done") {
        clearInterval(this._pollInterval);
        this.rebuildBanner = null;
        this.simResult = await API.getResultJson(this.job.id);
        this.simResult._role = this.job.role;
        // W trybie addon nie przypisujemy postaci z Armory
        const isAddon = this.job.isAddonMode;
        await API.saveToHistory({
          job_id:               this.job.id,
          character_name:       isAddon ? "Addon Export" : (this.job.charName || "Addon Export"),
          character_class:      isAddon ? "" : (this.job.charClass || ""),
          character_spec:       isAddon ? "" : (this.job.charSpec || ""),
          character_spec_id:    isAddon ? null : (this.job.charSpecId || null),
          character_realm_slug: isAddon ? "" : (this.job.realmSlug || ""),
          dps:                  this.simResult.dps,
          hps:                  this.simResult.hps || 0,
          dtps:                 0,
          role:                 this.effectiveRole(),
          fight_style:          this.simOptions.fight_style,
          user_id:              this.sessionId || null,
          source:               this.job.source || 'web',
          wow_build:            this.job.wow_build || null,
          one_button_mode:      this.job.one_button_mode || false,
        });
        this.loadHistory();
        this.loadingSim = false;
      } else if (status.status === "error") {
        clearInterval(this._pollInterval);
        this.rebuildBanner = null;
        alert(Alpine.store('i18n').t('sim.error_sim_prefix') + (status.error || Alpine.store('i18n').t('common.unknown')));
        this.loadingSim = false;
      }
    } catch (e) {
      clearInterval(this._pollInterval);
      this.rebuildBanner = null;
      this.loadingSim = false;
    }
  },

  async startGuestSim() {
    if (!this.guestAddonText.trim()) { this.guestSimError = Alpine.store('i18n').t('sim.error_paste_addon'); return; }
    this.guestSimError = null;
    this.guestLoadingSim = true;
    this.pubResult = null;
    this.pubJob = null;
    try {
      const { job_id, source } = await API.startSim({
        addon_text:       this.guestAddonText.trim(),
        fight_style:      this.guestSimOptions.fight_style,
        iterations:       this.guestSimOptions.iterations,
        target_error:     this.guestSimOptions.target_error,
        one_button_mode:  this.guestSimOptions.one_button_mode,
      });
      const guestJobId  = job_id;
      const guestSource = source || 'addon';
      const guestOneButtonMode = this.guestSimOptions.one_button_mode || false;
      let guestWowBuild = null;   // ← TUTAJ
      this._guestPollInterval = setInterval(async () => {
        try {
          const status = await API.getJobStatus(guestJobId);

          if (status.rebuild_banner) {
            this.rebuildBanner = status.rebuild_banner;
          }
          if (status.wow_build) guestWowBuild = status.wow_build;

          if (status.status === "done") {
            clearInterval(this._guestPollInterval);
            this.rebuildBanner = null;
            const result = await API.getResultJson(guestJobId);
            result._source = guestSource;
            this.pubResult = result;
            this.pubJob = { id: guestJobId, charName: null, realmSlug: null, charClass: null, charSpec: null, charSpecId: null, role: 'dps' };
            await API.saveToHistory({
              job_id:               guestJobId,
              character_name:       "Addon Export",
              character_class:      "",
              character_spec:       "",
              character_spec_id:    null,
              character_realm_slug: "",
              dps:                  result.dps,
              hps:                  result.hps || 0,
              dtps:                 0,
              role:                 'dps',
              fight_style:          this.guestSimOptions.fight_style,
              user_id:              null,
              source:               guestSource,
              wow_build:            guestWowBuild || null,
              one_button_mode:      guestOneButtonMode,
            });
            this.loadPublicHistory();
            this.guestLoadingSim = false;
          } else if (status.status === "error") {
            clearInterval(this._guestPollInterval);
            this.rebuildBanner = null;
            this.guestSimError = Alpine.store('i18n').t('sim.error_sim_prefix') + (status.error || Alpine.store('i18n').t('common.unknown'));
            this.guestLoadingSim = false;
          }
        } catch (e) {
          clearInterval(this._guestPollInterval);
          this.rebuildBanner = null;
          this.guestLoadingSim = false;
        }
      }, 3000);
    } catch (e) {
      this.guestSimError = Alpine.store('i18n').t('common.error_prefix') + e.message;
      this.guestLoadingSim = false;
    }
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
        charSpecId: meta?.character_spec_id || null,
        role:      meta?.role || 'dps',
      };
    } catch (e) {
      console.error("loadPubResult failed", e);
    }
  },

  // gettery przeniesione do app() — nie umieszczaj ich tutaj!
};
