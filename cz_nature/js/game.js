// game.js — Chráněná území Česka: clickable map of the large-scale
// specially protected areas (velkoplošná ZCHÚ) with the same modes as the
// other games in this repo.
//
// All 31 areas — 4 národní parky + 27 chráněných krajinných oblastí —
// play together; there is no category switch. Names always carry the
// category prefix ("NP Šumava", "CHKO Brdy"), which is also what tells
// NP Šumava apart from the CHKO Šumava wrapped around it.
//
// The map draws the country silhouette plus both categories (brown = NP,
// green = CHKO, NPs on top where they overlap).
//
// Modes
//   • explore — hover/click any area to learn its name and category.
//   • click   — the game names areas one by one in random order; the
//               player points to the right one.
//   • type    — the game highlights areas one by one; the player types
//               the name. Diacritics are optional and the category
//               prefix may be abbreviated, spelled out or omitted
//               ("Brdy", "CHKO Brdy", "chráněná krajinná oblast Brdy"
//               all count — see normalize.js).
//
// Data comes from js/data.js (window.NATURE, window.NATURE_VIEWBOX).
// Text comes from the language layer (../i18n/core.js + ../i18n/common.js +
// js/i18n.js): the hub page picks the language and passes it as ?lang=…, and
// area names (NP/CHKO prefixes included) stay Czech in every language.
(function () {
  "use strict";

  var G = window.NATURE || { base: "", np: [], chko: [] };
  var VIEWBOX = window.NATURE_VIEWBOX || "0 0 517.213 295.669";
  var N = window.NatureNormalize;
  var tr = window.GeoI18N.t;
  var QUIZ_LEN = 10;

  // tag every unit with its category so one flat list can drive the map
  (G.np || []).forEach(function (u) { u.kind = "np"; });
  (G.chko || []).forEach(function (u) { u.kind = "chko"; });
  var ALL = (G.np || []).concat(G.chko || []);

  // ---- DOM refs ----------------------------------------------------------
  var elMap = document.getElementById("map");
  var elPrompt = document.getElementById("prompt");
  var elStatus = document.getElementById("status");
  var elInputWrap = document.getElementById("input-wrap");
  var elInput = document.getElementById("answer-input");
  var elProgress = document.getElementById("progress");
  var elScore = document.getElementById("score");
  var elActions = document.getElementById("actions");
  var elRevealWrap = document.getElementById("reveal-wrap");
  var elTooltip = document.getElementById("tooltip");

  // ---- State -------------------------------------------------------------
  var mode = "explore";          // explore | click | type
  var queue = [];                // array of unit codes to ask
  var qi = 0;                    // index into queue
  var score = 0;
  var target = null;             // current target unit object
  var locked = false;            // ignore input while showing feedback
  var pathEls = {};              // code -> <path>

  function quizLen() { return Math.min(QUIZ_LEN, ALL.length); }
  function byCode(code) {
    var found = null;
    ALL.forEach(function (u) { if (u.code === code) found = u; });
    return found;
  }

  // Full display name with the category prefix: "NP Šumava" / "CHKO Brdy".
  function displayName(u) { return u.alt || u.name; }
  // Accepted typed answers (prefix / short / spelled-out forms).
  function acceptedNames(u) {
    if (u.accept && u.accept.length) return u.accept;
    return u.alt ? [u.name, u.alt] : [u.name];
  }
  // Secondary info shown in tooltips/status after " · " — the category
  // spelled out, which also teaches what the CHKO/NP abbreviations mean.
  // Category words live in the data, so they are translated by key with the
  // Czech original as the fallback. No "cat.*" key is defined while Czech is
  // the only language — the lookup is the seam where a translation would go.
  function infoLine(u) { return tr("cat." + u.cat, null, u.cat); }

  // ---- Map labels --------------------------------------------------------
  // Long names render on two lines so a label never sticks out of its
  // region (or the map window). The viewBox is only ~517 units wide, so
  // the limits are in (small) viewBox units; CHKO labels use a smaller
  // font and tolerate slightly shorter lines.
  var LABEL_WRAP_LEN = { np: 16, chko: 13 };

  // Split a name into two balanced lines: at the space nearest the middle,
  // or after a hyphen for compound one-word names. An en dash between
  // words ("Kokořínsko – Máchův kraj") is glued to the preceding word so
  // a line never starts with a lone dash.
  function splitTwo(name) {
    var words = name.replace(/ \u2013 /g, " \u00a0\u2013 ").split(" ");
    if (words.length >= 2) {
      var half = name.length / 2, best = 1, bestDiff = Infinity;
      for (var i = 1; i < words.length; i++) {
        var diff = Math.abs(words.slice(0, i).join(" ").length - half);
        if (diff < bestDiff) { bestDiff = diff; best = i; }
      }
      return [words.slice(0, best).join(" "), words.slice(best).join(" ")];
    }
    var h = name.indexOf("-");
    if (h > 0 && h < name.length - 1) return [name.slice(0, h + 1), name.slice(h + 1)];
    return null;
  }
  function labelLines(name, kind) {
    if (name.length <= LABEL_WRAP_LEN[kind]) return [name];
    return splitTwo(name) || [name];
  }

  // ---- Map construction --------------------------------------------------
  // All areas are drawn once; mode switches need no rebuild.
  function buildMap() {
    var svgNS = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", VIEWBOX);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.classList.add("nature-map");

    // country silhouette (decorative context, not clickable)
    var base = document.createElementNS(svgNS, "path");
    base.setAttribute("d", G.base);
    base.classList.add("base");
    svg.appendChild(base);

    // geometry group — CHKO first, NPs on top (they overlap locally:
    // Šumava, České Švýcarsko/Labské pískovce, Krkonoše)
    var g = document.createElementNS(svgNS, "g");
    g.setAttribute("id", "regions");

    // label group (hidden by default)
    var lg = document.createElementNS(svgNS, "g");
    lg.setAttribute("id", "labels");
    lg.setAttribute("pointer-events", "none");

    pathEls = {};
    ALL.slice().sort(function (a, b) {
      return a.kind === b.kind ? 0 : (a.kind === "chko" ? -1 : 1);
    }).forEach(function (u) {
      var p = document.createElementNS(svgNS, "path");
      p.setAttribute("d", u.path);
      p.setAttribute("data-code", u.code);
      p.setAttribute("data-name", u.name);
      p.classList.add("region");
      p.classList.add(u.kind);
      p.addEventListener("click", onRegionClick.bind(null, u));
      p.addEventListener("mouseenter", onRegionHover.bind(null, u));
      p.addEventListener("mouseleave", onRegionLeave.bind(null, u));
      g.appendChild(p);
      pathEls[u.code] = p;

      var t = document.createElementNS(svgNS, "text");
      t.setAttribute("x", u.cx);
      t.setAttribute("y", u.cy);
      t.setAttribute("text-anchor", "middle");
      t.classList.add("label");
      t.classList.add(u.kind);
      t.setAttribute("data-code", u.code);
      var lines = labelLines(displayName(u), u.kind);
      if (lines.length === 1) {
        t.setAttribute("dy", "0.3em");
        t.textContent = lines[0];
      } else {
        // two tspans centred as a block on (cx, cy)
        lines.forEach(function (ln, i) {
          var ts = document.createElementNS(svgNS, "tspan");
          ts.setAttribute("x", u.cx);
          ts.setAttribute("dy", i ? "1.15em" : "-0.25em");
          ts.textContent = ln;
          t.appendChild(ts);
        });
      }
      lg.appendChild(t);
    });

    svg.appendChild(g);
    svg.appendChild(lg);
    elMap.innerHTML = "";
    elMap.appendChild(svg);
  }

  // ---- Hover (explore + click affordance) --------------------------------
  function onRegionHover(u, ev) {
    if (locked && mode !== "explore") return;
    var el = pathEls[u.code];
    if (mode === "explore" || mode === "click") el.classList.add("hover");
    if (mode === "explore") {
      showLabel(u.code, true);
      moveTooltip(ev, displayName(u) + " · " + infoLine(u));
    }
  }
  function onRegionLeave(u) {
    pathEls[u.code].classList.remove("hover");
    if (mode === "explore") {
      showLabel(u.code, false);
      hideTooltip();
    }
  }

  // The tooltip lives inside .mapwrap (position:relative), so position it
  // against that box, not against the page. Flip it to the other side of
  // the cursor near the edges so it never grows the scrollable area — an
  // overflowing tooltip would shift the whole map.
  function moveTooltip(ev, text) {
    elTooltip.textContent = text;
    elTooltip.style.display = "block";
    var host = elTooltip.offsetParent || elMap;
    var r = host.getBoundingClientRect();
    var x = ev.clientX - r.left + 12;
    var y = ev.clientY - r.top + 12;
    var w = elTooltip.offsetWidth, h = elTooltip.offsetHeight;
    if (x + w > r.width - 4) x = ev.clientX - r.left - w - 12;
    if (y + h > r.height - 4) y = ev.clientY - r.top - h - 12;
    elTooltip.style.left = Math.max(4, x) + "px";
    elTooltip.style.top = Math.max(4, y) + "px";
  }
  function hideTooltip() { elTooltip.style.display = "none"; }

  // ---- Click handling ----------------------------------------------------
  function onRegionClick(u) {
    if (mode === "explore") {
      // clicking a region in explore just pins the selection briefly
      flash(u.code, "info", 600);
      setStatus(displayName(u) + " — " + infoLine(u));
      return;
    }
    if (mode === "click" && !locked) {
      handleGuess(u);
    }
    // type mode ignores map clicks
  }

  function handleGuess(u) {
    if (!target || locked) return;
    locked = true;
    if (u.code === target.code) {
      score++;
      flash(target.code, "good");
      setStatus(tr("app.status.correct", { name: displayName(target) }));
    } else {
      flash(u.code, "bad");
      flash(target.code, "good");
      setStatus(tr("app.status.wrongClick", {
        name: displayName(target), info: " · " + infoLine(target),
      }));
    }
    updateScore();
    setTimeout(nextRound, 1100);
  }

  // ---- Visual helpers ----------------------------------------------------
  function flash(code, kind, ms) {
    var el = pathEls[code];
    if (!el) return;
    el.classList.remove("good", "bad", "info", "ask");
    el.classList.add(kind);
    if (ms) {
      setTimeout(function () {
        el.classList.remove(kind);
      }, ms);
    }
  }

  function clearAllFlash() {
    Object.keys(pathEls).forEach(function (c) {
      pathEls[c].classList.remove("good", "bad", "info", "ask", "hover");
    });
  }

  function showLabel(code, on) {
    var t = elMap.querySelector('text.label[data-code="' + code + '"]');
    if (t) t.classList.toggle("on", !!on);
  }
  function showAllLabels(on) {
    elMap.querySelectorAll("text.label").forEach(function (t) {
      t.classList.toggle("on", !!on);
    });
  }

  function setStatus(html) { elStatus.innerHTML = html; }
  function updateScore() {
    elScore.textContent = score + " / " + quizLen();
    elProgress.textContent = (qi) + " / " + quizLen();
  }

  // ---- Shuffling ---------------------------------------------------------
  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  function pickQueue() {
    return shuffle(ALL).slice(0, quizLen()).map(function (u) { return u.code; });
  }

  // ---- Quiz flow ---------------------------------------------------------
  function startQuiz(newMode) {
    mode = newMode;
    queue = pickQueue();
    qi = 0;
    score = 0;
    locked = false;
    clearAllFlash();
    hideTooltip();
    showAllLabels(false);
    elInputWrap.style.display = (mode === "type") ? "" : "none";
    elActions.style.display = "none";
    elRevealWrap.style.display = "none";
    if (mode === "type" && elInput) {
      elInput.placeholder = tr("app.input.placeholder");
      elInput.value = "";
      elInput.focus();
    }
    nextRound();
  }

  // Click-mode prompt spells the full display name, prefix included
  // ("CHKO Brdy", "NP Šumava") — for the two Šumavas the prefix is what
  // tells them apart.
  function renderClickPrompt() {
    if (!target) return;
    elPrompt.innerHTML = tr("app.prompt.click") +
                         "<br><b>" + displayName(target) + "</b>";
  }

  function nextRound() {
    if (qi >= queue.length) { finishQuiz(); return; }
    target = byCode(queue[qi]);
    qi++;
    locked = false;
    clearAllFlash();
    elInputWrap.classList.remove("good", "bad", "close");
    if (elInput) elInput.value = "";
    updateScore(); // reflects qi increment for progress

    if (mode === "click") {
      renderClickPrompt();
      setStatus("");
      if (elInput) elInput.blur();
    } else if (mode === "type") {
      flash(target.code, "ask");
      elPrompt.innerHTML = tr("app.prompt.type");
      setStatus("");
      if (elInput) elInput.focus();
    }
  }

  function finishQuiz() {
    locked = true;
    target = null;
    clearAllFlash();
    var len = quizLen();
    var pct = Math.round(score / len * 100);
    var best = bestScore();
    var isBest = score > best;
    if (isBest) saveBest(score);
    var bestNow = Math.max(best, score);
    elPrompt.innerHTML = tr("app.prompt.finish",
                            { score: score, len: len, pct: pct });
    setStatus(tr("app.status.best", {
      score: bestNow,
      len: len,
      record: isBest ? tr("app.status.record") : "",
    }));
    elInputWrap.style.display = "none";
    elActions.style.display = "";
    elProgress.textContent = len + " / " + len;
  }

  // ---- Type mode submit --------------------------------------------------
  function submitAnswer() {
    if (mode !== "type" || !target || locked) return;
    var typed = elInput.value;
    if (!typed.trim()) return;
    locked = true;
    var names = acceptedNames(target);
    if (N.answersMatch(typed, names)) {
      score++;
      flash(target.code, "good");
      elInputWrap.classList.add("good");
      setStatus(tr("app.status.correct", { name: displayName(target) }));
    } else if (N.isClose(typed, names)) {
      flash(target.code, "bad");
      elInputWrap.classList.add("close");
      setStatus(tr("app.status.almost", {
        name: displayName(target), info: " · " + infoLine(target),
      }));
    } else {
      flash(target.code, "bad");
      elInputWrap.classList.add("bad");
      setStatus(tr("app.status.wrongType", {
        name: displayName(target), info: " · " + infoLine(target),
      }));
    }
    updateScore();
    setTimeout(nextRound, 1300);
  }

  function skipQuestion() {
    if (mode !== "type" || !target || locked) return;
    locked = true;
    flash(target.code, "bad");
    elInputWrap.classList.add("bad");
    setStatus(tr("app.status.skipped", {
      name: displayName(target), info: " · " + infoLine(target),
    }));
    updateScore();
    setTimeout(nextRound, 1300);
  }

  // ---- localStorage best scores (per mode) --------------------------------
  function bestKey() { return "nature_best_" + mode; }
  function bestScore() {
    try { return parseInt(localStorage.getItem(bestKey()) || "0", 10) || 0; }
    catch (e) { return 0; }
  }
  function saveBest(s) {
    try { localStorage.setItem(bestKey(), String(s)); } catch (e) {}
  }

  // ---- Explore mode ------------------------------------------------------
  function enterExplore() {
    mode = "explore";
    clearAllFlash();
    hideTooltip();
    target = null;
    elPrompt.innerHTML = tr("app.prompt.explore");
    setStatus(tr("app.status.explore"));
    elInputWrap.style.display = "none";
    elActions.style.display = "none";
    elRevealWrap.style.display = "";
    elScore.textContent = "—";
    elProgress.textContent = "—";
    showAllLabels(false);
    var reveal = document.getElementById("reveal-all");
    if (reveal) reveal.checked = false;
  }

  // ---- Wiring ------------------------------------------------------------
  function wire() {
    document.querySelectorAll("[data-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var m = btn.getAttribute("data-mode");
        document.querySelectorAll("[data-mode]").forEach(function (b) {
          b.classList.toggle("active", b === btn);
        });
        if (m === "explore") enterExplore();
        else startQuiz(m);
      });
    });

    if (elInput) {
      elInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); submitAnswer(); }
      });
    }
    var submitBtn = document.getElementById("btn-submit");
    if (submitBtn) submitBtn.addEventListener("click", submitAnswer);
    var skipBtn = document.getElementById("btn-skip");
    if (skipBtn) skipBtn.addEventListener("click", skipQuestion);

    // reveal-all labels toggle (explore study aid)
    var reveal = document.getElementById("reveal-all");
    if (reveal) {
      reveal.addEventListener("change", function () {
        showAllLabels(reveal.checked);
      });
    }

    // restart buttons
    document.querySelectorAll("[data-restart]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        startQuiz(btn.getAttribute("data-restart"));
      });
    });
  }

  // ---- Boot --------------------------------------------------------------
  function init() {
    buildMap();
    wire();
    enterExplore();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
