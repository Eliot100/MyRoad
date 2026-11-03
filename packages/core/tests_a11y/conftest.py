"""Accessibility (axe-core) checks of the learner flow in a real browser (issue #61).

Not part of core-tests: pytest's testpaths is ``tests`` only. Run with
``pytest tests_a11y`` after ``pip install -r tests_a11y/requirements.txt`` and
``python -m playwright install chromium``. See decision 0008.

One uvicorn server on a temp SQLite DB and temp CONTENT_DIR (real content plus
the small fixture path in this folder), one Chromium, one browser context.
Sign in goes through the real two step email code flow; the code is read from
the server's dev mail console (MYROAD_DEV_MAIL_CONSOLE=1, local only).
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

HERE = Path(__file__).resolve().parent
CORE = HERE.parent
EMAIL = "a11y@example.com"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server():
    """Yield (base_url, log_path) of a seeded app on a temp DB."""
    src = Path(os.environ.get("CONTENT_DIR") or CORE / "content")
    if not any(src.rglob("*.json")):
        pytest.skip(f"no content in {src}; vendor MyRoad-content first")
    tmp = Path(tempfile.mkdtemp(prefix="myroad-a11y-"))
    content = tmp / "content"
    shutil.copytree(src, content, ignore=shutil.ignore_patterns(".git"))
    for fx in HERE.glob("path_a11y_*.json"):
        shutil.copy(fx, content / "adult" / fx.name)
    port = _free_port()
    log = tmp / "server.log"
    env = {
        **os.environ,
        "CONTENT_DIR": str(content),
        "MYROAD_DB": str(tmp / "a11y.db"),
        "MYROAD_DEV_MAIL_CONSOLE": "1",
        "MYROAD_DEV_INSECURE_COOKIES": "1",
    }
    env.pop("MYROAD_SMTP_HOST", None)
    with open(log, "w") as out:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "myroad_core.ui.app:app", "--host", "127.0.0.1",
             "--port", str(port), "--log-level", "warning"],
            cwd=CORE, env=env, stdout=out, stderr=subprocess.STDOUT,
        )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/health", timeout=1)
                break
            except OSError:
                if proc.poll() is not None:
                    raise RuntimeError(log.read_text())
                time.sleep(0.2)
        else:
            raise RuntimeError("server did not start:\n" + log.read_text())
        yield base, log
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def browser_context(server):
    """One Chromium and one context for the whole run; tests change viewport/theme on the page."""
    with playwright_sync.sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(base_url=server[0], locale="he-IL")
        yield context
        context.close()
        browser.close()


@pytest.fixture(scope="session")
def page(browser_context, server):
    pg = browser_context.new_page()
    pg.set_default_timeout(10_000)
    yield pg
    pg.close()


def login(page, log: Path, email: str = EMAIL) -> None:
    """Register + sign in through the real form; the code comes from the dev mail console."""
    page.goto("/login?mode=register")
    page.fill("input[name=first_name]", "Ada")
    page.fill("input[name=last_name]", "Test")
    page.fill("input[name=email]", email)
    page.locator("form:has(input[name=email]) [type=submit]").first.click()
    page.wait_for_url(re.compile(r"/login/verify"))
    code = None
    for _ in range(50):
        found = re.findall(rf"Code for {re.escape(email)}: (\w+)", log.read_text())
        if found:
            code = found[-1]
            break
        time.sleep(0.1)
    assert code, "no login code in the dev mail console"
    field = page.locator("input[name=code]")
    if field.get_attribute("data-autosubmit") is not None:
        # login-code.js (#59) submits once by itself when the full code is in.
        with page.expect_navigation():
            page.fill("input[name=code]", code)
    else:
        page.fill("input[name=code]", code)
        page.locator("form:has(input[name=code]) [type=submit]").first.click()
    page.wait_for_url(lambda url: "/login" not in url)
