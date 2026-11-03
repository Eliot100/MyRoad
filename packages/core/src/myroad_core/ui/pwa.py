"""Service worker + offline page (#234, docs/decisions/0015-service-worker.md).

Hand-written SW: precaches only the public app shell under /static plus /offline, serves
navigations network-only with /offline as the fallback, and never writes a runtime
response to Cache Storage, so no signed-in page, API answer or cookie can be cached.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response

from myroad_core.ui.i18n import dir_for, html_lang, t

STATIC_DIR = Path(__file__).resolve().parent / "static"
SHELL_SUFFIXES = {".css", ".js", ".woff2"}
CACHE_PREFIX = "myroad-shell-"
OFFLINE_URL = "/offline"
OFFLINE_LOCALES = ("he", "en", "ar")


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


def register_pwa_routes(app: FastAPI) -> None:
    source = sw_source()
    offline = offline_html()

    @app.get("/sw.js", include_in_schema=False)
    def service_worker() -> Response:
        # no-cache: the browser re-checks the SW on every load, so a deploy is picked up.
        return Response(source, media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @app.get(OFFLINE_URL, include_in_schema=False)
    def offline_page() -> HTMLResponse:
        return HTMLResponse(offline, headers={"Cache-Control": "no-cache"})
