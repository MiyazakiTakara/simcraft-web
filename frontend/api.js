const API = {
  loginUrl() {
    return "/auth/login";
  },

  logoutUrl() {
    return "/auth/logout";
  },

  async getCharacters(sessionId) {
    const r = await fetch(`/api/characters?session=${sessionId}`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  async getCharacterMedia(sessionId, realmSlug, name) {
    const r = await fetch(`/api/character/${sessionId}/${realmSlug}/${name}`);
    if (!r.ok) return { avatar: null };
    return r.json();
  },

  async startSim(payload) {
    const r = await fetch("/api/sim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  async getJobStatus(jobId) {
    const r = await fetch(`/api/sim/${jobId}/status`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  async getResultJson(jobId) {
    const r = await fetch(`/api/result/${jobId}/json`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  async getResultMeta(jobId) {
    const r = await fetch(`/api/result/${jobId}/meta`);
    if (!r.ok) return null;
    return r.json();
  },

  async saveToHistory(entry) {
    const r = await fetch("/api/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry),
    });
    if (!r.ok) console.warn("History save failed:", await r.text());
    return {};
  },

  async getHistory() {
    const r = await fetch("/api/history");
    if (!r.ok) return [];
    return r.json();
  },

  async getPublicHistory() {
    const r = await fetch("/api/history");
    if (!r.ok) return [];
    return r.json();
  },
};
