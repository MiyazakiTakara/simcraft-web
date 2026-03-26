const API = {
  base: "",

  async _fetch(url, opts = {}) {
    const res = await fetch(this.base + url, opts);
    if (!res.ok) {
      if (res.status === 401) {
        window.dispatchEvent(new CustomEvent('simcraft:session-expired'));
      }
      let detail = '';
      try { const e = await res.json(); detail = e.detail || e.message || ''; } catch {}
      throw Object.assign(new Error(detail || `HTTP ${res.status}`), { status: res.status });
    }
    try {
      return await res.json();
    } catch {
      throw new Error('Invalid JSON response');
    }
  },

  logoutUrl() { return "/auth/logout"; },

  async getCharacters(session) {
    return this._fetch(`/api/characters?session=${encodeURIComponent(session)}`);
  },

  async getCharacterMedia(session, realmSlug, charName) {
    return this._fetch(`/api/character-media?session=${encodeURIComponent(session)}&realm_slug=${encodeURIComponent(realmSlug)}&name=${encodeURIComponent(charName)}`);
  },

  async getCharacterEquipment(session, realmSlug, charName) {
    return this._fetch(`/api/character/equipment?session=${encodeURIComponent(session)}&realm_slug=${encodeURIComponent(realmSlug)}&name=${encodeURIComponent(charName)}`);
  },

  async getCharacterStatistics(session, realmSlug, charName) {
    return this._fetch(`/api/character/statistics?session=${encodeURIComponent(session)}&realm_slug=${encodeURIComponent(realmSlug)}&name=${encodeURIComponent(charName)}`);
  },

  async getCharacterTalents(session, realmSlug, charName) {
    return this._fetch(`/api/character/talents?session=${encodeURIComponent(session)}&realm_slug=${encodeURIComponent(realmSlug)}&name=${encodeURIComponent(charName)}`);
  },

  async startSim(payload) {
    return this._fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  async getJobStatus(jobId) {
    return this._fetch(`/api/job/${jobId}`);
  },

  async getResultJson(jobId) {
    return this._fetch(`/api/result/${jobId}/json`);
  },

  async getResultMeta(jobId) {
    return this._fetch(`/api/result/${jobId}/meta`);
  },

  // Historia zalogowanego uzytkownika (pelna historia w profilu - 10 na strone)
  async getHistory(session, page = 1, limit = 10) {
    if (session) {
      return this._fetch(`/api/history/mine?session=${encodeURIComponent(session)}&page=${page}&limit=${limit}`);
    }
    return this._fetch(`/api/history?page=${page}&limit=${limit}`);
  },

  // Publiczna historia (gosc)
  async getPublicHistory(page = 1, limit = 5) {
    return this._fetch(`/api/history?page=${page}&limit=${limit}`);
  },

  async saveToHistory(payload) {
    return this._fetch("/api/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
};
