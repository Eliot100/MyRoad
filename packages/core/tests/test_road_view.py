"""Behaviour of the bagrut5 road screen model (design D)."""
from datetime import datetime as date

from myroad_core.ui.road_view import build_road, first_try, split_levels, trend_svg_points, uses_road_view


def _topics(n, per=2):
    return [{"id": f"t{i}", "title": f"T{i}", "blockIds": [f"b{i}_{k}" for k in range(per)]} for i in range(n)]


def test_only_full_five_unit_roads_get_it():
    assert uses_road_view("path_english_bagrut5_06_module_g")
    assert uses_road_view("path_arabic_bagrut5_01_script")
    assert not uses_road_view("path_math_bagrut5_01")
    assert not uses_road_view("path_english_bagrut5_00_placement")
    assert not uses_road_view("path_english_basics")


def test_levels_are_three_consecutive_near_equal_groups():
    assert [len(g) for g in split_levels(9, 3)] == [3, 3, 3]
    assert [len(g) for g in split_levels(11, 3)] == [4, 4, 3]
    assert [len(g) for g in split_levels(2, 3)] == [1, 1]


def _road(events=(), mastered=()):
    t = _topics(6)
    return build_road(t, mastered=set(mastered), current_bid="b0_0", open_index=0, total=12,
                      read_only=False, events=list(events), today=date(2026, 11, 5, 12))


def test_no_data_means_no_numbers():
    r = _road()
    assert r["recentAccuracy"] is None and r["trend"] == [] and r["done"] == 0
    assert trend_svg_points(r["trend"], 400, 130) == ""


def test_accuracy_counts_first_try_only():
    ev = [{"blockId": "b0_0", "eventType": "answer", "ok": 0, "createdAt": "2026-11-04T10:00:00"},
          {"blockId": "b0_0", "eventType": "answer", "ok": 1, "createdAt": "2026-11-04T10:01:00"},
          {"blockId": "b0_1", "eventType": "answer", "ok": 1, "createdAt": "2026-11-05T10:00:00"}]
    assert len(first_try(ev)) == 2
    r = _road(ev, mastered={"b0_0", "b0_1"})
    assert r["recentAccuracy"] == 50
    assert r["stages"][0]["state"] == "done" and r["stages"][0]["accuracy"] == 50


def test_no_card_is_left_alone_in_a_grid_row():
    r = _road()
    for lv in r["levels"]:
        col = 0
        for s in lv["stages"]:
            col = 0 if s["wide"] else col ^ 1
            if s["wide"]:
                continue
        assert col == 0
