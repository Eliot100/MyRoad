"""The math metrics block sits on the stats screen and does not add links to the aside."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient  # noqa: E402

from auth_helpers import login  # noqa: E402
from myroad_core.store import PathStore  # noqa: E402
from myroad_core.ui.app import create_learner_app  # noqa: E402

PID = "path_math_bagrut5_01_algebra"


def _path() -> dict:
    return {
        "id": PID,
        "subject": "math",
        "group_ids": ["adult"],
        "emoji": "🔢",
        "estimated_minutes": 30,
        "explain_locale": "he",
        "content_locale": "he",
        "titles": {"he": "אלגברה", "en": "Algebra", "ar": "الجبر"},
        "blurbs": {"he": "שלב ראשון.", "en": "First stage.", "ar": "مرحلة."},
        "topics": [
            {"id": "alg_l1", "titles": {"he": "רמה 1", "en": "Level 1"}, "node_ids": ["learn", "practice"]},
            {"id": "alg_l2", "titles": {"he": "רמה 2", "en": "Level 2"}, "node_ids": ["learn2"]},
        ],
        "nodes": [
            {"id": "learn", "type": "learn", "title": "הסבר", "body_he": "מעבירים אגף ומחלקים."},
            {"id": "practice", "type": "practice", "title": "תרגול", "body_he": "פתרו 2x = 6.",
             "choices": [{"id": "a", "label": "3"}, {"id": "b", "label": "4"}], "correct": "a",
             "feedback_ok": "נכון.", "feedback_try": "חלקו ב 2."},
            {"id": "learn2", "type": "learn", "title": "המשך", "body_he": "עוד הסבר קצר."},
        ],
    }


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(_path(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "steps.db"))
    app = create_learner_app(store=store, seed=False, seed_content=True)
    c = TestClient(app)
    c.cookies.set("myroad_locale", "he")
    login(c, "noa-math@example.com", first_name="Noa", last_name="Levi")
    yield c
    store.close()


def test_stats_shows_level_and_keeps_the_aside_free_of_links(client: TestClient) -> None:
    client.post(f"/play/{PID}/start")
    page = client.get(f"/play/{PID}?view=stats").text
    main = page.split("<main", 1)[1].split("</main>", 1)[0]
    assert "stage-board" in main
    assert "רמה 0/2" in main
    assert "מגמת דיוק כללית" in main
    assert main.find("stage-board") < main.find("rm-side")
    aside = main.split('<aside class="card rm-side"', 1)[1]
    assert aside.count("<a ") == 0


def test_math_chain_page_opens_on_the_placement(client: TestClient) -> None:
    page = client.get("/series/math-bagrut5").text
    assert "שרשרת המתמטיקה, 5 יחידות" in page
    assert 'data-path-id="path_math_bagrut5_00_placement"' in page
    assert 'data-state="gap"' in page
    assert page.count('data-state="locked"') == 13
