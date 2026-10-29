/* Road world map (approved mockup option B, ported by hand: no library fits).
   Each שלב is a ring of משבצות, the בדיקה tile sits at the top, lit roads join opened
   שלבים, the end of the road is a gold hexagon. Data comes from #world-map data-stages
   (real stages and tiles). Review levels are sample data and only drawn in UI preview.
   No game mechanics here: no points, stars, streaks. */
(function () {
  "use strict";
  var host = document.getElementById("world-map");
  if (!host) return;
  var stages, L;
  try { stages = JSON.parse(host.dataset.stages || "[]"); L = JSON.parse(host.dataset.i18n || "{}"); } catch (e) { return; }
  if (!stages.length) return;
  var preview = host.dataset.preview === "1";
  var readOnly = host.dataset.readOnly === "1";
  var canvas = host.querySelector(".world-canvas");
  var NS = "http://www.w3.org/2000/svg";
  var list = document.querySelector(".world-list");

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function fill(tpl, o) { return String(tpl).replace(/\{(\w+)\}/g, function (_, k) { return o[k] != null ? o[k] : ""; }); }
  function clip(s, n) { s = String(s); return s.length > n ? s.slice(0, n - 1) + "…" : s; }
  function sampleLevel(t) { return t.state === "done" ? 1 + ((t.ix * 3) % 5) : 0; }

  var C = { done: ["#1aa596", "#0f766e", "#0a4f49", "#ffffff"], cur: ["#1aa596", "#0f766e", "#0a4f49", "#ffffff"],
            open: ["#13302d", "#0f2624", "#0a1a18", "#5fd3c4"], lock: ["#2a3432", "#222b29", "#1a2220", "#56625f"] };
  var gid = 0;

  function glyph(t, c, s) {
    if (t.check) return '<rect x="' + (-5 * s) + '" y="' + (-5 * s) + '" width="' + 10 * s + '" height="' + 10 * s + '" rx="' + 1.6 * s + '" transform="rotate(45)" fill="' + c + '"/>';
    if (t.review) return '<circle r="' + 6.5 * s + '" fill="none" stroke="' + c + '" stroke-width="' + 1.8 * s + '"/><circle r="' + 2.4 * s + '" fill="' + c + '"/>';
    if (t.state === "done") return '<path d="M' + (-5 * s) + ',0 L' + (-1.5 * s) + ',' + 3.5 * s + ' L' + 5 * s + ',' + (-4 * s) + '" fill="none" stroke="' + c + '" stroke-width="' + 2.2 * s + '" stroke-linecap="round" stroke-linejoin="round"/>';
    return '<circle r="' + 4.5 * s + '" fill="' + c + '"/>';
  }
  function levelArc(r, lv, decay) {
    var o = "", on = decay ? "#c9a227" : "#5fd3c4";
    for (var k = 0; k < 5; k++) {
      var a0 = (-90 + k * 72 + 5) * Math.PI / 180, a1 = a0 + 62 * Math.PI / 180;
      o += '<path d="M' + (r * Math.cos(a0)).toFixed(2) + "," + (r * Math.sin(a0)).toFixed(2) + "A" + r + "," + r + " 0 0,1 " + (r * Math.cos(a1)).toFixed(2) + "," + (r * Math.sin(a1)).toFixed(2) +
        '" stroke="' + (k < lv ? on : "#2a3432") + '" stroke-width="2.4" fill="none" stroke-linecap="round"/>';
    }
    return o;
  }
  function tileSvg(t, size) {
    var r = size / 2, lip = Math.max(2, size * 0.08), P = C[t.state] || C.open, id = "wmg" + gid++;
    var o = '<defs><linearGradient id="' + id + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + P[0] + '"/><stop offset="1" stop-color="' + P[1] + '"/></linearGradient></defs>';
    if (t.check) {
      var s = r * 1.5, sh = '<rect x="' + (-s / 2) + '" y="' + (-s / 2) + '" width="' + s + '" height="' + s + '" rx="' + s * 0.22 + '" transform="rotate(45)"';
      o += '<g transform="translate(0,' + lip + ')">' + sh + ' fill="' + P[2] + '"/></g>' + sh + ' fill="url(#' + id + ')"/>';
      if (t.state === "done") o += sh + ' fill="none" stroke="#f0c75e" stroke-width="2"/>';
    } else {
      o += '<circle cy="' + lip + '" r="' + r + '" fill="' + P[2] + '"/><circle r="' + r + '" fill="url(#' + id + ')"/>';
      if (t.state === "open") o += '<circle r="' + (r - 1) + '" fill="none" stroke="#14a093" stroke-width="2"/>';
    }
    o += glyph(t, P[3], size / 30);
    if (preview && t.review) { var lv = sampleLevel(t); o += levelArc(r + 4, lv, t.state === "done" && t.ix % 4 === 1); }
    return o;
  }

  function draw() {
    var W = Math.max(280, Math.min(canvas.clientWidth || host.clientWidth, 1088));
    var wide = W >= 700, cols = wide ? 3 : 1, cw = W / cols;
    var R = Math.max(70, Math.min(112, cw / 2 - 52)), nd = R > 95 ? 26 : 22, ch = wide ? 2 * R + 170 : 2 * R + 140;
    var n = stages.length, rows = Math.ceil(n / cols), H = rows * ch + 200;
    var pos = stages.map(function (s, i) {
      var r = Math.floor(i / cols), c = i % cols, cc = r % 2 ? cols - 1 - c : c;
      var rtl = document.documentElement.dir === "rtl";
      var x = wide ? (rtl ? W - (cc + 0.5) * cw : (cc + 0.5) * cw) : W / 2 + (i % 2 ? -1 : 1) * Math.min(18, W * 0.04);
      return { x: x, y: r * ch + ch / 2 };
    });
    var o = '<svg xmlns="' + NS + '" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + " " + H + '" role="group" aria-label="' + esc(L.label) + '">' +
      '<defs><radialGradient id="wm-pl" cx="50%" cy="35%" r="70%"><stop offset="0" stop-color="#1b2523"/><stop offset="1" stop-color="#0f1514"/></radialGradient>' +
      '<radialGradient id="wm-plc" cx="50%" cy="35%" r="70%"><stop offset="0" stop-color="#173a36"/><stop offset="1" stop-color="#0f1a18"/></radialGradient>' +
      '<filter id="wm-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>' +
      '<linearGradient id="wm-gold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6d77a"/><stop offset="1" stop-color="#b8860b"/></linearGradient></defs>';
    var seed = 11, rnd = function () { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
    o += '<g aria-hidden="true">';
    for (var k = 0; k < 6; k++) { var ex = rnd() * W, ey = rnd() * H; for (var j = 1; j < 6; j++) o += '<ellipse cx="' + ex.toFixed(0) + '" cy="' + ey.toFixed(0) + '" rx="' + j * 48 + '" ry="' + j * 30 + '" fill="none" stroke="#fff" stroke-opacity=".035"/>'; }
    for (var i = 0; i < n - 1; i++) {
      var a = pos[i], b = pos[i + 1], lit = stages[i].state === "done" && stages[i + 1].state !== "lock", my = (a.y + b.y) / 2;
      var d = Math.abs(a.y - b.y) < 1 ? "M" + a.x + "," + a.y + "L" + b.x + "," + b.y : "M" + a.x + "," + a.y + "C" + a.x + "," + my + " " + b.x + "," + my + " " + b.x + "," + b.y;
      /* No SVG filter on roads: a straight road has a zero-width box and a filter would hide it. */
      if (lit) o += '<path d="' + d + '" stroke="#14a093" stroke-opacity=".22" stroke-width="16" fill="none" stroke-linecap="round"/>';
      o += '<path d="' + d + '" stroke="' + (lit ? "#14a093" : "#1f2a28") + '" stroke-width="' + (lit ? 6 : 5) + '" fill="none" stroke-linecap="round"/>';
      if (!lit) o += '<path d="' + d + '" stroke="#334240" stroke-width="2" stroke-dasharray="2 10" fill="none" stroke-linecap="round"/>';
    }
    o += "</g>";
    var marker = "";
    stages.forEach(function (s, i) {
      var p = pos[i], cur = s.state === "cur", lock = s.state === "lock";
      o += '<g transform="translate(' + p.x.toFixed(1) + "," + p.y + ')"><g aria-hidden="true">';
      o += '<circle r="' + (R + 34) + '" fill="url(#' + (cur ? "wm-plc" : "wm-pl") + ')" stroke="' + (cur ? "#14a093" : "#ffffff") + '" stroke-opacity="' + (cur ? 0.6 : 0.06) + '" stroke-width="' + (cur ? 2 : 1) + '"/>';
      if (cur) o += '<circle r="' + (R + 46) + '" fill="none" stroke="#14a093" stroke-opacity=".18" stroke-width="10"/>';
      o += '<circle r="' + R + '" fill="none" stroke="#25302e" stroke-width="3"/>';
      var tn = s.tiles.length, dn = s.tiles.filter(function (t) { return t.state === "done"; }).length;
      if (dn && tn) {
        var fr = dn / tn, an = fr * 2 * Math.PI;
        o += fr >= 1 ? '<circle r="' + R + '" fill="none" stroke="#0f766e" stroke-width="3"/>' :
          '<path d="M0,' + (-R) + "A" + R + "," + R + " 0 " + (an > Math.PI ? 1 : 0) + ",1 " + (R * Math.sin(an)).toFixed(1) + "," + (-R * Math.cos(an)).toFixed(1) + '" stroke="#14a093" stroke-width="3" fill="none"/>';
      }
      o += '<text y="-16" text-anchor="middle" font-size="12" font-weight="600" fill="' + (lock ? "#8b9895" : "#5fd3c4") + '">' + esc(fill(L.stage, { n: i + 1 })) + "</text>";
      var title = clip(s.title, wide ? 20 : 18);
      o += '<text y="10" text-anchor="middle" font-size="' + (title.length > 14 ? 14 : 17) + '" font-weight="700" fill="' + (lock ? "#a3aeab" : "#ffffff") + '">' + esc(title) + "</text>";
      o += '<text y="34" text-anchor="middle" font-size="12" fill="#a3aeab">' + esc(fill(L.cells, { done: s.done, total: s.total })) + "</text>";
      o += "</g>";
      s.tiles.forEach(function (t, k) {
        var ang = (k + 1) / tn * 2 * Math.PI, x = R * Math.sin(ang), y = -R * Math.cos(ang);
        var sz = t.check ? nd * 1.3 : nd;
        var stateTxt = t.state === "done" ? L.done : t.state === "cur" ? L.here : t.state === "lock" ? L.lock : L.open;
        var kind = t.check ? L.check + " · " : t.review ? L.review + " · " : "";
        var lvTxt = preview && t.review ? " · " + fill(L.level, { n: sampleLevel(t) }) : "";
        var label = kind + t.title + " · " + stateTxt + lvTxt;
        var g = '<g transform="translate(' + x.toFixed(1) + "," + y.toFixed(1) + ')">' + tileSvg(t, sz) + "</g>";
        if (t.state === "lock") o += '<g aria-hidden="true">' + g + "</g>";
        else {
          var href = readOnly ? "/play/" + encodeURIComponent(host.dataset.path) + "?topic=" + encodeURIComponent(s.id) : "#";
          o += '<a class="wm-tile" href="' + href + '" data-node="' + esc(t.id) + '" aria-label="' + esc(label) + '"' + (t.state === "cur" ? ' aria-current="step"' : "") + "><title>" + esc(label) + "</title>" + g + "</a>";
        }
        if (t.state === "cur") {
          /* The marker sits outside the ring, along the tile's own direction, so it never covers the stage name. */
          var ux = Math.sin(ang), uy = -Math.cos(ang), off = sz / 2 + 30, bw = Math.max(76, L.here.length * 8 + 24);
          var mx = p.x + x + ux * off, myy = p.y + y + uy * off;
          marker = '<g class="wm-here" aria-hidden="true"><circle cx="' + (p.x + x).toFixed(1) + '" cy="' + (p.y + y).toFixed(1) + '" r="' + (sz / 2 + 8) + '" fill="none" stroke="#5fd3c4" stroke-width="2" opacity=".85"/>' +
            '<line x1="' + (p.x + x + ux * (sz / 2 + 8)).toFixed(1) + '" y1="' + (p.y + y + uy * (sz / 2 + 8)).toFixed(1) + '" x2="' + (mx - ux * 12).toFixed(1) + '" y2="' + (myy - uy * 12).toFixed(1) + '" stroke="#ffffff" stroke-width="2"/>' +
            '<g transform="translate(' + mx.toFixed(1) + "," + myy.toFixed(1) + ')"><rect x="' + (-bw / 2) + '" y="-15" width="' + bw + '" height="30" rx="15" fill="#ffffff"/>' +
            '<text y="5" text-anchor="middle" font-size="13" font-weight="700" fill="#0f766e">' + esc(L.here) + "</text></g></g>";
        }
      });
      o += "</g>";
    });
    var last = pos[n - 1], sx = wide ? last.x : W / 2, sy = last.y + ch / 2 + 50;
    o += '<g aria-hidden="true"><path d="M' + last.x + "," + (last.y + R + 34) + "L" + sx + "," + (sy - 40) + '" stroke="#1f2a28" stroke-width="5"/>' +
      '<g transform="translate(' + sx + "," + sy + ')" filter="url(#wm-glow)"><path d="M0,-40 L35,-20 35,20 0,40 -35,20 -35,-20Z" fill="url(#wm-gold)"/><path d="M-16,12 L-4,-10 3,2 8,-5 18,12Z" fill="#fff" opacity=".9"/></g>' +
      '<text x="' + sx + '" y="' + (sy + 66) + '" text-anchor="middle" font-size="16" font-weight="700" fill="#f6d77a">' + esc(L.end) + "</text>" +
      '<text x="' + sx + '" y="' + (sy + 86) + '" text-anchor="middle" font-size="12" fill="#a3aeab">' + esc(clip(host.dataset.title || "", 34)) + "</text></g>";
    canvas.innerHTML = o + marker + "</svg>";
  }

  function legend() {
    var items = [[{ state: "done" }, L.done], [{ state: "cur" }, L.here], [{ state: "open" }, L.open], [{ state: "lock" }, L.lock], [{ state: "done", check: true }, L.check], [{ state: "done", review: true, ix: 1 }, L.review]];
    host.querySelector(".world-legend").innerHTML = items.map(function (it) {
      return '<span><svg width="26" height="26" viewBox="-13 -13 26 26">' + tileSvg(it[0], it[0].check ? 15 : 17) + "</svg>" + esc(it[1]) + "</span>";
    }).join("");
  }

  canvas.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a.wm-tile");
    if (!a || readOnly) return;
    var form = document.getElementById("world-go");
    if (!form) return;
    e.preventDefault();
    form.querySelector('input[name="node"]').value = a.getAttribute("data-node");
    form.submit();
  });

  /* The map draws its own position marker; the list's floating shortcut would point into a closed list. */
  var fh = document.querySelector(".float-here");
  if (fh) fh.remove();
  host.hidden = false;
  if (list) list.open = false;
  legend();
  draw();
  var tm;
  window.addEventListener("resize", function () { clearTimeout(tm); tm = setTimeout(draw, 120); });
  var here = canvas.querySelector(".wm-here");
  if (here && location.hash !== "#track" && here.scrollIntoView) {
    var rm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    here.scrollIntoView({ block: "center", behavior: rm ? "auto" : "smooth" });
  }
})();
