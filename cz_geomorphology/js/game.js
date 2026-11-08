// game.js — Geomorfologie Česka: clickable map of the geomorphological
// division with the same modes as game_cesko (Okresy).
//
// Levels (modern terminology)
//   • soustavy    — 10 geomorfologických soustav (default)
//   • provincie   — 4 geomorfologické provincie
//   • podsoustavy — 27 geomorfologických podsoustav
//
// Modes
//   • explore — hover/click any unit to learn its name (+ parent unit or
//               soustava count).
//   • click   — the game names all units one by one in random order; the
//               player points to the right one on the map. Optional hint:
//               the parent unit (soustava / podsoustava levels).
//   • type    — the game highlights units one by one; the player types the
//               name. Diacritics are optional and the level word
//               ("soustava") may be omitted (see normalize.js).
//
// Data comes from js/data.js (window.GEOMORPH, window.GEOMORPH_VIEWBOX).
(function () {
  "use strict";

  var G = window.GEOMORPH || { provincie: [], soustavy: [], podsoustavy: [] };
  var VIEWBOX = window.GEOMORPH_VIEWBOX || "0 0 1640 935";
  var N = window.GeomorphNormalize;
  var MAX_QUIZ = 10;

  var LEVELS = {
    provincie: {
      units: G.provincie || [],
      acc: "provincii",        // "Klikni na …"
      gen: "provincie",        // "Napiš název zvýrazněné …"
      hintable: false,
      hintWord: "",
      cls: "prov",
    },
    soustavy: {
      units: G.soustavy || [],
      acc: "soustavu",
      gen: "soustavy",
      hintable: true,
      hintWord: "provincie",
      cls: "soust",
    },
    podsoustavy: {
      units: G.podsoustavy || [],
      acc: "podsoustavu",
      gen: "podsoustavy",
      hintable: true,
      hintWord: "soustava",
      cls: "pod",
    },
  };

  // ---- DOM refs ----------------------------------------------------------
  var elMap = document.getElementById("map");
  var elPrompt = document.getElementById("prompt");
  var elStatus = document.getElementById("status");
  var elInputWrap = document.getElementById("input-wrap");
  var elInput = document.getElementById("answer-input");
  var elProgress = document.getElementById("progress");
  var elScore = document.getElementById("score");
  var elActions = document.getElementById("actions");
  var elHintParent = document.getElementById("hint-parent");
  var elRevealWrap = document.getElementById("reveal-wrap");
  var elTooltip = document.getElementById("tooltip");

  // ---- State -------------------------------------------------------------
  var level = "soustavy";        // provincie | soustavy | podsoustavy
  var mode = "explore";          // explore | click | type
  var queue = [];                // array of unit codes to ask
  var qi = 0;                    // index into queue
  var score = 0;
  var target = null;             // current target unit object
  var locked = false;            // ignore input while showing feedback
  var pathEls = {};              // code -> <path>

  function L() { return LEVELS[level]; }
  function units() { return L().units; }
  function quizLen() { return Math.min(MAX_QUIZ, units().length); }
  function byCode(code) {
    var found = null;
    units().forEach(function (u) { if (u.code === code) found = u; });
    return found;
  }

  // Full display name: "Šumavská soustava" / "Česká vysočina".
  function displayName(u) { return u.alt || u.name; }
  // Accepted typed answers for a unit (short + full/old forms).
  function acceptedNames(u) {
    if (u.accept && u.accept.length) return u.accept;
    return u.alt ? [u.name, u.alt] : [u.name];
  }
  // Czech plural for the province-level tooltip.
  function subsText(n) {
    var word = n === 1 ? "soustava" : (n < 5 ? "soustavy" : "soustav");
    return n + " " + word;
  }
  // Secondary info shown in tooltips/status after " · ".
  function infoLine(u) {
    return level === "provincie" ? subsText(u.subs) : u.parent;
  }

  // ---- Map labels --------------------------------------------------------
  // Long names render on two lines so a label never sticks out of its region
  // (or the map window). Limit is in characters; podsoustavy use a smaller
  // font, so they tolerate slightly longer single lines.
  var LABEL_WRAP_LEN = { prov: 18, soust: 18, pod: 20 };

  // Split a name into two balanced lines: at the space nearest the middle,
  // or after a hyphen for compound one-word names ("Krkonošsko-jesenická").
  function splitTwo(name) {
    var words = name.split(" ");
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
  function labelLines(name) {
    if (name.length <= LABEL_WRAP_LEN[L().cls]) return [name];
    return splitTwo(name) || [name];
  }

  // ---- Map construction --------------------------------------------------
  function buildMap() {
    var svgNS = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", VIEWBOX);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.classList.add("geo-map");
    svg.classList.add(L().cls);

    // geometry group
    var g = document.createElementNS(svgNS, "g");
    g.setAttribute("id", "regions");

    // label group (hidden by default)
    var lg = document.createElementNS(svgNS, "g");
    lg.setAttribute("id", "labels");
    lg.setAttribute("pointer-events", "none");

    pathEls = {};
    units().forEach(function (u) {
      var p = document.createElementNS(svgNS, "path");
      p.setAttribute("d", u.path);
      p.setAttribute("data-code", u.code);
      p.setAttribute("data-name", u.name);
      p.classList.add("region");
      p.classList.add(L().cls);
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
      t.setAttribute("data-code", u.code);
      var lines = labelLines(u.name);
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
    if (locked) return;
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
    if (locked) return;
    if (mode === "explore") {
      // clicking a region in explore just pins the selection briefly
      flash(u.code, "info", 600);
      setStatus(displayName(u) + " — " + infoLine(u));
      return;
    }
    if (mode === "click") {
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
      setStatus("Správně! " + displayName(target));
    } else {
      flash(u.code, "bad");
      flash(target.code, "good");
      setStatus("Nesprávně. Hledali jsme: " + displayName(target) +
                " · " + infoLine(target));
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
    return shuffle(units()).slice(0, quizLen()).map(function (u) { return u.code; });
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
    elHintParent.style.display =
      (mode === "click" && L().hintable) ? "" : "none";
    var hintWhat = document.getElementById("hint-what");
    if (hintWhat) hintWhat.textContent = L().hintWord;
    elInputWrap.style.display = (mode === "type") ? "" : "none";
    elActions.style.display = "none";
    elRevealWrap.style.display = "none";
    if (mode === "type" && elInput) {
      elInput.placeholder = "Napiš název " + L().gen + "…";
      elInput.value = "";
      elInput.focus();
    }
    nextRound();
  }

  // Click-mode prompt: the name to find, plus the province as an optional
  // hint (the checkbox can be flipped mid-round, so this is re-renderable).
  function renderClickPrompt() {
    if (!target) return;
    var hint = "";
    if (L().hintable && elHintParent.querySelector("input").checked) {
      hint = " <small>(" + target.parent + ")</small>";
    }
    elPrompt.innerHTML = "Klikni na " + L().acc + ":<br><b>" +
      displayName(target) + "</b>" + hint;
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
      elPrompt.innerHTML = "Napiš název zvýrazněné " + L().gen + ":";
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
    elPrompt.innerHTML =
      "Konec kvízu!<br><b>" + score + " / " + len +
      "</b> (" + pct + " %)";
    setStatus("Nejlepší výsledek: " + bestNow + " / " + len +
              (isBest ? " — nový rekord!" : ""));
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
      setStatus("Správně! " + displayName(target));
    } else if (N.isClose(typed, names)) {
      flash(target.code, "bad");
      elInputWrap.classList.add("close");
      setStatus("Téměř. Správně: " + displayName(target) +
                " · " + infoLine(target));
    } else {
      flash(target.code, "bad");
      elInputWrap.classList.add("bad");
      setStatus("Nesprávně. Správně: " + displayName(target) +
                " · " + infoLine(target));
    }
    updateScore();
    setTimeout(nextRound, 1300);
  }

  function skipQuestion() {
    if (mode !== "type" || !target || locked) return;
    locked = true;
    flash(target.code, "bad");
    elInputWrap.classList.add("bad");
    setStatus("Správně bylo: " + displayName(target) +
              " · " + infoLine(target));
    updateScore();
    setTimeout(nextRound, 1300);
  }

  // ---- localStorage best scores (per level + mode) ------------------------
  function bestKey() { return "geomorph_best_" + level + "_" + mode; }
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
    elPrompt.innerHTML = "Prozkoumávání";
    setStatus("Najedni myší na území a podívej se na jeho název a " +
              (level === "provincie" ? "počet soustav."
                                     : "nadřazenou jednotku."));
    elInputWrap.style.display = "none";
    elActions.style.display = "none";
    elHintParent.style.display = "none";
    elRevealWrap.style.display = "";
    elScore.textContent = "—";
    elProgress.textContent = "—";
    showAllLabels(false);
    var reveal = document.getElementById("reveal-all");
    if (reveal) reveal.checked = false;
  }

  // ---- Level switching ---------------------------------------------------
  function setLevel(newLevel) {
    if (!LEVELS[newLevel] || newLevel === level) return;
    level = newLevel;
    buildMap();
    if (mode === "explore") enterExplore();
    else startQuiz(mode); // restart the running quiz on the new level
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

    document.querySelectorAll("[data-level]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var l = btn.getAttribute("data-level");
        document.querySelectorAll("[data-level]").forEach(function (b) {
          b.classList.toggle("active", b === btn);
        });
        setLevel(l);
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

    // province hint can be flipped mid-round → refresh the click prompt
    var hintInput = elHintParent.querySelector("input");
    if (hintInput) {
      hintInput.addEventListener("change", function () {
        if (mode === "click" && !locked) renderClickPrompt();
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
