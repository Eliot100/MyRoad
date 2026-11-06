"""Service worker + offline page (#234, docs/decisions/0015-service-worker.md).

Hand-written SW: precaches only the public app shell under /static plus /offline, serves
navigations network-only with /offline as the fallback, and never writes a runtime
response to Cache Storage, so no signed-in page, API answer or cookie can be cached.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, Response

from myroad_core.ui.i18n import dir_for, html_lang, t

STATIC_DIR = Path(__file__).resolve().parent / "static"
SHELL_SUFFIXES = {".css", ".js", ".woff2"}
CACHE_PREFIX = "myroad-shell-"
OFFLINE_URL = "/offline"
OFFLINE_LOCALES = ("he", "en", "ar")

MANIFEST = {
    "name": "MyRoad",
    "short_name": "MyRoad",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "lang": "he",
    "dir": "rtl",
    "theme_color": "#171614",
    "background_color": "#F3EFE6",
    "icons": [
        {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    ],
}


def shell_files() -> list[str]:
    """Public app-shell URLs to precache (CSS, JS incl. htmx, fonts), sorted."""
    files = [p for p in STATIC_DIR.rglob("*") if p.is_file() and p.suffix in SHELL_SUFFIXES and p.name != "sw.template.js"]
    return sorted("/static/" + p.relative_to(STATIC_DIR).as_posix() for p in files)


def offline_html() -> str:
    parts = []
    for code in OFFLINE_LOCALES:
        hidden = "" if code == "he" else " hidden"
        parts.append(
            f'<main class="offline" data-locale="{code}" lang="{html_lang(code)}" dir="{dir_for(code)}"{hidden}>'
            f'<h1>{t(code, "offline_title")}</h1><p>{t(code, "offline_body")}</p>'
            f'<p><a class="primary" href="/">{t(code, "offline_retry")}</a></p></main>'
        )
    return (
        '<!DOCTYPE html>\n<html lang="he" dir="rtl"><head><meta charset="utf-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        '<title>MyRoad</title><link rel="stylesheet" href="/static/platform.css" />'
        '<script src="/static/offline.js" defer></script></head><body>'
        + "".join(parts) + "</body></html>\n"
    )


def shell_version(files: list[str], offline: str) -> str:
    h = hashlib.sha256(offline.encode())
    for url in files:
        h.update(url.encode())
        h.update((STATIC_DIR / url[len("/static/"):]).read_bytes())
    return h.hexdigest()[:12]


def sw_source() -> str:
    files = shell_files()
    offline = offline_html()
    template = (STATIC_DIR / "sw.template.js").read_text(encoding="utf-8")
    return (
        template.replace("__CACHE__", json.dumps(CACHE_PREFIX + shell_version(files, offline)))
        .replace("__PREFIX__", json.dumps(CACHE_PREFIX))
        .replace("__OFFLINE__", json.dumps(OFFLINE_URL))
        .replace("__PRECACHE__", json.dumps(files + [OFFLINE_URL]))
    )


KILL_ENV = "MYROAD_SW_KILL"

# Served instead of the real worker when MYROAD_SW_KILL=1: browsers that installed an older
# worker fetch /sw.js on their next visit, get this one, drop every cache and unregister.
KILL_SW = """/* MyRoad service worker kill switch (MYROAD_SW_KILL=1, decision 0015). */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) await caches.delete(key);
    await self.registration.unregister();
    for (const client of await self.clients.matchAll({ type: "window" })) client.navigate(client.url);
  })());
});
"""


def sw_killed() -> bool:
    return os.environ.get(KILL_ENV, "").strip() == "1"


def register_pwa_routes(app: FastAPI) -> None:
    source = KILL_SW if sw_killed() else sw_source()
    offline = offline_html()

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def web_manifest() -> JSONResponse:
        return JSONResponse(MANIFEST, media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})

    @app.get("/sw.js", include_in_schema=False)
    def service_worker() -> Response:
        # no-cache: the browser re-checks the SW on every load, so a deploy is picked up.
        return Response(source, media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @app.get(OFFLINE_URL, include_in_schema=False)
    def offline_page() -> HTMLResponse:
        return HTMLResponse(offline, headers={"Cache-Control": "no-cache"})
