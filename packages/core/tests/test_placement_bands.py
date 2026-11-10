"""Every 5-unit placement can return a starting level 1-5.

The bank has at least two scored items in each difficulty band. The level is
the first-try percent, and an exact edge uses the hardest item as a tie-break.
"""

from myroad_core.content.loader import load_content_paths
from myroad_core.content.placement_score import (
    band_counts,
    level_from_counts,
    placement_band_gaps,
    tie_up_from_answers,
)


def test_each_subject_placement_has_two_items_in_every_band() -> None:
    paths = {p.id: p for p in load_content_paths()}
    ids = [
        "path_english_bagrut5_00_placement",
        "path_math_bagrut5_00_placement",
        "path_physics_bagrut5_00_placement",
        "path_arabic_bagrut5_00_placement",
    ]
    for pid in ids:
        path = paths[pid]
        assert placement_band_gaps(pid, path.nodes) == []
        counts = band_counts(path.nodes)
        assert all(counts[band] >= 2 for band in range(1, 6)), counts


def test_tie_break_uses_the_hardest_answered_item() -> None:
    items = [
        type("I", (), {"block_id": "easy", "b": -2.0, "order": 0})(),
        type("I", (), {"block_id": "hard", "b": 2.0, "order": 1})(),
    ]
    assert tie_up_from_answers(items, [("easy", False), ("hard", True)]) is True
    assert tie_up_from_answers(items, [("easy", True), ("hard", False)]) is False
    assert tie_up_from_answers(items, [("missing", True)]) is None
    # 2 of 10 is exactly 20. The hard item lifts it; a miss keeps level 1.
    assert level_from_counts(2, 8, tie_up=True) == 2
    assert level_from_counts(2, 8, tie_up=False) == 1
    assert level_from_counts(2, 8) == 1
