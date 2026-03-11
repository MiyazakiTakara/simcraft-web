// Logika symulacji (startSim, polling, guest sim, pubResult)
const SimMixin = {
  resultMetric(result) {
    if (!result) return { value: 0, std: 0, label: 'DPS' };
    return { value: result.dps ?? 0, std: result.dps_std ?? 0, label: 'DPS' };
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
          dtps:                 0,
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

  async startGuestSim() {
    if (!this.guestAddonText.trim()) { this.guestSimError = "Wklej tekst z addona!"; return; }
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
            this.pubJob = { id: guestJobId, charName: null, realmSlug: null, charClass: null, charSpec: null, role: 'dps' };
            await API.saveToHistory({
              job_id:               guestJobId,
              character_name:       "Addon Export",
              character_class:      "",
              character_spec:       "",
              character_realm_slug: "",
              dps:                  result.dps,
              hps:                  result.hps || 0,
              dtps:                 0,
              role:                 'dps',
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

  // gettery przeniesione do app() — nie umieszczaj ich tutaj!
};
