// ---- Helpers ----

function toast(msg, color = '#eee') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.color = color;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

function fmt(ts) {
  if (!ts) return '—';
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
  return d.toLocaleString('pl-PL');
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function setRefreshLabel(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

// ---- WoW Class Colors ----

const CLASS_COLORS = {
  'Death Knight':  '#C41E3A',
  'Demon Hunter':  '#A330C9',
  'Druid':         '#FF7C0A',
  'Evoker':        '#33937F',
  'Hunter':        '#AAD372',
  'Mage':          '#3FC7EB',
  'Monk':          '#00FF98',
  'Paladin':       '#F48CBA',
  'Priest':        '#FFFFFF',
  'Rogue':         '#FFF468',
  'Shaman':        '#0070DD',
  'Warlock':       '#8788EE',
  'Warrior':       '#C69B3A',
};

const PLOTLY_LAYOUT_BASE = {
  paper_bgcolor: 'transparent',
  plot_bgcolor:  'transparent',
  font:          { color: '#aaa', size: 11 },
  margin:        { t: 10, r: 10, b: 40, l: 40 },
  xaxis: { gridcolor: '#222', linecolor: '#333', tickcolor: '#444', type: 'linear' },
  yaxis: { gridcolor: '#222', linecolor: '#333', tickcolor: '#444', rangemode: 'tozero' },
  showlegend: false,
};

const PLOTLY_CONFIG = { displayModeBar: false, responsive: true };
