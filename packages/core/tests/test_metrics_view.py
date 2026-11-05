"""Metrics screen: weekly history, accuracy, and time, from stored answers only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient

from myroad_core.ui.app import create_learner_app
from myroad_core.ui.metrics_view import build_metrics, stage_accuracy, tile_times, weekly_history
from myroad_core.store import PathStore

PID = "path_english_bagrut5_01_zero"


def _events_week():
    return [
        {"eventType": "answer", "blockId": "a", "ok": True, "createdAt": "2026-11-03T10:00:00+00:00", "durationMs": 60_000},
        {"eventType": "answer", "blockId": "b", "ok": False, "createdAt": "2026-11-03T10:01:00+00:00", "durationMs": 60_000},
    ]


def test_a_week_is_met_only_when_both_saved_targets_are_reached() -> None:
    today = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
    met = weekly_history(_events_week(), weekly_tiles=2, weekly_minutes=2, today=today)
    assert met[-1]["start"] == "2026-11-02"
    assert met[-1]["tiles"] == 2
    assert met[-1]["minutes"] == 2
    assert met[-1]["met"] is True
    missed = weekly_history(_events_week(), weekly_tiles=3, weekly_minutes=1, today=today)
    assert missed[-1]["met"] is False
    no_plan = weekly_history(_events_week(), weekly_tiles=None, weekly_minutes=None, today=today)
    assert no_plan[-1]["met"] is None


def test_missing_duration_does_not_count_as_meeting_the_minute_target() -> None:
    today = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
    events = [{"eventType": "answer", "blockId": "a", "ok": True, "createdAt": "2026-11-03T10:00:00+00:00"}]
    week = weekly_history(events, weekly_tiles=1, weekly_minutes=1, today=today)[-1]
    assert week["tiles"] == 1
    assert week["minutes"] is None
    assert week["met"] is None


def test_history_keeps_the_empty_weeks_between_the_first_answer_and_today() -> None:
    today = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
    events = [{"eventType": "answer", "blockId": "a", "ok": True, "createdAt": "2026-10-26T08:00:00+00:00", "durationMs": 1000}]
    weeks = weekly_history(events, weekly_tiles=None, weekly_minutes=None, today=today)
    assert [week["start"] for week in weeks] == ["2026-10-26", "2026-11-02"]
    assert weeks[1]["tiles"] == 0
    assert weeks[1]["minutes"] == 0


def test_accuracy_is_first_try_and_time_ignores_answers_without_a_duration() -> None:
    topics = [
        {"id": "t", "title": "אותיות", "level": 1, "blockIds": ["a", "b"],
         "steps": [{"blockId": "a", "title": "א"}, {"blockId": "b", "title": "ב"}]},
        {"id": "u", "title": "בדיקה", "level": 2, "blockIds": ["c"],
         "steps": [{"blockId": "c", "title": "ג"}]},
    ]
    events = [
        {"eventType": "answer", "blockId": "a", "ok": True, "createdAt": "2026-11-03T10:00:00+00:00", "durationMs": 1500},
        {"eventType": "answer", "blockId": "a", "ok": False, "createdAt": "2026-11-03T11:00:00+00:00", "durationMs": 4500},
        {"eventType": "answer", "blockId": "c", "ok": False, "createdAt": "2026-11-04T10:00:00+00:00"},
    ]
    stages = stage_accuracy(topics, events)
    assert stages[0]["accuracy"] == 100 and stages[0]["answered"] == 1
    assert stages[1]["accuracy"] == 0 and stages[1]["answered"] == 1
    view = build_metrics(topics, events, {}, today=datetime(2026, 11, 5, tzinfo=timezone.utc))
    assert [row["level"] for row in view["levels"]] == [1, 2]
    assert view["levels"][0]["accuracy"] == 100
    assert view["levels"][1]["accuracy"] == 0
    times = tile_times(topics, events)
    assert [row["blockId"] for row in times] == ["a"]
    assert times[0]["ms"] == 3000


def _mini() -> dict:
    return {
        "id": PID, "subject": "english", "group_ids": ["adult"], "emoji": "א",
        "explain_locale": "he", "content_locale": "en", "estimated_minutes": 20,
        "titles": {"he": "מאפס", "en": "From zero"},
        "blurbs": {"he": "בדיקה.", "en": "Test."},
        "topics": [{
            "id": "t0", "level": 1,
            "titles": {"he": "אותיות", "en": "Letters"},
            "node_ids": ["learn0", "p0"],
        }],
        "nodes": [
            {"id": "learn0", "type": "learn", "title": "הסבר", "body_he": "הסבר.", "body_content": "I am here."},
            {"id": "p0", "type": "practice", "title": "תרגול", "body_he": "בחרו.", "body_content": "I ___ here.",
             "choices": [{"id": "a", "label": "am"}, {"id": "b", "label": "is"}], "correct": "a",
             "feedback_ok": "נכון.", "feedback_try": "עוד."},
        ],
    }


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(_mini(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "metrics.db"))
    app = create_learner_app(store=store, seed=False, seed_content=True)
    yield TestClient(app), store
    store.close()


def test_metrics_page_is_empty_until_there_are_answers(client) -> None:
    http, _store = client
    page = http.get(f"/metrics/{PID}").text
    assert "מדדים" in page
    assert 'data-met="none"' in page
    assert "המגמה תופיע אחרי יומיים של תרגול" in page
    assert "אותיות" in page
    assert 'data-tile=' not in page
    road = http.get(f"/play/{PID}").text
    assert f'href="/metrics/{PID}"' in road
