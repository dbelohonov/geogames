// normalize.js — answer comparison helpers (diacritics-insensitive)
//
// The player may type a unit name with or without Czech diacritics
// (háček/čárka), with hyphens, spaces, or capitalization in any mix.
// normalizeName() collapses all of that to a single canonical string so
// two answers compare equal regardless of how they were typed.
//
//   "Krkonošsko-jesenická"   → "krkonosskojesenicka"
//   "krkonossko jesenicka"   → "krkonosskojesenicka"
//   "Česká vysočina"         → "ceskavysocina"
//   "ceska vysocina"         → "ceskavysocina"
(function () {
  "use strict";

  function normalizeName(s) {
    if (s == null) return "";
    // NFD decomposes combined letters (č → c + combining háček); stripping
    // the combining block leaves the base ASCII letter.
    var deaccented = String(s)
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "");
    // Lowercase, drop everything that isn't a–z or 0–9 (hyphens, spaces,
    // punctuation, etc.). This makes "Krkonošsko-jesenická" and
    // "krkonossko jesenicka" identical.
    return deaccented
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
  }

  // Accepts the player's raw input and a list of accepted official names
  // (e.g. ["Šumavská", "Šumavská soustava"]). True on any exact
  // normalized match.
  function answersMatch(typed, officials) {
    var t = normalizeName(typed);
    return officials.some(function (o) { return t === normalizeName(o); });
  }

  // A forgiving "close" check used only to color the input amber as a hint
  // that the player is on the right track (e.g. correct root, wrong suffix),
  // never to accept the answer.
  function isClose(typed, officials) {
    var t = normalizeName(typed);
    if (!t) return false;
    return officials.some(function (o) {
      var n = normalizeName(o);
      return t !== n && t.length >= 4 && n.indexOf(t) === 0;
    });
  }

  window.GeomorphNormalize = {
    normalizeName: normalizeName,
    answersMatch: answersMatch,
    isClose: isClose,
  };
})();
