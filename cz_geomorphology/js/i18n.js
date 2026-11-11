// i18n.js — strings specific to this game, registered on top of
// ../i18n/common.js (loaded first). The Czech values are exactly the copy the
// page ships with, so nothing changes on screen while Czech is the only
// language; another language would register its own table alongside cs below.
//
// Place names are not translated: unit names (Česká vysočina, Šumavská
// soustava, …) and the parent shown as a hint stay Czech.
//
// The level.* keys carry one grammatical form per level, because Czech
// inflects the noun inside the shared prompt templates
// ("Klikni na {noun.clickTarget}:", "Napiš název {noun.typeTarget}:").
(function () {
  "use strict";

  window.GeoI18N.register({
    cs: {
      "page.title": "Geomorfologie Česka · učící hra",
      "app.h1": "⛰️ Geomorfologie Česka",

      "noun.correct": "hledaný útvar",
      "noun.highlighted": "zvýrazněný útvar",

      "app.levels.title": "Úroveň geomorfologického členění",
      "level.provincie.name": "Provincie",
      "level.soustavy.name": "Soustavy",
      "level.podsoustavy.name": "Podsoustavy",

      // "Klikni na …:"
      "level.provincie.clickTarget": "provincii",
      "level.soustavy.clickTarget": "soustavu",
      "level.podsoustavy.clickTarget": "podsoustavu",
      // "Napiš název …:"
      "level.provincie.typeTarget": "zvýrazněné provincie",
      "level.soustavy.typeTarget": "zvýrazněné soustavy",
      "level.podsoustavy.typeTarget": "zvýrazněné podsoustavy",
      // typed-quiz placeholder, per level
      "level.provincie.placeholder": "Napiš název provincie…",
      "level.soustavy.placeholder": "Napiš název soustavy…",
      "level.podsoustavy.placeholder": "Napiš název podsoustavy…",
      // what the click-quiz hint reveals
      "level.provincie.hint": "",
      "level.soustavy.hint": "provincie",
      "level.podsoustavy.hint": "soustava",

      "app.status.exploreParent": "Najedni myší na území a podívej se na jeho název a nadřazenou jednotku.",
      "app.status.exploreSubs": "Najedni myší na území a podívej se na jeho název a počet soustav.",
      "app.plural.subs": ["{n} soustava", "{n} soustavy", "{n} soustav"],
      "app.refmapSource": "atlas MU",

      "foot.source": "Zdroj mapy:",
      "foot.atlas": "Česká republika – Tematický atlas",
      "foot.by": "Pedagogická fakulta Masarykovy univerzity (© 2017 Masarykova univerzita)",
      "foot.count": "4 provincie, 10 soustav a 27 podsoustav. Data generována přes",
    },
  });
})();
