// normalize.js — answer comparison helpers (diacritics-insensitive)
//
// The player may type a district name with or without Czech diacritics
// (háček/čárka), with hyphens, spaces, or capitalization in any mix.
// normalizeName() collapses all of that to a single canonical string so
// two answers compare equal regardless of how they were typed.
//
//   "Brno-město"  → "brnomesto"
//   "brno MESTO"  → "brnomesto"
//   "Ústí nad Labem" → "ustinadlabem"
//   "usti nad labem" → "ustinadlabem"
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
    // punctuation, the German ß, etc.). This makes "Brno-město" and
    // "brno mesto" identical.
    return deaccented
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
  }

  // Accepts the player's raw input and the official district name.
  // Returns true on a normalized match.
  function answersMatch(typed, official) {
    return normalizeName(typed) === normalizeName(official);
  }

  // A forgiving "close" check used only to color the input amber as a hint
  // that the player is on the right track (e.g. correct root, wrong suffix),
  // never to accept the answer.
  function isClose(typed, official) {
    var t = normalizeName(typed);
    var o = normalizeName(official);
    if (!t || t === o) return false;
    // Official starts with what the player typed (≥4 chars) — e.g. typed
    // "hradec" for "Hradec Králové". Not a match, but close.
    return t.length >= 4 && o.indexOf(t) === 0;
  }

  window.OkresyNormalize = {
    normalizeName: normalizeName,
    answersMatch: answersMatch,
    isClose: isClose,
  };
})();
