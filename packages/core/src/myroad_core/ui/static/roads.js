/* /roads: live search over the GET form (works without JS) + shelf scroll arrows. */
(function () {
  var form = document.querySelector("[data-rs-form]");
  if (!form) return;
  var rtl = document.documentElement.dir === "rtl";

  function wireShelves(root) {
    root.querySelectorAll(".rs-row").forEach(function (row) {
      var shelf = row.querySelector("[data-shelf]");
      var btns = row.querySelectorAll(".rs-arrow");
      if (!shelf || !btns.length) return;
      function update() {
        var max = shelf.scrollWidth - shelf.clientWidth;
        var pos = Math.abs(shelf.scrollLeft);
        var over = max > 4;
        btns.forEach(function (b) {
          b.hidden = !over;
          var atEnd = b.dataset.dir === "prev" ? pos <= 2 : pos >= max - 2;
          b.setAttribute("aria-disabled", atEnd ? "true" : "false");
        });
      }
      btns.forEach(function (b) {
        b.addEventListener("click", function () {
          if (b.getAttribute("aria-disabled") === "true") return;
          var step = shelf.clientWidth * 0.85 * (b.dataset.dir === "next" ? 1 : -1);
          shelf.scrollBy({ left: rtl ? -step : step, behavior: "smooth" });
        });
      });
      shelf.addEventListener("scroll", update, { passive: true });
      window.addEventListener("resize", update);
      update();
    });
  }
  wireShelves(document);

  var det = form.querySelector("[data-rs-filters]");
  if (det && window.matchMedia("(max-width: 760px)").matches && !form.querySelector("input[type=checkbox]:checked")) det.open = false;
  if (!window.fetch || !window.DOMParser) return;
  var timer = null, seq = 0;
  function run() {
    var params = new URLSearchParams(new FormData(form));
    if (!params.get("q")) params.delete("q");
    if (params.get("sort") === "recommended") params.delete("sort");
    var qs = params.toString(), url = "/roads" + (qs ? "?" + qs : ""), mine = ++seq;
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
      .then(function (html) {
        if (mine !== seq) return;
        var doc = new DOMParser().parseFromString(html, "text/html");
        var res = doc.getElementById("rs-results"), cur = document.getElementById("rs-results");
        if (res && cur) { cur.replaceWith(res); wireShelves(res); }
        doc.querySelectorAll(".rs-n").forEach(function (n) {
          var m = document.querySelector('.rs-n[data-n="' + n.getAttribute("data-n") + '"]');
          if (m) m.textContent = n.textContent;
        });
        var b = doc.querySelector(".rs-filters > summary"), cb = document.querySelector(".rs-filters > summary");
        if (b && cb) cb.innerHTML = b.innerHTML;
        history.replaceState(null, "", url);
      })
      .catch(function () { /* keep current results; the submit button still works */ });
  }
  form.addEventListener("input", function (e) {
    if (e.target.name !== "q") return;
    clearTimeout(timer); timer = setTimeout(run, 250);
  });
  form.addEventListener("change", function (e) { if (e.target.name !== "q") run(); });
  form.addEventListener("submit", function (e) { e.preventDefault(); clearTimeout(timer); run(); });
})();
