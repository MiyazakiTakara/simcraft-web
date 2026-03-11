// Historia symulacji i newsy
const HistoryMixin = {
  async loadHistory() {
    try {
      const data = await API.getHistory(this.sessionId, this.historyPage, this.historyPerPage);
      this.history = data.items || [];
    } catch (e) { console.error("Failed to load history", e); }
  },

  async loadPublicHistory() {
    try {
      const data = await API.getPublicHistory(this.historyPage, this.historyPerPage);
      this.history = data.items || [];
    } catch (e) { console.error("Failed to load public history", e); }
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

  get newsPageCount() {
    return Math.max(1, Math.ceil(this.news.length / this.newsPerPage));
  },
  get pagedNews() {
    const start = (this.newsPage - 1) * this.newsPerPage;
    return this.news.slice(start, start + this.newsPerPage);
  },
  newsPages() {
    return Array.from({ length: this.newsPageCount }, (_, i) => i + 1);
  },

  get sortedHistory() { return [...this.history]; },
  get historyPageCount() { return 1; },
  get pagedHistory() { return this.sortedHistory.slice(0, 5); },
  historyPages() {
    return Array.from({ length: this.historyPageCount }, (_, i) => i + 1);
  },

  loadHistoryResult(jobId) { window.location.href = '/result/' + jobId; },
  openResultPage(jobId)    { window.open('/result/' + jobId, '_blank'); },
};
