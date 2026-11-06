/* Register the service worker (#234) and surface an install button when the browser offers one.
   Browsers allow the worker only on HTTPS or localhost. */
(function () {
  var deferred = null;
  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    deferred = event;
    var btn = document.getElementById("pwa-install");
    if (btn) btn.hidden = false;
  });
  document.addEventListener("click", function (event) {
    var btn = event.target && event.target.closest && event.target.closest("#pwa-install");
    if (!btn || !deferred) return;
    deferred.prompt();
    deferred = null;
    btn.hidden = true;
  });
  if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
  });
})();
