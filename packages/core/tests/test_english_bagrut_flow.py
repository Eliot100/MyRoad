"""English 5-unit chain: linear tiles, no station list, and a lock that follows the gap."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code

from myroad_core.content.english_bagrut import series_index
from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

PLACE = "path_english_bagrut5_00_placement"
ZERO = "path_english_bagrut5_01_zero"
TIME = "path_english_bagrut5_03_time"
EMAIL = "bagrut@example.com"


def _mini(pid: str, title: str, prereq: list[str]) -> dict:
    topics, nodes = [], []
    for i in range(2):
        learn, prac = f"l{i}", f"p{i}"
        topics.append({
            "id": f"t{i}",
            "titles": {"he": f"נושא {i}", "en": f"Topic {i}"},
            "emoji": "א",
            "node_ids": [learn, prac],
        })
        nodes.append({
            "id": learn, "type": "learn", "title": f"הסבר {i}",
            "body_he": "הסבר קצר בעברית.", "body_content": "I am here.",
        })
        nodes.append({
            "id": prac, "type": "practice", "title": f"תרגול {i}",
            "body_he": "בחרו את המשפט התקין.", "body_content": "I ___ here.",
            "choices": [{"id": "a", "label": "am"}, {"id": "b", "label": "is"}, {"id": "c", "label": "are"}],
            "correct": "a", "feedback_ok": "נכון.", "feedback_try": "עוד ניסיון.",
        })
    doc = {
        "id": pid, "subject": "english", "group_ids": ["adult"], "emoji": "א",
        "explain_locale": "he", "content_locale": "en", "estimated_minutes": 20,
        "prerequisite_path_ids": prereq,
        "titles": {"he": title, "en": title},
        "blurbs": {"he": "בדיקה של השרשרת.", "en": "Series test."},
        "topics": topics, "nodes": nodes,
    }
    index = series_index(pid)
    if index:  # mirrors MyRoad-content #20: each English road declares its band
        doc["placement_route"] = {"from_placement": PLACE, "band_min": index, "band_max": index}
    return doc


@pytest.fixture
def bagrut_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    docs = [
        _mini(PLACE, "מבדק רמה", []),
        _mini(ZERO, "מאפס", [PLACE]),
        _mini(TIME, "זמן וסיפור", [PLACE]),
    ]
    for doc in docs:
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "bagrut.db"))
    app = create_learner_app(store=store, seed=False, seed_content=True)
    yield app, store
    store.close()


def _client(app) -> TestClient:
    client = TestClient(app)
    client.cookies.set("myroad_locale", "he")
    login_with_code(client, {"first_name": "Eli", "last_name": "R", "email": EMAIL, "next": "/"})
    client.cookies.set("myroad_locale", "he")
    return client


def test_bagrut_map_is_one_tile_per_row_not_stations(bagrut_app) -> None:
    app, _store = bagrut_app
    client = _client(app)
    html = client.get(f"/play/{ZERO}").text
    assert 'data-map="linear"' in html  # the stage grid, in linear mode: tiles past the gap are not buttons
    assert "שלב 1" in html and "שלב 2" in html  # the same word the goal meter uses
    # ZERO is still locked here (no placement yet): every tile is listed, and each part opens
    # read-only through a link, never a start form (one rule for every read-only road).
    assert html.count('data-block-id="') >= 1 and f'href="/play/{ZERO}?topic=' in html
    assert f'action="/play/{ZERO}/start"' not in html
    assert "חזרה לשרשרת" in html


def test_a_tile_past_the_gap_snaps_back(bagrut_app) -> None:
    app, _store = bagrut_app
    client = _client(app)
    html = client.get(f"/play/{PLACE}").text
    ids = re.findall(r'data-block-id="([^"]+)"', html)
    assert len(ids) >= 2
    opened = client.post(f"/play/{PLACE}/start", data={"node": ids[-1]}, follow_redirects=True)
    assert opened.status_code == 200
    card = opened.text[opened.text.find('class="card step-card'):opened.text.find("</section>", opened.text.find('class="card step-card'))]
    assert 'data-node-type="learn"' in card
    assert "הסבר" in card
    assert "תרגול 1" not in card


def test_many_mistakes_lock_everything_past_the_zero_road(bagrut_app) -> None:
    app, store = bagrut_app
    client = _client(app)
    user = store.get_learner_by_email(EMAIL)["userId"]
    store.save_progress(
        user, PLACE, version_id=None, node_index=0, mastered=set(),
        correct_taps=1, incorrect_taps=6, completed_at="2026-10-21T00:00:00+00:00",
        needs_practice=True,
    )
    zero = client.get(f"/play/{ZERO}").text
    assert "lock-banner" not in zero and 'data-map="linear"' in zero
    locked = client.get(f"/play/{TIME}").text
    assert "lock-banner" in locked
    assert ZERO in locked
    chain = client.get("/series/english-bagrut5").text
    gap = chain[chain.find('data-state="gap"') - 80:chain.find('data-state="gap"') + 40]
    assert ZERO in gap
    assert 'data-path-id="' + TIME + '" data-state="locked"' in chain


def test_home_links_the_chain_when_the_roads_are_in_the_catalog(bagrut_app) -> None:
    app, _store = bagrut_app
    client = _client(app)
    home = client.get("/?group=adult").text
    assert 'href="/series/english-bagrut5"' in home
    assert "שרשרת האנגלית" in home


def _finish_placement(client, place: str = PLACE, mistake: bool = True) -> str:
    """Play the placement to the end without following redirects; return the 303 Location (#169)."""
    client.post(f"/play/{place}/start", data={"reset": "1"})
    missed = not mistake
    for _ in range(12):
        html = client.get(f"/play/{place}?view=learn").text
        if 'data-node-type="practice"' in html:
            if not missed:  # one mistake puts the band on road 03
                client.post(f"/play/{place}/answer", data={"choice": "b"})
                missed = True
            r = client.post(f"/play/{place}/answer", data={"choice": "a"}, follow_redirects=False)
        else:
            r = client.post(f"/play/{place}/ack", follow_redirects=False)
        while r.status_code in (302, 303) and r.headers["location"].startswith(f"/play/{place}"):
            r = client.get(r.headers["location"], follow_redirects=False)
        if r.status_code == 303:
            return r.headers["location"]
    return ""


def test_finishing_placement_flows_into_the_next_cell(bagrut_app) -> None:
    app, _store = bagrut_app
    client = _client(app)
    nxt = f"/play/{TIME}?view=learn&from=placement"  # one mistake: band 3
    assert _finish_placement(client) == nxt  # 303, no result screen, no meta refresh
    again = client.get(f"/play/{PLACE}", follow_redirects=False)
    assert again.status_code == 303 and again.headers["location"] == nxt
    step = client.get(nxt).text
    assert 'class="card step-card' in step and "lock-banner" not in step  # straight into a משבצת
    # #212: the per domain result sits above the first step (no separate screen); map stays optional.
    assert 'id="placement-result"' in step and f'href="/play/{TIME}?view=map#here"' in step
    assert 'id="step-card"' in step
    dismissed = client.get(f"/play/{TIME}?view=learn").text
    assert 'id="placement-hint"' not in dismissed and 'id="placement-result"' not in dismissed


def test_finishing_placement_without_recommendation_falls_back_to_series(tmp_path, monkeypatch) -> None:
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PLACE}.json").write_text(json.dumps(_mini(PLACE, "מבדק רמה", []), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "fb.db"))
    try:
        client = _client(create_learner_app(store=store, seed=False, seed_content=True))
        assert _finish_placement(client) == "/series/english-bagrut5"
    finally:
        store.close()


def test_finishing_arabic_placement_routes_to_road_01(tmp_path, monkeypatch) -> None:
    ar_place, ar_zero = "path_arabic_bagrut5_00_placement", "path_arabic_bagrut5_01_script"
    zero = _mini(ar_zero, "ערבית מאפס", [])
    zero.update(subject="arabic", placement_route={"from_placement": ar_place, "band_min": 1, "band_max": 3})
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    ar_doc = _mini(ar_place, "מבדק ערבית", [])
    ar_doc["subject"] = "arabic"
    for doc in (ar_doc, zero):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "ar.db"))
    try:
        app = create_learner_app(store=store, seed=False, seed_content=True)
        assert _finish_placement(_client(app), ar_place) == f"/play/{ar_zero}?view=learn&from=placement"
        # band 5 (no mistakes) is outside road 01's 1-3 route: in-subject fallback, never English
        c2 = TestClient(app)
        login_with_code(c2, {"first_name": "A", "last_name": "B", "email": "ar5@example.com", "next": "/"})
        assert _finish_placement(c2, ar_place, mistake=False) == f"/play/{ar_zero}?view=learn&from=placement"
        # a path that is not a placement still shows its summary
        r = c2.get(f"/play/{ar_zero}", follow_redirects=False)
        assert r.status_code == 200
    finally:
        store.close()


def test_finishing_a_cell_continues_into_the_next_cell(bagrut_app) -> None:
    app, _store = bagrut_app
    client = _client(app)
    _finish_placement(client)  # opens road 03
    client.post(f"/play/{TIME}/start", data={"reset": "1"})
    first = client.get(f"/play/{TIME}?view=learn").text
    after = client.post(f"/play/{TIME}/ack", follow_redirects=True).text
    assert 'class="card step-card' in after and "סיכום הדרך" not in after
    assert 'data-node-type="learn"' in first and 'data-node-type="practice"' in after  # the next משבצת
    assert 'class="road-rail"' in after and 'class="is-here" aria-current="step"' in after  # visible progress
