"""View model for the road page timeline (map view of /play/{path_id}).

One pure function turns the road's topics (שלבים) and steps (משבצות) plus the learner's
position into what the template draws: one vertical line of שלבים, each with its משבצות,
the single next action, and calm totals. Any road shape in the content schema goes
through here: one שלב or twenty, two משבצות or a hundred, free order or a linear chain
that cannot skip ahead of the פער. Nothing touches the store; the route passes data in.

Tile states:  done | here | open | ahead (linear chain, past the פער) | view (read only)
Stage states: done | here | started | open | ahead | view
A stage is ``walked`` once the learner's position is past it (the line behind them is solid,
the line ahead is dashed); a finished road is walked end to end, a read-only road not at all.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

# A road this short opens every שלב: the whole road fits on one screen without a tap.
OPEN_ALL_MAX_TILES = 12


def _tile_state(*, done: bool, here: bool, ahead: bool, read_only: bool) -> str:
    if read_only:
        return "view"
    if done:
        return "done"
    if here:
        return "here"
    return "ahead" if ahead else "open"


def _stage_state(tiles: list[dict[str, Any]], read_only: bool) -> str:
    if read_only:
        return "view"
    states = [t["state"] for t in tiles]
    if states and all(s == "done" for s in states):
        return "done"
    if "here" in states:
        return "here"
    if "done" in states:
        return "started"
    if states and all(s == "ahead" for s in states):
        return "ahead"
    return "open"


def road_timeline(
    topics: Iterable[Mapping[str, Any]] | None,
    *,
    mastered: Iterable[str] | None,
    current_block: str | None,
    linear: bool = False,
    read_only: bool = False,
) -> dict[str, Any]:
    """Stages, tiles, totals and the next tile for the road timeline template.

    ``topics`` is the ``_topics_for_ui`` list (steps carry blockId, index, title, titleLang, kind).
    ``linear`` locks every tile after the first unfinished one (the פער) in road order.
    """
    topics = list(topics or [])
    done_ids = set(mastered or [])
    ordered = [st for tp in topics for st in (tp.get("steps") or [])]
    total = len(ordered)
    done_total = sum(1 for st in ordered if st.get("blockId") in done_ids)
    gap = next((int(st.get("index", i)) for i, st in enumerate(ordered) if st.get("blockId") not in done_ids), None)
    if read_only or current_block not in {st.get("blockId") for st in ordered} or current_block in done_ids:
        # The saved position is gone, finished or not this road's: the next tile is the first open one.
        current_block = None if read_only else next(
            (st.get("blockId") for st in ordered if st.get("blockId") not in done_ids), None
        )

    stages: list[dict[str, Any]] = []
    next_tile: dict[str, Any] | None = None
    for n, tp in enumerate(topics, start=1):
        steps = list(tp.get("steps") or [])
        tiles = []
        for i, st in enumerate(steps):
            bid = st.get("blockId")
            here = bid == current_block
            tile = {
                "id": bid,
                "title": st.get("title") or "",
                "titleLang": st.get("titleLang") or "",
                "review": st.get("kind") == "review",
                "check": i == len(steps) - 1 and len(steps) > 1 and st.get("kind") != "review",
                "state": _tile_state(
                    done=bid in done_ids,
                    here=here,
                    ahead=linear and gap is not None and int(st.get("index", 0)) > gap,
                    read_only=read_only,
                ),
            }
            tiles.append(tile)
            if here:
                next_tile = {**tile, "stageN": n, "stageTitle": tp.get("title") or "",
                             "stageLang": tp.get("titleLang") or ""}
        done = sum(1 for t in tiles if t["state"] == "done")
        stages.append({
            "n": n,
            "id": tp.get("id"),
            "title": tp.get("title") or "",
            "titleLang": tp.get("titleLang") or "",
            "review": bool(tp.get("isReview")),
            "tiles": tiles,
            "done": done,
            "total": len(tiles),
            "state": _stage_state(tiles, read_only),
        })

    open_all = total <= OPEN_ALL_MAX_TILES
    finished = total > 0 and done_total == total
    here_n = next_tile["stageN"] if next_tile else None
    for st in stages:
        st["open"] = open_all or st["state"] == "here" or (read_only and st["n"] == 1)
        st["pct"] = round(100 * st["done"] / st["total"]) if st["total"] else 0
        st["walked"] = finished or (here_n is not None and st["n"] < here_n)
    stages_done = sum(1 for st in stages if st["state"] == "done")
    return {
        "stages": stages,
        "next": next_tile,
        "done": done_total,
        "total": total,
        "pct": round(100 * done_total / total) if total else 0,
        "stagesDone": stages_done,
        "stagesTotal": len(stages),
        "hereStage": here_n,
        "finished": finished,
        "first": ordered[0].get("blockId") if ordered else None,
        "linear": linear,
        "readOnly": read_only,
    }
