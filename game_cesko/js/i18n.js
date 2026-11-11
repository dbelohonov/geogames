// i18n.js — strings specific to this game, registered on top of
// ../i18n/common.js (loaded first). The Czech values are exactly the copy the
// page ships with, so nothing changes on screen while Czech is the only
// language; another language would register its own table alongside cs below.
//
// Place names are not translated: the map, the quiz answers and the kraje
// stay Czech.
//
// The noun.* keys carry the grammatical form the shared templates in
// common.js need — Czech accusative/genitive.
(function () {
  "use strict";

  window.GeoI18N.register({
    cs: {
      "page.title": "Okresy v Česku · učící hra",
      "app.h1": "🗺️ Okresy v\u00a0Česku",

      "noun.correct": "hledaný okres",
      "noun.highlighted": "zvýrazněný okres",
      "noun.clickTarget": "okres",
      "noun.typeTarget": "zvýrazněného okresu",

      "app.status.explore": "Najedni myší na okres a podívej se na jeho název a kraj.",
      // this game phrases the miss in the second person, unlike the others
      "app.status.wrongClick": "Nesprávně. Hledali jste: {name}{info}",
      "app.input.placeholder": "Napiš název okresu…",
      "app.hint.kraj": "nápověda: kraj",
      "app.refmapSource": "Wikipedia",

      "foot.source": "Zdroj hranic:",
      "foot.count": "77 okresů ČR. Data generována přes",
    },
  });
})();
