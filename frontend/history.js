// Historia symulacji i newsy
const HistoryMixin = {
  async loadHistory() {
    this.loadingHistory = true;
    this.historyLoading = true;
    try {
      const data = await API.getHistory(this.sessionId, this.historyPage, this.historyPerPage);
      this.history = data.results || [];
    } catch (e) { console.error("Failed to load history", e); }
    finally {
      this.loadingHistory = false;
      this.historyLoading = false;
    }
  },

  async loadPublicHistory() {
    this.loadingHistory = true;
    this.historyLoading = true;
    try {
      const data = await API.getPublicHistory(this.historyPage, this.historyPerPage);
      this.history = data.results || [];
    } catch (e) { console.error("Failed to load public history", e); }
    finally {
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
