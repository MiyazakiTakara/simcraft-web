async function loadNews() {
  const res = await fetch('/admin/api/news');
  if (res.status === 302 || res.redirected) { window.location = '/admin/login'; return; }
  const news = await res.json();
  const list = document.getElementById('news-list');
  if (!news.length) { list.innerHTML = `<p class="empty">${adminT('admin.news.empty')}</p>`; return; }
  list.innerHTML = news.map(n => `
    <div class="news-card" id="card-${n.id}">
      <div class="info">
        <h3>${escHtml(n.title)}
          <span class="badge ${n.published ? 'published' : 'draft'}">
            ${n.published ? adminT('admin.news.badge_published') : adminT('admin.news.badge_draft')}
          </span>
        </h3>
        <p>${escHtml(n.body)}</p>
        <div class="meta">${fmt(n.created_at)}</div>
      </div>
      <div class="actions">
        <button class="danger" onclick="togglePublish(${n.id}, ${n.published})">
          ${n.published ? adminT('admin.news.hide') : adminT('admin.news.publish')}
        </button>
        <button class="danger" onclick="deleteNews(${n.id})">${adminT('admin.news.delete')}</button>
      </div>
    </div>
  `).join('');
}

async function createNews() {
  const title     = document.getElementById('news-title').value.trim();
  const body      = document.getElementById('news-body').value.trim();
  const published = document.getElementById('news-published').checked;
  if (!title || !body) { toast(adminT('admin.toast.news_fill'), '#e88'); return; }
  const res = await fetch('/admin/api/news', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, body, published }),
  });
  if (res.ok) {
    toast(adminT('admin.toast.news_added'), '#4c4');
    document.getElementById('news-title').value = '';
    document.getElementById('news-body').value  = '';
    loadNews();
  } else {
    toast(adminT('admin.toast.error_generic'), '#e55');
  }
}

async function deleteNews(id) {
  const ok = await adminConfirm(
    '🗑️ Usuń news',
    'Czy na pewno chcesz usunąć ten news? Tej operacji nie można cofnąć.',
    'Usuń'
  );
  if (!ok) return;
  const res = await fetch(`/admin/api/news/${id}`, { method: 'DELETE' });
  if (res.ok) { toast(adminT('admin.toast.deleted'), '#aaa'); loadNews(); }
  else toast(adminT('admin.toast.error_generic'), '#e55');
}

async function togglePublish(id, current) {
  const res = await fetch(`/admin/api/news/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ published: !current }),
  });
  if (res.ok) loadNews();
  else toast(adminT('admin.toast.error_generic'), '#e55');
}
