"""Behaviour of the bagrut5 road screen model (design D)."""
from datetime import datetime as date

from myroad_core.ui.road_view import (
    build_road, first_try, is_public_catalog, trend_svg_points, uses_road_view, weekly_progress,
)


def _topics(n, per=2):
    return [{"id": f"t{i}", "title": f"T{i}", "blockIds": [f"b{i}_{k}" for k in range(per)]} for i in range(n)]


def test_only_full_five_unit_roads_get_it():
    assert uses_road_view("path_english_bagrut5_06_module_g")
    assert uses_road_view("path_arabic_bagrut5_01_script")
    assert not uses_road_view("path_math_bagrut5_01")
    assert not uses_road_view("path_english_bagrut5_00_placement")
    assert not uses_road_view("path_english_basics")


def test_catalog_keeps_only_bagrut5_subjects():
    assert is_public_catalog("path_english_bagrut5_01_zero", "english")
    assert is_public_catalog("path_math_bagrut5_01", "math")
    assert is_public_catalog("path_physics_bagrut5_01", "physics")
    assert is_public_catalog("path_arabic_bagrut5_01_script", "arabic")
    assert not is_public_catalog("path_grade3_math_add20", "math")
    assert not is_public_catalog("path_math_bagrut_3_units", "math")
    assert not is_public_catalog("path_math_zero_to_equation", "math")
    assert not is_public_catalog("path_english_bagrut5_01_zero", "piano")
    assert not is_public_catalog("path_english_bagrut5_01_zero", None)


def test_levels_follow_the_content_field():
    topics = _topics(6)
    for i, topic in enumerate(topics):
        topic["level"] = 1 if i < 4 else (2 if i == 4 else 3)
    r = build_road(topics, mastered=set(), current_bid="b0_0", open_index=0, total=12,
                   read_only=False, events=[], today=date(2026, 11, 5, 12))
    assert [lv["n"] for lv in r["levels"]] == [1, 2, 3]
    assert [len(lv["stages"]) for lv in r["levels"]] == [4, 1, 1]
    assert r["levelCount"] == 3
    # Six stages with no level field stay one group. Nothing is split into three.
    plain = _road()
    assert [lv["n"] for lv in plain["levels"]] == [None]


def _road(events=(), mastered=(), plan=None, total=12):
    t = _topics(6)
    return build_road(t, mastered=set(mastered), current_bid="b0_0", open_index=0, total=total,
                      read_only=False, events=list(events), today=date(2026, 11, 5, 12), plan=plan)


def test_no_data_means_no_numbers():
    r = _road()
    assert r["recentAccuracy"] is None and r["trend"] == [] and r["done"] == 0
    assert trend_svg_points(r["trend"], 400, 130) == ""
    assert r["week"]["doneTiles"] == 0 and r["week"]["doneMinutes"] == 0
    assert r["week"]["hasTarget"] is False and r["week"]["onTrack"] is None


def test_accuracy_counts_first_try_only():
    ev = [{"blockId": "b0_0", "eventType": "answer", "ok": 0, "createdAt": "2026-11-04T10:00:00"},
          {"blockId": "b0_0", "eventType": "answer", "ok": 1, "createdAt": "2026-11-04T10:01:00"},
          {"blockId": "b0_1", "eventType": "answer", "ok": 1, "createdAt": "2026-11-05T10:00:00"}]
    assert len(first_try(ev)) == 2
    r = _road(ev, mastered={"b0_0", "b0_1"})
    assert r["recentAccuracy"] == 50
    assert r["stages"][0]["state"] == "done" and r["stages"][0]["accuracy"] == 50


def test_weekly_pace_uses_answer_events_and_a_real_plan():
    ev = [
        {"blockId": "b0_0", "eventType": "answer", "ok": 1, "createdAt": "2026-11-04T10:00:00", "durationMs": 60000},
        {"blockId": "b0_0", "eventType": "answer", "ok": 1, "createdAt": "2026-11-04T10:05:00", "durationMs": 60000},
        {"blockId": "b1_0", "eventType": "answer", "ok": 0, "createdAt": "2026-10-01T10:00:00", "durationMs": 60000},
        {"blockId": "b0_1", "eventType": "mastery", "ok": 1, "createdAt": "2026-11-05T10:00:00", "durationMs": 1000},
    ]
    bare = weekly_progress(ev, weekly_tiles=None, weekly_minutes=None, goal_date=None,
                           road_done=0, road_total=12, today=date(2026, 11, 5, 12))
    assert bare["doneTiles"] == 1 and bare["doneMinutes"] == 2 and bare["onTrack"] is None
    missing_time = weekly_progress(
        [{"blockId": "b0_0", "eventType": "answer", "ok": 1, "createdAt": "2026-11-05T10:00:00"}],
        weekly_tiles=4, weekly_minutes=30, goal_date="2026-12-01",
        road_done=0, road_total=12, today=date(2026, 11, 5, 12),
    )
    assert missing_time["doneTiles"] == 1 and missing_time["doneMinutes"] is None
    on = _road(ev, mastered={"b0_0"}, plan={"weeklyTiles": 4, "weeklyMinutes": 30, "goalDate": "2026-12-31"}, total=12)
    assert on["week"]["hasTarget"] is True and on["week"]["onTrack"] is True
    behind = _road(ev, plan={"weeklyTiles": 1, "weeklyMinutes": 10, "goalDate": "2026-11-06"}, total=12)
    assert behind["week"]["onTrack"] is False
    one_sided = _road(ev, plan={"weeklyTiles": 4, "weeklyMinutes": None, "goalDate": "2026-12-31"})
    assert one_sided["week"]["hasTarget"] is False and one_sided["week"]["onTrack"] is None


def test_no_card_is_left_alone_in_a_grid_row():
    r = _road()
    for lv in r["levels"]:
        col = 0
        for s in lv["stages"]:
            col = 0 if s["wide"] else col ^ 1
            if s["wide"]:
                continue
        assert col == 0
