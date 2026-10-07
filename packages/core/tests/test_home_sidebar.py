"""Home status panel is a side column whose side follows locale dir."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient

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
        client.post(
            "/login",
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


def test_status_panel_is_start_column_for_each_manifest_dir(platform_client: TestClient) -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    for entry in manifest["locales"]:
        code = entry["code"]
        direction = entry["dir"]
        page = platform_client.post(
            "/locale",
            data={"locale": code, "next": "/?tab=catalog&view=status"},
            follow_redirects=True,
        )
        assert page.status_code == 200
        assert f'dir="{direction}"' in page.text
        assert f'lang="{code}"' in page.text
        layout = _layout_slice(page.text)
        nav = layout.find('class="home-nav')
        catalog = layout.find('class="home-catalog"')
        filters = layout.find('class="filters')
        assert 0 <= nav < catalog < filters, (code, nav, catalog, filters)
        assert "view=status" in layout and "view=time" in layout
        assert "tab=in_progress" in layout
        assert "tab=completed" in layout
        assert "tab=practice" in layout
        # Group/subject filters stay in the catalog column.
        assert "group=all" in layout[filters:]
        assert "subject=all" in layout[filters:]


def test_platform_css_sidebar_uses_inline_start_not_physical_side() -> None:
    css = _CSS.read_text(encoding="utf-8")
    block = css.split("/* --- Home status sidebar ---", 1)[1].split(".status-pill.practice", 1)[0]
    assert "grid-template-columns: minmax(13.5rem, 17.5rem) minmax(0, 1fr)" in block
    assert "position: sticky" in block
    assert re.search(r"(?<![\w-])(left|right)\s*:", block) is None
    assert "float:" not in block
    # Narrow screens stack; they must not pin the panel to a physical edge.
    assert "grid-template-columns: 1fr" in block
