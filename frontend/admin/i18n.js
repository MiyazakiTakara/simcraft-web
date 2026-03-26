/**
 * admin/i18n.js — lekki system tłumaczeń dla panelu admina
 * Nie wymaga Alpine. Używa data-i18n="key" w HTML.
 *
 * Użycie w HTML:  <span data-i18n="admin.tabs.dashboard"></span>
 * Użycie w JS:    adminT('admin.tabs.dashboard')
 */

const ADMIN_SUPPORTED_LANGS = ['pl', 'en'];
const ADMIN_DEFAULT_LANG    = 'en';
const ADMIN_STORAGE_KEY     = 'simcraft_lang';

let _adminTranslations = {};
let _adminFallback     = {};
let _adminLang         = ADMIN_DEFAULT_LANG;

function _adminDetectLang() {
  const saved = localStorage.getItem(ADMIN_STORAGE_KEY);
  if (saved && ADMIN_SUPPORTED_LANGS.includes(saved)) return saved;
  const browser = (navigator.language || '').slice(0, 2).toLowerCase();
  return ADMIN_SUPPORTED_LANGS.includes(browser) ? browser : ADMIN_DEFAULT_LANG;
}

async function _adminLoadLocale(lang) {
  try {
    const res = await fetch(`/locales/${lang}.json?v=2`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.warn(`[admin i18n] Failed to load locale '${lang}':`, e);
    return {};
  }
}

function _adminGetKey(obj, key) {
  return key.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), obj);
}

// Publiczne API
function adminT(key, params) {
  const val = _adminGetKey(_adminTranslations, key)
           ?? _adminGetKey(_adminFallback, key)
           ?? key;
  if (!params || typeof val !== 'string') return val;
  return val.replace(/\{\{\s*(\w+)\s*\}\}/g, (_, k) => params[k] ?? '');
}

function adminApplyTranslations() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const val = adminT(key);
    if (val && val !== key) el.textContent = val;
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.dataset.i18nPlaceholder;
    const val = adminT(key);
    if (val && val !== key) el.placeholder = val;
  });
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.dataset.i18nTitle;
    const val = adminT(key);
    if (val && val !== key) el.title = val;
  });
  document.querySelectorAll('[data-i18n-tooltip]').forEach(el => {
    const key = el.dataset.i18nTooltip;
    const val = adminT(key);
    if (val && val !== key) el.dataset.tooltip = val;
  });
  // Zaktualizuj aktywny przycisk języka
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.lang === _adminLang);
  });
}

async function adminSetLang(lang) {
  if (!ADMIN_SUPPORTED_LANGS.includes(lang)) return;
  localStorage.setItem(ADMIN_STORAGE_KEY, lang);
  _adminLang         = lang;
  _adminTranslations = await _adminLoadLocale(lang);
  if (lang !== ADMIN_DEFAULT_LANG) {
    _adminFallback = await _adminLoadLocale(ADMIN_DEFAULT_LANG);
  } else {
    _adminFallback = _adminTranslations;
  }
  document.documentElement.lang = lang;
  adminApplyTranslations();
}

async function initAdminI18n() {
  _adminLang         = _adminDetectLang();
  _adminTranslations = await _adminLoadLocale(_adminLang);
  _adminFallback     = _adminLang !== ADMIN_DEFAULT_LANG
    ? await _adminLoadLocale(ADMIN_DEFAULT_LANG)
    : _adminTranslations;
  document.documentElement.lang = _adminLang;
  adminApplyTranslations();
}
