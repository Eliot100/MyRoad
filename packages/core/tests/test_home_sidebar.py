"""Home status panel is a side column whose side follows locale dir."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code

from myroad_core.ui.app import create_learner_app
from myroad_core.store import PathStore

_CORE = Path(__file__).resolve().parents[1]
_CSS = _CORE / "src" / "myroad_core" / "ui" / "static" / "platform.css"
_MANIFEST = _CORE / "locales" / "manifest.json"


@pytest.fixture
def platform_client(tmp_path):
    store = PathStore(str(tmp_path / "plat.db"))
    app = create_learner_app(store=store, seed=True, seed_content=True)
    with TestClient(app) as client:
        login_with_code(
            client,
            data={
                "first_name": "Test",
                "last_name": "User",
                "email": "sidebar@example.com",
                "next": "/",
            },
            follow_redirects=True,
        )
        yield client
    store.close()


def _layout_slice(html: str) -> str:
    start = html.find('class="home-layout"')
    assert start >= 0, "home layout wrapper missing"
    end = html.find("<footer", start)
    assert end > start
    return html[start:end]


def test_home_rows_render_for_each_manifest_dir(platform_client: TestClient) -> None:
    """Netflix home: no duplicate filter card / tabs; rows render in every locale dir."""
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest["locales"]:
        code = entry["code"]
        page = platform_client.post("/locale", data={"locale": code, "next": "/"}, follow_redirects=True)
        assert page.status_code == 200
        assert f'dir="{entry["dir"]}"' in page.text and f'lang="{code}"' in page.text
        assert 'class="filters' not in page.text and 'class="home-nav' not in page.text
        assert "tv-rec" in page.text


def test_platform_css_sidebar_uses_inline_start_not_physical_side() -> None:
    css = _CSS.read_text(encoding="utf-8")
    block = css.split("/* --- Home status sidebar ---", 1)[1].split(".status-pill.practice", 1)[0]
    assert "grid-template-columns: minmax(13.5rem, 17.5rem) minmax(0, 1fr)" in block
    assert "position: sticky" in block
    assert re.search(r"(?<![\w-])(left|right)\s*:", block) is None
    assert "float:" not in block
    # Narrow screens stack; they must not pin the panel to a physical edge.
    assert "grid-template-columns: 1fr" in block
