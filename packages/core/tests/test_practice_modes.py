"""Typing, voice transcript, a calm round, and a short level test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app
from myroad_core.ui.practice_modes import (
    build_level_test,
    build_round,
    check_transcript,
    check_typed,
    fold,
    mark_level,
    mark_round,
    new_level_state,
    new_round_state,
    round_view,
)

PID = "path_test_step_player"
HX = {"HX-Request": "true"}


def test_fold_arabic_ignores_harakat_and_alef() -> None:
    assert fold("كِتَاب") == fold("كتاب")
    assert fold("أَنا") == fold("انا")
    assert fold("مَدْرَسَة") == fold("مدرسه")
    assert fold("8") == fold("8.0")
    assert not check_typed({"choices": [{"id": "b", "label": "8"}], "correct": "b"}, "2")
    assert check_typed({"choices": [{"id": "b", "label": "8"}], "correct": "b"}, "8")
    kids = {"speak_text": "I am here", "type": "speak"}
    assert check_transcript(kids, "I am here.")
    assert check_transcript(kids, "well I am here today")
    assert not check_transcript(kids, "I am")


def test_round_streak_resets_and_stops() -> None:
    state = new_round_state(
        [
            {"prompt": "a", "choices": ["1", "2"], "answer": "1", "stage": "s"},
            {"prompt": "b", "choices": ["3", "4"], "answer": "4", "stage": "s"},
        ]
    )
    assert mark_round(state, "1") is True
    assert state["streak"] == 1
    assert mark_round(state, "3") is False
    assert state["streak"] == 0 and state["done"] is True
    view = round_view(state)
    assert view["done"] and view["hits"] == 1 and "answer" not in view


def test_level_test_names_the_missed_stage() -> None:
    state = new_level_state(
        [
            {"prompt": "p", "choices": ["כן", "לא"], "answer": "כן", "stage": "ישר"},
            {"prompt": "q", "choices": ["1", "2"], "answer": "2", "stage": "נגזרת"},
        ]
    )
    assert mark_level(state, "לא") is False
    assert mark_level(state, "2") is True
    assert state["misses"] == ["ישר"] and state["hits"] == 1


def test_english_stage_round_and_level_use_saved_items() -> None:
    items = build_round("path_english_bagrut5_01_zero", "t_letters")
    assert items and all(item["answer"] in item["choices"] for item in items)
    level = build_level_test("path_english_bagrut5_01_zero", 1)
    assert level and {item["stage"] for item in level}


def _path() -> dict:
    return {
        "id": PID, "subject": "math", "group_ids": ["adult"], "emoji": "➖", "estimated_minutes": 10,
        "titles": {"he": "מספרים שליליים", "en": "Negative numbers", "ar": "الأعداد السالبة"},
        "blurbs": {"he": "חיסור של מספר שלילי.", "en": "Subtracting a negative.", "ar": "طرح عدد سالب."},
        "topics": [{"id": "t1", "titles": {"he": "חיסור", "en": "Subtraction"}, "node_ids": ["l1", "p1", "end"]}],
        "nodes": [
            {"id": "l1", "type": "learn", "title": "הסבר", "body_he": "חיסור של מספר שלילי הוא חיבור.",
             "speak_text": "חיסור של מספר שלילי הוא חיבור"},
            {"id": "p1", "type": "practice", "title": "תרגול", "body_he": "כמה זה 5 − (−3)?",
             "choices": [{"id": "a", "label": "2"}, {"id": "b", "label": "8"}],
             "correct": "b", "feedback_ok": "נכון.", "feedback_try": "מינוס של מינוס."},
            {"id": "end", "type": "celebrate", "title": "סוף", "body_he": "סיום"},
        ],
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(_path(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "ui.db"))
    app = create_learner_app(store=store, seed=False, seed_content=True)
    with TestClient(app) as c:
        login(c, "modes@example.com", first_name="Noa", last_name="Levi")
        c.post(f"/play/{PID}/start")
        c.post(f"/play/{PID}/ack")
        yield c
    store.close()


def test_typed_and_voice_check_on_the_step(client: TestClient) -> None:
    page = client.get(f"/play/{PID}?view=learn")
    assert "הקלדה" in page.text and "דיבור" in page.text and "טקסט בלבד" in page.text
    wrong = client.post(f"/play/{PID}/answer", data={"mode": "type", "typed": "2"}, headers=HX)
    assert wrong.status_code == 200 and "step-feedback try" in wrong.text
    # A wrong typed answer does not advance.
    again = client.get(f"/play/{PID}?view=learn")
    assert 'name="typed"' in again.text
    heard = client.post(
        f"/play/{PID}/answer",
        data={"mode": "voice", "transcript": "8"},
        headers=HX,
    )
    assert "step-feedback ok" in heard.text or "נכון" in heard.text


def test_spoken_explanation_checks_the_transcript(client: TestClient) -> None:
    # Fresh session on the learn step: start again.
    client.post(f"/play/{PID}/start", data={"reset": "1"})
    page = client.get(f"/play/{PID}?view=learn")
    assert "דיבור" in page.text
    bad = client.post(f"/play/{PID}/answer", data={"mode": "voice", "transcript": "שלום"}, headers=HX)
    assert "step-feedback try" in bad.text
    ok = client.post(
        f"/play/{PID}/answer",
        data={"mode": "voice", "transcript": "חיסור של מספר שלילי הוא חיבור"},
        headers=HX,
    )
    assert "step-feedback ok" in ok.text or "הבנתי" in ok.text


def test_blank_typed_or_spoken_answer_is_not_a_first_try_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty 'type' or 'voice' submit is not scored and leaves no 'answer' event (#199 first try)."""
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(_path(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "ui.db"))
    try:
        with TestClient(create_learner_app(store=store, seed=False, seed_content=True)) as c:
            login(c, "blank@example.com", first_name="Noa", last_name="Levi")
            c.post(f"/play/{PID}/start")
            c.post(f"/play/{PID}/ack")
            uid = store.get_learner_by_email("blank@example.com")["userId"]
            for data in ({"mode": "type", "typed": "  "}, {"mode": "voice", "transcript": ""}):
                blank = c.post(f"/play/{PID}/answer", data=data, headers=HX)
                assert "בחרו תשובה אחרת" not in blank.text
                assert "צריך תשובה לפני הבדיקה" in blank.text
                assert "step-feedback try" not in blank.text
            assert store.first_try_answers(uid, PID) == []
            assert store.first_try_wrong_count(uid, PID) == 0
            right = c.post(f"/play/{PID}/answer", data={"mode": "type", "typed": "8"}, headers=HX)
            assert "step-feedback ok" in right.text or "נכון" in right.text
            assert [ok for _bid, ok in store.first_try_answers(uid, PID)] == [True]
    finally:
        store.close()
