// The kit's interface languages in the browser (ADR-0027): English, Italian, Spanish, French, German
// and Simplified Chinese (zh-Hans).
//
// - The catalogs are static files (static/i18n/<locale>.js, made from the .json catalogs by
//   tools/build_i18n.py), loaded by the page before this script, so they work offline.
// - PRG32I18n.t(key, values) gives the text of a key in the page's language, with {name} filled
//   in; a key ending in .one/.other is a plural pair chosen by values.count. A missing key falls
//   back to English, then to the key itself.
// - Pages drawn by the server are already translated; elements with data-i18n="key" (and
//   data-i18n-attr="title:key;aria-label:key") are filled in here, for the static offline pages.
// - The language menu (data-locale-choice) stores the choice in the prg32_locale cookie and in
//   localStorage, saves unsaved IDE work, and reloads the page. The language never changes a
//   saved project or the code made from it.
window.PRG32I18n = (function () {
  'use strict';
  const LOCALES = ['en', 'it', 'es', 'fr', 'de', 'zh-Hans'];

  // The kit's locale for one language tag, as i18n.locale_of does on the server: en-GB -> en,
  // zh / zh-CN / zh-Hans-* -> zh-Hans; Traditional Chinese (zh-Hant, zh-TW, zh-HK, zh-MO) -> none.
  function localeOf(tag) {
    const code = String(tag || '').trim().replace(/_/g, '-').toLowerCase();
    const starts = prefixes => prefixes.some(prefix => code === prefix || code.startsWith(prefix + '-'));
    if (code.startsWith('zh')) {
      if (starts(['zh-hant', 'zh-tw', 'zh-hk', 'zh-mo'])) return null;
      return starts(['zh', 'zh-hans', 'zh-cn', 'zh-sg', 'zh-my']) ? 'zh-Hans' : null;
    }
    const base = code.split('-')[0];
    return LOCALES.includes(base) ? base : null;
  }
  const COOKIE = 'prg32_locale';
  // The names of Blockly's own language packs (static/vendor/blockly/11.2.1/msg/, i18n.BLOCKLY_PACKS).
  const BLOCKLY_PACKS = { it: 'it', es: 'es', fr: 'fr', de: 'de', 'zh-Hans': 'zh-hans' };
  const STORE = 'prg32-kit-locale';
  const catalogs = window.PRG32I18nCatalogs || (window.PRG32I18nCatalogs = {});

  function chosen() {
    const cookie = (document.cookie.match(/(?:^|;\s*)prg32_locale=([A-Za-z-]{2,7})/) || [])[1];
    if (LOCALES.includes(cookie)) return cookie;
    try { const kept = localStorage.getItem(STORE); if (LOCALES.includes(kept)) return kept; } catch (_) { /* private window */ }
    const browser = (navigator.languages || [navigator.language || 'en']).map(localeOf);
    return browser.find(code => code) || 'en';
  }

  // The server writes the page's language into <html lang>; a static page has none of its own.
  const htmlLang = document.documentElement.getAttribute('lang') || '';
  const serverDrawn = document.documentElement.hasAttribute('data-i18n-server');
  let locale = serverDrawn && LOCALES.includes(htmlLang) ? htmlLang : chosen();

  // Chinese has no plural forms; French counts 0 as one.
  function pluralForm(count) {
    if (locale === 'zh-Hans') return 'other';
    return count === 1 || (locale === 'fr' && count === 0) ? 'one' : 'other';
  }

  function t(key, values) {
    const vals = values || {};
    const mine = catalogs[locale] || {};
    const english = catalogs.en || {};
    let wanted = key;
    if (typeof vals.count === 'number') {
      const form = key + '.' + pluralForm(vals.count);
      if (form in mine || form in english) wanted = form;
    }
    const text = mine[wanted] ?? english[wanted] ?? key;
    return String(text).replace(/\{([a-z_][a-z0-9_]*)\}/g, (all, name) => (name in vals ? String(vals[name]) : all));
  }

  // Fill in data-i18n elements under root (the static pages, and parts built from templates).
  function apply(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.getAttribute('data-i18n')); });
    scope.querySelectorAll('[data-i18n-attr]').forEach(el => {
      for (const pair of el.getAttribute('data-i18n-attr').split(';')) {
        const [attr, key] = pair.split(':').map(part => part.trim());
        if (attr && key) el.setAttribute(attr, t(key));
      }
    });
  }

  // A static page (offline.html): load the chosen language's catalog, then translate.
  function loadCatalog(code) {
    if (catalogs[code]) return Promise.resolve();
    return new Promise(resolve => {
      const script = document.createElement('script');
      script.src = '/static/i18n/' + code + '.js';
      script.onload = resolve;
      script.onerror = resolve;   // English stays
      document.head.appendChild(script);
    });
  }

  function remember(code) {
    document.cookie = `${COOKIE}=${code}; path=/; max-age=31536000; SameSite=Lax`
      + (location.protocol === 'https:' ? '; Secure' : '');
    try { localStorage.setItem(STORE, code); } catch (_) { /* private window */ }
  }

  function setLocale(code) {
    if (!LOCALES.includes(code) || code === locale) return Promise.resolve();
    remember(code);
    // Unsaved work in the IDE is saved first, so changing the language never loses an edit.
    const ide = window.PRG32Ide;
    const saving = ide && ide.dirty && !ide.autosavePaused ? ide.save({ quiet: true }).catch(() => {}) : Promise.resolve();
    return saving.then(() => {
      if (serverDrawn) { window.location.reload(); return; }
      locale = code;
      return loadCatalog(code).then(() => { document.documentElement.setAttribute('lang', code); apply(); });
    });
  }

  function init() {
    document.querySelectorAll('[data-locale-choice]').forEach(select => {
      select.value = locale;
      select.addEventListener('change', () => setLocale(select.value));
    });
    if (!serverDrawn) {
      loadCatalog(locale).then(() => { document.documentElement.setAttribute('lang', locale); apply(); });
      // Blockly reads its menu texts when a menu opens, so the pack may arrive after the workspace.
      const pack = BLOCKLY_PACKS[locale];
      if (pack && window.Blockly && !window.define) {
        const script = document.createElement('script');
        script.src = '/static/vendor/blockly/11.2.1/msg/' + pack + '.js';
        document.head.appendChild(script);
      }
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();

  // tr(key, english, values): the message of a script. The English text stays in the script (so it
  // reads like plain code, and works where no catalog is loaded); tests/test_i18n.py checks that
  // it equals the catalog's English.
  // A count picks the plural form: key.one / key.other in the catalogs (English included).
  function text(key, english, values) {
    let wanted = key;
    if (values && typeof values.count === 'number') {
      const form = key + '.' + pluralForm(values.count);
      if (form in (catalogs[locale] || {}) || form in (catalogs.en || {})) wanted = form;
    }
    const mine = locale === 'en' ? null : catalogs[locale];
    const english_ = wanted === key ? english : ((catalogs.en || {})[wanted] ?? english);
    const found = mine && wanted in mine ? mine[wanted] : english_;
    return fill(found, values);
  }
  function fill(message, values) {
    return String(message).replace(/\{([a-z_][a-z0-9_]*)\}/g, (all, name) => (values && name in values ? String(values[name]) : all));
  }
  window.tr = text;

  return { t, text, apply, setLocale, LOCALES, get locale() { return locale; },
    // Numbers and dates written the reader's way (never inside saved data or generated code).
    number: value => new Intl.NumberFormat(locale).format(value),
    dateTime: value => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(value) };
})();
