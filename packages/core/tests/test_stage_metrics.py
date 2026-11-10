"""Level x/y, last-N accuracy, and the trend. No screen, no database."""

from datetime import date

from myroad_core.content.math_bagrut import first_gap, road_state
from myroad_core.content.stage_metrics import build_stage_board, level_of


def test_level_stops_at_the_first_open_level() -> None:
    topics = [
        {"id": "alg_l1", "blockIds": ["a", "b"]},
        {"id": "alg_l2", "blockIds": ["c"]},
        {"id": "alg_l3", "blockIds": ["d"]},
        {"id": "alg_review", "blockIds": ["e"]},
    ]
    assert level_of(topics, {"a", "b"}) == (1, 3)
    assert level_of(topics, {"a", "b", "c", "d"}) == (3, 3)
    # l2 is done but l1 is not, so the level stays 0.
    assert level_of(topics, {"c"}) == (0, 3)
    assert level_of([{"id": "plain", "blockIds": ["a"]}], {"a"}) == (0, 0)


def test_board_uses_last_window_and_skips_other_roads() -> None:
    rows = [{"pathId": "path_math_bagrut5_01_algebra", "title": "אלגברה", "topics": [
        {"id": "alg_l1", "blockIds": ["a"]},
        {"id": "alg_l2", "blockIds": ["b"]},
        {"id": "alg_l3", "blockIds": ["c"]},
    ], "mastered": {"a"}}]
    events = [
        {"pathId": "path_math_bagrut5_01_algebra", "eventType": "answer", "ok": False, "createdAt": "2026-05-01T10:00:00+00:00"},
        {"pathId": "other", "eventType": "answer", "ok": True, "createdAt": "2026-05-02T10:00:00+00:00"},
    ]
    events += [
        {"pathId": "path_math_bagrut5_01_algebra", "eventType": "answer", "ok": True, "createdAt": f"2026-05-{day:02d}T10:00:00+00:00"}
        for day in range(3, 8)
    ]
    board = build_stage_board(rows, events, recent=20, window=4, trend_days=30, today=date(2026, 5, 20))
    assert board["rows"][0]["level"] == 1
    assert board["rows"][0]["levels"] == 3
    # Last 4 answers on this road are the five-minus-one correct tail: 4 corrects.
    assert board["rows"][0]["accuracy"] == 100
    assert board["rows"][0]["spark"]
    assert board["meanLevel"] == "1.0"
    assert board["levelScale"] == 3
    assert board["recentAccuracy"] == 83  # 5 correct, 1 wrong, the other road is ignored
    assert board["trendLine"]
    assert board["trendPoints"][0]["label"] == "1.5"


def test_empty_history_is_not_a_fake_percent() -> None:
    board = build_stage_board(
        [{"pathId": "path_math_bagrut5_01_algebra", "title": "אלגברה", "topics": [{"id": "alg_l1", "blockIds": ["a"]}], "mastered": set()}],
        [],
    )
    assert board["rows"][0]["accuracy"] is None
    assert board["recentAccuracy"] is None
    assert board["trendPoints"] == []
    assert board["meanLevel"] == "0.0"


def test_chain_does_not_open_the_exam_early() -> None:
    done = {"path_math_bagrut5_00_placement", "path_math_bagrut5_01_algebra"}
    assert first_gap(done) == 2
    assert road_state(1, done) == "done"
    assert road_state(2, done) == "gap"
    assert road_state(13, done) == "locked"
    assert road_state(1, done, {"path_math_bagrut5_01_algebra"}) == "review"
