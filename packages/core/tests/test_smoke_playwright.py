"""Browser smoke: home, roads, one placement question, and one road, at phone and desktop width."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

PLACEMENT = "path_math_bagrut5_00_placement"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("playwright.sync_api")
    uvicorn = pytest.importorskip("uvicorn")
    monkeypatch.setenv("MYROAD_DEV_INSECURE_COOKIES", "1")
    store = PathStore(str(tmp_path / "s.db"))
    app = create_learner_app(store=store, seed=True)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    th.join(timeout=5)
    store.close()


def _browser(p):
    chrome = os.environ.get("MYROAD_CHROME", "/usr/bin/google-chrome")
    try:
        return p.chromium.launch(executable_path=chrome if Path(chrome).exists() else None, args=["--no-sandbox"])
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no headless browser: {exc}")


def _fits(pg) -> None:
    extra = pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert extra <= 8, extra


def _advance(pg) -> bool:
    """Move past a learn card or a step that was just answered."""
    ack = pg.locator("form[action$='/ack'] button")
    if ack.count() and ack.first.is_visible():
        ack.first.click()
        pg.wait_for_load_state("domcontentloaded")
        return True
    nxt = pg.locator("a.continue-step")
    if nxt.count() and nxt.first.is_visible():
        nxt.first.click(timeout=5000)
        pg.wait_for_load_state("domcontentloaded")
        return True
    return False


def _finish_placement(pg, base: str) -> None:
    """Answer the rest of the math check through the same session the browser opened."""
    seen = []
    for _ in range(12):
        resp = pg.request.post(
            base + f"/play/{PLACEMENT}/answer",
            form={"choice": "a"},
            headers={"Origin": base},
            max_redirects=0,
        )
        loc = resp.headers.get("location", "")
        seen.append(f"{resp.status} {loc}")
        if resp.status in (302, 303) and ("view=stats" in loc or (loc and PLACEMENT not in loc)):
            if loc:
                pg.request.get(base + loc if loc.startswith("/") else loc, max_redirects=5)
            return
    raise AssertionError("placement did not finish: " + " | ".join(seen))


def _answer_a(pg) -> None:
    pg.locator("button[name=choice][value=a]:not([disabled])").first.click()
    pg.wait_for_selector("#step-feedback", timeout=10000)


@pytest.mark.parametrize("width", [375, 1280])
def test_home_roads_placement_and_one_road(served: str, width: int) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        br = _browser(p)
        pg = br.new_context(viewport={"width": width, "height": 800}, locale="he-IL").new_page()
        home = pg.goto(served + "/")
        assert home is not None and home.status == 200
        assert pg.locator("#main").count() == 1
        _fits(pg)

        roads = pg.goto(served + "/roads")
        assert roads is not None and roads.status == 200
        assert pg.locator("a[href*='/road/path_']").count() >= 1
        _fits(pg)

        opened = pg.goto(served + f"/play/{PLACEMENT}")
        assert opened is not None and opened.status == 200
        pg.locator("form[action$='/start'] button.primary").first.click()
        pg.wait_for_load_state("domcontentloaded")
        _answer_a(pg)
        feedback = pg.locator("#step-feedback").inner_text()
        assert "נכון" in feedback
        assert "בחרו תשובה אחרת" not in feedback
        _finish_placement(pg, served)

        road = pg.goto(served + "/road/path_math_bagrut5_01_analysis")
        assert road is not None and road.status == 200
        assert "עוד אין תשובות בדרך הזו" in pg.locator("body").inner_text()
        _fits(pg)
        pg.locator("a.primary").first.click()
        pg.wait_for_load_state("domcontentloaded")
        for _ in range(8):
            if pg.locator("button[name=choice][value=a]:not([disabled])").count():
                break
            if not _advance(pg):
                break
        _answer_a(pg)
        assert "נכון" in pg.locator("#step-feedback").inner_text()
        br.close()
