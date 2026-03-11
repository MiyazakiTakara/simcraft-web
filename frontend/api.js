const API = {
  base: "",

  async _fetch(url, opts = {}) {
    const res = await fetch(this.base + url, opts);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
    }
    return res.json();
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
