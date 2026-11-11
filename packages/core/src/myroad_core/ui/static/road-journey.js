/* Journey style: stepping-stones path. Handles the wide-screen orientation
   toggle (vertical | horizontal), persistence, keyboard scrolling, and
   scrolling the current משבצת into view. The winding itself is CSS; this
   file only refines behaviour. Respects reduced motion. */
(function () {
  var WIDE = "(min-width: 1024px)";

  function styleIsJourney() {
    return (document.documentElement.getAttribute("data-road-style") || "timeline") === "journey";
  }
  function root() {
    return document.querySelector("html[data-road-style='journey'] .road-jy") ||
           (styleIsJourney() ? document.querySelector(".road-jy") : null);
  }
  function storedOrientation() {
    if (window.myroadRoadOrientation) return window.myroadRoadOrientation();
    return document.documentElement.getAttribute("data-road-orientation") || "vertical";
  }
  function isWide() {
    return !!(window.matchMedia && window.matchMedia(WIDE).matches);
  }
  function isHorizontal() {
    return isWide() && storedOrientation() === "horizontal";
  }
  function reduceMotion() {
    return window.myroadReduceMotion ? window.myroadReduceMotion() : false;
  }
  function setOrientation(v, persist) {
    v = v === "horizontal" ? "horizontal" : "vertical";
    if (persist !== false) {
      try { localStorage.setItem("myroad.roadOrientation", v); } catch (err) {}
    }
    document.documentElement.setAttribute("data-road-orientation", v);
    if (window.myroadRoadOrientation) {
      /* keep the getter in sync; it reads the attribute already */
    }
    syncButtons();
    syncCanvas();
    scheduleHere();
  }
  function syncButtons() {
    var v = storedOrientation();
    document.querySelectorAll("[data-jy-orient]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-jy-orient") === v ? "true" : "false");
    });
    document.querySelectorAll('input[name="road_orient"]').forEach(function (r) {
      r.checked = r.value === v;
    });
  }
  function syncCanvas() {
    var jy = root();
    if (!jy) return;
    var canvas = jy.querySelector(".jy-canvas");
    if (!canvas) return;
    var horiz = isHorizontal();
    canvas.classList.toggle("is-horizontal", horiz);
    if (horiz) {
      canvas.setAttribute("tabindex", "0");
      canvas.setAttribute("role", "region");
    } else {
      canvas.removeAttribute("tabindex");
      if (canvas.getAttribute("role") === "region") canvas.removeAttribute("role");
    }
    jy.classList.add("is-drawn");
  }
  function scrollHereIntoView() {
    if (!styleIsJourney() || !isHorizontal()) return;
    var jy = root();
    if (!jy) return;
    var here = jy.querySelector("#jy-here") || jy.querySelector(".jy-stone.is-here, .jy-step.is-here");
    if (!here) return;
    var behavior = reduceMotion() ? "auto" : "smooth";
    try {
      here.scrollIntoView({ inline: "center", block: "nearest", behavior: behavior });
    } catch (err) {
      here.scrollIntoView(true);
    }
  }
  var hereTimer = null;
  function scheduleHere() {
    if (hereTimer) clearTimeout(hereTimer);
    hereTimer = setTimeout(function () { hereTimer = null; scrollHereIntoView(); }, 40);
  }
  function onOrientClick(e) {
    var btn = e.target.closest && e.target.closest("[data-jy-orient]");
    if (!btn) return;
    e.preventDefault();
    setOrientation(btn.getAttribute("data-jy-orient"), true);
  }
  function onKey(e) {
    if (!isHorizontal()) return;
    var jy = root();
    if (!jy) return;
    var canvas = jy.querySelector(".jy-canvas");
    if (!canvas) return;
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Home" && e.key !== "End") return;
    /* Only when focus is inside the journey (canvas, a stone, a card). */
    if (!jy.contains(document.activeElement) && document.activeElement !== canvas) return;
    var stages = Array.prototype.slice.call(jy.querySelectorAll(".jy-stage"));
    if (!stages.length) return;
    var rtl = (document.documentElement.getAttribute("dir") || "rtl") === "rtl";
    var idx = 0, i, r, best = 1e9, cr = canvas.getBoundingClientRect();
    var mid = (cr.left + cr.right) / 2;
    for (i = 0; i < stages.length; i++) {
      r = stages[i].getBoundingClientRect();
      var err = Math.abs((r.left + r.right) / 2 - mid);
      if (err < best) { best = err; idx = i; }
    }
    var next = idx;
    if (e.key === "Home") next = 0;
    else if (e.key === "End") next = stages.length - 1;
    else if (e.key === "ArrowLeft") next = rtl ? idx + 1 : idx - 1;
    else if (e.key === "ArrowRight") next = rtl ? idx - 1 : idx + 1;
    next = Math.max(0, Math.min(stages.length - 1, next));
    if (next === idx && e.key !== "Home" && e.key !== "End") return;
    e.preventDefault();
    var behavior = reduceMotion() ? "auto" : "smooth";
    try {
      stages[next].scrollIntoView({ inline: "center", block: "nearest", behavior: behavior });
    } catch (err) {
      stages[next].scrollIntoView(true);
    }
  }
  function bind(jy) {
    if (!jy || jy.__jyBound) return;
    jy.__jyBound = true;
    jy.addEventListener("click", onOrientClick);
    var canvas = jy.querySelector(".jy-canvas");
    if (canvas) canvas.addEventListener("keydown", onKey);
  }
  function init() {
    syncButtons();
    if (!styleIsJourney()) return;
    var jy = root();
    if (jy) bind(jy);
    syncCanvas();
    scheduleHere();
    if (!window.__jyRoadResize) {
      window.__jyRoadResize = true;
      window.addEventListener("resize", function () {
        syncCanvas();
        scheduleHere();
      }, { passive: true });
      if (window.matchMedia) {
        var mq = window.matchMedia(WIDE);
        var onMq = function () { syncCanvas(); scheduleHere(); };
        if (mq.addEventListener) mq.addEventListener("change", onMq);
        else if (mq.addListener) mq.addListener(onMq);
      }
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  window.myroadDrawJourneyRoad = function () { syncCanvas(); scheduleHere(); };
  window.myroadSetRoadOrientation = setOrientation;
})();
