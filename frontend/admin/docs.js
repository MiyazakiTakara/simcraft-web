// =====================
// ADMIN DOCS — marked.js + highlight.js viewer
// =====================

let _docsFiles    = [];
let _docsActive   = null;
let _docsLang     = 'pl';
let _docsRendered = {};
let _docsQuery    = '';
let _docsSearchTimer = null;

function _docsGetLang() {
  if (typeof adminGetLang === 'function') return adminGetLang() || 'pl';
  return localStorage.getItem('simcraft_lang') || 'pl';
}

// Hook na globalny adminSetLang — przeładuj docs jeśli zakładka aktywna
(function _hookAdminSetLang() {
  const _orig = window.adminSetLang;
  if (typeof _orig !== 'function') {
    document.addEventListener('DOMContentLoaded', _hookAdminSetLang);
    return;
  }
  window.adminSetLang = async function (lang) {
    await _orig(lang);
    const newLang = _docsGetLang();
    if (newLang !== _docsLang) {
      _docsLang     = newLang;
      _docsActive   = null;
      _docsRendered = {};
      _docsQuery    = '';
      const panel = document.getElementById('tab-docs');
      if (panel && panel.classList.contains('active')) loadDocs();
    }
  };
})();

async function loadDocs() {
  const wrap    = document.getElementById('docs-file-list');
  const content = document.getElementById('docs-content');
  if (!wrap) return;

  const lang = _docsGetLang();
  if (lang !== _docsLang) {
    _docsLang     = lang;
    _docsActive   = null;
    _docsRendered = {};
    _docsQuery    = '';
  }

  wrap.innerHTML = '<div class="docs-loading">⏳ Ładowanie listy...</div>';
  content.innerHTML = '<div class="docs-welcome"><span class="docs-welcome-icon">📚</span><p>Wybierz plik z listy po lewej.</p></div>';

  try {
    const res = await fetch(`/admin/api/docs?lang=${_docsLang}`);
    if (!res.ok) throw new Error(res.statusText);
    _docsFiles = await res.json();
  } catch (e) {
    wrap.innerHTML = `<div class="docs-error">❌ Błąd: ${e.message}</div>`;
    return;
  }

  if (!_docsFiles.length) {
    wrap.innerHTML = `<div class="docs-empty">Brak plików .md w docs/${_docsLang}/</div>`;
    return;
  }

  _renderFileList(wrap);
  if (typeof markRefreshed === 'function') markRefreshed('docs');
}

// ── Sidebar ──────────────────────────────────────────────

function _renderFileList(wrap) {
  wrap.innerHTML = '';

  const searchWrap = document.createElement('div');
  searchWrap.style.cssText = 'margin-bottom:0.5rem';
  const input = document.createElement('input');
  input.type        = 'text';
  input.className   = 'docs-search';
  input.placeholder = '🔍 Szukaj...';
  input.value       = _docsQuery;
  input.oninput     = (e) => {
    _docsQuery = e.target.value;
    clearTimeout(_docsSearchTimer);
    if (_docsQuery.length === 0) {
      _renderFileButtons(wrap, searchWrap);
    } else if (_docsQuery.length >= 2) {
      _renderFileButtons(wrap, searchWrap); // natychmiastowy filtr po nazwie
      _docsSearchTimer = setTimeout(() => _runFulltextSearch(wrap, searchWrap), 400);
    } else {
      _renderFileButtons(wrap, searchWrap);
    }
  };
  searchWrap.appendChild(input);
  wrap.appendChild(searchWrap);

  _renderFileButtons(wrap, searchWrap);
}

function _clearResults(wrap, searchWrap) {
  Array.from(wrap.children).forEach(el => {
    if (el !== searchWrap) el.remove();
  });
}

function _renderFileButtons(wrap, searchWrap) {
  _clearResults(wrap, searchWrap);
  const q = _docsQuery.toLowerCase();
  const filtered = q
    ? _docsFiles.filter(f => f.name.toLowerCase().replace('.md', '').includes(q))
    : _docsFiles;

  if (!filtered.length && !q) {
    _appendEmpty(wrap, 'Brak plików.');
    return;
  }
  if (!filtered.length) return; // fulltext może dopiero nadejść

  filtered.forEach(f => _appendFileBtn(wrap, f.name));
}

function _appendFileBtn(wrap, filename) {
  const btn = document.createElement('button');
  btn.className = 'docs-file-btn' + (filename === _docsActive ? ' active' : '');
  btn.innerHTML = `<span class="docs-file-icon">📄</span><span class="docs-file-name">${filename.replace('.md', '')}</span>`;
  btn.title     = filename;
  btn.onclick   = () => _openDoc(filename);
  wrap.appendChild(btn);
  return btn;
}

function _appendEmpty(wrap, msg) {
  const p = document.createElement('p');
  p.className   = 'docs-empty';
  p.textContent = msg;
  wrap.appendChild(p);
}

// ── Fulltext search ───────────────────────────────────────

async function _runFulltextSearch(wrap, searchWrap) {
  // Pokaż loader pod już wyrenderowanymi wynikami nazw
  const loader = document.createElement('div');
  loader.className   = 'docs-loading';
  loader.textContent = '⏳';
  loader.id          = 'docs-ft-loader';
  wrap.appendChild(loader);

  let results;
  try {
    const res = await fetch(`/admin/api/docs/search?q=${encodeURIComponent(_docsQuery)}&lang=${_docsLang}`);
    if (!res.ok) throw new Error(res.statusText);
    results = await res.json();
  } catch (e) {
    document.getElementById('docs-ft-loader')?.remove();
    return;
  }

  // Anuluj jeśli query się zmieniło w trakcie fetcha
  if (_docsQuery.length < 2) {
    document.getElementById('docs-ft-loader')?.remove();
    return;
  }

  _clearResults(wrap, searchWrap);

  if (!results.length) {
    _appendEmpty(wrap, 'Brak wyników.');
    return;
  }

  const q_lower = _docsQuery.toLowerCase();

  results.forEach(r => {
    // Nagłówek — nazwa pliku (rodzic)
    const header = document.createElement('div');
    header.className = 'docs-search-group';

    const fileBtn = document.createElement('button');
    fileBtn.className = 'docs-file-btn' + (r.file === _docsActive ? ' active' : '');
    fileBtn.innerHTML = `<span class="docs-file-icon">${r.name_match ? '📁' : '📄'}</span><span class="docs-file-name">${r.file.replace('.md', '')}</span>`;
    fileBtn.onclick   = () => _openDoc(r.file);
    header.appendChild(fileBtn);
    wrap.appendChild(header);

    // Dopasowania z treści
    r.matches.forEach(m => {
      const lineBtn = document.createElement('button');
      lineBtn.className = 'docs-match-btn';
      lineBtn.innerHTML = `<span class="docs-match-line">L${m.line}</span><span class="docs-match-text">${_highlightQuery(m.text, q_lower)}</span>`;
      lineBtn.onclick   = () => _openDoc(r.file, m.line);
      wrap.appendChild(lineBtn);
    });
  });
}

function _highlightQuery(text, q) {
  const escaped = _escapeHtml(text);
  const re = new RegExp(_escapeRegex(q), 'gi');
  return escaped.replace(re, match => `<mark class="docs-hl">${match}</mark>`);
}

function _escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ── Otwieranie pliku ─────────────────────────────────────

async function _openDoc(filename, scrollToLine) {
  _docsActive = filename;
  const wrap = document.getElementById('docs-file-list');
  // Odśwież sidebar zachowując query
  _clearResults(wrap, wrap.querySelector('.docs-search')?.parentElement);
  if (_docsQuery.length >= 2) {
    _renderFileButtons(wrap, wrap.querySelector('.docs-search')?.parentElement);
    _runFulltextSearch(wrap, wrap.querySelector('.docs-search')?.parentElement);
  } else {
    _renderFileButtons(wrap, wrap.querySelector('.docs-search')?.parentElement);
  }

  const content  = document.getElementById('docs-content');
  const cacheKey = `${_docsLang}:${filename}`;

  if (_docsRendered[cacheKey]) {
    content.innerHTML = _docsRendered[cacheKey];
    _highlightCode(content);
    if (scrollToLine) _scrollToLine(content, scrollToLine);
    return;
  }

  content.innerHTML = '<div class="docs-loading">⏳ Ładowanie...</div>';

  try {
    const res = await fetch(`/admin/api/docs/${encodeURIComponent(filename)}?lang=${_docsLang}`);
    if (!res.ok) throw new Error(res.statusText);
    const raw  = await res.text();
    const html = _renderMarkdown(raw, filename);
    _docsRendered[cacheKey] = html;
    content.innerHTML = html;
    _highlightCode(content);
    if (scrollToLine) _scrollToLine(content, scrollToLine);
  } catch (e) {
    content.innerHTML = `<div class="docs-error">❌ Błąd ładowania: ${e.message}</div>`;
  }
}

function _scrollToLine(container, line) {
  const target = container.querySelector(`[data-line="${line}"]`);
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    target.classList.add('docs-line-highlight');
    setTimeout(() => target.classList.remove('docs-line-highlight'), 2500);
  }
}

// ── Rendering ────────────────────────────────────────────

function _renderMarkdown(raw, filename) {
  if (typeof marked === 'undefined') {
    return `<pre style="white-space:pre-wrap;font-family:monospace">${_escapeHtml(raw)}</pre>`;
  }
  // Owijamy każdą linię w span z data-line aby scroll do linii działał
  const lines = raw.split('\n');
  const annotated = lines.map((l, i) =>
    `<span data-line="${i + 1}" style="display:block;min-height:1px">${l}</span>`
  ).join('\n');
  marked.setOptions({ breaks: true, gfm: true });
  return `<div class="docs-md">${marked.parse(annotated)}</div>`;
}

function _highlightCode(container) {
  if (typeof hljs === 'undefined') return;
  container.querySelectorAll('pre code').forEach(block => hljs.highlightElement(block));
}

function _escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Kopiowanie ───────────────────────────────────────────

function docsCopyRaw() {
  if (!_docsActive) return;
  fetch(`/admin/api/docs/${encodeURIComponent(_docsActive)}?lang=${_docsLang}`)
    .then(r => r.text())
    .then(raw => {
      navigator.clipboard.writeText(raw);
      const btn = document.getElementById('docs-copy-btn');
      if (btn) { btn.textContent = '✅ Skopiowano!'; setTimeout(() => { btn.textContent = '📋 Kopiuj Markdown'; }, 2000); }
    })
    .catch(() => {});
}
