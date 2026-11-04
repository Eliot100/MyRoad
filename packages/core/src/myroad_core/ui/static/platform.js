(function () {
  // Read aloud (הקראה): content audio first, then a voice that matches the text's script,
  // else a calm on-screen note instead of silence.
  var AR_RE = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;
  var HE_RE = /[\u0590-\u05FF]/;
  function speakLang(text) {
    if (AR_RE.test(text)) return "ar";
    if (HE_RE.test(text)) return "he-IL";
    return "en-US";
  }
  function langPrefix(lang) { return String(lang || "").toLowerCase().split(/[-_]/)[0]; }
  function pickVoice(voices, lang) {
    var want = langPrefix(lang);
    if (want === "he") want = /^(he|iw)$/;
    for (var i = 0; i < (voices || []).length; i++) {
      var p = langPrefix(voices[i].lang);
      if (typeof want === "string" ? p === want : want.test(p)) return voices[i];
    }
    return null;
  }
  // getVoices() is often empty until voiceschanged fires; wait briefly, then use what we have.
  function withVoices(cb) {
    var synth = window.speechSynthesis;
    var v = synth.getVoices();
    if (v && v.length) { cb(v); return; }
    var done = false;
    function finish() {
      if (done) return;
      done = true;
      if (synth.removeEventListener) synth.removeEventListener("voiceschanged", finish);
      cb(synth.getVoices() || []);
    }
    if (synth.addEventListener) synth.addEventListener("voiceschanged", finish);
    setTimeout(finish, 800);
  }
  function speakNote(key) {
    var el = document.getElementById("speak-note");
    if (!el) return;
    var msg = el.getAttribute("data-msg-" + key) || "";
    el.textContent = msg;
    el.hidden = !msg;
  }
  function playAudio(url, onFail) {
    try {
      var a = new Audio(url);
      var p = a.play();
      if (p && p.catch) p.catch(function () { onFail(); });
      a.onerror = function () { onFail(); };
    } catch (err) { onFail(); }
  }
  function speakTts(text, lang) {
    var synth = window.speechSynthesis;
    if (!synth || typeof window.SpeechSynthesisUtterance !== "function") { speakNote("unsupported"); return; }
    withVoices(function (voices) {
      var voice = pickVoice(voices, lang);
      if (!voice) { speakNote("novoice"); return; }
      synth.cancel();
      var u = new SpeechSynthesisUtterance(text);
      u.lang = lang;
      u.voice = voice;
      synth.speak(u);
    });
  }
  function speak(text, audioUrl) {
    speakNote("");
    text = (text || "").trim();
    var lang = speakLang(text);
    if (audioUrl) { playAudio(audioUrl, function () { if (text) speakTts(text, lang); else speakNote("novoice"); }); return; }
    if (!text) return;
    speakTts(text, lang);
  }
  window.MyRoadSpeak = { lang: speakLang, pickVoice: pickVoice };

  // Delegated, so it keeps working after htmx swaps in a new step card.
  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest("#btn-speak");
    if (!btn) return;
    var source = document.getElementById("speak-source");
    if (source) speak(source.getAttribute("data-speak") || source.textContent || "", source.getAttribute("data-speak-audio") || "");
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
    var reduce = window.myroadReduceMotion ? window.myroadReduceMotion() : (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    here.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
  }
  // Floating "back to my station" (UI): visible only while the current station is off screen.
  // Without JS (or IntersectionObserver) it stays hidden and the #here pill link still works.
  function floatBackToStation() {
    var here = document.getElementById("here");
    var btn = document.querySelector(".float-here");
    if (!here || !btn || !("IntersectionObserver" in window)) return;
    new IntersectionObserver(function (entries) {
      btn.hidden = entries[entries.length - 1].isIntersecting;
    }).observe(here);
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      var reduce = window.myroadReduceMotion ? window.myroadReduceMotion() : false;
      here.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
      var f = here.querySelector("summary, a, button");
      if (f) f.focus({ preventScroll: true });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", floatBackToStation);
  } else {
    floatBackToStation();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", jumpToCurrentStation);
  } else {
    jumpToCurrentStation();
  }

  // --- Step player + htmx (progressive enhancement: without JS the forms post normally) ---
  var reduceMotion = window.myroadReduceMotion ? window.myroadReduceMotion() : (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

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
    if (tile) {
      tile.form.setAttribute("data-last-choice", tile.value);
      tile.setAttribute("data-pending", "");
    }
  });
  // Pending state: mark the step card busy while htmx works, so the tap visibly registered
  // (CSS dims the other tiles) and assistive tech hears that content is updating.
  function stepCard(e) {
    var elt = e.detail && e.detail.elt;
    return elt && elt.closest ? elt.closest("#step-card") : null;
  }
  document.addEventListener("htmx:beforeRequest", function (e) {
    var card = stepCard(e);
    if (card) card.setAttribute("aria-busy", "true");
  });
  document.addEventListener("htmx:afterRequest", function (e) {
    var card = stepCard(e);
    if (!card) return;
    card.removeAttribute("aria-busy");
    var pending = card.querySelectorAll("[data-pending]");
    for (var i = 0; i < pending.length; i++) pending[i].removeAttribute("data-pending");
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
  // Offline: a native post would land on the browser's error page and lose the learner's place.
  // Keep them on the step and say what happened; the next tap retries.
  function sendError(e) {
    var card = stepCard(e);
    if (card && navigator.onLine === false) {
      var fb = card.querySelector("#step-feedback");
      if (fb) {
        fb.className = "step-feedback try offline";
        fb.textContent = card.getAttribute("data-offline-msg") || "";
      }
      card.removeAttribute("aria-busy");
      return;
    }
    fallbackPost(e);
  }
  document.addEventListener("htmx:sendError", sendError);
  document.addEventListener("htmx:responseError", fallbackPost);
})();

// Scratchpad (#183): the learner's own working on a practice step. Stored only in this
// browser's localStorage, keyed by user + road + step, so it survives Next / Previous and
// reloads. Never posted and never graded. Strokes are kept as points and redrawn with the
// current theme's ink colour, so a drawing stays readable after switching light / dark.
(function () {
  var MAX_POINTS = 4000;
  function load(key) {
    try { return JSON.parse(localStorage.getItem(key) || "null") || {}; } catch (e) { return {}; }
  }
  function save(key, st) {
    try {
      if (!st.t && !(st.s && st.s.length) && !st.o) localStorage.removeItem(key);
      else localStorage.setItem(key, JSON.stringify(st));
    } catch (e) { /* storage full or blocked: the pad still works for this view */ }
  }
  function init(pad) {
    if (pad.hasAttribute("data-scratch-ready")) return;
    pad.setAttribute("data-scratch-ready", "");
    var key = pad.getAttribute("data-scratch-key");
    var st = load(key);
    st.s = st.s || [];
    var text = pad.querySelector("[data-scratch-text]");
    var canvas = pad.querySelector("[data-scratch-canvas]");
    var clear = pad.querySelector("[data-scratch-clear]");
    if (st.o) pad.open = true;
    if (text) {
      text.value = st.t || "";
      text.addEventListener("input", function () { st.t = text.value; save(key, st); });
    }
    pad.addEventListener("toggle", function () { st.o = pad.open ? 1 : 0; save(key, st); if (pad.open) draw(); });
    if (!canvas) return;
    var ctx = canvas.getContext("2d");
    function count() { var n = 0; for (var i = 0; i < st.s.length; i++) n += st.s[i].length; return n; }
    function draw() {
      var r = canvas.getBoundingClientRect();
      if (!r.width) return;
      var dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(r.width * dpr);
      canvas.height = Math.round(r.height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, r.width, r.height);
      ctx.strokeStyle = getComputedStyle(canvas).color;
      ctx.lineWidth = 2.25; ctx.lineCap = "round"; ctx.lineJoin = "round";
      for (var i = 0; i < st.s.length; i++) {
        var line = st.s[i];
        ctx.beginPath();
        for (var j = 0; j < line.length; j++) {
          var x = line[j][0] * r.width, y = line[j][1] * r.height;
          if (j) ctx.lineTo(x, y); else { ctx.moveTo(x, y); ctx.lineTo(x + 0.01, y); }
        }
        ctx.stroke();
      }
    }
    var cur = null;
    function pt(e) {
      var r = canvas.getBoundingClientRect();
      return [Math.round(((e.clientX - r.left) / r.width) * 1000) / 1000, Math.round(((e.clientY - r.top) / r.height) * 1000) / 1000];
    }
    canvas.addEventListener("pointerdown", function (e) {
      if (count() >= MAX_POINTS) return;
      canvas.setPointerCapture(e.pointerId);
      cur = [pt(e)]; st.s.push(cur); draw();
    });
    canvas.addEventListener("pointermove", function (e) {
      if (!cur || count() >= MAX_POINTS) return;
      cur.push(pt(e)); draw();
    });
    function end() { if (cur) { cur = null; save(key, st); } }
    canvas.addEventListener("pointerup", end);
    canvas.addEventListener("pointercancel", end);
    if (clear) clear.addEventListener("click", function () { st.s = []; save(key, st); draw(); });
    window.addEventListener("resize", draw);
    if (window.matchMedia) {
      var mq = window.matchMedia("(prefers-color-scheme: dark)");
      if (mq.addEventListener) mq.addEventListener("change", draw);
    }
    new MutationObserver(draw).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    draw();
  }
  function scan(root) {
    var pads = (root || document).querySelectorAll("details.scratchpad[data-scratch-key]");
    for (var i = 0; i < pads.length; i++) init(pads[i]);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { scan(); });
  else scan();
  document.addEventListener("htmx:afterSettle", function () { scan(); });
})();


/* Issue 233: when the soft keyboard opens on a phone, keep the focused field in view. */
(function () {
  var vv = window.visualViewport;
  if (!vv) return;
  function keep() {
    var el = document.activeElement;
    if (!el || !el.matches || !el.matches("input:not([type=hidden]):not([type=checkbox]):not([type=radio]), textarea, select")) return;
    var r = el.getBoundingClientRect();
    if (r.bottom > vv.height - 8 || r.top < 0) el.scrollIntoView({ block: "center", behavior: "auto" });
  }
  vv.addEventListener("resize", keep);
  document.addEventListener("focusin", function () { setTimeout(keep, 300); });
})();
