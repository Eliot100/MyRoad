"""Next tile, and the weekly plan a finished placement may set.

Pure. The learner database stores reviews and the plan; this module only decides.
"""
from __future__ import annotations

from typing import Any


def plan_from_wrong(incorrect: int) -> dict[str, int]:
    """Starting level and a weekly plan from how many placement items were wrong.

    4 or more: level 1, a short week. 1 to 3: level 2. None: level 3.
    Days are only 2, 3 or 5, the goals the learner store already accepts.
    """
    n = int(incorrect)
    if n >= 4:
        return {"startingLevel": 1, "weeklyTiles": 12, "weeklyMinutes": 40, "weeklyGoal": 2}
    if n >= 1:
        return {"startingLevel": 2, "weeklyTiles": 20, "weeklyMinutes": 70, "weeklyGoal": 3}
    return {"startingLevel": 3, "weeklyTiles": 30, "weeklyMinutes": 100, "weeklyGoal": 5}


def apply_placement_plan(store: Any, user_id: str, placement_id: str, incorrect: int) -> dict[str, int]:
    """Set the plan once. An existing weekly tile target or day goal is left as the learner set it.

    ``startingLevel`` is merged into the stored placement detail so a CAT summary stays.
    """
    plan = plan_from_wrong(incorrect)
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
