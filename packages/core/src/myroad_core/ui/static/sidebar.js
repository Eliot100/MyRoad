/* Road picker side panel: client-side search over the loaded rows, auto-submit of the group
   filter, and the phone drawer (aria-expanded, focus trap, Esc, inert background).
   Without this file the panel is a plain list and ☰ is an in-page link to it. */
(function () {
  var d = document.documentElement;
  d.classList.add("js");
  var shell = document.querySelector(".app-shell");
  var side = document.getElementById("roads");
  if (!shell || !side) return;
  var main = document.getElementById("app-main");
  var search = side.querySelector(".side-search");
  var q = document.getElementById("side-q");
  var none = side.querySelector(".side-none");
  if (search) search.hidden = false;
  if (q) q.addEventListener("input", function () {
    var v = q.value.trim().toLowerCase(), shown = 0;
    side.querySelectorAll(".side-list > li:not(.side-none):not(.side-empty)").forEach(function (li) {
      var hit = !v || li.textContent.toLowerCase().indexOf(v) >= 0;
      li.hidden = !hit; if (hit) shown++;
    });
    if (none) none.hidden = shown > 0 || !v;
  });
  var sel = document.getElementById("side-group");
  if (sel) sel.addEventListener("change", function () { sel.form.submit(); });

  var btn = document.querySelector(".menu-btn");
  var closeBtn = side.querySelector(".side-close");
  var scrim = shell.querySelector(".side-scrim");
  var mq = window.matchMedia("(max-width: 760px)");
  if (!btn) return;
  btn.setAttribute("role", "button");
  btn.setAttribute("aria-expanded", "false");
  function isOpen() { return shell.classList.contains("side-open"); }
  function setOpen(open) {
    shell.classList.toggle("side-open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    if (main) main.inert = open;
    if (scrim) scrim.hidden = !open;
    if (closeBtn) closeBtn.hidden = !open;
    if (open) { (q || side.querySelector("a,button,input,select")).focus(); }
    else btn.focus();
  }
  function sync() {
    if (mq.matches) { side.inert = !isOpen(); }
    else { side.inert = false; if (isOpen()) setOpen(false); }
  }
  btn.addEventListener("click", function (e) {
    if (!mq.matches) return;
    e.preventDefault(); setOpen(true); sync();
  });
  if (closeBtn) closeBtn.addEventListener("click", function () { setOpen(false); sync(); });
  if (scrim) scrim.addEventListener("click", function () { setOpen(false); sync(); });
  document.addEventListener("keydown", function (e) {
    if (!isOpen()) return;
    if (e.key === "Escape") { e.preventDefault(); setOpen(false); sync(); return; }
    if (e.key !== "Tab") return;
    var f = Array.prototype.filter.call(side.querySelectorAll("a[href],button,input,select"), function (el) {
      return !el.hidden && !el.disabled && el.offsetParent !== null;
    });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });
  if (mq.addEventListener) mq.addEventListener("change", sync);
  sync();
})();
