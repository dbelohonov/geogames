// core.js — the language layer shared by the GeoGames games.
//
// No build step and no dependencies: plain ES5 that exposes window.GeoI18N.
// Czech is currently the only language shipped, so in practice this layer
// resolves to "cs" and rewrites nothing. It is kept as the seam where another
// language would be added: LANGS below is the single switch, and every string
// a new language needs is already looked up by key.
//
// Language resolution, first hit wins:
//   1. ?lang=… on the URL          (also remembered),
//   2. localStorage["geogames.lang"] (kept across visits),
//   3. "cs"                        (the default).
// An unknown code — a stale ?lang=de or localStorage entry left over from
// before German was dropped — falls through to the default, so old links and
// returning visitors still get a working Czech page.
//
// Pages ship their Czech text inline and are only rewritten when another
// language is active, so a missing dictionary, a missing key or a blocked
// localStorage all degrade to the Czech original rather than to blank text or
// to raw keys. Keys that do not exist in the active language are left alone.
//
// Dictionaries register themselves: GeoI18N.register({ cs: {…} }).
// ../i18n/common.js holds the strings the games share; a game's own
// js/i18n.js holds its specifics and may override any common key.
//
// Lookup is by flat dotted key and "{name}" placeholders in a value are filled
// from the params object. Values are rendered as HTML by the same callers that
// always used innerHTML, so params must be trusted data (map names from
// js/data.js), never user input.
(function () {
  "use strict";

  var DEFAULT_LANG = "cs";
  var LANGS = ["cs"];
  var STORE_KEY = "geogames.lang";

  // one table per language; LANGS is the single place a new language is added
  var dicts = {};
  LANGS.forEach(function (code) { dicts[code] = {}; });
  var lang = DEFAULT_LANG;
  var booted = false;
  var listeners = [];
  var api = null;                // window.GeoI18N, once published below

  function isKnown(code) { return LANGS.indexOf(code) !== -1; }
  function has(key) {
    return Object.prototype.hasOwnProperty.call(dicts[lang], key);
  }

  // localStorage throws when it is blocked (private mode, some file:// setups).
  function readStore() {
    try { return localStorage.getItem(STORE_KEY); } catch (e) { return null; }
  }
  function writeStore(code) {
    try { localStorage.setItem(STORE_KEY, code); } catch (e) {}
  }

  // Parsed by hand so it also works from file:// URLs, where the hub page may
  // well be opened by double-clicking it.
  function fromQuery() {
    var m = /[?&]lang=([^&#]*)/.exec(window.location.search || "");
    if (!m) return null;
    try { return decodeURIComponent(m[1]); } catch (e) { return m[1]; }
  }

  function resolve() {
    var q = fromQuery();
    if (isKnown(q)) { writeStore(q); return q; }  // an explicit choice sticks
    var stored = readStore();
    return isKnown(stored) ? stored : DEFAULT_LANG;
  }

  function merge(code, table) {
    if (!table) return;
    Object.keys(table).forEach(function (key) { dicts[code][key] = table[key]; });
  }

  // Register one dictionary ({ cs: {…} }). Later registrations win,
  // which is how a game overrides a common string. Safe to call before or
  // after boot — a late arrival is applied straight away.
  function register(dict) {
    LANGS.forEach(function (code) { merge(code, dict[code]); });
    if (booted) refresh();
  }

  // A "{placeholder}" takes its value from params; if params does not supply
  // one, the placeholder name is itself looked up as a key. That is what lets
  // a shared template ("Klikni na {noun.clickTarget}:") pick up each game's
  // own grammatical form without the caller passing it. Placeholders left
  // unresolved are kept verbatim rather than blanked.
  function fill(value, params) {
    return value.replace(/\{([\w.]+)\}/g, function (all, key) {
      if (params && Object.prototype.hasOwnProperty.call(params, key)) {
        return String(params[key]);
      }
      if (has(key)) return dicts[lang][key];
      return all;
    });
  }

  // t(key, params, fallback) — params fill {placeholders}; fallback is used
  // when the key is unknown (a raw value such as a Czech category word from
  // js/data.js). Without a fallback the key itself is returned, so a typo is
  // visible in the UI instead of rendering as "undefined".
  function t(key, params, fallback) {
    if (!has(key)) {
      if (fallback == null) return key;
      return fill(String(fallback), params);
    }
    var value = dicts[lang][key];
    // a non-string value is a plural-form table — that one belongs to plural()
    return typeof value === "string" ? fill(value, params) : value;
  }

  // Language-aware plural for the few places that count things. The value
  // under key is an array of forms; Czech uses [1, 2–4, 5+]. {n} is filled in
  // automatically. A new language adds its own index rule here.
  function plural(key, n, params) {
    var forms = dicts[lang][key];
    if (!forms || !forms.length) return String(n);
    var idx = (n === 1) ? 0 : ((n >= 2 && n <= 4) ? 1 : 2);   // Czech
    var p = {};
    if (params) Object.keys(params).forEach(function (k) { p[k] = params[k]; });
    p.n = n;
    return fill(forms[Math.min(idx, forms.length - 1)], p);
  }

  // ---- Static translation ------------------------------------------------
  // Elements opt in with data-i18n (textContent), data-i18n-html (innerHTML),
  // data-i18n-placeholder or data-i18n-title. Dynamic text — quiz prompts,
  // feedback, tooltips — is translated by the game itself via t().
  var BINDINGS = [
    ["data-i18n", function (el, s) { el.textContent = s; }],
    ["data-i18n-html", function (el, s) { el.innerHTML = s; }],
    ["data-i18n-placeholder", function (el, s) { el.setAttribute("placeholder", s); }],
    ["data-i18n-title", function (el, s) { el.setAttribute("title", s); }],
  ];

  function apply(root) {
    var scope = root || document;
    BINDINGS.forEach(function (binding) {
      var attr = binding[0], set = binding[1];
      var els = scope.querySelectorAll
        ? scope.querySelectorAll("[" + attr + "]")
        : [];
      Array.prototype.forEach.call(els, function (el) {
        var key = el.getAttribute(attr);
        if (has(key)) set(el, t(key));
      });
    });
  }

  function applyDoc() {
    document.documentElement.setAttribute("lang", lang);
    if (has("page.title")) document.title = t("page.title");
  }

  function notify() {
    listeners.forEach(function (fn) { fn(lang); });
  }

  function refresh() {
    if (api) api.lang = lang;    // keep the published property truthful
    applyDoc();
    apply();
    notify();
  }

  function boot() {
    booted = true;
    refresh();
  }

  // Switch language: persist, re-translate the page in place, tell listeners
  // (the hub page uses this to refresh its game links and its active pill).
  function setLang(code) {
    if (!isKnown(code)) return lang;
    lang = code;
    writeStore(code);
    refresh();
    return lang;
  }

  function onChange(fn) {
    if (typeof fn === "function") listeners.push(fn);
  }

  // ---- Boot --------------------------------------------------------------
  // Runs as soon as core.js loads: <html lang> is set immediately, and the
  // text itself once the body has been parsed (the dictionaries are loaded by
  // script tags below core.js, all of them before DOMContentLoaded fires).
  lang = resolve();
  document.documentElement.setAttribute("lang", lang);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  api = window.GeoI18N = {
    lang: lang,
    langs: LANGS.slice(),
    defaultLang: DEFAULT_LANG,
    register: register,
    t: t,
    plural: plural,
    apply: apply,
    setLang: setLang,
    onChange: onChange,
    isKnown: isKnown,
  };
})();
