// common.js — UI strings shared by the games that use the i18n layer.
//
// A game's own js/i18n.js is registered after this file and may override any
// key, which is how a game whose click prompt carries no noun (cz_nature) or
// whose wording differs slightly (game_cesko) keeps its Czech copy exactly as
// it was.
//
// Placeholders
//   {name}, {info}, {score}, {len}, {pct}, {what} — filled by the
//     game at runtime (see fill() in core.js);
//   {noun.*}, {app.refmapSource} — not passed by callers: a placeholder is
//     itself looked up as a key, so these resolve to the current game's own
//     strings, which carry the grammatical form the sentence needs (Czech
//     accusative/genitive).
//
// Non-breaking spaces are written as \u00a0 so these values stay safe for
// textContent bindings (data-i18n) and never need innerHTML.
(function () {
  "use strict";

  window.GeoI18N.register({
    cs: {
      // header / modes
      "app.mode.explore": "Prozkoumat",
      "app.mode.click": "Klikací kvíz",
      "app.mode.type": "Psaný kvíz",

      // panel
      "app.prompt.explore": "Prozkoumávání",
      "app.prompt.click": "Klikni na {noun.clickTarget}:",
      "app.prompt.type": "Napiš název {noun.typeTarget}:",
      "app.prompt.finish": "Konec kvízu!<br><b>{score} / {len}</b> ({pct} %)",
      "app.stats.question": "Otázka",
      "app.stats.score": "Skóre",
      "app.btn.ok": "OK",
      "app.btn.skip": "Přeskočit",
      "app.hint.label": "nápověda:",

      // feedback
      "app.status.correct": "Správně! {name}",
      "app.status.wrongClick": "Nesprávně. Hledali jsme: {name}{info}",
      "app.status.almost": "Téměř. Správně: {name}{info}",
      "app.status.wrongType": "Nesprávně. Správně: {name}{info}",
      "app.status.skipped": "Správně bylo: {name}{info}",
      "app.status.best": "Nejlepší výsledek: {score} / {len}{record}",
      "app.status.record": " — nový rekord!",

      // legend + actions
      "app.legend.correct": "správně / {noun.correct}",
      "app.legend.wrong": "nesprávně",
      "app.legend.highlighted": "{noun.highlighted} (psaný kvíz)",
      "app.legend.reveal": "ukázat všechny názvy",
      "app.action.restartClick": "Hrát znovu (klikací)",
      "app.action.restartType": "Hrát znovu (psaný)",
      "app.refmap": "📷 Referenční mapa s\u00a0názvy ({app.refmapSource})",
    },
  });
})();
