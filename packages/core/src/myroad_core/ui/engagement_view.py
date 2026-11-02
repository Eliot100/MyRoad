"""View side engagement data for the path head and the step player (#193, #191).

The server will pass ``ctx['engagement']`` once #192 lands. Until then templates call
``engagement_view(...)``, which returns that dict unchanged when present and otherwise
derives the same shape from what the page already has (topics, mastered set, position).
Nothing here touches the store or the routes; it is a pure function over the context.

The shape mirrors GET /api/path/{path_id}/engagement:
  session:    no, steps[{id,title,done,right_first_time}], size, done_count,
              right_first_time, complete, can_do[]
  goal_meter: target_label, stage, stages_total, start_stage, from_placement
  week, gap_days, warmup_suggested  (kept for the later week strip, unused today)
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

SESSION_SIZE = 6


def _blocks_in_order(topics: Iterable[Mapping[str, Any]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for tp in topics or []:
        steps = tp.get("steps") or []
        if steps:
            out.extend((str(s.get("blockId")), str(s.get("title") or "")) for s in steps)
        else:
            out.extend((str(b), "") for b in tp.get("blockIds") or [])
    return out


def derive_engagement(
    topics: Iterable[Mapping[str, Any]] | None,
    mastered: Iterable[str] | None,
    *,
    size: int = SESSION_SIZE,
    target_label: str | None = None,
) -> dict[str, Any]:
    """Same dict shape as #192, built only from the current page context."""
    topics = list(topics or [])
    done_ids = set(mastered or [])
    ordered = _blocks_in_order(topics)
    total = len(ordered)
    done_total = sum(1 for bid, _ in ordered if bid in done_ids)

    # Short sets of `size` steps along the road; the current one holds the first open step.
    first_open = next((i for i, (bid, _) in enumerate(ordered) if bid not in done_ids), total)
    set_ix = min(first_open, max(total - 1, 0)) // size if total else 0
    chunk = ordered[set_ix * size:(set_ix + 1) * size]
    steps = [{"id": bid, "title": title, "done": bid in done_ids, "right_first_time": False} for bid, title in chunk]
    done_count = sum(1 for s in steps if s["done"])

    stage = 0
    for i, tp in enumerate(topics):
        ids = set(tp.get("blockIds") or [s.get("blockId") for s in tp.get("steps") or []])
        if ids - done_ids:
            stage = i + 1
            break
    else:
        stage = len(topics)

    return {
        "session": {
            "no": set_ix + 1,
            "steps": steps,
            "size": len(steps),
            "done_count": done_count,
            "right_first_time": 0,
            "complete": bool(steps) and done_count == len(steps),
            "can_do": [s["title"] for s in steps if s["done"] and s["title"]],
        },
        "week": None,
        "goal_meter": {
            "target_label": target_label,
            "stage": max(stage, 1) if topics else 0,
            "stages_total": len(topics),
            "start_stage": None,
            "from_placement": False,
        },
        "gap_days": None,
        "warmup_suggested": False,
        "started": done_total > 0,
        "derived": True,
    }


def engagement_view(
    engagement: Mapping[str, Any] | None,
    topics: Iterable[Mapping[str, Any]] | None = None,
    mastered: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Server dict when present (#192), else the derived one. Never raises."""
    if isinstance(engagement, Mapping) and engagement.get("goal_meter") is not None:
        out = dict(engagement)
        sess = dict(out.get("session") or {})
        sess.setdefault("steps", [])
        sess.setdefault("done_count", sum(1 for s in sess["steps"] if s.get("done")))
        sess.setdefault("size", len(sess["steps"]))
        sess.setdefault("can_do", [])
        out["session"] = sess
        out.setdefault("started", bool(sess["done_count"]) or (sess.get("no") or 1) > 1)
        return out
    try:
        return derive_engagement(topics, mastered)
    except Exception:  # view glue must never break a page
        return derive_engagement([], [])


def can_do_line(engagement: Mapping[str, Any] | None, block_id: str | None, fallback: str | None) -> str:
    """The 'now you can' text for a step: its session can_do entry, else the step title."""
    sess = (engagement or {}).get("session") or {}
    steps = sess.get("steps") or []
    can = sess.get("can_do") or []
    done_ids = [s.get("id") for s in steps if s.get("done")]
    if block_id in done_ids:
        i = done_ids.index(block_id)
        if i < len(can) and can[i]:
            return str(can[i])
    return str(fallback or "")
