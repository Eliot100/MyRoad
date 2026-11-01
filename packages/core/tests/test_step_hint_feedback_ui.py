"""Step hint, per choice feedback and media_hint in the step player (UI for #185).

- ``kids['hint']`` renders as a closed <details> ("רמז") before the choices, only until the step is answered.
- ``choices[i].feedback`` renders under the picked choice only (aria-live polite), never for other choices.
- Absent keys render nothing; ``media_hint`` (an internal asset slug) is never shown as text.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

_CORE = Path(__file__).resolve().parents[1]
PID = "path_test_step_hint"
HX = {"HX-Request": "true"}
HINT = "חשבו על חיבור בעמודות."
FB_A = "633 יוצא כשלא מעבירים את ה 1 לעמודה הבאה."
FB_B = "743: 7 + 6 = 13, כותבים 3 ומעבירים 1."


def _path() -> dict:
    return {
        "id": PID, "subject": "math", "group_ids": ["adult"], "emoji": "➕", "estimated_minutes": 5,
        "titles": {"he": "חיבור", "en": "Addition", "ar": "الجمع"},
        "blurbs": {"he": "חיבור בעמודות.", "en": "Column addition.", "ar": "الجمع بالأعمدة."},
        "topics": [{"id": "t1", "titles": {"he": "חיבור", "en": "Addition", "ar": "الجمع"},
                    "node_ids": ["p1", "p2", "end"]}],
        "nodes": [
            {"id": "p1", "type": "practice", "title": "חיבור עם העברה", "body_he": "487 + 256 = ?",
             "hint": HINT, "media_hint": "column_addition",
             "choices": [{"id": "a", "label": "633", "feedback": FB_A},
                         {"id": "b", "label": "743", "feedback": FB_B},
                         {"id": "c", "label": "733"}],
             "correct": "b", "feedback_try": "נסו שוב.", "feedback_ok": "נכון."},
            {"id": "p2", "type": "practice", "title": "עוד אחד", "body_he": "15 + 7 = ?",
             "choices": [{"id": "a", "label": "22"}, {"id": "b", "label": "21"}], "correct": "a"},
            {"id": "end", "type": "celebrate", "title": "סוף", "body_he": "סיימת"},
        ],
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(_path(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "steps.db"))
    app = create_learner_app(store=store, seed=False, seed_content=True)
    c = TestClient(app)
    c.cookies.set("myroad_locale", "he")
    login(c, "hint@example.com", first_name="Noa", last_name="Levi")
    c.cookies.set("myroad_locale", "he")
    c.post(f"/play/{PID}/start")
    yield c
    store.close()


def test_hint_is_closed_disclosure_before_choices(client) -> None:
    html = client.get(f"/play/{PID}?view=learn").text
    m = re.search(r'<details class="step-hint">\s*<summary>(.*?)</summary>', html)
    assert m and m.group(1) == "רמז"
    assert HINT in html and "<details class=\"step-hint\" open" not in html
    assert html.index('class="step-hint"') < html.index("data-step-form")
    assert "choice-feedback" not in html and "column_addition" not in html


def test_wrong_choice_shows_its_feedback_under_it_only(client) -> None:
    html = client.post(f"/play/{PID}/answer", data={"choice": "a"}, headers=HX).text
    m = re.search(r'value="a".*?</button>\s*<p id="choice-feedback"[^>]*>(.*?)</p>', html, re.S)
    assert m and "633" in m.group(1)
    assert 'aria-live="polite"' in html[html.index('id="choice-feedback"') - 200:html.index('id="choice-feedback"') + 200]
    assert FB_B not in html and html.count('class="choice-feedback"') == 1
    assert 'aria-describedby="choice-feedback step-feedback"' in html
    assert 'class="step-hint"' in html  # still answering, hint stays available
    assert "column_addition" not in html


def test_right_choice_feedback_and_hint_hidden_after(client) -> None:
    html = client.post(f"/play/{PID}/answer", data={"choice": "b"}, headers=HX).text
    assert "choice-feedback" in html and "ומעבירים" in html and 'class="step-hint"' not in html


def test_absent_keys_render_nothing(client) -> None:
    client.post(f"/play/{PID}/answer", data={"choice": "b"})
    client.post(f"/play/{PID}/nav", data={"direction": "next"})
    html = client.post(f"/play/{PID}/answer", data={"choice": "b"}, headers=HX).text
    assert "15 + 7" in html
    assert "step-hint" not in html and "choice-feedback" not in html
    assert 'aria-describedby="step-feedback"' in html


@pytest.mark.parametrize("loc", ["he", "en", "ar"])
def test_hint_title_translated(loc: str) -> None:
    data = json.loads((_CORE / "locales" / f"{loc}.json").read_text(encoding="utf-8"))
    assert data["step_hint_title"] and "-" not in data["step_hint_title"]
