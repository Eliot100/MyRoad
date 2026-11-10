"""Next tile, and the weekly plan a finished placement may set.

Pure. The learner database stores reviews and the plan; this module only decides.
"""
from __future__ import annotations

from typing import Any

from myroad_core.content.placement_score import level_from_counts

# Tiles, minutes, and the day goal the learner store already accepts (2, 3 or 5).
_WEEK = {
    1: (12, 40, 2),
    2: (16, 55, 2),
    3: (20, 70, 3),
    4: (25, 85, 5),
    5: (30, 100, 5),
}


def plan_from_score(correct: int, incorrect: int, *, tie_up: bool | None = None) -> dict[str, int]:
    """Starting level 1-5 and the weekly plan that level sets."""
    level = level_from_counts(correct, incorrect, tie_up=tie_up)
    tiles, minutes, days = _WEEK[level]
    return {
        "startingLevel": level,
        "weeklyTiles": tiles,
        "weeklyMinutes": minutes,
        "weeklyGoal": days,
    }


def plan_from_wrong(incorrect: int, correct: int = 0, *, tie_up: bool | None = None) -> dict[str, int]:
    """Same plan, with the wrong-count first so older callers keep their argument order."""
    return plan_from_score(correct, incorrect, tie_up=tie_up)


def apply_placement_plan(
    store: Any,
    user_id: str,
    placement_id: str,
    incorrect: int,
    correct: int | None = None,
    *,
    tie_up: bool | None = None,
) -> dict[str, int]:
    """Set the plan once. An existing weekly tile target or day goal is left as the learner set it.

    ``startingLevel`` is merged into the stored placement detail so a CAT summary stays.
    ``correct`` defaults to 0. Pass both counts from first-try answers, not from retries.
    """
    plan = plan_from_score(0 if correct is None else correct, incorrect, tie_up=tie_up)
    current = store.get_road_plan(user_id)
    if current.get("weeklyTiles") is None:
        store.set_road_plan(
            user_id,
            weekly_tiles=plan["weeklyTiles"],
            weekly_minutes=plan["weeklyMinutes"],
            goal_date=current.get("goalDate"),
        )
    if not store.get_weekly_goal(user_id).get("goal_set"):
        store.set_weekly_goal(user_id, plan["weeklyGoal"])
    detail = dict(store.get_placement_detail(user_id, placement_id) or {})
    detail["startingLevel"] = plan["startingLevel"]
    store.save_placement_detail(user_id, placement_id, detail)
    return plan


def choose_tile(
    order: list[str],
    levels: dict[str, int | None],
    mastered: set[str],
    wrong: set[str],
    due: list[str],
) -> str | None:
    """Due review first, then the lowest-level unmastered mistake, then the next new tile.

    A review whose block is no longer on the road is skipped. ``due`` is already
    limited to reviews that are due today, so a success scheduled for tomorrow
    does not jump the queue.
    """
    known = set(order)
    for block_id in due:
        if block_id in known:
            return block_id
    mistakes = [block_id for block_id in order if block_id in wrong and block_id not in mastered]
    if mistakes:
        def rank(block_id: str) -> tuple[int, int]:
            level = levels.get(block_id)
            return (level if isinstance(level, int) else 99, order.index(block_id))

        return min(mistakes, key=rank)
    for block_id in order:
        if block_id not in mastered:
            return block_id
    return None
