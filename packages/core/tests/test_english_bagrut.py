"""Placement decides which English road opens. No database."""

from myroad_core.content.english_bagrut import extra_lock, open_through, placement_band, recommended_index

PLACE = "path_english_bagrut5_00_placement"
ZERO = "path_english_bagrut5_01_zero"
TIME = "path_english_bagrut5_03_time"
MOD_E = "path_english_bagrut5_05_module_e"
EXAM = "path_english_bagrut5_08_exam"


def test_unfinished_placement_opens_nothing_else() -> None:
    progress = {"completedAt": None, "incorrectTaps": 3, "needsPractice": True}
    assert placement_band(progress) == 0
    assert open_through(progress, set()) == 0
    assert extra_lock(ZERO, progress, set())["pathId"] == PLACE
    assert extra_lock(PLACE, progress, set()) is None


def test_many_mistakes_open_only_the_zero_road() -> None:
    progress = {"completedAt": "2026-10-21T00:00:00Z", "incorrectTaps": 6, "needsPractice": True}
    assert placement_band(progress) == 1
    assert extra_lock(ZERO, progress, set()) is None
    assert extra_lock(TIME, progress, set())["pathId"] == ZERO


def test_a_few_mistakes_stop_at_time() -> None:
    progress = {"completedAt": "2026-10-21T00:00:00Z", "incorrectTaps": 2, "needsPractice": False}
    assert placement_band(progress) == 3
    assert extra_lock(TIME, progress, set()) is None
    assert extra_lock(MOD_E, progress, set())["pathId"] == TIME


def test_a_clean_placement_starts_at_module_e() -> None:
    progress = {"completedAt": "2026-10-21T00:00:00Z", "incorrectTaps": 0, "needsPractice": False}
    assert placement_band(progress) == 5
    assert extra_lock(MOD_E, progress, set()) is None
    assert extra_lock(EXAM, progress, set())["pathId"] == MOD_E


def test_finishing_the_weak_road_opens_the_next_not_the_exam() -> None:
    progress = {"completedAt": "2026-10-21T00:00:00Z", "incorrectTaps": 5, "needsPractice": True}
    present = "path_english_bagrut5_02_present"
    assert open_through(progress, {ZERO}) == 2
    assert extra_lock(present, progress, {ZERO}) is None
    assert extra_lock(TIME, progress, {ZERO})["pathId"] == present
    assert extra_lock(EXAM, progress, {ZERO})["pathId"] == present


def test_a_clean_placement_advances_one_road_at_a_time() -> None:
    progress = {"completedAt": "2026-10-21T00:00:00Z", "incorrectTaps": 0, "needsPractice": False}
    module_g = "path_english_bagrut5_06_module_g"
    assert recommended_index(progress, set()) == 5
    assert extra_lock(module_g, progress, set())["pathId"] == MOD_E
    assert open_through(progress, {MOD_E}) == 6
    assert extra_lock(module_g, progress, {MOD_E}) is None
    assert recommended_index(progress, {MOD_E}, weak={MOD_E}) == 5
