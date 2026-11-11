/* Stepping-stones journey: place stones on a gentle meander, draw a worn trail
   with a teal walked-path glow, support horizontal layout, keyboard scrolling,
   and sticky-bar-aware scroll to the current stone. No-JS keeps a centred
   column (or row). Recalculates on resize. Respects reduced motion. */
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
    syncCanvasRole(jy, horiz);
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
      fieldH = Math.max(field.clientHeight || 0, 520);
      fieldW = pad * 2 + Math.max(n, 1) * pitch + (endEl ? size * 1.6 + 240 : 120);
      canvas.style.inlineSize = fieldW + "px";
      canvas.style.blockSize = fieldH + "px";
      path.style.inlineSize = fieldW + "px";
      path.style.blockSize = fieldH + "px";
    } else {
      fieldW = field.clientWidth || jy.clientWidth || 320;
      fieldH = pad * 2 + Math.max(n, 1) * pitch + (endEl ? 140 : 48) + 88;
      canvas.style.inlineSize = "100%";
      canvas.style.blockSize = fieldH + "px";
      path.style.inlineSize = "100%";
      path.style.blockSize = fieldH + "px";
    }

    var mid = (horiz ? fieldH : fieldW) / 2;
    var amp = Math.min(ampMax, horiz ? fieldH * 0.18 : fieldW * 0.2);
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
      el.classList.toggle("label-towards-start", off >= 0);
      el.classList.toggle("label-towards-end", off < 0);
    });

    if (endEl) {
      var alongEnd = pad + n * pitch + (horiz ? 8 : 4);
      var endW = endEl.offsetWidth || 180;
      endEl.style.transform = "";
      if (horiz) {
        endEl.style.insetInlineStart = alongEnd + "px";
        endEl.style.insetBlockStart = Math.max(12, mid - (endEl.offsetHeight || 100) / 2) + "px";
      } else {
        endEl.style.insetBlockStart = alongEnd + "px";
        endEl.style.insetInlineStart = Math.max(8, mid - endW / 2) + "px";
      }
    }

    jy.classList.add("is-laid");
    placeLabels(jy, steps, horiz, size, fieldW, fieldH, amp, mid, pad, pitch);
    drawTrail(svg, canvas, steps, endEl, horiz, size);
    if (scrollToHere) scrollHere(jy, horiz);
  }

  function placeLabels(jy, steps, horiz, size, fieldW, fieldH, amp, mid, pad, pitch) {
    var labels = [].slice.call(jy.querySelectorAll(".jy-stage-label"));
    var canvas = jy.querySelector(".jy-canvas");
    labels.forEach(function (label) {
      var stage = label.closest(".jy-stage") || label.parentElement;
      var first = stage ? stage.querySelector(".jy-step") : null;
      if (!first) return;
      var idx = steps.indexOf(first);
      var off = offsetAt(Math.max(idx, 0), amp);
      var along = pad + Math.max(idx, 0) * pitch;
      var labelW = Math.min(label.offsetWidth || 180, horiz ? 176 : 216);
      var labelH = label.offsetHeight || 72;
      if (horiz) {
        // Always above the first stone. Grow toward the walked side (inline-start)
        // so a plaque at the upcoming (end) edge stays inside the field.
        var above = mid + off - size / 2 - labelH - 18;
        if (above < 10) above = mid + off + size / 2 + 18;
        label.style.insetBlockStart = above + "px";
        // Align the label's inline-end with the stone's inline-end: the plaque
        // extends toward inline-start (walked / already-visible).
        label.style.insetInlineStart = "auto";
        var endFromStart = along + size;
        var endFromEnd = fieldW - endFromStart;
        label.style.insetInlineEnd = Math.max(8, endFromEnd) + "px";
        label.style.maxInlineSize = "11rem";
        label.style.textAlign = "";
      } else {
        label.style.insetBlockStart = Math.max(8, along - 4) + "px";
        var towardStart = off >= 0;
        var side = mid + off + (towardStart ? -(size / 2 + 14 + labelW) : (size / 2 + 14));
        side = Math.max(8, Math.min(side, fieldW - labelW - 8));
        label.style.insetInlineStart = side + "px";
        label.style.insetInlineEnd = "auto";
      }
    });
    // Final clamp: keep plaques inside the canvas (not the scrollport — that is
    // handled by aligning toward the walked side).
    if (canvas) clampToCanvas(jy, canvas);
  }

  function clampToCanvas(jy, canvas) {
    var cr = canvas.getBoundingClientRect();
    var pad = 8;
    var rtl = rtlDoc();
    jy.querySelectorAll(".jy-stage-label").forEach(function (el) {
      var lr = el.getBoundingClientRect();
      if (!lr.width) return;
      var dx = 0, dy = 0;
      if (lr.left < cr.left + pad) dx = (cr.left + pad) - lr.left;
      if (lr.right > cr.right - pad) dx += (cr.right - pad) - lr.right;
      if (lr.top < cr.top + pad) dy = (cr.top + pad) - lr.top;
      if (lr.bottom > cr.bottom - pad) dy += (cr.bottom - pad) - lr.bottom;
      if (!dx && !dy) return;
      var curI = el.style.insetInlineStart;
      var curE = el.style.insetInlineEnd;
      var curB = parseFloat(el.style.insetBlockStart) || 0;
      var logicalDx = rtl ? -dx : dx;
      if (curI && curI !== "auto" && curI.indexOf("%") === -1) {
        el.style.insetInlineStart = (parseFloat(curI) + logicalDx) + "px";
      } else if (curE && curE !== "auto") {
        el.style.insetInlineEnd = Math.max(8, parseFloat(curE) - logicalDx) + "px";
      }
      el.style.insetBlockStart = (curB + dy) + "px";
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
    if (steps[0]) {
      var c0 = center(steps[0]);
      if (horiz) {
        var dir = rtlDoc() ? -1 : 1;
        pts.push({ x: c0.x - size * 0.8 * dir, y: c0.y });
      } else {
        pts.push({ x: c0.x, y: Math.max(0, c0.y - size * 0.8) });
      }
    }
    steps.forEach(function (el) { pts.push(center(el)); });
    if (endEl) {
      var es = endEl.querySelector(".jy-end-stone") || endEl;
      pts.push(center(es));
    }
    var d = smooth(pts);
    var ahead = svg.querySelector(".jy-worn-ahead");
    var done = svg.querySelector(".jy-worn-done");
    var halo = svg.querySelector(".jy-glow-halo");
    var core = svg.querySelector(".jy-glow-core");
    if (ahead) ahead.setAttribute("d", d);
    var here = canvas.querySelector(".jy-step.is-here") ||
               (canvas.querySelector(".jy-end.is-done") ? endEl : null);
    var anyWalked = canvas.querySelector(".jy-step.is-done, .jy-step.is-here, .jy-end.is-done");
    function dashTo(path, targetEl) {
      if (!path) return;
      if (!anyWalked || !d) { path.setAttribute("d", ""); return; }
      path.setAttribute("d", d);
      if (!targetEl) { path.removeAttribute("stroke-dasharray"); return; }
      var len = 0;
      try { len = path.getTotalLength(); } catch (e) { len = 0; }
      if (!len) return;
      var hr = (targetEl.querySelector(".jy-stone") || targetEl).getBoundingClientRect();
      var hx = hr.left - cr.left + hr.width / 2;
      var hy = hr.top - cr.top + hr.height / 2;
      var target = 0, best = 1e9, i, pt, stepsN = 120;
      for (i = 0; i <= stepsN; i++) {
        pt = path.getPointAtLength((len * i) / stepsN);
        var err = (pt.x - hx) * (pt.x - hx) + (pt.y - hy) * (pt.y - hy);
        if (err < best) { best = err; target = (len * i) / stepsN; }
      }
      target = Math.min(len, target + 8);
      path.setAttribute("stroke-dasharray", target.toFixed(1) + " " + len.toFixed(1));
    }
    if (done) dashTo(done, here);
    if (halo) dashTo(halo, here);
    if (core) dashTo(core, here);
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
        // Vertically, keep the stone inside the field and above the page's sticky bar.
        var floor = barFloor();
        if (hr.bottom > floor - 12) {
          window.scrollBy({ top: hr.bottom - (floor - 12), behavior: "auto" });
        }
        return;
      }
      var floor = barFloor();
      var pad = 16;
      // Sit in the upper-middle of the area above the bar, so the current stone
      // is never hidden and the next plaque has a little air above the bar.
      var visible = floor - 8;
      var targetMid = 8 + visible * 0.38;
      var mid = hr.top + hr.height / 2;
      var delta = mid - targetMid;
      // If the stone would go above the top, don't.
      if (hr.top - delta < 8) delta = hr.top - 8;
      // If after the move the stone would still sit under the bar, push it up.
      if (hr.bottom - delta > floor - pad) delta = hr.bottom - (floor - pad);
      if (Math.abs(delta) > 2) window.scrollBy({ top: delta, behavior: "auto" });
    }

    here.scrollIntoView({
      block: "center",
      inline: horiz ? "center" : "nearest",
      behavior: "auto"
    });
    adjust();
    // The sticky bar is `hidden` until IntersectionObserver reveals it; adjust again.
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
