/* Stepping-stones journey: place square stones along a gentle meander in the lawn,
   draw a worn trail through them, and support a horizontal layout on wide screens.
   No-JS keeps a centred column (or row). Recalculates on resize. Respects reduced motion. */
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

  function setOrientation(v) {
    v = v === "horizontal" ? "horizontal" : "vertical";
    try { localStorage.setItem("myroad.roadOrientation", v); } catch (e) {}
    document.documentElement.setAttribute("data-road-orientation", v);
    document.querySelectorAll('input[name="road_orientation"], input[name="jy_orient"]').forEach(function (r) {
      r.checked = r.value === v;
    });
    layout(true);
  }
  window.myroadSetRoadOrientation = setOrientation;

  function syncOrientRadios() {
    var v = orientation();
    document.querySelectorAll('input[name="jy_orient"]').forEach(function (r) {
      r.checked = r.value === v;
    });
  }

  function offsetAt(i, amp) {
    var t = i / 5.5;
    return Math.sin(t * Math.PI) * amp + Math.sin(t * Math.PI * 0.37) * amp * 0.22;
  }

  function smooth(pts) {
    if (!pts.length) return "";
    var d = "M " + pts[0].x.toFixed(1) + " " + pts[0].y.toFixed(1);
    for (var i = 1; i < pts.length; i++) {
      var p0 = pts[i - 1], p1 = pts[i];
      var dx = p1.x - p0.x, dy = p1.y - p0.y;
      var c = Math.max(16, Math.sqrt(dx * dx + dy * dy) * 0.42);
      var lx = dx / (Math.abs(dx) + Math.abs(dy) + 0.001);
      var ly = dy / (Math.abs(dx) + Math.abs(dy) + 0.001);
      d += " C " + (p0.x + lx * c).toFixed(1) + " " + (p0.y + ly * c).toFixed(1) +
           ", " + (p1.x - lx * c).toFixed(1) + " " + (p1.y - ly * c).toFixed(1) +
           ", " + p1.x.toFixed(1) + " " + p1.y.toFixed(1);
    }
    return d;
  }

  function layout(scrollToHere) {
    var jy = root();
    if (!jy) return;
    var horiz = isHorizontal();
    jy.classList.toggle("is-horizontal", horiz);
    jy.classList.toggle("is-vertical", !horiz);
    var field = jy.querySelector(".jy-field");
    var canvas = jy.querySelector(".jy-canvas");
    var path = jy.querySelector(".jy-path");
    var svg = jy.querySelector("svg.jy-ground");
    if (!field || !canvas || !path) return;

    var steps = [].slice.call(jy.querySelectorAll(".jy-step"));
    var endEl = jy.querySelector(".jy-end");
    var cs = getComputedStyle(jy);
    var size = parseFloat(cs.getPropertyValue("--jy-stone-size")) || 64;
    var gap = parseFloat(cs.getPropertyValue("--jy-gap")) || 28;
    var pad = parseFloat(cs.getPropertyValue("--jy-pad")) || 48;
    var ampMax = parseFloat(cs.getPropertyValue("--jy-amp")) || 64;
    var pitch = size + gap;
    var n = steps.length;

    var fieldW, fieldH;
    if (horiz) {
      fieldH = Math.max(field.clientHeight || 0, 420);
      fieldW = pad * 2 + Math.max(n, 1) * pitch + (endEl ? size * 1.6 + 200 : 80);
      canvas.style.inlineSize = fieldW + "px";
      canvas.style.blockSize = fieldH + "px";
      path.style.inlineSize = fieldW + "px";
      path.style.blockSize = fieldH + "px";
    } else {
      fieldW = field.clientWidth || jy.clientWidth || 320;
      fieldH = pad * 2 + Math.max(n, 1) * pitch + (endEl ? 120 : 32);
      canvas.style.inlineSize = "100%";
      canvas.style.blockSize = fieldH + "px";
      path.style.inlineSize = "100%";
      path.style.blockSize = fieldH + "px";
    }

    var mid = (horiz ? fieldH : fieldW) / 2;
    var amp = Math.min(ampMax, horiz ? fieldH * 0.22 : fieldW * 0.2);
    if (n < 4) amp *= 0.45;

    steps.forEach(function (el, i) {
      var off = offsetAt(i, amp);
      var along = pad + i * pitch;
      if (horiz) {
        el.style.insetInlineStart = along + "px";
        el.style.insetBlockStart = (mid + off - size / 2) + "px";
      } else {
        el.style.insetBlockStart = along + "px";
        el.style.insetInlineStart = (mid + off - size / 2) + "px";
      }
      el.style.inlineSize = size + "px";
      el.style.blockSize = size + "px";
      // Put the caption on the side with more room (opposite the meander).
      el.classList.toggle("label-towards-start", off >= 0);
      el.classList.toggle("label-towards-end", off < 0);
    });

    if (endEl) {
      var alongEnd = pad + n * pitch + (horiz ? 8 : 4);
      var endW = endEl.offsetWidth || 180;
      if (horiz) {
        endEl.style.insetInlineStart = alongEnd + "px";
        endEl.style.insetBlockStart = Math.max(12, mid - (endEl.offsetHeight || 100) / 2) + "px";
        endEl.style.transform = "";
      } else {
        endEl.style.insetBlockStart = alongEnd + "px";
        endEl.style.insetInlineStart = Math.max(8, mid - endW / 2) + "px";
        endEl.style.transform = "";
      }
    }

    placeLabels(jy, steps, horiz, size, fieldW, fieldH, amp, mid, pad, pitch);
    jy.classList.add("is-laid");
    clampLabels(jy, canvas);
    drawTrail(svg, canvas, steps, endEl, horiz, size);

    jy.classList.add("is-laid");
    if (scrollToHere) scrollHere(jy, horiz);
  }

  function placeLabels(jy, steps, horiz, size, fieldW, fieldH, amp, mid, pad, pitch) {
    var labels = [].slice.call(jy.querySelectorAll(".jy-stage-label"));
    labels.forEach(function (label) {
      var stage = label.closest(".jy-stage") || label.parentElement;
      var first = stage ? stage.querySelector(".jy-step") : null;
      if (!first) return;
      var idx = steps.indexOf(first);
      var off = offsetAt(Math.max(idx, 0), amp);
      var along = pad + Math.max(idx, 0) * pitch;
      var labelW = Math.min(label.offsetWidth || 200, 220);
      var labelH = label.offsetHeight || 64;
      // Vertical: sit beside the first stone, on the roomier side.
      // Horizontal: sit above (or below) the stone, centred on it, so a scroll edge cannot clip the plaque.
      var towardStart = off >= 0;
      if (horiz) {
        label.style.insetInlineStart = Math.max(8, along + size / 2 - labelW / 2) + "px";
        var above = mid + off - size / 2 - labelH - 16;
        var below = mid + off + size / 2 + 16;
        label.style.insetBlockStart = (above >= 8 ? above : Math.min(below, fieldH - labelH - 8)) + "px";
      } else {
        label.style.insetBlockStart = Math.max(8, along - 4) + "px";
        var side = mid + off + (towardStart ? -(size / 2 + 14 + labelW) : (size / 2 + 14));
        side = Math.max(8, Math.min(side, fieldW - labelW - 8));
        label.style.insetInlineStart = side + "px";
      }
    });
  }

  function drawTrail(svg, canvas, steps, endEl, horiz, size) {
    if (!svg || !canvas) return;
    var cr = canvas.getBoundingClientRect();
    var w = canvas.offsetWidth || cr.width;
    var h = canvas.offsetHeight || cr.height;
    svg.setAttribute("viewBox", "0 0 " + Math.max(1, w) + " " + Math.max(1, h));
    svg.setAttribute("width", String(Math.max(1, w)));
    svg.setAttribute("height", String(Math.max(1, h)));
    var pts = [];
    function center(el) {
      var r = el.getBoundingClientRect();
      return { x: r.left - cr.left + r.width / 2, y: r.top - cr.top + r.height / 2 };
    }
    // Start a little before the first stone so the trail eases in from the lawn.
    if (steps[0]) {
      var c0 = center(steps[0]);
      if (horiz) pts.push({ x: c0.x - (size * 0.8) * (document.documentElement.dir === "rtl" ? -1 : 1), y: c0.y });
      else pts.push({ x: c0.x, y: Math.max(0, c0.y - size * 0.8) });
    }
    steps.forEach(function (el) { pts.push(center(el)); });
    if (endEl) {
      var es = endEl.querySelector(".jy-end-stone") || endEl;
      pts.push(center(es));
    }
    var d = smooth(pts);
    var ahead = svg.querySelector(".jy-worn-ahead");
    var done = svg.querySelector(".jy-worn-done");
    if (ahead) ahead.setAttribute("d", d);
    if (done) {
      var here = canvas.querySelector(".jy-step.is-here") ||
                 (canvas.querySelector(".jy-end.is-done") ? endEl : null);
      if (here && d) {
        done.setAttribute("d", d);
        var len = 0;
        try { len = done.getTotalLength(); } catch (e) { len = 0; }
        if (len) {
          var hr = (here.querySelector(".jy-stone") || here).getBoundingClientRect();
          var hx = hr.left - cr.left + hr.width / 2;
          var hy = hr.top - cr.top + hr.height / 2;
          var target = 0, best = 1e9, i, pt;
          var stepsN = 120;
          for (i = 0; i <= stepsN; i++) {
            pt = done.getPointAtLength((len * i) / stepsN);
            var err = (pt.x - hx) * (pt.x - hx) + (pt.y - hy) * (pt.y - hy);
            if (err < best) { best = err; target = (len * i) / stepsN; }
          }
          done.setAttribute("stroke-dasharray", target + " " + len);
        }
      } else if (canvas.querySelector(".jy-end.is-done") && d) {
        done.setAttribute("d", d);
        done.removeAttribute("stroke-dasharray");
      } else {
        done.setAttribute("d", "");
      }
    }
  }


  function clampLabels(jy, canvas) {
    if (!canvas) return;
    var cr = canvas.getBoundingClientRect();
    var pad = 10;
    var rtl = (document.documentElement.getAttribute("dir") || "rtl") === "rtl";
    jy.querySelectorAll(".jy-stage-label, .jy-end").forEach(function (el) {
      var lr = el.getBoundingClientRect();
      if (!lr.width) return;
      var dx = 0, dy = 0;
      if (lr.left < cr.left + pad) dx = (cr.left + pad) - lr.left;
      if (lr.right > cr.right - pad) dx += (cr.right - pad) - lr.right;
      if (lr.top < cr.top + pad) dy = (cr.top + pad) - lr.top;
      if (lr.bottom > cr.bottom - pad) dy += (cr.bottom - pad) - lr.bottom;
      if (!dx && !dy) return;
      var curI = el.style.insetInlineStart;
      var curB = parseFloat(el.style.insetBlockStart) || 0;
      var logicalDx = rtl ? -dx : dx;
      if (curI && curI.indexOf("%") === -1) {
        el.style.insetInlineStart = (parseFloat(curI) + logicalDx) + "px";
      } else {
        el.style.translate = logicalDx + "px " + dy + "px";
      }
      el.style.insetBlockStart = (curB + dy) + "px";
    });
  }


  function scrollHere(jy, horiz) {
    var here = document.getElementById("jy-here") || jy.querySelector(".jy-step.is-here");
    if (!here) return;
    var reduce = reduceMotion();
    // Instant: this is a load-time position, and a smooth scroll can finish after
    // a test (or the learner) looks at the page.
    here.scrollIntoView({
      block: "center",
      inline: horiz ? "center" : "nearest",
      behavior: "auto"
    });
  }

  var t = null;
  function schedule(scrollToHere) {
    if (t) cancelAnimationFrame(t);
    t = requestAnimationFrame(function () { t = null; layout(!!scrollToHere); });
  }

  function bindOrient(jy) {
    if (!jy || jy.__jyOrientBound) return;
    jy.__jyOrientBound = true;
    var fs = jy.querySelector(".jy-orient");
    if (!fs) return;
    fs.addEventListener("change", function (e) {
      if (!e.target || e.target.name !== "jy_orient") return;
      setOrientation(e.target.value);
    });
  }

  function init() {
    if (!styleIsJourney()) return;
    syncOrientRadios();
    var jy = root();
    bindOrient(jy);
    layout(true);
    if (!window.__jyRoadResize) {
      window.__jyRoadResize = true;
      window.addEventListener("resize", function () { schedule(false); }, { passive: true });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  window.myroadDrawJourneyRoad = function () { schedule(false); };
})();
