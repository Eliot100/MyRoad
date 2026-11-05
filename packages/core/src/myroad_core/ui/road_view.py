"""Road screen view model (design D, approved by Eliot 2026-11-05).

Look of Library mockup 12 (dark winding road, stage cards), levels from mockup 10,
metrics from mockup 01. Pure functions, no store access: the route passes in the
learner's real answer events, so every number here comes from stored engagement.

Levels: content has no per-road level field yet, so a road's שלבים are split into
``LEVEL_COUNT`` consecutive groups of near-equal size, in content order (the first
groups take the extra stage). Deterministic, and replaced once content ships levels.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

LEVEL_COUNT = 3
RECENT_ANSWERS = 20
TREND_DAYS = 30


def uses_road_view(path_id: str) -> bool:
    """Full 5-unit roads (English, Arabic, ...) get design D; placements and math-5 do not."""
    pid = str(path_id or "")
    return "_bagrut5_" in pid and "placement" not in pid and "math" not in pid


def split_levels(n: int, count: int = LEVEL_COUNT) -> list[range]:
    """Consecutive near-equal groups of stage indexes; never an empty level."""
    count = max(1, min(count, n))
    if n <= 0:
        return []
    base, extra = divmod(n, count)
    out, start = [], 0
    for i in range(count):
        size = base + (1 if i < extra else 0)
        out.append(range(start, start + size))
        start += size
    return out


def first_try(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """First answer per block, in event order (the #199 first-try rule)."""
    seen: set[str] = set()
    out = []
    for e in events:
        if e.get("eventType") != "answer" or e.get("ok") is None:
            continue
        bid = e.get("blockId")
        if bid in seen:
            continue
        seen.add(bid)
        out.append(e)
    return out


def _pct(ok: int, total: int) -> int | None:
    return int(round(100 * ok / total)) if total else None


def _day(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def trend(answers: list[dict[str, Any]], today: datetime | None = None, days: int = TREND_DAYS) -> list[dict[str, Any]]:
    """Cumulative first-try accuracy at the end of each active day in the last ``days`` days."""
    today = today or datetime.now(timezone.utc)
    start = (today - timedelta(days=days - 1)).date().isoformat()
    ok = total = 0
    by_day: dict[str, int | None] = {}
    for a in answers:
        d = _day(a.get("createdAt"))
        total += 1
        ok += 1 if a.get("ok") else 0
        if d and d >= start:
            by_day[d] = _pct(ok, total)
    return [{"day": d, "pct": p} for d, p in sorted(by_day.items())]


def build_road(
    topics: list[dict[str, Any]],
    *,
    mastered: set[str],
    current_bid: str | None,
    open_index: int,
    total: int,
    read_only: bool,
    events: list[dict[str, Any]] | None = None,
    today: datetime | None = None,
) -> dict[str, Any]:
    """Stages with real states, levels, and metrics from real answer events."""
    answers = first_try(events or [])
    ok_by_block = {a["blockId"]: bool(a["ok"]) for a in answers}
    stages = []
    for i, tp in enumerate(topics):
        bids = list(tp.get("blockIds") or [])
        steps = tp.get("steps") or []
        n = int(tp.get("stepCount") or len(bids))
        done = sum(1 for b in bids if b in mastered)
        first_ix = steps[0]["index"] if steps else 0
        if n and done >= n:
            state = "done"
        elif current_bid and current_bid in bids and not read_only:
            state = "cur"
        elif not read_only and open_index < total and first_ix > open_index:
            state = "lock"
        else:
            state = "open"
        answered = [ok_by_block[b] for b in bids if b in ok_by_block]
        cur_step = next((s for s in steps if s.get("blockId") == current_bid), None)
        stages.append({
            "n": i + 1,
            "id": tp.get("id"),
            "title": tp.get("title"),
            "titleLang": tp.get("titleLang"),
            "state": state,
            "done": done,
            "total": n,
            "firstBlockId": bids[0] if bids else "",
            "accuracy": _pct(sum(answered), len(answered)),
            "answered": len(answered),
            "currentStep": (steps.index(cur_step) + 1) if cur_step else None,
            "currentTitle": cur_step.get("title") if cur_step else None,
            "isReview": bool(tp.get("isReview")),
        })
    levels = []
    for li, rng in enumerate(split_levels(len(stages))):
        group = [stages[k] for k in rng]
        # Two-column grid as in mockup 12: the current stage takes a full row, and a card left
        # alone in its row (before a full-row card or at the end) widens instead of leaving a hole.
        col, prev = 0, None
        for s in group:
            s["level"] = li + 1
            s["wide"] = s["state"] == "cur"
            if s["wide"]:
                if col and prev:
                    prev["wide"] = True
                col = 0
            else:
                col ^= 1
                prev = s
        if col and prev:
            prev["wide"] = True
        lt = sum(s["total"] for s in group)
        ld = sum(s["done"] for s in group)
        state = "done" if lt and ld >= lt else ("lock" if all(s["state"] == "lock" for s in group) else "active")
        levels.append({"n": li + 1, "stages": group, "done": ld, "total": lt,
                       "pct": int(round(100 * ld / lt)) if lt else 0, "state": state,
                       "first": group[0]["n"], "last": group[-1]["n"]})
    recent = answers[-RECENT_ANSWERS:]
    cur = next((s for s in stages if s["state"] == "cur"), None)
    cur_level = cur["level"] if cur else next((lv["n"] for lv in levels if lv["state"] != "done"), len(levels))
    return {
        "stages": stages,
        "levels": levels,
        "levelCount": len(levels),
        "currentLevel": cur_level,
        "current": cur,
        "done": len(mastered),
        "total": total,
        "pct": int(round(100 * len(mastered) / total)) if total else 0,
        "recentAccuracy": _pct(sum(1 for a in recent if a["ok"]), len(recent)),
        "recentCount": len(recent),
        "trend": trend(answers, today),
        "answered": len(answers),
    }


def trend_svg_points(points: list[dict[str, Any]], width: int = 400, height: int = 130) -> str:
    """Polyline points for the accuracy chart, oldest on the left (as in mockup 01)."""
    if len(points) < 2:
        return ""
    step = width / (len(points) - 1)
    return " ".join(f"{round(i * step, 1)},{round(height - height * p['pct'] / 100, 1)}" for i, p in enumerate(points))


__all__ = ["uses_road_view", "split_levels", "first_try", "trend", "build_road", "trend_svg_points", "LEVEL_COUNT"]
