"""Read aloud (הקראה): Arabic gets lang 'ar', voice matched by prefix, calm note instead of silence."""

from __future__ import annotations

import json
import re
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
UI = CORE / "src" / "myroad_core" / "ui"
JS = (UI / "static" / "platform.js").read_text(encoding="utf-8")
CARD = (UI / "templates" / "_step_card.html").read_text(encoding="utf-8")
PRODUCT_DASHES = re.compile(r"[\u2013\u2014]| - ")


def test_js_detects_arabic_ranges_and_lang():
    for rng in (r"\u0600-\u06FF", r"\u0750-\u077F", r"\u08A0-\u08FF", r"\uFB50-\uFDFF", r"\uFE70-\uFEFF"):
        assert rng in JS
    assert 'return "ar"' in JS
    assert 'return "he-IL"' in JS and 'return "en-US"' in JS
    # The old Latin-vs-Hebrew-only rule (Arabic fell to he-IL) is gone.
    assert '? "en-US" : "he-IL"' not in JS


def test_js_picks_voice_handles_voiceschanged_and_missing_api():
    assert "getVoices()" in JS and "voiceschanged" in JS
    assert "u.voice = voice" in JS
    assert 'speakNote("novoice")' in JS and 'speakNote("unsupported")' in JS
    assert "data-speak-audio" in JS and "new Audio(" in JS


def test_card_has_live_note_wired_to_strings():
    assert 'id="speak-note"' in CARD
    assert 'aria-live="polite"' in CARD and 'role="status"' in CARD
    assert "t('speak_no_voice')" in CARD and "t('speak_unsupported')" in CARD
    assert "data-speak-audio" in CARD


def test_strings_exist_in_he_en_ar_without_dashes():
    for code in ("he", "en", "ar"):
        d = json.loads((CORE / "locales" / f"{code}.json").read_text(encoding="utf-8"))
        for key in ("speak_no_voice", "speak_unsupported"):
            assert d.get(key), (code, key)
            assert not PRODUCT_DASHES.search(d[key]), (code, key)


def test_browser_en_only_voices_shows_note_and_arabic_is_ar():
    """Real browser run with speechSynthesis stubbed to en-US voices only (Eliot's Windows)."""
    import os
    import shutil

    import pytest

    sync_api = pytest.importorskip("playwright.sync_api")
    exe = os.environ.get("MYROAD_CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
    stub = """(()=>{const vs=[{lang:'en-US',name:'David'}];window.__spoken=[];
    Object.defineProperty(window,'speechSynthesis',{configurable:true,value:{getVoices:()=>vs,speak:u=>window.__spoken.push(u),cancel(){},addEventListener(){},removeEventListener(){}}});
    window.SpeechSynthesisUtterance=function(t){this.text=t};})()"""
    html = (
        '<html dir="rtl" lang="he"><body><button id="btn-speak">הקראה</button>'
        '<p id="speak-source" data-speak="مَرْحَبًا">مَرْحَبًا</p>'
        '<p id="speak-note" role="status" aria-live="polite" hidden data-msg-novoice="NOVOICE" data-msg-unsupported="UNSUP"></p>'
        f"<script>{stub}</script><script>{JS}</script></body></html>"
    )
    with sync_api.sync_playwright() as p:
        try:
            br = p.chromium.launch(executable_path=exe, args=["--no-sandbox"]) if exe else p.chromium.launch()
        except Exception as err:  # no browser installed on this runner
            pytest.skip(f"no chromium: {err}")
        page = br.new_page()
        page.set_content(html)
        assert page.evaluate("MyRoadSpeak.lang('مَرْحَبًا')") == "ar"
        assert page.evaluate("MyRoadSpeak.lang('שלום')") == "he-IL"
        assert page.evaluate("MyRoadSpeak.lang('hello')") == "en-US"
        page.click("#btn-speak")
        page.wait_for_selector("#speak-note:not([hidden])", timeout=3000)
        assert page.inner_text("#speak-note") == "NOVOICE"
        assert page.evaluate("__spoken.length") == 0
        # With an Arabic voice present, it speaks with lang 'ar' and that voice.
        page.evaluate("speechSynthesis.getVoices=()=>[{lang:'en-US'},{lang:'ar-SA',name:'Naayf'}]")
        page.click("#btn-speak")
        assert page.evaluate("[__spoken[0].lang, __spoken[0].voice.name]") == ["ar", "Naayf"]
        assert page.is_hidden("#speak-note")
        br.close()
