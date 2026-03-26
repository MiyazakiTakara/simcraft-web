// Pomocnicze funkcje — brak zależności od stanu Alpine
const Utils = {
  STAT_LABELS: {
    strength:    'Strength',
    agility:     'Agility',
    stamina:     'Stamina',
    intellect:   'Intellect',
    crit:        'Critical Strike',
    haste:       'Haste',
    mastery:     'Mastery',
    versatility: 'Versatility',
  },

  CLASS_COLORS: {
    'Death Knight':  '#C41E3A',
    'Demon Hunter':  '#A330C9',
    'Druid':         '#FF7C0A',
    'Evoker':        '#33937F',
    'Hunter':        '#AAD372',
    'Mage':          '#3FC7EB',
    'Monk':          '#00FF98',
    'Paladin':       '#F48CBA',
    'Priest':        '#CCCCCC',
    'Rogue':         '#FFF468',
    'Shaman':        '#0070DD',
    'Warlock':       '#8788EE',
    'Warrior':       '#C69B3A',
  },

  formatTime(timestamp) {
    if (!timestamp && timestamp !== 0) return '\u2014';
    let date;
    if (typeof timestamp === 'string') {
      date = new Date(timestamp.endsWith('Z') || timestamp.includes('+') ? timestamp : timestamp + 'Z');
    } else if (typeof timestamp === 'number') {
      date = new Date(timestamp < 1e10 ? timestamp * 1000 : timestamp);
    } else {
      return '\u2014';
    }
    if (isNaN(date.getTime())) return '\u2014';
    const now  = new Date();
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60)    return 'teraz';
    if (diff < 3600)  return Math.floor(diff / 60)   + 'm temu';
    if (diff < 86400) return Math.floor(diff / 3600)  + 'h temu';
    return date.toLocaleDateString('pl-PL');
  },

  formatDps(v) {
    if (!v && v !== 0) return '\u2014';
    if (v >= 1_000_000) return (v / 1_000_000).toFixed(2) + 'M';
    if (v >= 1_000)     return (v / 1_000).toFixed(1)     + 'k';
    return String(Math.round(v));
  },

  formatDmg(v) {
    if (!v && v !== 0) return '\u2014';
    if (v >= 1_000_000) return (v / 1_000_000).toFixed(2) + 'M';
    if (v >= 1_000)     return (v / 1_000).toFixed(0)     + 'k';
    return String(Math.round(v));
  },

  pctBarWidth(val, spells, key) {
    const max = Math.max(...spells.map(s => s[key] ?? 0));
    return max > 0 ? Math.round((val / max) * 100) + '%' : '0%';
  },

  formatStatName(key)      { return Utils.STAT_LABELS[key] || key; },
  formatStatValue(key, val) {
    if (typeof val === 'number') return val.toLocaleString();
    return val;
  },

  getShareUrl(jobId)       { return window.location.origin + '/result/' + jobId; },

  copyToClipboard(text, jobId, setState) {
    navigator.clipboard.writeText(text)
      .then(() => { setState(jobId || true); setTimeout(() => setState(null), 2000); })
      .catch(() => {});
  },

  classColor(className)    { return Utils.CLASS_COLORS[className] || '#aaa'; },

  classTextColor(className) {
    const light = ['Hunter', 'Mage', 'Monk', 'Rogue', 'Priest'];
    return light.includes(className) ? '#111' : '#fff';
  },

  armoryUrl(realmSlug, name) {
    if (!realmSlug || !name) return null;
    return `https://worldofwarcraft.blizzard.com/en-gb/character/eu/${realmSlug}/${name.toLowerCase()}`;
  },

  getItemQualityColor(quality) {
    const colors = {
      'Poor': '#9d9d9d', 'Common': '#ffffff', 'Uncommon': '#1eff00',
      'Rare': '#0070dd', 'Epic':   '#a335ee', 'Legendary': '#ff8000',
      'Artifact': '#e6cc80', 'Heirloom': '#00ccff',
    };
    return colors[quality] || '#fff';
  },
};

// Eksport globalny — wymagany dla stron bez modułów ES
window.Utils = Utils;
