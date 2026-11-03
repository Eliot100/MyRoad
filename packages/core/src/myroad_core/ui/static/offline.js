/* Offline page (#234): show the section for the locale cookie (he default), set lang/dir. */
(function () {
  var m = document.cookie.match(/(?:^|;\s*)myroad_locale=(he|en|ar)/);
  var code = m ? m[1] : "he";
  var shown = null;
  document.querySelectorAll("main[data-locale]").forEach(function (el) {
    el.hidden = el.getAttribute("data-locale") !== code;
    if (!el.hidden) shown = el;
  });
  if (shown) {
    document.documentElement.lang = shown.lang;
    document.documentElement.dir = shown.dir;
  }
})();
