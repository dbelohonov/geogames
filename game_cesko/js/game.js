// game.js — Okresy v Česku: clickable district map with two quiz modes.
//
// Modes
//   • explore — hover/click any district to learn its name + kraj.
//   • click   — the game names 10 random districts one by one; the player
//               points to the right one on the map.
//   • type    — the game highlights 10 random districts one by one; the
//               player types the name. Diacritics are optional (see
//               normalize.js).
//
// Data comes from js/data.js (window.OKRESY, window.OKRESY_VIEWBOX).
// Text comes from the language layer (../i18n/core.js + ../i18n/common.js +
// js/i18n.js): the hub page picks the language and passes it as ?lang=…, and
// district names stay Czech in every language.
(function () {
  "use strict";

  var OKRESY = window.OKRESY || [];
  var VIEWBOX = window.OKRESY_VIEWBOX || "0 0 961 551";
  var N = window.OkresyNormalize;
  var tr = window.GeoI18N.t;
  var QUIZ_LEN = 10;

  // Lookup by code for O(1) hit-testing feedback.
  var BY_CODE = {};
  OKRESY.forEach(function (o) { BY_CODE[o.code] = o; });

  // ---- DOM refs ----------------------------------------------------------
  var elMap = document.getElementById("map");
  var elPanel = document.getElementById("panel");
  var elPrompt = document.getElementById("prompt");
  var elStatus = document.getElementById("status");
  var elInputWrap = document.getElementById("input-wrap");
  var elInput = document.getElementById("answer-input");
  var elProgress = document.getElementById("progress");
  var elScore = document.getElementById("score");
  var elActions = document.getElementById("actions");
  var elHintKraj = document.getElementById("hint-kraj");
  var elRevealWrap = document.getElementById("reveal-wrap");
  var elTooltip = document.getElementById("tooltip");

  // ---- State -------------------------------------------------------------
  var mode = "explore";          // explore | click | type
  var queue = [];                // array of district codes to ask
  var qi = 0;                    // index into queue
  var score = 0;
  var target = null;             // current target district object
  var locked = false;            // ignore clicks while showing feedback
  var pathEls = {};              // code -> <path>

  // ---- Map construction --------------------------------------------------
  function buildMap() {
    var svgNS = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", VIEWBOX);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.classList.add("cesko-map");

    // geometry group
    var g = document.createElementNS(svgNS, "g");
    g.setAttribute("id", "districts");

    // label group (hidden by default)
    var lg = document.createElementNS(svgNS, "g");
    lg.setAttribute("id", "labels");
    lg.setAttribute("pointer-events", "none");

    OKRESY.forEach(function (o) {
      var p = document.createElementNS(svgNS, "path");
      p.setAttribute("d", o.path);
      p.setAttribute("data-code", o.code);
      p.setAttribute("data-name", o.name);
      p.classList.add("district");
      p.addEventListener("click", onDistrictClick.bind(null, o));
      p.addEventListener("mouseenter", onDistrictHover.bind(null, o));
      p.addEventListener("mouseleave", onDistrictLeave.bind(null, o));
      g.appendChild(p);
      pathEls[o.code] = p;

      var t = document.createElementNS(svgNS, "text");
      t.setAttribute("x", o.cx);
      t.setAttribute("y", o.cy);
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("dy", "0.3em");
      t.classList.add("label");
      t.setAttribute("data-code", o.code);
      t.textContent = o.name;
      lg.appendChild(t);
    });

    svg.appendChild(g);
    svg.appendChild(lg);
    elMap.innerHTML = "";
    elMap.appendChild(svg);
  }

  // ---- Hover (explore + click affordance) --------------------------------
  function onDistrictHover(o, ev) {
    if (locked) return;
    var el = pathEls[o.code];
    if (mode === "explore" || mode === "click") el.classList.add("hover");
    if (mode === "explore") {
      showLabel(o.code, true);
      moveTooltip(ev, o.name + " · " + o.kraj);
    }
  }
  function onDistrictLeave(o) {
    pathEls[o.code].classList.remove("hover");
    if (mode === "explore") {
      showLabel(o.code, false);
      hideTooltip();
    }
  }

  // The tooltip lives inside .mapwrap (position:relative), so position it
  // against that box, not against the page.
  function moveTooltip(ev, text) {
    elTooltip.textContent = text;
    elTooltip.style.display = "block";
    var host = elTooltip.offsetParent || elMap;
    var r = host.getBoundingClientRect();
    elTooltip.style.left = (ev.clientX - r.left + 12) + "px";
    elTooltip.style.top = (ev.clientY - r.top + 12) + "px";
  }
  function hideTooltip() { elTooltip.style.display = "none"; }

  // ---- Click handling ----------------------------------------------------
  function onDistrictClick(o) {
    if (locked) return;
    if (mode === "explore") {
      // clicking a district in explore just pins the selection briefly
      flash(o.code, "info", 600);
      setStatus(o.name + " — " + o.kraj);
      return;
    }
    if (mode === "click") {
      handleGuess(o);
    }
    // type mode ignores map clicks
  }

  function handleGuess(o) {
    if (!target || locked) return;
    locked = true;
    if (o.code === target.code) {
      score++;
      flash(target.code, "good");
      setStatus(tr("app.status.correct", { name: target.name }));
    } else {
      flash(o.code, "bad");
      flash(target.code, "good");
      setStatus(tr("app.status.wrongClick",
                   { name: target.name, info: " · " + target.kraj }));
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
    elScore.textContent = score + " / " + QUIZ_LEN;
    elProgress.textContent = (qi) + " / " + QUIZ_LEN;
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
    return shuffle(OKRESY).slice(0, QUIZ_LEN).map(function (o) { return o.code; });
  }

  // ---- Quiz flow ---------------------------------------------------------
  function startQuiz(newMode) {
    mode = newMode;
    queue = pickQueue();
    qi = 0;
    score = 0;
    locked = false;
    clearAllFlash();
    showAllLabels(false);
    elHintKraj.style.display = (mode === "click") ? "" : "none";
    elInputWrap.style.display = (mode === "type") ? "" : "none";
    elActions.style.display = "none";
    elRevealWrap.style.display = "none";
    if (mode === "type" && elInput) { elInput.value = ""; elInput.focus(); }
    nextRound();
  }

  // Click-mode prompt: the name to find, plus the kraj as an optional hint
  // (the checkbox can be flipped mid-round, so this is re-renderable).
  function renderClickPrompt() {
    if (!target) return;
    var hint = elHintKraj.querySelector("input").checked
      ? " <small>(" + target.kraj + ")</small>" : "";
    elPrompt.innerHTML = tr("app.prompt.click") +
                         "<br><b>" + target.name + "</b>" + hint;
  }

  function nextRound() {
    if (qi >= queue.length) { finishQuiz(); return; }
    target = BY_CODE[queue[qi]];
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
    var pct = Math.round(score / QUIZ_LEN * 100);
    var best = bestScore(mode);
    var isBest = score > best;
    if (isBest) saveBest(mode, score);
    var bestNow = Math.max(best, score);
    elPrompt.innerHTML = tr("app.prompt.finish",
                            { score: score, len: QUIZ_LEN, pct: pct });
    setStatus(tr("app.status.best", {
      score: bestNow,
      len: QUIZ_LEN,
      record: isBest ? tr("app.status.record") : "",
    }));
    elInputWrap.style.display = "none";
    elActions.style.display = "";
    elProgress.textContent = QUIZ_LEN + " / " + QUIZ_LEN;
  }

  // ---- Type mode submit --------------------------------------------------
  function submitAnswer() {
    if (mode !== "type" || !target || locked) return;
    var typed = elInput.value;
    if (!typed.trim()) return;
    locked = true;
    if (N.answersMatch(typed, target.name)) {
      score++;
      flash(target.code, "good");
      elInputWrap.classList.add("good");
      setStatus(tr("app.status.correct", { name: target.name }));
    } else if (N.isClose(typed, target.name)) {
      flash(target.code, "bad");
      elInputWrap.classList.add("close");
      setStatus(tr("app.status.almost",
                   { name: target.name, info: " · " + target.kraj }));
    } else {
      flash(target.code, "bad");
      elInputWrap.classList.add("bad");
      setStatus(tr("app.status.wrongType",
                   { name: target.name, info: " · " + target.kraj }));
    }
    updateScore();
    setTimeout(nextRound, 1300);
  }

  function skipQuestion() {
    if (mode !== "type" || !target || locked) return;
    locked = true;
    flash(target.code, "bad");
    elInputWrap.classList.add("bad");
    setStatus(tr("app.status.skipped",
                 { name: target.name, info: " · " + target.kraj }));
    updateScore();
    setTimeout(nextRound, 1300);
  }

  // ---- localStorage best scores -----------------------------------------
  function bestKey(m) { return "okresy_best_" + m; }
  function bestScore(m) {
    try { return parseInt(localStorage.getItem(bestKey(m)) || "0", 10) || 0; }
    catch (e) { return 0; }
  }
  function saveBest(m, s) {
    try { localStorage.setItem(bestKey(m), String(s)); } catch (e) {}
  }

  // ---- Explore mode ------------------------------------------------------
  function enterExplore() {
    mode = "explore";
    clearAllFlash();
    target = null;
    elPrompt.innerHTML = tr("app.prompt.explore");
    setStatus(tr("app.status.explore"));
    elInputWrap.style.display = "none";
    elActions.style.display = "none";
    elHintKraj.style.display = "none";
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

    // kraj hint can be flipped mid-round → refresh the click prompt
    var hintInput = elHintKraj.querySelector("input");
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
