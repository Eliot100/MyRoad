/* Reading comfort preferences (UX M7, #104). Loaded synchronously in <head> so the
   attributes are on <html> before first paint (no flash of the wrong size).
   Client-side only (localStorage); no server state. */
(function () {
  var d = document.documentElement, size = null, motion = null;
  try { size = localStorage.getItem("myroad.textSize"); motion = localStorage.getItem("myroad.motion"); } catch (e) {}
  if (size === "125" || size === "150") d.setAttribute("data-text-size", size);
  if (motion === "reduce" || motion === "full") d.setAttribute("data-motion", motion);
  /* Theme (light/dark): unset = follow the system (prefers-color-scheme). */
  var theme = null;
  try { theme = localStorage.getItem("myroad.theme"); } catch (e) {}
  if (theme === "light" || theme === "dark") d.setAttribute("data-theme", theme);
  window.myroadTheme = function () {
    var th = d.getAttribute("data-theme");
    if (th) return th;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  };
  window.myroadReduceMotion = function () {
    var m = d.getAttribute("data-motion");
    if (m) return m === "reduce";
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  };
  /* Skip cross-document view transitions when the learner asked for less motion. */
  function skip(e) { if (e.viewTransition && window.myroadReduceMotion()) e.viewTransition.skipTransition(); }
  window.addEventListener("pageswap", skip);
  window.addEventListener("pagereveal", skip);
})();
