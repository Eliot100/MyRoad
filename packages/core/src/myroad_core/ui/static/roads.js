/* /roads live search: progressive enhancement over the GET form (works without JS). */
(function () {
  var form = document.querySelector("[data-rs-form]");
  if (!form || !window.fetch || !window.DOMParser) return;
  var det = form.querySelector("[data-rs-filters]");
  if (det && window.matchMedia("(max-width: 760px)").matches && !form.querySelector("input[type=checkbox]:checked")) det.open = false;
  var timer = null, seq = 0;
  function run() {
    var params = new URLSearchParams(new FormData(form));
    if (!params.get("q")) params.delete("q");
    if (params.get("sort") === "recommended") params.delete("sort");
    var qs = params.toString(), url = "/roads" + (qs ? "?" + qs : ""), mine = ++seq;
    fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
      .then(function (html) {
        if (mine !== seq) return;
        var doc = new DOMParser().parseFromString(html, "text/html");
        var res = doc.getElementById("rs-results"), cur = document.getElementById("rs-results");
        if (res && cur) cur.replaceWith(res);
        doc.querySelectorAll(".rs-n").forEach(function (n) {
          var mine2 = document.querySelector('.rs-n[data-n="' + n.getAttribute("data-n") + '"]');
          if (mine2) mine2.textContent = n.textContent;
        });
        var act = doc.querySelector(".rs-actions"), cact = document.querySelector(".rs-actions");
        if (act && cact) cact.innerHTML = act.innerHTML;
        history.replaceState(null, "", url);
      })
      .catch(function () { /* keep the current results; the submit button still works */ });
  }
  form.addEventListener("input", function (e) {
    if (e.target.name !== "q") return;
    clearTimeout(timer); timer = setTimeout(run, 250);
  });
  form.addEventListener("change", function (e) { if (e.target.name !== "q") run(); });
  form.addEventListener("submit", function (e) { e.preventDefault(); clearTimeout(timer); run(); });
})();
