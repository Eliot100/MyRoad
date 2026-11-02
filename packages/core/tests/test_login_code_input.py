"""Login code field (#59): one input, paste and autofill, works without JS.

Template/CSS/JS only; server auth logic is untouched.
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
from auth_helpers import request_login_code

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

LOCALES = Path(__file__).resolve().parents[1] / "locales"
USER = {"mode": "register", "first_name": "Noa", "last_name": "Levi", "email": "code@example.com", "next": "/"}
STATIC = Path(__file__).resolve().parents[1] / "src" / "myroad_core" / "ui" / "static"


@pytest.fixture
def app(tmp_path: Path):
    store = PathStore(str(tmp_path / "s.db"))
    application = create_learner_app(store=store, seed=False)
    yield application
    store.close()


def _verify_page(app, locale: str = "he", error: str | None = None) -> tuple[TestClient, str, str]:
    c = TestClient(app)
    c.cookies.set("myroad_locale", locale)
    resp, outbox = request_login_code(c, USER)
    assert resp.status_code == 303 and outbox
    url = resp.headers["location"] + (f"&error={error}" if error else "")
    return c, c.get(url).text, outbox[-1][1]


def _code_input(html: str) -> str:
    m = re.search(r"<input id=\"code\"[^>]*>", html, re.S)
    assert m, "no #code input"
    return m.group(0)


@pytest.mark.parametrize("locale", ["he", "en", "ar"])
def test_single_code_input_attributes(app, locale: str) -> None:
    _, html, _ = _verify_page(app, locale)
    assert html.count('name="code"') == 1, "exactly one code field"
    tag = _code_input(html)
    for attr in ('autocomplete="one-time-code"', 'inputmode="numeric"', 'pattern="[0-9]{8}"',
                 'maxlength="8"', 'dir="ltr"', "required", 'aria-describedby="code-hint"'):
        assert attr in tag, attr
    assert '<label for="code">' in html
    assert 'id="code-hint"' in html
    assert "/static/login-code.js" in html
    assert "aria-invalid" not in tag


def test_error_is_tied_to_field(app) -> None:
    _, html, _ = _verify_page(app, "he", error="code_wrong")
    tag = _code_input(html)
    assert 'aria-describedby="code-hint code-error"' in tag
    assert 'aria-invalid="true"' in tag
    m = re.search(r'<p id="code-error"[^>]*role="alert"[^>]*>([^<]+)</p>', html)
    assert m and m.group(1).strip()
    # The error sits after the field, not above the heading.
    assert html.index('id="code-error"') > html.index('id="code"')


def test_hint_copy_in_all_locales_without_dashes() -> None:
    for loc in ("he", "en", "ar"):
        text = json.loads((LOCALES / f"{loc}.json").read_text(encoding="utf-8"))["login_code_hint"]
        assert text and not re.search("[-\u2013\u2014]", text), loc


def test_js_is_progressive_and_local() -> None:
    js = (STATIC / "login-code.js").read_text(encoding="utf-8")
    assert "fetch(" not in js and "localStorage" not in js and "XMLHttpRequest" not in js


def test_no_js_post_signs_in(app) -> None:
    c, _, code = _verify_page(app)
    r = c.post("/login/verify", data={"code": code, "next": "/"}, follow_redirects=False)
    assert r.status_code == 303 and not r.headers["location"].startswith("/login")


# --- headless browser -------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def served(app):
    pytest.importorskip("playwright.sync_api")
    uvicorn = pytest.importorskip("uvicorn")
    codes: list[str] = []
    app.state.login_code_sender = lambda email, code: codes.append(code)
    app.state.login_notice_sender = lambda email: None
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", codes
    server.should_exit = True
    th.join(timeout=5)


def _browser(p):
    chrome = os.environ.get("MYROAD_CHROME", "/usr/bin/google-chrome")
    try:
        return p.chromium.launch(executable_path=chrome if Path(chrome).exists() else None, args=["--no-sandbox"])
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no headless browser: {exc}")


def _to_verify(pg, base: str, codes: list[str]) -> str:
    pg.request.post(base + "/login", headers={"Origin": base}, form=USER, max_redirects=0)
    assert codes
    pg.goto(base + "/login/verify?next=/&email=code@example.com")
    return codes[-1]


PASTE = """(t) => { const i = document.getElementById('code'); i.focus();
  const dt = new DataTransfer(); dt.setData('text/plain', t);
  i.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
  return i.value; }"""


def test_browser_paste_normalizes_digits(served) -> None:
    from playwright.sync_api import sync_playwright
    base, codes = served
    with sync_playwright() as p:
        br = _browser(p)
        pg = br.new_context(viewport={"width": 375, "height": 812}).new_page()
        _to_verify(pg, base, codes)
        pg.evaluate("document.getElementById('code').removeAttribute('data-autosubmit')")
        assert pg.evaluate(PASTE, " 1234-56 78 ") == "12345678"
        assert pg.evaluate(PASTE, "123 456") == "123456"  # partial paste kept, browser validation asks for more
        assert pg.evaluate(PASTE, "١٢٣٤٥٦٧٨") == "12345678"
        assert pg.evaluate(PASTE, "1234567890") == "12345678"
        pg.fill("#code", "")
        pg.type("#code", "12a3-4")
        assert pg.input_value("#code") == "1234"
        br.close()


def test_browser_paste_full_code_submits_once(served) -> None:
    from playwright.sync_api import sync_playwright
    base, codes = served
    with sync_playwright() as p:
        br = _browser(p)
        pg = br.new_context(viewport={"width": 375, "height": 812}).new_page()
        code = _to_verify(pg, base, codes)
        posts: list[str] = []
        pg.on("request", lambda r: posts.append(r.url) if r.method == "POST" and r.url.endswith("/login/verify") else None)
        with pg.expect_navigation():
            pg.evaluate(PASTE, code[:4] + " " + code[4:])
        pg.wait_for_load_state()
        # A second submit attempt on the same page load is ignored.
        assert len(posts) == 1
        assert "/login" not in pg.url
        br.close()


def test_browser_no_js_submit(served) -> None:
    from playwright.sync_api import sync_playwright
    base, codes = served
    with sync_playwright() as p:
        br = _browser(p)
        pg = br.new_context(java_script_enabled=False, viewport={"width": 375, "height": 812}).new_page()
        code = _to_verify(pg, base, codes)
        pg.fill("#code", code)
        with pg.expect_navigation():
            pg.click("button[type=submit].primary")
        assert "/login" not in pg.url
        br.close()
