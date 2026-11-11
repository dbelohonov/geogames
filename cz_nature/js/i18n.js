// i18n.js — strings specific to this game, registered on top of
// ../i18n/common.js (loaded first). The Czech values are exactly the copy the
// page ships with, so nothing changes on screen while Czech is the only
// language; another language would register its own table alongside cs below.
//
// Place names and the NP/CHKO prefixes baked into them ("NP Šumava",
// "CHKO Brdy") are data and stay Czech. The legend spells the abbreviations
// out, so a player still learns what NP and CHKO stand for.
//
// app.prompt.click is overridden here: this game names the area right below
// the instruction, so the sentence carries no noun of its own.
(function () {
  "use strict";

  window.GeoI18N.register({
    cs: {
      "page.title": "Chráněná území Česka · učící hra",
      "app.h1": "🌿 Chráněná území Česka",

      "noun.correct": "hledané území",
      "noun.highlighted": "zvýrazněné území",
      "noun.typeTarget": "zvýrazněného území",
      "app.prompt.click": "Klikni na:",

      "app.status.explore": "Najedni myší na území a podívej se na jeho název a kategorii. Kvízy se ptají na všech 31 území dohromady.",
      "app.input.placeholder": "Napiš název území…",
      "app.legend.np": "národní park",
      "app.legend.chko": "chráněná krajinná oblast",
      // category words come from js/data.js already in Czech; a "cat.<word>"
      // key here is where another language would translate them (game.js
      // looks the key up and falls back to the Czech original)
      "app.refmapSource": "VZCHÚ 2025",

      "foot.source": "Zdroj mapy:",
      "foot.desc": "velkoplošná zvláště chráněná území ČR, stav 2025",
      "foot.count": "4 národní parky a 27 CHKO (včetně Soutoku). Data generována přes",
    },
  });
})();
