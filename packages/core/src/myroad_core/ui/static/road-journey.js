/* Hopscotch journey: orientation, keyboard scrolling on wide horizontal
   views, and sticky-bar-aware scroll to the current stone. Layout itself
   is CSS (column-reverse hopscotch, 90° rotation when horizontal). */
(function () {
  var WIDE = "(min-width: 1024px)";

  function styleIsJourney() {
    return (document.documentElement.getAttribute("data-road-style") || "timeline") === "journey";
  }
  function orientation() {
    if (window.myroadRoadOrientation) return window.myroadRoadOrientation();
    return document.documentElement.getAttribute("data-road-orientation") || "vertical";
  }
  function isWide() {
    return !!(window.matchMedia && window.matchMedia(WIDE).matches);
  }
  function isHorizontal() {
    return isWide() && orientation() === "horizontal";
  }
  function reduceMotion() {
    return window.myroadReduceMotion ? window.myroadReduceMotion() : false;
  }
  function root() {
    return document.querySelector("html[data-road-style='journey'] .road-jy") ||
           (styleIsJourney() ? document.querySelector(".road-jy") : null);
  }
  function rtlDoc() {
    return (document.documentElement.getAttribute("dir") || "rtl") === "rtl";
  }

  function setOrientation(v) {
    v = v === "horizontal" ? "horizontal" : "vertical";
    try { localStorage.setItem("myroad.roadOrientation", v); } catch (e) {}
    document.documentElement.setAttribute("data-road-orientation", v);
    document.querySelectorAll('input[name="road_orientation"]').forEach(function (r) {
      r.checked = r.value === v;
    });
    document.querySelectorAll("[data-jy-orient]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-jy-orient") === v ? "true" : "false");
    });
    layout(true);
  }
  window.myroadSetRoadOrientation = setOrientation;

  function syncOrientControls() {
    var v = orientation();
    document.querySelectorAll("[data-jy-orient]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-jy-orient") === v ? "true" : "false");
    });
    document.querySelectorAll('input[name="road_orientation"]').forEach(function (r) {
      r.checked = r.value === v;
    });
  }

  function syncCanvasRole(jy, horiz) {
    var field = jy && jy.querySelector(".jy-field");
    if (!field) return;
    if (horiz) {
      field.setAttribute("tabindex", "0");
      field.setAttribute("role", "region");
    } else {
      field.removeAttribute("tabindex");
      if (field.getAttribute("role") === "region") field.removeAttribute("role");
    }
  }

  function layout(scrollToHere) {
    var jy = root();
    if (!jy) return;
    var horiz = isHorizontal();
    jy.classList.toggle("is-horizontal", horiz);
    jy.classList.toggle("is-vertical", !horiz);
    jy.classList.add("is-laid");
    syncCanvasRole(jy, horiz);
    if (scrollToHere) scrollHere(jy, horiz);
  }

  function continueBar() {
    var style = document.documentElement.getAttribute("data-road-style") || "timeline";
    var panel = document.querySelector('[data-road-style-panel="' + style + '"]');
    return (panel && panel.querySelector("[data-tl-continue], [data-jy-continue]")) ||
           document.querySelector("[data-jy-continue], .jy-continue, [data-tl-continue]");
  }

  function barFloor() {
    var floor = window.innerHeight || document.documentElement.clientHeight;
    var bar = continueBar();
    if (bar && !bar.hidden) {
      var br = bar.getBoundingClientRect();
      if (br.height && br.top > 0 && br.top < floor) floor = br.top;
    }
    return floor;
  }

  function scrollHere(jy, horiz) {
    var here = document.getElementById("jy-here") ||
               (jy && jy.querySelector("[data-jy-current], .jy-step.is-here"));
    if (!here || !jy) return;
    if (window.location.hash) return;

    function adjust() {
      var hr = here.getBoundingClientRect();
      if (horiz) {
        var field = jy.querySelector(".jy-field");
        if (!field) return;
        var fr = field.getBoundingClientRect();
        var mid = hr.left + hr.width / 2;
        var target = field.scrollLeft + (mid - fr.left) - fr.width / 2;
        field.scrollTo({ left: target, behavior: "auto" });
        var floor = barFloor();
        if (hr.bottom > floor - 12) {
          window.scrollBy({ top: hr.bottom - (floor - 12), behavior: "auto" });
        }
        return;
      }
      var floor = barFloor();
      var pad = 16;
      var visible = floor - 8;
      var targetMid = 8 + visible * 0.48;
      var mid = hr.top + hr.height / 2;
      var delta = mid - targetMid;
      if (hr.top - delta < 8) delta = hr.top - 8;
      if (hr.bottom - delta > floor - pad) delta = hr.bottom - (floor - pad);
      if (Math.abs(delta) > 2) window.scrollBy({ top: delta, behavior: "auto" });
    }

    here.scrollIntoView({
      block: "center",
      inline: horiz ? "center" : "nearest",
      behavior: "auto"
    });
    adjust();
    setTimeout(adjust, 50);
    setTimeout(adjust, 180);
    watchBar(jy, adjust);
  }
  window.myroadScrollJourneyHere = function () {
    var jy = root();
    if (jy) scrollHere(jy, isHorizontal());
  };

  function watchBar(jy, adjust) {
    var bar = continueBar();
    if (!bar || jy.__jyBarWatch) return;
    jy.__jyBarWatch = true;
    if (typeof MutationObserver !== "undefined") {
      new MutationObserver(function () { adjust(); }).observe(bar, {
        attributes: true,
        attributeFilter: ["hidden"]
      });
    }
  }

  function onKey(e) {
    if (!isHorizontal()) return;
    var jy = root();
    if (!jy) return;
    var field = jy.querySelector(".jy-field");
    if (!field) return;
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Home" && e.key !== "End") return;
    if (!jy.contains(document.activeElement) && document.activeElement !== field) return;
    var stages = [].slice.call(jy.querySelectorAll(".jy-stage"));
    if (!stages.length) return;
    var rtl = rtlDoc();
    var idx = 0, i, r, best = 1e9;
    var cr = field.getBoundingClientRect();
    var mid = (cr.left + cr.right) / 2;
    for (i = 0; i < stages.length; i++) {
      r = stages[i].querySelector(".jy-step");
      r = (r || stages[i]).getBoundingClientRect();
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
    var target = stages[next].querySelector(".jy-step") || stages[next];
    var behavior = reduceMotion() ? "auto" : "smooth";
    try {
      target.scrollIntoView({ inline: "center", block: "nearest", behavior: behavior });
    } catch (err) {
      target.scrollIntoView(true);
    }
  }

  var t = null;
  function schedule(scrollToHere) {
    if (t) cancelAnimationFrame(t);
    t = requestAnimationFrame(function () { t = null; layout(!!scrollToHere); });
  }

  function bind(jy) {
    if (!jy || jy.__jyBound) return;
    jy.__jyBound = true;
    jy.addEventListener("click", function (e) {
      var btn = e.target.closest && e.target.closest("[data-jy-orient]");
      if (!btn) return;
      e.preventDefault();
      setOrientation(btn.getAttribute("data-jy-orient"));
    });
    var field = jy.querySelector(".jy-field");
    if (field) field.addEventListener("keydown", onKey);
  }

  function init() {
    syncOrientControls();
    if (!styleIsJourney()) return;
    var jy = root();
    bind(jy);
    layout(true);
    if (!window.__jyRoadResize) {
      window.__jyRoadResize = true;
      window.addEventListener("resize", function () { schedule(false); }, { passive: true });
      if (window.matchMedia) {
        var mq = window.matchMedia(WIDE);
        var onMq = function () { schedule(true); };
        if (mq.addEventListener) mq.addEventListener("change", onMq);
        else if (mq.addListener) mq.addListener(onMq);
      }
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  window.myroadDrawJourneyRoad = function () { schedule(false); };
})();
