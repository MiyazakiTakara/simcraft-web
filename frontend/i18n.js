/**
 * i18n.js — system tłumaczeń SimCraft Web
 *
 * Strategia ładowania (v3):
 * 1. Fetch tłumaczeń startuje NATYCHMIAST
 * 2. window._i18nReady = Promise który resolvuje się z finalnym store
 * 3. result.html ładuje Alpine BEZ defer, ręcznie woła Alpine.start()
 *    dopiero po await window._i18nReady — Alpine nigdy nie widzi podmiany store
 */

const SUPPORTED_LANGS = ['pl', 'en'];
const DEFAULT_LANG    = 'en';
const STORAGE_KEY     = 'simcraft_lang';

function detectLang() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved && SUPPORTED_LANGS.includes(saved)) return saved;
  const browser = (navigator.language || navigator.userLanguage || '').slice(0, 2).toLowerCase();
  return SUPPORTED_LANGS.includes(browser) ? browser : DEFAULT_LANG;
}

async function loadLocale(lang) {
  try {
    const res = await fetch(`/locales/${lang}.json?v=1`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.warn(`[i18n] Failed to load locale '${lang}':`, e);
    return {};
  }
}

function interpolate(str, params) {
  if (!params || typeof str !== 'string') return str;
  return str.replace(/\{\{\s*(\w+)\s*\}\}/g, (_, key) => params[key] ?? '');
}

function getKey(obj, key) {
  return key.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), obj);
}

function makeStore(lang, translations, fallback) {
  return {
    lang,
    translations,
    fallback,
    t(key, params) {
      const val = getKey(this.translations, key)
               ?? getKey(this.fallback, key)
               ?? key;
      return interpolate(val, params);
    },
    async setLang(newLang) {
      if (!SUPPORTED_LANGS.includes(newLang)) return;
      localStorage.setItem(STORAGE_KEY, newLang);
      const t = await loadLocale(newLang);
      const f = newLang !== DEFAULT_LANG ? await loadLocale(DEFAULT_LANG) : t;
      Alpine.store('i18n', makeStore(newLang, t, f));
      document.documentElement.lang = newLang;
    },
  };
}

// Startuj fetch natychmiast
const _lang = detectLang();

window._i18nReady = (async () => {
  const translations = await loadLocale(_lang);
  const fallback     = _lang !== DEFAULT_LANG ? await loadLocale(DEFAULT_LANG) : translations;
  document.documentElement.lang = _lang;
  return makeStore(_lang, translations, fallback);
})();

// Dla stron ktore nadal uzywaja alpine:init (np. sim.html)
// Rejestrujemy handler ktory ustawi store synchronicznie jesli Alpine
// juz czeka — ale TYLKO jesli strona nie uzywa recznego Alpine.start()
document.addEventListener('alpine:init', () => {
  // Jesli strona uzywa window._alpineManualStart, pomijamy —
  // store zostanie ustawiony przed Alpine.start()
  if (window._alpineManualStart) return;
  // Fallback dla innych stron: ustaw pusty store, potem podmien
  Alpine.store('i18n', makeStore(_lang, {}, {}));
  window._i18nReady.then(store => {
    Alpine.store('i18n', store);
  });
});
