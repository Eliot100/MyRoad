"""/roads search screen (preview/netflix-home): renders, subject filter, query, empty state."""
from __future__ import annotations

import re

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient

from auth_helpers import login_with_code
from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app


@pytest.fixture
def client(tmp_path):
    store = PathStore(str(tmp_path / "roads.db"))
    app = create_learner_app(store=store, seed=True, seed_content=True)
    with TestClient(app) as c:
        login_with_code(c, data={"first_name": "R", "last_name": "S", "email": "roads@example.com", "next": "/"})
        yield c
    store.close()


def _ids(html: str) -> list[str]:
    grid = html[html.find('id="rs-results"'):]
    return re.findall(r'class="tv-tile tv-rec rs-card"[^>]*data-path-id="([^"]+)"', grid)


def test_renders_all_roads_with_facets_and_sidebar_button(client) -> None:
    r = client.get("/roads")
    assert r.status_code == 200
    ids = _ids(r.text)
    assert len(ids) >= 5 and "path_grade3_math_add20" in ids
    assert 'role="search"' in r.text and 'name="q"' in r.text
    assert 'name="subject" value="math"' in r.text and 'name="status" value="open"' in r.text
    assert re.search(r'<a class="ibtn" href="/roads"[^>]*aria-current="page"', r.text)
    assert "rs_" not in re.sub(r'(id|class|data-[a-z-]+)="[^"]*"', "", r.text)  # no raw keys
    assert 'href="/road/path_grade3_math_add20"' in r.text
    # Home links the search screen from the sidebar too, and dropped the text "add road" link.
    home = client.get("/").text
    assert 'href="/roads"' in home and 'class="text-link" href="/add-path"' not in home


def test_filter_by_subject(client) -> None:
    ids = _ids(client.get("/roads?subject=english").text)
    assert ids and all("english" in i for i in ids)
    both = _ids(client.get("/roads?subject=english&subject=math").text)
    assert set(ids) < set(both) and any("math" in i for i in both)


def test_query_matches_title_and_description(client) -> None:
    r = client.get("/roads", params={"q": "חיבור עד 20"})
    assert _ids(r.text)[0] == "path_grade3_math_add20"
    assert "path_grade3_english_colors" not in _ids(r.text)
    assert 'value="חיבור עד 20"' in r.text


def test_empty_state_offers_clear(client) -> None:
    r = client.get("/roads", params={"q": "zzzz-no-such-road"})
    assert r.status_code == 200 and _ids(r.text) == []
    assert "לא נמצאה דרך" in r.text and 'href="/roads">ניקוי סינון<' in r.text


def test_sort_by_duration_and_status_filter(client) -> None:
    client.post("/play/path_grade3_math_add20/start")
    client.post("/play/path_grade3_math_add20/ack")
    prog = _ids(client.get("/roads?status=in_progress").text)
    assert prog == ["path_grade3_math_add20"]
    rec = _ids(client.get("/roads").text)
    assert rec[0] == "path_grade3_math_add20"  # started road first in recommended order
    html = client.get("/roads?sort=duration").text
    mins = [int(m) for m in re.findall(r'class="tv-sub tv-foot">(\d+) ', html[html.find('id="rs-results"'):])]
    assert mins == sorted(mins)
