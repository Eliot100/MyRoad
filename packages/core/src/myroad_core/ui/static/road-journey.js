/* Draw a winding asphalt road through the journey-style stage cards.
   Measures card centres and builds a smooth cubic path. No-JS keeps the CSS fallback ribbon.
   Recalculates on resize. Respects reduced motion (no animated dash). */
(function () {
  function styleIsJourney() {
    return (document.documentElement.getAttribute("data-road-style") || "timeline") === "journey";
  }
  function root() {
    return document.querySelector("html[data-road-style='journey'] .road-jy") ||
           (styleIsJourney() ? document.querySelector(".road-jy") : null);
  }
  function pointsFor(wrap, stages, endEl, rtl) {
    var wr = wrap.getBoundingClientRect();
    var w = wr.width, h = wrap.scrollHeight || wr.height;
    var mid = w / 2;
    var ampAttr = getComputedStyle(wrap.closest(".road-jy") || wrap).getPropertyValue("--jy-amp");
    var amp = parseFloat(ampAttr) || Math.min(w * 0.18, 96);
    if (w < 720) {
      // Mobile: the road runs along the reading-start edge and weaves slightly inward.
      mid = rtl ? (w - 22) : 22;
      amp = Math.min(amp, 28);
    }
    var pts = [{ x: mid, y: 0 }];
    for (var i = 0; i < stages.length; i++) {
      var r = stages[i].getBoundingClientRect();
      var y = r.top - wr.top + r.height / 2;
      var side = (i % 2 === 0) ? 1 : -1;
      if (rtl) side = -side;
      // On wide screens the road bows toward the card (card is on start side first).
      // Start side in RTL is the right half, which is a positive x from centre? 
      // First card is grid-column 1 = start = right in RTL = higher x.
      // side +1 should move toward the first card.
      if (w >= 720) {
        var towardStart = rtl ? 1 : -1;
        side = (i % 2 === 0) ? towardStart : -towardStart;
      } else {
        // Weave inward from the start-edge ribbon.
        side = rtl ? -1 : 1;
        if (i % 2) side = -side * 0.35;
        else side = side * 0.15;
      }
      pts.push({ x: mid + side * amp, y: y });
    }
    if (endEl) {
      var er = endEl.getBoundingClientRect();
      pts.push({ x: mid, y: er.top - wr.top + er.height / 2 });
    }
    pts.push({ x: mid, y: h });
    return { pts: pts, w: w, h: h };
  }
  function smooth(pts) {
    if (!pts.length) return "";
    var d = "M " + pts[0].x.toFixed(1) + " " + pts[0].y.toFixed(1);
    for (var i = 1; i < pts.length; i++) {
      var p0 = pts[i - 1], p1 = pts[i];
      var dy = p1.y - p0.y;
      var c = Math.max(24, dy * 0.42);
      d += " C " + p0.x.toFixed(1) + " " + (p0.y + c).toFixed(1) +
           ", " + p1.x.toFixed(1) + " " + (p1.y - c).toFixed(1) +
           ", " + p1.x.toFixed(1) + " " + p1.y.toFixed(1);
    }
    return d;
  }
  function pathLength(path) {
    try { return path.getTotalLength(); } catch (e) { return 0; }
  }
  function draw() {
    var jy = root();
    if (!jy) return;
    var wrap = jy.querySelector(".jy-canvas");
    var svg = jy.querySelector("svg.jy-road");
    var pave = jy.querySelector(".jy-pave-path");
    var edge = jy.querySelector(".jy-edge-path");
    var dash = jy.querySelector(".jy-dash-path");
    var done = jy.querySelector(".jy-done-path");
    if (!wrap || !svg || !pave) return;
    var stages = jy.querySelectorAll(".jy-stage");
    var endEl = jy.querySelector(".jy-end");
    var rtl = (document.documentElement.getAttribute("dir") || "rtl") === "rtl";
    var m = pointsFor(wrap, stages, endEl, rtl);
    svg.setAttribute("viewBox", "0 0 " + m.w + " " + m.h);
    svg.setAttribute("width", String(m.w));
    svg.setAttribute("height", String(m.h));
    var d = smooth(m.pts);
    pave.setAttribute("d", d);
    if (edge) edge.setAttribute("d", d);
    if (dash) dash.setAttribute("d", d);
    // The walked part of the road is solid teal up to the current שלב (or the end if finished).
    if (done) {
      var here = jy.querySelector(".jy-stage.is-here") || (jy.querySelector(".jy-end.is-done") ? endEl : null);
      if (here) {
        var wr = wrap.getBoundingClientRect();
        var hr = here.getBoundingClientRect();
        var y = hr.top - wr.top + (here.classList.contains("jy-end") ? hr.height / 2 : 0);
        // Use a second path clipped by length: copy the path and dash it to the here y via getPoint.
        done.setAttribute("d", d);
        var len = pathLength(done);
        if (len) {
          // Find length along the path closest to y of the current שלב's top.
          var target = 0, best = 1e9, i, pt;
          var steps = 80;
          for (i = 0; i <= steps; i++) {
            pt = done.getPointAtLength((len * i) / steps);
            var err = Math.abs(pt.y - y);
            if (err < best) { best = err; target = (len * i) / steps; }
          }
          done.setAttribute("stroke-dasharray", target + " " + len);
        }
      } else {
        done.setAttribute("d", "");
      }
    }
    jy.classList.add("is-drawn");
  }
  var t = null;
  function schedule() {
    if (t) cancelAnimationFrame(t);
    t = requestAnimationFrame(function () { t = null; draw(); });
  }
  function init() {
    if (!styleIsJourney()) return;
    draw();
    if (!window.__jyRoadResize) {
      window.__jyRoadResize = true;
      window.addEventListener("resize", schedule, { passive: true });
    }
    // Recalculate when a שלב opens or closes (height changes).
    var jy = root();
    if (jy && !jy.__jyBound) {
      jy.__jyBound = true;
      jy.addEventListener("toggle", schedule, true);
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  window.myroadDrawJourneyRoad = schedule;
})();
