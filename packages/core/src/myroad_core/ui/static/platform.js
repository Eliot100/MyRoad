(function () {
  function speak(text) {
    if (!text || !window.speechSynthesis) {
      var s = document.getElementById("record-status");
      if (s) s.textContent = "הקראה לא נתמכת בדפדפן זה.";
      return;
    }
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.lang = /[a-zA-Z]/.test(text) && !/[\u0590-\u05FF]/.test(text) ? "en-US" : "he-IL";
    window.speechSynthesis.speak(u);
  }

  // Delegated, so it keeps working after htmx swaps in a new step card.
  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest("#btn-speak");
    if (!btn) return;
    var source = document.getElementById("speak-source");
    if (source) speak(source.getAttribute("data-speak") || source.textContent || "");
  });

  // Widgets inside a step card bind once per element; init() runs on load and on every swap.
  function bindOnce(el) {
    if (!el || el.getAttribute("data-bound") === "1") return false;
    el.setAttribute("data-bound", "1");
    return true;
  }

  function init(root) {
    // Optional recording (MediaRecorder / SpeechRecognition) — graceful fallback
    var btnRec = root.querySelector("#btn-record");
    var recStatus = root.querySelector("#record-status");
    if (btnRec && bindOnce(btnRec)) {
      var recording = false;
      var mediaRecorder = null;
      var chunks = [];
      btnRec.addEventListener("click", async function () {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          if (recStatus) recStatus.textContent = "הקלטה לא נתמכת — אפשר להמשיך בלי.";
          return;
        }
        try {
          if (!recording) {
            var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            chunks = [];
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
            mediaRecorder.onstop = function () {
              stream.getTracks().forEach(function (t) { t.stop(); });
              if (recStatus) recStatus.textContent = "ההקלטה נשמרה מקומית לתרגול (לא נשלחת לשרת).";
            };
            mediaRecorder.start();
            recording = true;
            btnRec.textContent = "⏹ עצירה";
            if (recStatus) recStatus.textContent = "מקליט…";
          } else {
            mediaRecorder.stop();
            recording = false;
            btnRec.textContent = "🎤 הקלטה";
          }
        } catch (err) {
          if (recStatus) recStatus.textContent = "לא ניתן להקליט — המשיכו בלי הקלטה.";
        }
      });
    }

    // Piano keys
    var piano = root.querySelector("#piano");
    if (piano && bindOnce(piano)) {
      var seq = [];
      var seqEl = root.querySelector("#piano-seq");
      var seqInput = root.querySelector("#piano-sequence");
      var freqs = { do: 261.63, re: 293.66, mi: 329.63, fa: 349.23, sol: 392.0 };
      var ctx = null;
      function beep(key) {
        try {
          ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
          var o = ctx.createOscillator();
          var g = ctx.createGain();
          o.frequency.value = freqs[key] || 300;
          o.connect(g); g.connect(ctx.destination);
          g.gain.value = 0.08;
          o.start();
          setTimeout(function () { o.stop(); }, 220);
        } catch (e) { /* audio optional */ }
      }
      piano.querySelectorAll(".piano-key").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var k = btn.getAttribute("data-key");
          seq.push(k);
          btn.classList.add("lit");
          setTimeout(function () { btn.classList.remove("lit"); }, 180);
          beep(k);
          if (seqEl) seqEl.textContent = "רצף: " + seq.join(" → ");
          if (seqInput) seqInput.value = seq.join(",");
        });
      });
    }

    // Rhythm
    var rhythm = root.querySelector("#rhythm");
    if (rhythm && bindOnce(rhythm)) {
      var pattern = (rhythm.getAttribute("data-pattern") || "").split(",").map(function (x) { return x.trim(); });
      var picked = pattern.map(function () { return null; });
      var seqInput = root.querySelector("#rhythm-sequence");
      function sync() {
        if (seqInput) seqInput.value = picked.map(function (v) { return v === null ? "" : v; }).join(",");
      }
      rhythm.querySelectorAll(".beat-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var idx = parseInt(btn.getAttribute("data-idx"), 10);
          // toggle: clap (1) vs rest (0)
          var cur = picked[idx];
          var next = cur === 1 ? 0 : 1;
          picked[idx] = next;
          btn.classList.toggle("selected", next === 1);
          btn.textContent = next === 1 ? "👏 מחיאה" : "שקט";
          sync();
        });
      });
      var reset = root.querySelector("#rhythm-reset");
      if (reset) {
        reset.addEventListener("click", function () {
          picked = pattern.map(function () { return null; });
          rhythm.querySelectorAll(".beat-btn").forEach(function (btn, i) {
            btn.classList.remove("selected");
            btn.textContent = "פעימה " + (i + 1);
          });
          sync();
        });
      }
    }
  }

  init(document);

  // --- Path map: bring the current station (#here, aria-current="step") into view on load ---
  // Without JS the "Station N of M" pill and the map links (?view=map#here) jump there instead.
  function jumpToCurrentStation() {
    var here = document.getElementById("here");
    if (!here || !document.body.classList.contains("map-view")) return;
    if (window.location.hash) return; // the browser already scrolled to the fragment
    var nav = window.performance && performance.getEntriesByType && performance.getEntriesByType("navigation")[0];
    if (nav && nav.type === "back_forward") return; // keep the restored scroll position
    var r = here.getBoundingClientRect();
    var fits = r.top >= 0 && r.bottom <= (window.innerHeight || document.documentElement.clientHeight);
    if (fits) return; // already on screen: do not move the page
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    here.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", jumpToCurrentStation);
  } else {
    jumpToCurrentStation();
  }

  // --- Step player + htmx (progressive enhancement: without JS the forms post normally) ---
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // After a swap, move focus to the feedback (answer) or the new step title (next step).
  document.addEventListener("htmx:load", function (e) {
    var el = e.target;
    if (!el || !el.querySelector) return;
    init(el);
    var card = el.matches && el.matches("[data-swap-focus]") ? el : el.querySelector("[data-swap-focus]");
    if (!card) return;
    var target = document.getElementById(card.getAttribute("data-swap-focus"));
    card.removeAttribute("data-swap-focus");
    if (!target) return;
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
  });

  // Remember the tapped choice, so a failed htmx request can fall back to a normal post / link.
  document.addEventListener("click", function (e) {
    var tile = e.target.closest && e.target.closest("form[data-step-form] button[name=choice]");
    if (tile) tile.form.setAttribute("data-last-choice", tile.value);
  });
  function fallbackPost(e) {
    var form = e.detail && e.detail.elt;
    if (!form || !form.matches) return;
    if (form.matches("a.continue-step")) { window.location.href = form.href; return; }
    if (!form.matches("form[data-step-form]")) return;
    var input = document.createElement("input");
    input.type = "hidden";
    input.name = "choice";
    input.value = form.getAttribute("data-last-choice") || "";
    form.appendChild(input);
    HTMLFormElement.prototype.submit.call(form); // native submit: htmx does not intercept it
  }
  document.addEventListener("htmx:sendError", fallbackPost);
  document.addEventListener("htmx:responseError", fallbackPost);
})();
