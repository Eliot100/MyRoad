// Engagement head and session end (decision 0010). Separate from platform.js, which stays network free.
// Session end (#191): 'עוד אחד קצר' starts the next short סשן, then follows its link.
// Weekly goal (#193): the change disclosure needs JS (JSON API), so it stays hidden without it.
(function () {
  var H = { "X-MyRoad-Request": "1", "Content-Type": "application/json" };
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[data-next-session]");
    if (!a || a.dataset.started) return;
    ev.preventDefault();
    ev.stopPropagation();
    a.dataset.started = "1";
    fetch(a.getAttribute("data-next-session"), { method: "POST", headers: H, credentials: "same-origin" })
      .catch(function () {})
      .then(function () { a.click(); });
  }, true);
  function wireGoals(root) {
    (root || document).querySelectorAll("[data-weekly-goal]").forEach(function (box) {
      if (box.dataset.wired) return;
      box.dataset.wired = "1";
      box.hidden = false;
      var form = box.querySelector("form");
      var status = box.querySelector(".week-goal-status");
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var pick = form.querySelector("input[name=goal]:checked");
        if (!pick) return;
        fetch("/api/settings/weekly-goal", { method: "POST", headers: H, credentials: "same-origin",
          body: JSON.stringify({ goal: Number(pick.value) }) })
          .then(function (r) { if (!r.ok) throw r; return r.json(); })
          .then(function () { status.textContent = status.dataset.ok; setTimeout(function () { location.reload(); }, 600); })
          .catch(function () { status.textContent = status.dataset.err; });
      });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { wireGoals(); });
  else wireGoals();
})();
