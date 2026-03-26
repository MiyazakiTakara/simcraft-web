function favoritesView() {
  return {
    loading: true,
    sessionId: localStorage.getItem('simcraft_session'),
    favorites: [],

    async init() {
      if (!this.sessionId) { this.loading = false; return; }
      try {
        const res = await fetch(`/api/favorites?session=${encodeURIComponent(this.sessionId)}`);
        if (res.ok) {
          const data = await res.json();
          this.favorites = data.favorites || [];
        }
      } catch(e) {}
      finally { this.loading = false; }
    },

    async removeFavorite(targetBnetId) {
      if (!this.sessionId) return;
      try {
        await fetch(`/api/favorites/${encodeURIComponent(targetBnetId)}?session=${encodeURIComponent(this.sessionId)}`, {
          method: 'DELETE',
        });
        this.favorites = this.favorites.filter(f => f.bnet_id !== targetBnetId);
      } catch(e) {}
    },

    formatTime(v) {
      if (!v) return '';
      return new Date(v).toLocaleDateString('pl-PL', { day:'2-digit', month:'2-digit', year:'numeric' });
    },
  };
}

window.favoritesView = favoritesView;
