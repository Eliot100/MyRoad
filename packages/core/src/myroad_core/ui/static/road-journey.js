/* Stepping-stones journey: draw the progress glow through stone centres,
   wire the orientation toggle, and scroll the current stone into view.
   No-JS keeps a centred winding column (CSS). Recalculates on resize.
   Respects reduced motion. Horizontal orientation is wide screens only. */
(function () {
  var WIDE = 1024;

  function styleIsJourney() {
    return (document.documentElement.getAttribute("data-road-style") || "timeline") === "journey";
  }
  function orientation() {
    var o = document.documentElement.getAttribute("data-road-orientation") || "vertical";
    return o === "horizontal" ? "horizontal" : "vertical";
  }
  function isWide() {
    return window.matchMedia && window.matchMedia("(min-width: " + WIDE + "px)").matches;
  }
  function isHorizontal() {
    return styleIsJourney() && orientation() === "horizontal" && isWide();
  }
  function reduceMotion() {
    return window.myroadReduceMotion ? window.myroadReduceMotion() : !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }
  function root() {
    return document.querySelector("html[data-road-style='journey'] .road-jy") ||
           (styleIsJourney() ? document.querySelector(".road-jy") : null);
  }

  function setOrientation(v) {
    v = v === "horizontal" ? "horizontal" : "vertical";
    try { localStorage.setItem("myroad.roadOrientation", v); } catch (e) {}
    document.documentElement.setAttribute("data-road-orientation", v);
    document.querySelectorAll('input[name="road_orientation"], input[name="jy_orientation"]').forEach(function (r) {
      r.checked = r.value === v;
    });
    schedule();
    window.setTimeout(scrollCurrent, 40);
  }
  window.myroadRoadOrientation = function () {
    return document.documentElement.getAttribute("data-road-orientation") || "vertical";
  };
  window.myroadSetRoadOrientation = setOrientation;

  function pointsFor(wrap, stones, endEl) {
    var wr = wrap.getBoundingClientRect();
    var w = wrap.scrollWidth || wr.width;
    var h = wrap.scrollHeight || wr.height;
    var pts = [];
    function centre(el) {
      var r = el.getBoundingClientRect();
      var pad = el.querySelector(".jy-pad, .jy-flag") || el;
      var pr = pad.getBoundingClientRect();
      return {
        x: pr.left - wr.left + wrap.scrollLeft + pr.width / 2,
        y: pr.top - wr.top + wrap.scrollTop + pr.height / 2
      };
    }
    for (var i = 0; i < stones.length; i++) pts.push(centre(stones[i]));
    if (endEl) pts.push(centre(endEl));
    return { pts: pts, w: w, h: h };
  }
  function smooth(pts) {
    if (!pts.length) return "";
    var d = "M " + pts[0].x.toFixed(1) + " " + pts[0].y.toFixed(1);
    for (var i = 1; i < pts.length; i++) {
      var p0 = pts[i - 1], p1 = pts[i];
      var dx = p1.x - p0.x, dy = p1.y - p0.y;
      var c = Math.max(16, Math.sqrt(dx * dx + dy * dy) * 0.38);
      if (isHorizontal()) {
        var sx = (dx >= 0 ? 1 : -1) * c;
        d += " C " + (p0.x + sx).toFixed(1) + " " + p0.y.toFixed(1) +
             ", " + (p1.x - sx).toFixed(1) + " " + p1.y.toFixed(1) +
             ", " + p1.x.toFixed(1) + " " + p1.y.toFixed(1);
      } else {
        var sy = (dy >= 0 ? 1 : -1) * c;
        d += " C " + p0.x.toFixed(1) + " " + (p0.y + sy).toFixed(1) +
             ", " + p1.x.toFixed(1) + " " + (p1.y - sy).toFixed(1) +
             ", " + p1.x.toFixed(1) + " " + p1.y.toFixed(1);
      }
    }
    return d;
  }
  function pathLength(path) {
    try { return path.getTotalLength(); } catch (e) { return 0; }
  }
  function dashTo(path, targetEl, wrap) {
    if (!path || !targetEl) {
      if (path) { path.setAttribute("stroke-dasharray", "0 1"); path.setAttribute("d", path.getAttribute("d") || ""); }
      return;
    }
    var len = pathLength(path);
    if (!len) return;
    var wr = wrap.getBoundingClientRect();
    var pad = targetEl.querySelector(".jy-pad, .jy-flag") || targetEl;
    var pr = pad.getBoundingClientRect();
    var tx = pr.left - wr.left + wrap.scrollLeft + pr.width / 2;
    var ty = pr.top - wr.top + wrap.scrollTop + pr.height / 2;
    var best = 1e9, target = 0, i, pt, err, steps = 120;
    for (i = 0; i <= steps; i++) {
      pt = path.getPointAtLength((len * i) / steps);
      err = (pt.x - tx) * (pt.x - tx) + (pt.y - ty) * (pt.y - ty);
      if (err < best) { best = err; target = (len * i) / steps; }
    }
    // A little past the stone centre so the glow meets the pad.
    target = Math.min(len, target + 8);
    path.setAttribute("stroke-dasharray", target.toFixed(1) + " " + len.toFixed(1));
  }

  function draw() {
    var jy = root();
    if (!jy) return;
    var wrap = jy.querySelector(".jy-canvas");
    var svg = jy.querySelector("svg.jy-glow");
    var halo = jy.querySelector(".jy-glow-halo");
    var core = jy.querySelector(".jy-glow-core");
    if (!wrap || !svg || !core) return;
    var stones = jy.querySelectorAll(".jy-stone");
    var endEl = jy.querySelector(".jy-end");
    var m = pointsFor(wrap, stones, endEl);
    if (!m.pts.length) return;
    svg.setAttribute("viewBox", "0 0 " + m.w + " " + m.h);
    svg.setAttribute("width", String(m.w));
    svg.setAttribute("height", String(m.h));
    var d = smooth(m.pts);
    if (halo) halo.setAttribute("d", d);
    core.setAttribute("d", d);
    var here = jy.querySelector(".jy-stone.is-here") ||
               (jy.querySelector(".jy-end.is-done") ? endEl : jy.querySelector(".jy-stone.is-done:last-of-type"));
    // If nothing is walked yet, hide the glow.
    var anyWalked = jy.querySelector(".jy-stone.is-done, .jy-stone.is-here, .jy-end.is-done");
    if (!anyWalked) {
      core.setAttribute("d", "");
      if (halo) halo.setAttribute("d", "");
    } else {
      dashTo(core, here, wrap);
      if (halo) dashTo(halo, here, wrap);
    }
    jy.classList.add("is-drawn");
  }

  function scrollCurrent() {
    var jy = root();
    if (!jy) return;
    var here = jy.querySelector("[data-jy-current]") || jy.querySelector("#jy-here");
    if (!here) return;
    if (window.location.hash) return;
    var reduce = reduceMotion();
    if (isHorizontal()) {
      var field = jy.querySelector(".jy-field");
      if (field) {
        var fr = field.getBoundingClientRect();
        var hr = here.getBoundingClientRect();
        var mid = hr.left + hr.width / 2;
        var target = field.scrollLeft + (mid - fr.left) - fr.width / 2;
        field.scrollTo({ left: target, behavior: reduce ? "auto" : "smooth" });
      } else {
        here.scrollIntoView({ inline: "center", block: "nearest", behavior: reduce ? "auto" : "smooth" });
      }
    } else {
      var r = here.getBoundingClientRect();
      var bar = document.querySelector("[data-jy-continue], .jy-continue, [data-tl-continue]");
      var floor = (window.innerHeight || document.documentElement.clientHeight);
      if (bar && !bar.hidden) {
        var br = bar.getBoundingClientRect();
        if (br.top > 0 && br.top < floor) floor = br.top;
      }
      var pad = 20;
      if (r.top >= 8 && r.bottom <= floor - pad) return;
      var delta = r.bottom - (floor - pad);
      if (r.top - delta < 8) delta = r.top - 8; /* don't scroll the stone off the top */
      window.scrollBy({ top: delta, behavior: reduce ? "auto" : "smooth" });
    }
  }

  var t = null;
  function schedule() {
    if (t) cancelAnimationFrame(t);
    t = requestAnimationFrame(function () { t = null; draw(); });
  }
  window.myroadDrawJourneyRoad = schedule;

  function bindOrient(rootEl) {
    if (!rootEl || rootEl.__jyOrientBound) return;
    rootEl.__jyOrientBound = true;
    rootEl.addEventListener("change", function (e) {
      var n = e.target && e.target.name;
      if (n !== "jy_orientation" && n !== "road_orientation") return;
      setOrientation(e.target.value);
      var msg = document.getElementById("road-style-saved") || document.getElementById("road-orient-saved");
      if (msg && msg.dataset && msg.dataset.savedLabel) msg.textContent = msg.dataset.savedLabel;
    });
  }

  function syncRadios() {
    var v = orientation();
    document.querySelectorAll('input[name="road_orientation"], input[name="jy_orientation"]').forEach(function (r) {
      r.checked = r.value === v;
    });
  }

  function init() {
    syncRadios();
    bindOrient(document.getElementById("road-style-prefs"));
    bindOrient(document.getElementById("road-orient-prefs"));
    var jy = root();
    if (jy) bindOrient(jy);
    if (!styleIsJourney()) return;
    draw();
    scrollCurrent();
    if (!window.__jyRoadResize) {
      window.__jyRoadResize = true;
      window.addEventListener("resize", schedule, { passive: true });
    }
    if (jy && !jy.__jyBound) {
      jy.__jyBound = true;
      jy.addEventListener("toggle", schedule, true);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
