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

  var btnSpeak = document.getElementById("btn-speak");
  var source = document.getElementById("speak-source");
  if (btnSpeak && source) {
    btnSpeak.addEventListener("click", function () {
      speak(source.getAttribute("data-speak") || source.textContent || "");
    });
  }

  // Optional recording (MediaRecorder / SpeechRecognition) — graceful fallback
  var btnRec = document.getElementById("btn-record");
  var recStatus = document.getElementById("record-status");
  if (btnRec) {
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
  var piano = document.getElementById("piano");
  if (piano) {
    var seq = [];
    var seqEl = document.getElementById("piano-seq");
    var seqInput = document.getElementById("piano-sequence");
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
  var rhythm = document.getElementById("rhythm");
  if (rhythm) {
    var pattern = (rhythm.getAttribute("data-pattern") || "").split(",").map(function (x) { return x.trim(); });
    var picked = pattern.map(function () { return null; });
    var seqInput = document.getElementById("rhythm-sequence");
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
    var reset = document.getElementById("rhythm-reset");
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
})();
