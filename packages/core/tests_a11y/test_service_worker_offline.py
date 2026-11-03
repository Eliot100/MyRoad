"""Service worker in a real browser (#234, decision 0015): precache, offline page, updates,
and that signed-in pages / API / login responses never land in Cache Storage."""
from __future__ import annotations

import pytest

from conftest import login

LIST_CACHE = """async () => {
  const out = {};
  for (const k of await caches.keys()) {
    out[k] = (await (await caches.open(k)).keys()).map(r => new URL(r.url).pathname);
  }
  return out;
}"""


@pytest.fixture
def ctx(browser_context, server):
    c = browser_context.browser.new_context(base_url=server[0], locale="he-IL")
    yield c
    c.close()


def _ready(pg) -> None:
    pg.evaluate("navigator.serviceWorker.ready.then(() => true)")
    pg.wait_for_function("navigator.serviceWorker.controller !== null || location.reload()", timeout=10_000)


def _caches(pg) -> dict:
    return pg.evaluate(LIST_CACHE)


@pytest.mark.parametrize("locale,lang,dir_", [("he", "he", "rtl"), ("en", "en", "ltr"), ("ar", "ar", "rtl")])
def test_offline_navigation_shows_offline_page_in_locale(ctx, server, locale, lang, dir_) -> None:
    ctx.add_cookies([{"name": "myroad_locale", "value": locale, "url": server[0]}])
    pg = ctx.new_page()
    pg.goto("/login")
    _ready(pg)
    cached = _caches(pg)
    assert len(cached) == 1
    urls = next(iter(cached.values()))
    assert "/offline" in urls and "/static/htmx-2.0.11.min.js" in urls and "/static/platform.css" in urls
    ctx.set_offline(True)
    try:
        pg.goto("/roads")
        assert pg.evaluate("document.documentElement.dir") == dir_
        assert pg.evaluate("document.documentElement.lang").startswith(lang)
        shown = pg.locator(f"main[data-locale={locale}]")
        assert shown.is_visible() and shown.locator("h1").inner_text().strip()
        assert pg.locator("main[data-locale]:visible").count() == 1
    finally:
        ctx.set_offline(False)


def test_signed_in_pages_api_and_login_are_never_cached(ctx, server) -> None:
    pg = ctx.new_page()
    pg.set_default_timeout(10_000)
    login(pg, server[1], email="sw234@example.com")
    _ready(pg)
    pg.goto("/")
    pg.goto("/settings")
    pg.evaluate("fetch('/api/settings/steps', {credentials: 'same-origin'}).then(r => r.status)")
    for urls in _caches(pg).values():
        for u in urls:
            assert u.startswith("/static/") or u == "/offline", u
    # Offline, a signed-in page is not served from any cache: only the offline page.
    ctx.set_offline(True)
    try:
        pg.goto("/settings")
        assert pg.locator("main[data-locale]").count() == 3
        assert "sw234@example.com" not in pg.content()
    finally:
        ctx.set_offline(False)


def test_old_caches_deleted_on_update(ctx) -> None:
    """A previous version's cache (other name, same prefix) is gone once the new SW activates."""
    pg = ctx.new_page()
    pg.goto("/offline")  # no SW registration on this page
    pg.evaluate("caches.open('myroad-shell-old').then(c => c.put('/static/x.css', new Response('x')))")
    pg.evaluate("caches.open('other-app').then(c => c.put('/y', new Response('y')))")
    pg.goto("/login")
    _ready(pg)
    keys = set(_caches(pg))
    assert "myroad-shell-old" not in keys and "other-app" in keys
    assert len([k for k in keys if k.startswith("myroad-shell-")]) == 1


def test_plain_http_lan_host_degrades_cleanly(browser_context, server) -> None:
    """Production today: plain http on a LAN host -> not a secure context, so no SW is
    registered; pages load with no console errors or unhandled rejections."""
    port = server[0].rsplit(":", 1)[1]
    br = browser_context.browser.browser_type.launch(args=["--host-resolver-rules=MAP lan.test 127.0.0.1"])
    errors: list[str] = []
    try:
        pg = br.new_context(locale="he-IL").new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
        pg.add_init_script(
            "window.addEventListener('unhandledrejection', e => console.error('unhandled: ' + e.reason))")
        for path in ("/login", "/roads", "/offline"):
            r = pg.goto(f"http://lan.test:{port}{path}")
            assert r and r.status == 200, path
            pg.wait_for_load_state("load")
        assert pg.evaluate("window.isSecureContext") is False
        assert pg.evaluate("!('serviceWorker' in navigator) || navigator.serviceWorker.getRegistrations()"
                           ".then(r => r.length === 0)")
        pg.wait_for_timeout(300)
        assert errors == []
    finally:
        br.close()


def test_service_workers_blocked_degrades_cleanly(browser_context, server) -> None:
    c = browser_context.browser.new_context(base_url=server[0], locale="he-IL", service_workers="block")
    errors: list[str] = []
    try:
        pg = c.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
        for path in ("/login", "/roads"):
            assert pg.goto(path).status == 200, path
        assert errors == []
    finally:
        c.close()
