"""Road page view model (arena c3): one pure function that turns any road into the dashboard.

Input is what the play route already has: ``topics`` from ``_topics_for_ui`` (each with
``steps``), the learner's mastered block ids, the resume block, and whether the road is linear
(a tile past the first gap is ahead and cannot be opened) or read-only (a locked road).

Output is plain dicts, so the template stays dumb and the rules are unit tested:

- ``next``: the single next action (resume tile, else the first open one), with its שלב.
- ``done`` / ``total`` / ``stages_done`` / ``stages_total``: real counts, never a percent.
- ``stages``: one entry per שלב with ``state`` in done, here, started, open, ahead, and its
  tiles with ``state`` in done, here, open, ahead. The שלב the learner is on is ``expanded``.

Shapes covered: 0 topics (one synthetic שלב from the steps), 1 topic, many topics (AMIRNET 15/97),
long tile lists (math 5 at 13+ tiles per שלב), linear locks, read-only, and a finished road.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

STEP_STATES = ("done", "here", "open", "ahead")
STAGE_STATES = ("done", "here", "started", "open", "ahead")


def _gap(order: list[str], mastered: set[str]) -> int:
    return next((i for i, bid in enumerate(order) if bid not in mastered), len(order))


def road_dashboard(
    topics: Iterable[Mapping[str, Any]] | None,
    mastered: Iterable[str] | None = None,
    *,
    current_block: str | None = None,
    linear: bool = False,
    read_only: bool = False,
) -> dict[str, Any]:
    """Never raises on odd content: missing steps or ids just make smaller counts."""
    done_ids = set(mastered or ())
    stages_in = [dict(tp) for tp in (topics or [])]
    # Tile order is the road's step index order, the same order the player walks.
    tiles: list[dict[str, Any]] = []
    for s_ix, tp in enumerate(stages_in):
        for st in tp.get("steps") or []:
            if st.get("blockId"):
                tiles.append({**st, "_stage": s_ix})
    tiles.sort(key=lambda st: int(st.get("index") or 0))
    order = [st["blockId"] for st in tiles]
    gap = _gap(order, done_ids)
    finished = bool(order) and gap >= len(order)

    # The next action: the resume tile when it is still open work, else the first gap.
    nxt_ix: int | None = None
    if order and not finished:
        if current_block in order and current_block not in done_ids:
            nxt_ix = order.index(current_block)
            if linear and nxt_ix > gap:
                nxt_ix = gap
        else:
            nxt_ix = gap
    here_id = order[nxt_ix] if nxt_ix is not None and not read_only else None
    pos = {bid: i for i, bid in enumerate(order)}

    stages: list[dict[str, Any]] = []
    for s_ix, tp in enumerate(stages_in):
        steps_out = []
        raw = [st for st in (tp.get("steps") or []) if st.get("blockId")]
        for k, st in enumerate(raw):
            bid = st["blockId"]
            if bid in done_ids:
                state = "done"
            elif bid == here_id:
                state = "here"
            elif linear and not read_only and pos.get(bid, 0) > gap:
                state = "ahead"
            else:
                state = "open"
            steps_out.append({
                "blockId": bid,
                "n": pos.get(bid, 0) + 1,
                "title": st.get("title") or "",
                "titleLang": st.get("titleLang") or "",
                "review": st.get("kind") == "review",
                "check": k == len(raw) - 1 and len(raw) > 1 and st.get("type") == "check",
                "state": state,
            })
        n_done = sum(1 for st in steps_out if st["state"] == "done")
        n_total = len(steps_out)
        if n_total and n_done == n_total:
            sstate = "done"
        elif any(st["state"] == "here" for st in steps_out):
            sstate = "here"
        elif n_done:
            sstate = "started"
        elif steps_out and all(st["state"] == "ahead" for st in steps_out):
            sstate = "ahead"
        else:
            sstate = "open"
        stages.append({
            "id": tp.get("id") or f"s{s_ix + 1}",
            "n": s_ix + 1,
            "title": tp.get("title") or "",
            "titleLang": tp.get("titleLang") or "",
            "review": bool(tp.get("isReview")),
            "state": sstate,
            "done": n_done,
            "total": n_total,
            "steps": steps_out,
            "expanded": sstate == "here",
        })

    nxt = None
    if nxt_ix is not None:
        st = tiles[nxt_ix]
        stage = stages[st["_stage"]]
        nxt = {
            "blockId": st["blockId"],
            "n": nxt_ix + 1,
            "title": st.get("title") or "",
            "titleLang": st.get("titleLang") or "",
            "review": st.get("kind") == "review",
            "stage": stage["title"],
            "stageLang": stage["titleLang"],
            "stageN": stage["n"],
            "fresh": not done_ids.intersection(order),
        }
    return {
        "next": nxt,
        "finished": finished,
        "first": order[0] if order else None,
        "done": len(done_ids.intersection(order)),
        "total": len(order),
        "stages_done": sum(1 for s in stages if s["state"] == "done"),
        "stages_total": len(stages),
        "here_stage": next((s["n"] for s in stages if s["state"] == "here"), None),
        "stages": stages,
        "read_only": read_only,
        "linear": linear,
    }
