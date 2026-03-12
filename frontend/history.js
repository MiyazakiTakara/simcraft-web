// Historia symulacji i newsy
const HistoryMixin = {
  async loadHistory() {
    this.loadingHistory = true;
    this.historyLoading = true;
    try {
      if (this.sessionId) {
        let data;
        try {
          data = await API.getHistory(this.sessionId, 1, 100);
        } catch (e) {
          // Sesja wygasła lub nieprawidłowa — fallback na publiczną historię
          console.warn('loadHistory: sesja odrzucona, fallback na public', e);
          data = await API.getPublicHistory(1, 100);
        }
        this.history = data.results || [];
      } else {
        const data = await API.getPublicHistory(1, 100);
        this.history = data.results || [];
      }
      this.historyPage = 1;
    } catch (e) {
      console.error('Failed to load history', e);
      this.history = [];
    } finally {
      this.loadingHistory = false;
      this.historyLoading = false;
    }
  },

  async loadPublicHistory() {
    this.loadingHistory = true;
    this.historyLoading = true;
    try {
      const data = await API.getPublicHistory(1, 100);
      this.history = data.results || [];
      this.historyPage = 1;
    } catch (e) {
      console.error('Failed to load public history', e);
      this.history = [];
    } finally {
      this.loadingHistory = false;
      this.historyLoading = false;
    }
  },

  async loadNews() {
    try {
      const res = await fetch('/admin/api/news/public');
      if (res.ok) {
        this.news = await res.json();
        this.newsPage = 1;
      }
    } catch (e) { console.error('Failed to load news', e); }
  },

  newsTeaser(body) {
    if (!body) return "";
    return body.length > 150 ? body.slice(0, 150) + "..." : body;
  },

  // gettery przeniesione do app() — nie umieszczaj ich tutaj!
  newsPages() {
    return Array.from({ length: this.newsPageCount }, (_, i) => i + 1);
  },

  historyPages() {
    return Array.from({ length: this.historyPageCount }, (_, i) => i + 1);
  },

  loadHistoryResult(jobId) { window.location.href = '/result/' + jobId; },
  openResultPage(jobId)    { window.open('/result/' + jobId, '_blank'); },
};
