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
    const r = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  async getJobStatus(jobId) {
    const r = await fetch(`/api/job/${jobId}`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },

  async getResultJson(jobId) {
    const r = await fetch(`/api/result/${jobId}/json`);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
};
