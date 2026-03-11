/**
 * i18n.js — system tłumaczeń SimCraft Web
 *
 * Użycie w HTML:       x-text="$store.i18n.t('key')"
 * Użycie w JS:         Alpine.store('i18n').t('key')
 * Zmiana języka:       Alpine.store('i18n').setLang('en')
 * Interpolacja:        t('key', { name: 'Thrall' })  →  "Hello, Thrall!"
 */

const SUPPORTED_LANGS = ['pl', 'en'];
const DEFAULT_LANG    = 'en';
const STORAGE_KEY     = 'simcraft_lang';

// Wykrywa język przeglądarki, fallback na DEFAULT_LANG
function detectLang() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved && SUPPORTED_LANGS.includes(saved)) return saved;

  const browser = (navigator.language || navigator.userLanguage || '').slice(0, 2).toLowerCase();
  return SUPPORTED_LANGS.includes(browser) ? browser : DEFAULT_LANG;
}

// Ładuje plik locales/{lang}.json
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

// Interpoluje {{ key }} w stringu
function interpolate(str, params) {
  if (!params || typeof str !== 'string') return str;
  return str.replace(/\{\{\s*(\w+)\s*\}\}/g, (_, key) => params[key] ?? '');
}

// Pobiera zagnieżdżony klucz: 'header.login' → translations.header.login
function getKey(obj, key) {
  return key.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), obj);
}

// Inicjalizacja Alpine store — wywołaj przed Alpine.start()
async function initI18n() {
  const lang         = detectLang();
  const translations = await loadLocale(lang);

  // Fallback translations (EN) — ładowane gdy brakuje klucza w aktywnym języku
  const fallback = lang !== DEFAULT_LANG ? await loadLocale(DEFAULT_LANG) : translations;

  document.documentElement.lang = lang;

  Alpine.store('i18n', {
    lang,
    translations,
    fallback,

    t(key, params) {
      const val = getKey(this.translations, key)
               ?? getKey(this.fallback, key)
               ?? key;  // ostatni fallback: zwróć klucz
      return interpolate(val, params);
    },

    async setLang(newLang) {
      if (!SUPPORTED_LANGS.includes(newLang)) return;
      localStorage.setItem(STORAGE_KEY, newLang);
      this.translations         = await loadLocale(newLang);
      if (newLang !== DEFAULT_LANG) {
        this.fallback = await loadLocale(DEFAULT_LANG);
      } else {
        this.fallback = this.translations;
      }
      this.lang                  = newLang;
      document.documentElement.lang = newLang;
    },
  });
}

// Uruchom przed Alpine — blokuje inicjalizację Alpine do czasu załadowania tłumaczeń
document.addEventListener('alpine:init', () => {
  // alpine:init odpala się przed Alpine.start(), store musi być zainicjowany
  // ale initI18n jest async więc używamy synchronicznego pustego store jako placeholder
  Alpine.store('i18n', {
    lang: detectLang(),
    translations: {},
    fallback: {},
    t(key) { return key; },
    setLang() {},
  });
});

// Załaduj tłumaczenia i zaktualizuj store gdy DOM gotowy
document.addEventListener('DOMContentLoaded', async () => {
  const lang         = detectLang();
  const translations = await loadLocale(lang);
  const fallback     = lang !== DEFAULT_LANG ? await loadLocale(DEFAULT_LANG) : translations;

  document.documentElement.lang = lang;

  const store = Alpine.store('i18n');
  store.lang         = lang;
  store.translations = translations;
  store.fallback     = fallback;
  store.t = function(key, params) {
    const val = getKey(this.translations, key)
             ?? getKey(this.fallback, key)
             ?? key;
    return interpolate(val, params);
  };
  store.setLang = async function(newLang) {
    if (!SUPPORTED_LANGS.includes(newLang)) return;
    localStorage.setItem(STORAGE_KEY, newLang);
    this.translations = await loadLocale(newLang);
    this.fallback     = newLang !== DEFAULT_LANG ? await loadLocale(DEFAULT_LANG) : this.translations;
    this.lang         = newLang;
    document.documentElement.lang = newLang;
  };
});
