async function loadTasks() {
  const container = document.getElementById('tasks-list');
  container.innerHTML = `<p class="empty">${adminT('common.loading')}</p>`;
  const res = await fetch('/admin/api/tasks');
  if (!res.ok) { container.innerHTML = `<p class="empty">${adminT('admin.toast.error_generic')}</p>`; return; }
  const data = await res.json();
  markRefreshed('tasks');
  if (!data.active_tasks.length) { container.innerHTML = `<p class="empty">${adminT('admin.tasks.empty')}</p>`; return; }
  container.innerHTML = `<div class="news-list">${data.active_tasks.map(t => `
    <div class="sim-item">
      <div>
        <div style="font-weight:600">${escHtml(t.job_id)}</div>
        <div style="font-size:0.8rem;color:#888">Status: ${t.status} · ${fmt(t.started_at)}</div>
      </div>
      <button class="danger" onclick="cancelTask('${t.job_id}')">${adminT('admin.tasks.cancel')}</button>
    </div>
  `).join('')}</div>`;
}

async function cancelTask(jobId) {
  if (!confirm(adminT('admin.confirm.cancel_task') + ` ${jobId}?`)) return;
  const res = await fetch(`/admin/api/tasks/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
  if (res.ok) { toast(adminT('admin.toast.task_cancelled'), '#4c4'); loadTasks(); }
  else toast(adminT('admin.toast.error_generic'), '#e55');
}
