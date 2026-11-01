"""Optional scratchpad on practice steps (#183).

- practice / check steps with choices get a closed <details> scratchpad under the question:
  a dir=auto textarea and a drawing canvas with a clear button.
- The storage key is user + road + step; nothing about the pad is posted to the server.
- An optional ``worked_method`` field on a content node shows collapsed next to the pad;
  nodes without it render no method block (existing JSON keeps working).
- A headless browser test checks the text survives Previous / Next.
"""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login

from myroad_core.content.schema import ContentNode
from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

_CORE = Path(__file__).resolve().parents[1]
_STATIC = _CORE / "src" / "myroad_core" / "ui" / "static"
PID = "path_test_scratchpad"
METHOD = "מסדרים בעמודות.\n7 + 6 = 13: כותבים 3 ומעבירים 1."
KEYS = ("scratch_title", "scratch_hint", "scratch_text_label", "scratch_draw_label", "scratch_clear",
        "worked_method_title")


def _path() -> dict:
    return {
        "id": PID, "subject": "math", "group_ids": ["adult"], "emoji": "➕", "estimated_minutes": 5,
        "titles": {"he": "חיבור", "en": "Addition", "ar": "الجمع"},
        "blurbs": {"he": "חיבור בעמודות.", "en": "Column addition.", "ar": "الجمع بالأعمدة."},
        "topics": [{"id": "t1", "titles": {"he": "חיבור", "en": "Addition", "ar": "الجمع"},
                    "node_ids": ["l1", "p1", "p2", "end"]}],
        "nodes": [
            {"id": "l1", "type": "learn", "title": "הסבר", "body_he": "מחברים מימין לשמאל."},
            {"id": "p1", "type": "practice", "title": "חיבור עם העברה", "body_he": "487 + 256 = ?",
             "choices": [{"id": "a", "label": "633"}, {"id": "b", "label": "743"}], "correct": "b",
             "worked_method": METHOD},
            {"id": "p2", "type": "practice", "title": "עוד אחד", "body_he": "15 + 7 = ?",
             "choices": [{"id": "a", "label": "22"}, {"id": "b", "label": "21"}], "correct": "a"},
            {"id": "end", "type": "celebrate", "title": "סוף", "body_he": "סיימת"},
        ],
    }


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(_path(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "s.db"))
    application = create_learner_app(store=store, seed=False, seed_content=True)
    yield application
    store.close()


def _at(app, steps: int, locale: str = "he") -> tuple[TestClient, str]:
    c = TestClient(app)
    c.cookies.set("myroad_locale", locale)
    login(c, f"pad-{locale}@example.com", first_name="Noa", last_name="Levi")
    c.cookies.set("myroad_locale", locale)
    c.post(f"/play/{PID}/start")
    c.post(f"/play/{PID}/ack")
    for _ in range(steps):
        c.post(f"/play/{PID}/answer", data={"choice": "b"})
    return c, c.get(f"/play/{PID}?view=learn").text


def test_schema_accepts_optional_worked_method() -> None:
    node = ContentNode(type="practice", title="t", body_he="x", worked_method="a\nb")
    assert node.worked_method == "a\nb"
    assert ContentNode(type="practice", title="t", body_he="x").worked_method is None


def test_practice_step_has_closed_scratchpad_under_the_question(app) -> None:
    _, html = _at(app, 0)
    pad = re.search(r'<details class="scratchpad"[^>]*>', html)
    assert pad, "no scratchpad"
    assert " open" not in pad.group(0)  # closed by default
    key = re.search(r'data-scratch-key="([^"]+)"', pad.group(0)).group(1)
    parts = key.split(".")
    assert parts[:2] == ["myroad", "scratch"] and parts[2].startswith("usr_") and parts[3] == PID and parts[4]
    ta = re.search(r"<textarea[^>]*data-scratch-text[^>]*>", html).group(0)
    assert 'dir="auto"' in ta and 'id="scratch-text"' in ta
    assert '<label class="scratch-label" for="scratch-text">כתיבה חופשית</label>' in html
    assert "data-scratch-canvas" in html and "data-scratch-clear" in html
    # Under the question, above the choices; never inside the answer form.
    assert html.index("487") < html.index('class="scratchpad"') < html.index('name="choice"')
    form = html[html.index("data-step-form"):html.index("</form>", html.index("data-step-form"))]
    assert "data-scratch" not in form and "scratch-text" not in form


def test_worked_method_shows_collapsed_with_bidi_and_is_optional(app) -> None:
    c, html = _at(app, 0)
    block = re.search(r'<details class="worked-method">(.*?)</details>', html, re.S)
    assert block and "איך פותרים" in block.group(1)
    assert '<bdi dir="ltr">7 + 6 = 13</bdi>' in block.group(1)
    _, html2 = _at(app, 1, locale="en")  # p2 has no worked_method
    assert "15 + 7" in html2 and "worked-method" not in html2 and 'class="scratchpad"' in html2


def test_non_practice_steps_have_no_scratchpad(app) -> None:
    c = TestClient(app)
    login(c, "learn@example.com", first_name="A", last_name="B")
    c.post(f"/play/{PID}/start")
    assert "class=\"scratchpad\"" not in c.get(f"/play/{PID}?view=learn").text


def test_strings_exist_in_every_locale_without_dashes() -> None:
    for code in ("he", "en", "ar"):
        pack = json.loads((_CORE / "locales" / f"{code}.json").read_text(encoding="utf-8"))
        for k in KEYS:
            assert pack.get(k), f"{code}:{k}"
            assert not re.search(r"[\u2013\u2014]| - ", pack[k]), f"dash in {code}:{k}"
    he = json.loads((_CORE / "locales" / "he.json").read_text(encoding="utf-8"))
    assert he["scratch_title"] == "דף עבודה"


def test_script_is_local_only_and_canvas_is_touch_safe() -> None:
    js = (_STATIC / "platform.js").read_text(encoding="utf-8")
    pad = js[js.index("Scratchpad (#183)"):]
    assert "localStorage" in pad
    assert not re.search(r"fetch\(|XMLHttpRequest|sendBeacon|htmx\.ajax", pad)
    assert "pointerdown" in pad and "setPointerCapture" in pad
    css = (_STATIC / "platform.css").read_text(encoding="utf-8")
    canvas = css[css.index(".scratch-canvas {"):]
    assert "touch-action: none" in canvas[:400] and "color: var(--ink)" in canvas[:400]


# --- headless browser: text survives Previous / Next --------------------------------

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_browser_text_persists_across_prev_next(app) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    uvicorn = pytest.importorskip("uvicorn")
    codes: list[str] = []
    app.state.login_code_sender = lambda email, code: codes.append(code)
    app.state.login_notice_sender = lambda email: None
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        with sync_api.sync_playwright() as p:
            chrome = os.environ.get("MYROAD_CHROME", "/usr/bin/google-chrome")
            try:
                br = p.chromium.launch(executable_path=chrome if Path(chrome).exists() else None,
                                       args=["--no-sandbox"])
            except Exception as exc:  # no browser installed (e.g. CI without playwright browsers)
                pytest.skip(f"no headless browser: {exc}")
            pg = br.new_context(viewport={"width": 375, "height": 812}).new_page()
            pg.request.post(base + "/login", headers={"Origin": base}, form={
                "mode": "register", "first_name": "Noa", "last_name": "Levi", "email": "pw@example.com", "next": "/"})
            assert codes, "no login code"
            pg.request.post(base + "/login/verify", headers={"Origin": base}, form={"code": codes[-1], "next": "/"})
            pg.request.post(base + f"/play/{PID}/start", headers={"Origin": base})
            pg.request.post(base + f"/play/{PID}/ack", headers={"Origin": base})
            pg.goto(base + f"/play/{PID}?view=learn")
            assert "487" in pg.inner_text("#step-card")
            pg.click("details.scratchpad summary")
            pg.fill("#scratch-text", "487 + 256\n7 + 6 = 13 כותבים 3")
            pg.locator("form[action$='/nav'] button").first.click()  # Previous
            pg.wait_for_load_state()
            assert "487" not in pg.inner_text("#step-card")
            pg.locator("form[action$='/nav'] button").last.click()  # Next
            pg.wait_for_load_state()
            assert "487" in pg.inner_text("#step-card")
            assert pg.input_value("#scratch-text") == "487 + 256\n7 + 6 = 13 כותבים 3"
            assert pg.evaluate("document.querySelector('details.scratchpad').open")
            br.close()
    finally:
        server.should_exit = True
        th.join(timeout=5)
