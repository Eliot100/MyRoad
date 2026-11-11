"""Path head goal meter + continue card (#193) and the in flow step done moment (#191, first AC).

- The map view head shows 'שלב n מתוך N', the starting point (or an empty state), and a continue
  card with dots for the current short נתיב. The whole road map stays on the same screen.
- ctx['engagement'] from #192 wins when present; otherwise the head is derived from the page.
- A right answer keeps the learner on the step card: ✓ + one 'עכשיו אפשר:' line inside the
  existing polite live region, then Next. No separate screen.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
jinja2 = pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app
from myroad_core.ui.engagement_view import can_do_line, derive_engagement, engagement_view
from myroad_core.ui.i18n import content_lang
from myroad_core.ui.road_view import road_dashboard

_CORE = Path(__file__).resolve().parents[1]
_TPL = _CORE / "src" / "myroad_core" / "ui" / "templates"
PID = "path_test_engagement"
HX = {"HX-Request": "true"}
ENG_KEYS = ["eng_start_before", "eng_start_past", "eng_meter_goal", "eng_meter", "eng_start_from", "eng_start_none", "eng_set_title",
            "eng_set_first", "eng_set_progress", "eng_continue", "eng_now_you_can"]


def _path() -> dict:
    nodes = [{"id": f"p{i}", "type": "practice", "title": f"כלל {i}", "body_he": f"{i} + 1 = ?",
              "choices": [{"id": "a", "label": str(i + 1)}, {"id": "b", "label": "0"}], "correct": "a"}
             for i in range(1, 5)]
    return {
        "id": PID, "subject": "math", "group_ids": ["adult"], "emoji": "➕", "estimated_minutes": 5,
        "titles": {"he": "חיבור", "en": "Addition", "ar": "الجمع"},
        "blurbs": {"he": "חיבור.", "en": "Addition.", "ar": "الجمع."},
        "topics": [{"id": "t1", "titles": {"he": "א", "en": "A", "ar": "أ"}, "node_ids": ["p1", "p2"]},
                   {"id": "t2", "titles": {"he": "ב", "en": "B", "ar": "ب"}, "node_ids": ["p3", "p4"]}],
        "nodes": nodes,
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
    login(c, "eng@example.com", first_name="Noa", last_name="Levi")
    c.cookies.set("myroad_locale", "he")
    yield c
    store.close()


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html))


def test_map_head_empty_state_and_whole_road(client) -> None:
    html = client.get(f"/play/{PID}?view=map").text
    assert 'class="goal-meter"' in html and 'class="road-hero continue-card is-fresh"' in html
    assert "שלב <bdi>1</bdi> מתוך <bdi>2</bdi> בדרך" in html
    assert "עוד אין נקודת התחלה" in html
    assert "הנתיב הקצר הראשון" in html and "התחל את הדרך" in html
    assert html.count('<li class="is-next">') == 1 and "is-done" not in html[html.index("set-dots"):html.index("set-count")]
    assert 'class="stage-grid"' in html and 'id="track"' in html  # the whole road stays on this screen
    assert html.count('class="primary big continue-btn"') == 1  # one primary action, in the hero
    assert "%" not in _text(html[html.index("road-hero"):html.index("eng-links")])


def test_map_head_after_progress_shows_dots_and_continue(client) -> None:
    client.post(f"/play/{PID}/start")
    client.post(f"/play/{PID}/answer", data={"choice": "a"})
    html = client.get(f"/play/{PID}?view=map").text
    dots = html[html.index('class="set-dots"'):html.index('class="set-count')]
    assert dots.count("is-done") == 1 and dots.count("is-next") == 1
    assert "<bdi>1</bdi> מתוך <bdi>4</bdi> בנתיב הזה" in html
    assert "המשך למשבצת הזאת" in html and "הנתיב הקצר שלך" in html


def test_right_answer_shows_step_done_line_in_flow(client) -> None:
    client.post(f"/play/{PID}/start")
    html = client.post(f"/play/{PID}/answer", data={"choice": "a"}, headers=HX).text
    fb = html[html.index('id="step-feedback"'):]
    head = fb[:fb.index(">")]
    assert 'aria-live="polite"' in head and 'role="status"' in head
    assert html.count('class="step-done-line"') == 1
    line = _text(fb[fb.index("step-done-line"):fb.index("</p>", fb.index("step-done-line"))])
    assert "עכשיו אפשר:" in line and "כלל 1" in line
    assert "continue-step" in html  # Next stays on the same card, no separate screen
    assert "כל הכבוד" not in html


def test_wrong_answer_has_no_step_done_line(client) -> None:
    client.post(f"/play/{PID}/start")
    html = client.post(f"/play/{PID}/answer", data={"choice": "b"}, headers=HX).text
    assert "step-done-line" not in html


def _render_head(engagement, locale: str = "he", meta=None) -> str:
    """The road hero (next tile + short נתיב dots + the one button) and the progress head."""
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(_TPL)), autoescape=True)
    env.globals.update(engagement_view=engagement_view)
    env.filters["content_lang"] = content_lang
    from myroad_core.ui.i18n import t
    tpl = env.from_string(
        '{% from "_road_dashboard.html" import road_hero with context %}'
        '{% set eng = engagement_view(engagement, topics, mastered) %}'
        '{{ road_hero(road, eng, doc.pathId, "he") }}{% include "_path_head_engagement.html" %}')
    return tpl.render(engagement=engagement, topics=[], mastered=set(), doc={"pathId": "p"}, meta=meta or {"title": "x"},
                      road=road_dashboard([]), t=lambda k, **kw: t(locale, k, **kw))


SERVER = {"session": {"no": 4, "steps": [{"id": f"s{i}", "title": f"T{i}", "done": i < 2, "right_first_time": i < 2} for i in range(6)],
                      "size": 6, "done_count": 2, "right_first_time": 2, "complete": False, "can_do": ["A", "B"]},
          "week": {}, "goal_meter": {"target_label": "800", "stage": 3, "stages_total": 9, "start_stage": 2, "from_placement": True},
          "gap_days": 4, "warmup_suggested": True}


def test_target_equal_to_title_is_not_repeated() -> None:
    d = json.loads(json.dumps(SERVER)); d["goal_meter"]["target_label"] = "חיבור"
    env_html = _render_head(d, meta={"title": "חיבור"})
    assert "היעד" not in env_html and "שלב <bdi>4</bdi> מתוך <bdi>9</bdi> בדרך" in env_html


def test_server_engagement_dict_wins() -> None:
    html = _render_head(SERVER)
    assert "שלב <bdi>4</bdi> מתוך <bdi>9</bdi>, היעד: <bdi>800</bdi>" in html
    assert "נקודת ההתחלה שלך: שלב <bdi>2</bdi>" in html
    track = html[html.index("goal-track"):html.index("</ol>", html.index("goal-track"))]
    assert track.count("is-done") == 3 and track.count("is-here") == 1 and track.count("is-start") == 1
    assert "<bdi>2</bdi> מתוך <bdi>6</bdi>" in html and 'data-derived="0"' in html


def test_server_empty_state() -> None:
    empty = json.loads(json.dumps(SERVER))
    empty["session"].update(no=1, done_count=0, steps=[{**s, "done": False} for s in empty["session"]["steps"]])
    empty["goal_meter"].update(stage=0, start_stage=None, from_placement=False)
    html = _render_head(empty)
    assert "שלב <bdi>1</bdi> מתוך <bdi>9</bdi>" in html
    assert "עוד אין נקודת התחלה" in html and "is-start" not in html and "התחל את הדרך" in html


def test_absent_engagement_and_no_topics_renders_plain_button() -> None:
    html = _render_head(None)
    assert "goal-meter" not in html and "התחל את הדרך" in html and html.count("<button") == 1


def test_derive_and_can_do() -> None:
    topics = [{"blockIds": ["a", "b"], "steps": [{"blockId": "a", "title": "A"}, {"blockId": "b", "title": "B"}]},
              {"blockIds": ["c"], "steps": [{"blockId": "c", "title": "C"}]}]
    d = derive_engagement(topics, {"a", "b"}, size=2)
    assert d["goal_meter"]["stage"] == 2 and d["session"]["no"] == 2 and d["session"]["steps"][0]["id"] == "c"
    assert can_do_line(SERVER, "s1", "own") == "own"
    assert can_do_line(SERVER, "zz", "fallback") == "fallback"


@pytest.mark.parametrize("loc", ["he", "en", "ar"])
def test_copy_rules(loc: str) -> None:
    data = json.loads((_CORE / "locales" / f"{loc}.json").read_text(encoding="utf-8"))
    for k in ENG_KEYS:
        v = data[k]
        assert v and not re.search(r"[-\u2013\u2014]", v), (k, v)
        assert not any(w in v for w in ("מפגש", "צעד", "כל הכבוד", "!")), (k, v)


@pytest.mark.parametrize("start,expect", [(0, "לפני השלב הראשון"), (9, "מעבר לשלב האחרון")])
def test_start_stage_edges(start: int, expect: str) -> None:
    d = json.loads(json.dumps(SERVER)); d["goal_meter"]["start_stage"] = start
    html = _render_head(d)
    assert expect in html and "is-start" not in html


@pytest.mark.parametrize("label", ["800", '5 יח"ל', "מהבסיס למשפטים"])
def test_target_label_kinds(label: str) -> None:
    d = json.loads(json.dumps(SERVER)); d["goal_meter"]["target_label"] = label
    html = _render_head(d)
    assert "היעד: <bdi>" in html and jinja2.utils.markupsafe.escape(label) in html


def test_step_done_line_is_each_steps_own_can_do() -> None:
    """Regression: can_do is newest first, so indexing by step order showed another step's text."""
    steps = [{"id": f"s{i}", "title": f"T{i}", "done": i < 3, "right_first_time": True} for i in range(4)]
    own = {"s0": "Read a clock", "s1": "Add tens", "s2": "Tell time"}
    eng = {**SERVER, "session": {**SERVER["session"], "steps": steps, "done_count": 3,
                                 "can_do": [own["s2"], own["s1"]]}}  # newest first
    for sid, text in own.items():
        assert can_do_line(eng, sid, text) == text
    assert can_do_line(eng, "s0", None) == ""
