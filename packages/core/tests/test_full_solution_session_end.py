"""Full solution after a wrong answer + session end with continue first (issue 215).

Behaviour seen by the learner in the step card: a miss shows the right answer and the
worked method right there with one next step; the session end shows real progress on the
road, 'now you can' lines as tappable actions, and continue as the filled button.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from auth_helpers import login

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

_CORE = Path(__file__).resolve().parents[1]
PID = "path_test_full_solution"
HX = {"HX-Request": "true"}
METHOD = "אחדות: 7 + 6 = 13. כותבים 3 ומעבירים 1."


def _path() -> dict:
    nodes = []
    for i in range(1, 9):
        node = {"id": f"p{i}", "type": "practice", "title": f"כלל {i}", "can_do": f"לחבר {i} ועוד 1",
                "body_he": f"{i} + 1 = ?",
                "choices": [{"id": "a", "label": str(i + 1), "feedback": f"{i} ועוד 1 הוא {i + 1}."},
                            {"id": "b", "label": "0", "feedback": "אפס יוצא כששוכחים לחבר."}],
                "correct": "a", "feedback_try": "נסו שוב."}
        if i == 1:
            node["worked_method"] = METHOD
        nodes.append(node)
    return {
        "id": PID, "subject": "math", "group_ids": ["adult"], "emoji": "➕", "estimated_minutes": 5,
        "titles": {"he": "חיבור", "en": "Addition", "ar": "الجمع"},
        "blurbs": {"he": "חיבור.", "en": "Addition.", "ar": "الجمع."},
        "topics": [{"id": f"t{i}", "titles": {"he": f"שלב {i}", "en": f"S{i}", "ar": f"م{i}"}, "node_ids": [f"p{i}"]}
                   for i in range(1, 9)],
        "nodes": nodes,
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(_path(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "fs.db"))
    c = TestClient(create_learner_app(store=store, seed=False, seed_content=True))
    c.cookies.set("myroad_locale", "he")
    login(c, "fs@example.com", first_name="Noa", last_name="Levi")
    c.cookies.set("myroad_locale", "he")
    c.post(f"/play/{PID}/start")
    yield c
    store.close()


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html))


def _feedback(card: str) -> str:
    return card.split('id="step-feedback"', 1)[1].split('class="nav row', 1)[0]


def test_wrong_answer_shows_right_answer_full_solution_and_one_next_step(client) -> None:
    card = client.post(f"/play/{PID}/answer", data={"choice": "b"}, headers=HX).text
    fb = _feedback(card)
    txt = _text(fb)
    assert "כמעט. ככה פותרים:" in txt
    assert "התשובה הנכונה:" in txt and "2" in fb.split("התשובה הנכונה:", 1)[1][:200]
    assert "אחדות" in txt and "ומעבירים" in txt  # the worked method, open, in the live region
    assert "בחרו את התשובה המסומנת כדי להמשיך." in txt
    assert "נסו שוב" not in _text(card)  # generic feedback_try gives way to the one instruction
    assert 'id="choice-feedback"' in card and "אפס יוצא כששוכחים לחבר." in card  # picked tile keeps its own note
    assert "✗" not in card  # no red cross as the dominant signal
    # The right tile is marked as the next tap (text, not colour only) and stays enabled.
    right = re.search(r'<button[^>]*value="a"[^>]*>.*?</button>', card, re.S).group(0)
    assert "is-solution" in right and "disabled" not in right and "התשובה הנכונה" in right
    # The method is not repeated in the closed disclosure above the choices.
    assert 'class="worked-method"' not in card
    # Still one primary at most: a miss adds no new filled button.
    assert card.count('class="primary') == 0


def test_wrong_answer_without_worked_method_falls_back_to_the_right_choice_feedback(client) -> None:
    client.post(f"/play/{PID}/answer", data={"choice": "a"}, headers=HX)
    client.get(f"/play/{PID}?view=learn", headers=HX)
    card = client.post(f"/play/{PID}/answer", data={"choice": "b"}, headers=HX).text
    txt = _text(_feedback(card))
    assert "התשובה הנכונה:" in txt and "2 ועוד 1 הוא 3." in txt


def test_right_answer_without_authored_text_shows_a_word_not_two_bare_marks(client) -> None:
    card = client.post(f"/play/{PID}/answer", data={"choice": "a"}, headers=HX).text
    line = _feedback(card).split('class="feedback-line"', 1)[1].split("</p>", 1)[0]
    assert "נכון." in _text(line)
    assert _text(line).count("✓") == 1


def _finish_session(client) -> str:
    html = ""
    for i in range(6):
        html = client.post(f"/play/{PID}/answer", data={"choice": "a"}, headers=HX).text
        if 'class="session-end"' in html:
            return html
        client.get(f"/play/{PID}?view=learn", headers=HX)
    return html


def test_session_end_continue_is_primary_and_done_today_secondary(client) -> None:
    html = _finish_session(client)
    assert 'class="session-end"' in html
    actions = html.split("session-actions", 1)[1]
    first = re.search(r"<a [^>]*>[^<]*</a>", actions).group(0)
    assert 'class="primary big continue-step"' in first and "עוד אחד קצר" in first
    done = re.search(r'<a class="secondary big"[^>]*>[^<]*</a>', actions).group(0)
    assert "סיימתי להיום" in done and f'href="/play/{PID}?view=map"' in done
    assert html.count('class="primary') == 1


def test_session_end_shows_real_road_progress_and_tappable_can_do(client) -> None:
    html = _finish_session(client)
    end = html[html.index('class="session-end"'):]
    txt = _text(end)
    assert "שלבים שהושלמו בנתיב" in txt
    assert "<bdi>6</bdi> מתוך <bdi>8</bdi>" in end
    forms = re.findall(r'<form method="post" action="/play/%s/start" class="cando-form">.*?</form>' % PID, end, re.S)
    assert forms, "now you can lines are real actions"
    assert 'name="node"' in forms[0] and "לתרגל שוב" in forms[0] and "לחבר" in forms[0]


def test_continue_strings_and_new_keys_have_no_dashes() -> None:
    keys = ["continue", "fb_wrong_lead", "fb_right_answer", "fb_pick_solution", "fb_solution_tag",
            "eng_stat_road", "eng_cando_practice"]
    for loc in ("he", "en", "ar"):
        j = json.loads((_CORE / "locales" / f"{loc}.json").read_text(encoding="utf-8"))
        for k in keys:
            assert j.get(k), (loc, k)
            assert not re.search(r"[\u2013\u2014]", j[k]), (loc, k)


def test_back_link_keeps_a_gap_between_arrow_and_word() -> None:
    css = (_CORE / "src" / "myroad_core" / "ui" / "static" / "platform.css").read_text(encoding="utf-8")
    assert re.search(r"\.play \.shell-top \.back[^{]*\{[^}]*gap:", css)
