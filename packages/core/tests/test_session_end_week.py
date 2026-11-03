"""Session end + stage end (#191), week strip (#193), mastered skills on the goal meter (#206).

Decision 0010. Everything stays inside the step card / path head: no separate screen.
Real numbers only; no points, no loss copy, no praise words.
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
from myroad_core.ui.engagement_view import (
    engagement_view, mastered_skills, session_end, stage_end, week_view,
)

_CORE = Path(__file__).resolve().parents[1]
_TPL = _CORE / "src" / "myroad_core" / "ui" / "templates"
PID = "path_test_session_end"
HX = {"HX-Request": "true"}
API = {"X-MyRoad-Request": "1"}
NEW_KEYS = ["eng_week_title", "eng_week_count", "eng_week_day_on", "eng_week_day_off", "eng_week_met",
            "eng_week_today_in", "eng_week_open", "eng_week_goal_change", "eng_week_goal_legend",
            "eng_week_goal_opt", "eng_week_goal_save", "eng_week_goal_saved", "eng_week_goal_error",
            "eng_skills_count", "eng_skills_none", "eng_stage_done", "eng_stage_next", "eng_stage_choose",
            "eng_session_done", "eng_stat_done", "eng_stat_of", "eng_stat_rft", "eng_stat_today",
            "eng_stat_today_yes", "eng_done_today", "eng_one_more"]
LOSS = ["הפסד", "איבדת", "פספסת", "רצף", "נקודות", "כל הכבוד", "מעולה", "lost", "streak", "points"]


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
    login(c, "se@example.com", first_name="Noa", last_name="Levi")
    c.cookies.set("myroad_locale", "he")
    yield c
    store.close()


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html))


def _answer(client, choice: str = "a") -> str:
    return client.post(f"/play/{PID}/answer", data={"choice": choice}, headers=HX).text


def test_locale_keys_present_and_dash_free() -> None:
    for loc in ("he", "en", "ar"):
        j = json.loads((_CORE / "locales" / f"{loc}.json").read_text(encoding="utf-8"))
        for k in NEW_KEYS:
            assert j.get(k), (loc, k)
            assert not re.search(r"[\u2013\u2014]| - ", j[k]), (loc, k)


def test_stage_end_after_closing_a_stage_then_choice(client) -> None:
    client.post(f"/play/{PID}/start")
    first = _answer(client)
    assert "stage-end" not in first and "session-end" not in first
    client.get(f"/play/{PID}?view=learn", headers=HX)
    html = _answer(client)
    assert html.count('class="stage-end"') == 1
    assert "שלב <bdi>1</bdi> מתוך <bdi>2</bdi> הושלם" in html
    assert "המשך לשלב הבא" in html and "בחירה בדרך" in html
    assert f'href="/play/{PID}?view=map"' in html  # returning to the road is a choice
    assert "session-end" not in html


def test_session_end_with_real_numbers_and_two_actions(client) -> None:
    client.post(f"/play/{PID}/start")
    _answer(client, "b")  # wrong first: not right first time
    html = ""
    for i in range(4):
        html = _answer(client)
        if i < 3:
            client.get(f"/play/{PID}?view=learn", headers=HX)
    end = html[html.index('class="session-end"'):]
    txt = _text(end)
    assert "הסשן של היום הושלם" in txt
    assert "<bdi>4</bdi> מתוך <bdi>4</bdi>" in end
    rft = end[end.index("נכון בפעם הראשונה"):]
    assert "<bdi>3</bdi>" in rft[:200]
    assert "נספר בשבוע" in txt
    # This session closed the whole road, so the finish link (records the attempt) leads.
    assert re.search(r'<a class="primary big continue-step" href="/play/%s\?view=stats"' % PID, html)
    for w in LOSS:
        assert w not in txt, w


def test_one_more_button_starts_next_session_hook(client) -> None:
    # A one step "session" closes after the first right answer when the session size is small:
    # render the partial directly with a complete server dict instead.
    html = _render_card_bits({"derived": False, "session": {"no": 2, "steps": [{"id": "x", "done": True}], "size": 1,
                              "done_count": 1, "right_first_time": 1, "complete": True, "can_do": ["לחבר"]},
                              "week": {"days": [{"wd": 1, "today": True, "active": True}]}, "goal_meter": {}},
                             continue_hx=True)
    assert 'data-next-session="/api/path/p/session/next"' in html
    assert "עוד אחד קצר" in html and "לחבר" in html


def _render_card_bits(eng, *, continue_hx=True, st=None) -> str:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(_TPL)), autoescape=True)
    from myroad_core.ui.i18n import t
    from markupsafe import Markup, escape
    env.filters["bdi"] = lambda v: Markup("<bdi>%s</bdi>") % escape(v)
    env.filters["content_lang"] = lambda v, loc: ""
    return env.get_template("_session_end.html").render(
        se=session_end(eng), st=st, doc={"pathId": "p"}, continue_url="/play/p?view=learn",
        continue_hx=continue_hx, locale="he", t=lambda k, **kw: t("he", k, **kw))


def test_session_end_missing_or_derived_engagement_renders_nothing() -> None:
    assert session_end(None) is None
    assert session_end({"derived": True, "session": {"complete": True, "steps": [{}]}}) is None
    assert session_end({"session": {"complete": False, "steps": [{}]}}) is None
    assert _render_card_bits(None).strip() == ""


def test_step_card_without_engagement_keeps_plain_next(client) -> None:
    # A guest (no learner) has no engagement: the old Next link stays, no end blocks.
    c = TestClient(client.app)
    c.cookies.set("myroad_locale", "he")
    c.post(f"/play/{PID}/start")
    html = c.post(f"/play/{PID}/answer", data={"choice": "a"}, headers=HX).text
    assert "session-end" not in html


WEEK = {"start": "2026-11-01", "days": [{"date": f"2026-11-0{i+1}", "wd": i, "active": i in (0, 1), "today": i == 1}
                                       for i in range(7)], "active_count": 2, "goal": 3, "goal_set": False}


def _render_head(eng, locale="he", topics=(), mastered=()) -> str:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(_TPL)), autoescape=True)
    env.globals.update(engagement_view=engagement_view, week_view=week_view, mastered_skills=mastered_skills)
    from myroad_core.ui.i18n import t
    return env.get_template("_path_head_engagement.html").render(
        engagement=eng, topics=list(topics), mastered=set(mastered), doc={"pathId": "p"}, meta={"title": "x"},
        locale=locale, t=lambda k, **kw: t(locale, k, **kw))


SERVER = {"session": {"no": 1, "steps": [{"id": "s1", "title": "T", "done": False}], "size": 1, "done_count": 0,
                      "right_first_time": 0, "complete": False, "can_do": []},
          "week": WEEK, "goal_meter": {"target_label": "800", "stage": 1, "stages_total": 4, "start_stage": None},
          "gap_days": 0, "warmup_suggested": False}


def test_week_strip_text_not_colour_and_forgiving_copy() -> None:
    html = _render_head(SERVER)
    strip = html[html.index('class="week-strip"'):]
    assert "<bdi>2</bdi> מתוך <bdi>3</bdi> ימים" in strip
    assert strip.count('<li class="week-day') == 7 and strip.count("is-active") == 2
    assert "ראשון: היה תרגול" in strip and "שלישי: עוד לא" in strip
    assert 'aria-current="date"' in strip
    assert "היום כבר נספר בשבוע" in strip
    assert "data-weekly-goal hidden" in strip  # needs JS; hidden without it
    assert [m for m in re.findall(r'value="(\d)"', strip)] == ["2", "3", "5"]
    assert re.search(r'value="3" checked', strip)
    for w in LOSS:
        assert w not in _text(strip), w


def test_week_strip_met_and_missing_week() -> None:
    met = json.loads(json.dumps(SERVER)); met["week"]["active_count"] = 3
    assert "הגעת ליעד הימים של השבוע" in _render_head(met)
    none = json.loads(json.dumps(SERVER)); none["week"] = None
    assert "week-strip" not in _render_head(none)
    assert week_view({}, "he") is None


def test_week_strip_locale_order_ar_en() -> None:
    en = json.loads(json.dumps(SERVER))
    en["week"]["days"] = [{"wd": (i + 1) % 7, "active": False, "today": False} for i in range(7)]  # Monday first
    html = _render_head(en, "en")
    names = re.findall(r'class="week-name" aria-hidden="true">(.)<', html)
    assert names == ["M", "T", "W", "T", "F", "S", "S"]
    assert "ح" in _render_head(SERVER, "ar")


def test_goal_meter_skills_line_and_empty_state() -> None:
    topics = [{"title": "א", "blockIds": ["b1", "b2"], "steps": [{"blockId": "b1", "title": "לחבר עד 10"},
                                                                 {"blockId": "b2", "title": "לחבר עם המרה"}]}]
    html = _render_head(SERVER, topics=topics, mastered={"b1", "b2"})
    assert "<bdi>2</bdi> מיומנויות שנשלטו" in html
    lst = html[html.index("goal-skills-list"):]
    assert lst.index("לחבר עם המרה") < lst.index("לחבר עד 10")  # newest (later on the road) first
    empty = _render_head(SERVER)
    assert "המיומנות הראשונה שתשלוט בה תופיע כאן" in empty and "<bdi>0</bdi> מיומנויות" not in empty
    srv = json.loads(json.dumps(SERVER)); srv["goal_meter"]["mastered_can_do"] = ["X", "Y"]
    assert "<bdi>2</bdi> מיומנויות" in _render_head(srv)


def test_stage_end_helper() -> None:
    topics = [{"title": "א", "blockIds": ["a", "b"]}, {"title": "ב", "blockIds": ["c"]}]
    assert stage_end(topics, {"a"}, "a") is None
    st = stage_end(topics, {"a", "b"}, "b")
    assert st["no"] == 1 and st["total"] == 2 and st["has_next"]
    assert stage_end(topics, {"a", "b", "c"}, "c")["has_next"] is False
    assert stage_end(topics, set(), None) is None


def test_map_view_has_week_strip_live(client) -> None:
    client.post(f"/play/{PID}/start")
    _answer(client)
    html = client.get(f"/play/{PID}?view=map").text
    assert 'class="week-strip"' in html and "<bdi>1</bdi> מתוך <bdi>3</bdi> ימים" in html
    assert "<bdi>1</bdi> מיומנויות שנשלטו" in html
    r = client.post("/api/settings/weekly-goal", json={"goal": 5}, headers=API)
    assert r.status_code == 200
    assert "<bdi>1</bdi> מתוך <bdi>5</bdi> ימים" in client.get(f"/play/{PID}?view=map").text


def test_reduced_motion_guard_in_css() -> None:
    css = (_CORE / "src" / "myroad_core" / "ui" / "static" / "platform.css").read_text(encoding="utf-8")
    block = css[css.index(".stage-end-road {"):]
    assert "@media (prefers-reduced-motion: no-preference)" in block[:2000]
    assert "animation" not in block[:block.index("@media (prefers-reduced-motion")]
