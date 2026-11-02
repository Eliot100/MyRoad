/* Login code field (#59). Progressive enhancement only: the form works without this file.
   - Paste or autofill of "1234 5678" / "1234-5678" keeps just the digits.
   - When the field holds a full code, the form submits once (skipped when a CAPTCHA is shown).
   No network calls, no storage; the code never leaves the form except by its normal POST. */
(function () {
  var input = document.querySelector("[data-code-input]");
  if (!input || !input.form) return;
  var form = input.form;
  var max = 8; /* CODE_DIGITS; maxlength is 11 so no-JS paste can carry separators (decision 0009, option C) */
  var sent = false;

  function digits(s) {
    /* Keep ASCII digits; also map Arabic-Indic and Eastern Arabic digits to ASCII. */
    return String(s || "").replace(/[\u0660-\u0669]/g, function (c) { return String(c.charCodeAt(0) - 0x0660); })
      .replace(/[\u06F0-\u06F9]/g, function (c) { return String(c.charCodeAt(0) - 0x06F0); })
      .replace(/[^0-9]/g, "").slice(0, max);
  }

  function maybeSubmit() {
    if (sent || !input.hasAttribute("data-autosubmit")) return;
    if (input.value.length === max && input.checkValidity()) {
      sent = true;
      if (form.requestSubmit) form.requestSubmit(); else form.submit();
    }
  }

  input.addEventListener("paste", function (e) {
    var text = (e.clipboardData || window.clipboardData);
    text = text ? text.getData("text") : "";
    if (!text) return;
    e.preventDefault();
    input.value = digits(text);
    input.removeAttribute("aria-invalid");
    maybeSubmit();
  });

  input.addEventListener("input", function () {
    var clean = digits(input.value);
    if (clean !== input.value) input.value = clean;
    input.removeAttribute("aria-invalid");
    maybeSubmit();
  });

  form.addEventListener("submit", function (e) {
    if (form.getAttribute("data-submitting") === "1") { e.preventDefault(); return; }
    input.value = digits(input.value);
    form.setAttribute("data-submitting", "1");
    sent = true;
    var btn = form.querySelector("button[type=submit]");
    if (btn) btn.setAttribute("aria-disabled", "true");
  });

  /* Back/forward cache: let the learner submit again after returning. */
  window.addEventListener("pageshow", function () {
    form.removeAttribute("data-submitting"); sent = false;
    var btn = form.querySelector("button[type=submit]");
    if (btn) btn.removeAttribute("aria-disabled");
  });
})();
