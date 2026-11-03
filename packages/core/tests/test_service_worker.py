"""Service worker source and offline page (#234, decision 0015). Browser checks: tests_a11y."""
from __future__ import annotations

import json
import re

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app
from myroad_core.ui.pwa import CACHE_PREFIX, shell_files


@pytest.fixture
def client(tmp_path):
    store = PathStore(str(tmp_path / "sw.db"))
    with TestClient(create_learner_app(store=store, seed=False, seed_content=False)) as c:
        yield c
    store.close()


def _precache(src: str) -> list[str]:
    return json.loads(re.search(r"const PRECACHE = (\[.*?\]);", src).group(1))


def test_sw_is_public_root_scoped_no_cache_and_versioned(client) -> None:
    r = client.get("/sw.js", follow_redirects=False)
    assert r.status_code == 200 and "javascript" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-cache"
    assert re.search(rf'const CACHE = "{CACHE_PREFIX}[0-9a-f]{{12}}"', r.text)
    assert 'navigator.serviceWorker.register("/sw.js", { scope: "/" })' in client.get(
        "/static/sw-register.js").text


def test_precache_is_only_public_shell(client) -> None:
    pre = _precache(client.get("/sw.js").text)
    assert "/offline" in pre and "/static/htmx-2.0.11.min.js" in pre
    assert any(u.endswith(".woff2") for u in pre)
    for u in pre:
        assert u == "/offline" or u.startswith("/static/"), u
        assert not re.match(r"^/(api|tools|login|settings|play|author)", u)
        assert client.get(u).status_code == 200, u
    assert "/static/sw.template.js" not in pre and pre[:-1] == shell_files()


def test_sw_never_writes_runtime_responses(client) -> None:
    src = client.get("/sw.js").text
    assert src.count("cache.put(") == 1  # only inside install, over PRECACHE
    install = src[src.index('"install"'):src.index('"activate"')]
    assert "cache.put(" in install and 'credentials: "omit"' in install
    assert "private|no-store" in src
    assert 'key.startsWith(PREFIX) && key !== CACHE' in src  # old caches deleted on activate


def test_offline_page_three_locales_with_dir(client) -> None:
    r = client.get("/offline", follow_redirects=False)
    assert r.status_code == 200
    html = r.text
    for code, d in (("he", "rtl"), ("en", "ltr"), ("ar", "rtl")):
        assert re.search(rf'data-locale="{code}" lang="{code}[^"]*" dir="{d}"', html), code
    assert "אין חיבור" in html and "offline" in html and "اتصال" in html
    assert "Set-Cookie" not in "".join(r.headers.keys()).title()


def test_base_shell_registers_sw(client) -> None:
    assert '<script src="/static/sw-register.js" defer>' in client.get("/login").text


def test_register_is_guarded_for_plain_http(client) -> None:
    """Plain http on a LAN IP is not a secure context: registration is skipped, never thrown."""
    js = client.get("/static/sw-register.js").text
    assert '!("serviceWorker" in navigator) || !window.isSecureContext) return;' in js
    assert ".catch(function () {})" in js  # a failed register is never an unhandled rejection
