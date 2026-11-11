"""Journey map view model for the road screen (arena c2, 2026-11-11).

Pure: takes the topics from ``_topics_for_ui`` after the map route marked progress on
them (``doneCount``, ``complete``, ``current`` and per step ``done`` / ``current``) and
returns everything ``_journey.html`` draws. No I/O, no scores: only real mastered steps.

Shape of the road: every שלב is a station on one winding road. The road wanders over
three lanes so it reads as a path, not a list; the lane of a station and of the next one
give the curve of the segment between them. Review stations are milestones (diamond).
"""
from __future__ import annotations

from typing import Any

#: Lane positions across the road track, in percent of its width (logical: 0 = inline start).
LANES = (18, 50, 82)
#: A gentle S: center, end, center, start, ... so neighbours never jump two lanes.
_LANE_CYCLE = (1, 2, 1, 0)


def lane_x(i: int) -> int:
    """Horizontal position (percent of the track) of station ``i`` (0-based)."""
    return LANES[_LANE_CYCLE[i % len(_LANE_CYCLE)]]


def _step_state(st: dict[str, Any], *, locked: bool, read_only: bool) -> str:
    if st.get("done"):
        return "done"
    if st.get("current") and not read_only:
        return "here"
    return "lock" if locked else "open"


def journey_view(
    topics: list[dict[str, Any]],
    *,
    read_only: bool = False,
    linear: bool = False,
    gap: int | None = None,
) -> dict[str, Any]:
    """View model for the journey map.

    ``linear``: roads that cannot skip ahead (English / math 5 series). Steps after ``gap``
    (index of the first unmastered step) are locked, and every station shows its steps.
    """
    total_cells = sum(len(tp.get("steps") or []) or int(tp.get("stepCount") or 0) for tp in topics)
    gap = total_cells if gap is None else gap
    stations: list[dict[str, Any]] = []
    here_n = 0
    next_step: dict[str, Any] | None = None
    for i, tp in enumerate(topics):
        steps_in = tp.get("steps") or []
        steps = []
        for st in steps_in:
            locked = linear and not read_only and st.get("index", 0) > gap
            state = _step_state(st, locked=locked, read_only=read_only)
            steps.append({
                "blockId": st.get("blockId"),
                "index": st.get("index", 0),
                "title": st.get("title") or "",
                "titleLang": st.get("titleLang") or "",
                "review": st.get("kind") == "review",
                "state": state,
            })
            if state == "here" and next_step is None:
                next_step = {**steps[-1], "stage": tp.get("title") or "", "stageLang": tp.get("titleLang") or "",
                             "stageN": i + 1}
        count = len(steps) or int(tp.get("stepCount") or 0)
        done = int(tp.get("doneCount") or sum(1 for s in steps if s["state"] == "done"))
        first_ix = steps[0]["index"] if steps else 0
        if tp.get("complete"):
            state = "done"
        elif tp.get("current") and not read_only:
            state = "here"
            here_n = i + 1
        elif linear and not read_only and first_ix > gap:
            state = "lock"
        else:
            state = "open"
        stations.append({
            "id": tp.get("id"),
            "n": i + 1,
            "title": tp.get("title") or "",
            "titleLang": tp.get("titleLang") or "",
            "review": bool(tp.get("isReview")),
            "state": state,
            "started": done > 0 and state != "done",
            "done": done,
            "total": count,
            "pct": int(round(100 * done / count)) if count else 0,
            "x": lane_x(i),
            "steps": steps,
        })
    # The segment after a station is travelled once that station is done.
    for i, s in enumerate(stations):
        s["nextX"] = stations[i + 1]["x"] if i + 1 < len(stations) else 50
        s["travelled"] = s["state"] == "done"
    cells_done = sum(s["done"] for s in stations)
    return {
        "stations": stations,
        "here_n": here_n,
        "stages_total": len(stations),
        "stages_done": sum(1 for s in stations if s["state"] == "done"),
        "cells_done": cells_done,
        "cells_total": total_cells,
        "finished": bool(stations) and all(s["state"] == "done" for s in stations),
        "next": next_step,
        "linear": linear,
        "read_only": read_only,
        "end_x": 50,
    }


__all__ = ["journey_view", "lane_x", "LANES"]
