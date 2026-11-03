/* MyRoad pseudonymous analytics batcher (#208, docs/analytics-events.md).
   Taps, screen transitions (with time on the previous screen) and answer latency are queued
   and sent to our own POST /api/events. No text, no form values, no PII: only element ids /
   data-ev names and URL paths. Flush on 20 events, every 10 s, and on pagehide.
   navigator.sendBeacon cannot send the X-MyRoad-Request header the API requires, so the
   pagehide flush uses fetch(..., {keepalive: true}), which survives unload the same way. */
(function () {
  "use strict";
  var ENDPOINT = "/api/events", MAX_BATCH = 20, FLUSH_MS = 10000, KEY = "myroad_ev_screen";
  var queue = [], shownAt = Date.now();

  function tok(s) {
    s = String(s || "").replace(/[^A-Za-z0-9_./:\-]/g, "_").slice(0, 160);
    return s || null;
  }
  function screen() { return tok(location.pathname); }
  function push(type, props) {
    var ev = { type: type, screen: screen(), ts: Date.now(), props: {} };
    for (var k in props) { if (props[k] !== null && props[k] !== undefined) ev.props[k] = props[k]; }
    queue.push(ev);
    if (queue.length >= MAX_BATCH) flush(false);
  }
  function flush(unloading) {
    if (!queue.length) return;
    var body = JSON.stringify({ events: queue.splice(0, 50) });
    try {
      fetch(ENDPOINT, {
        method: "POST", credentials: "same-origin", keepalive: !!unloading,
        headers: { "Content-Type": "application/json", "X-MyRoad-Request": "1" }, body: body
      }).catch(function () {});
    } catch (e) { /* analytics never breaks the page */ }
  }

  // Screen transition: previous screen + time spent there (kept in sessionStorage).
  var prev = null;
  try { prev = JSON.parse(sessionStorage.getItem(KEY) || "null"); } catch (e) { prev = null; }
  push("screen_view", prev ? { from_screen: tok(prev.s), ms: Math.max(0, Date.now() - prev.t) } : {});
  function remember() {
    try { sessionStorage.setItem(KEY, JSON.stringify({ s: location.pathname, t: shownAt })); } catch (e) {}
  }
  remember();

  document.addEventListener("htmx:afterSwap", function () { shownAt = Date.now(); });

  document.addEventListener("click", function (e) {
    var el = e.target && e.target.closest ? e.target.closest("button, a, [data-ev], input[type=radio], label") : null;
    if (!el) return;
    var name = el.getAttribute("data-ev") || el.id || el.getAttribute("name") || el.tagName.toLowerCase();
    push("tap", { target: tok(name) });
  }, true);

  document.addEventListener("submit", function (e) {
    var f = e.target, action = (f && f.getAttribute && (f.getAttribute("action") || f.getAttribute("hx-post"))) || "";
    var m = action.match(/\/play\/([^/?#]+)\/answer/);
    if (!m) return;
    push("answer_submit", { path_id: tok(decodeURIComponent(m[1])), latency_ms: Math.max(0, Date.now() - shownAt) });
    shownAt = Date.now();
  }, true);

  setInterval(function () { flush(false); }, FLUSH_MS);
  window.addEventListener("pagehide", function () { remember(); flush(true); });
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "hidden") flush(true); });
})();
