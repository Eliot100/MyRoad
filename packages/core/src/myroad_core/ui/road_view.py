"""Road screen view model (design D, approved by Eliot 2026-11-05).

Look of Library mockup 12 (winding road, stage cards), levels from mockup 10,
metrics from mockup 01. Pure functions, no store access: the route passes in the
learner's real answer events and, when set, the learner's own weekly plan.
Every number here comes from stored data. A missing plan stays empty.

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
# Same cap the store uses when it records an answer (idle tabs must not inflate a week).
_MAX_ANSWER_MS = 30 * 60 * 1000

PUBLIC_CATALOG_SUBJECTS = frozenset({"english", "math", "physics", "arabic"})


def uses_road_view(path_id: str) -> bool:
    """Full 5-unit roads (English, Arabic, ...) get design D; placements and math-5 do not."""
    pid = str(path_id or "")
    return "_bagrut5_" in pid and "placement" not in pid and "math" not in pid


def is_public_catalog(path_id: str, subject: str | None = None) -> bool:
    """Learner catalog keeps only 5-unit roads in English, math, physics and Arabic.

    Other published paths stay in the database and still open by address. They are
    not deleted. A path qualifies only when its id contains ``_bagrut5`` and its
    subject is one of those four. Missing subject is not guessed.
    """
    if "_bagrut5" not in str(path_id or ""):
        return False
    return subject in PUBLIC_CATALOG_SUBJECTS


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
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _as_utc(today: datetime | None) -> datetime:
    now = today or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _parse_date(raw: str | None):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw)[:10]).date()
    except ValueError:
        return None


def weekly_progress(
    events: Iterable[dict[str, Any]],
    *,
    weekly_tiles: int | None,
    weekly_minutes: int | None,
    goal_date: str | None,
    road_done: int,
    road_total: int,
    today: datetime | None = None,
) -> dict[str, Any]:
    """This ISO week's pace from answer events, plus an optional learner plan.

    Done this week counts distinct tiles (blocks) that have an ``answer`` event
    whose timestamp falls in the current Monday-Sunday week. Minutes are the sum
    of those events' ``durationMs``, each already capped at 30 minutes. If any
    answer this week has no duration, minutes stay unknown rather than a partial
    sum presented as exact. No answers means 0 tiles and 0 minutes.

    The weekly target is shown only when the learner set both a tile count and a
    minute count. Neither number is derived from the other or from the days goal.

    On track needs a goal date, a positive weekly tile target, and the road's
    real tile totals. Remaining tiles (not yet mastered) must fit in the weeks
    left at that weekly tile target. Minutes do not enter the pace: there is no
    stored minute-total for the road. Otherwise on track stays empty.
    """
    now = _as_utc(today)
    start_d = now.date() - timedelta(days=now.date().weekday())
    end_d = start_d + timedelta(days=6)
    start, end = start_d.isoformat(), end_d.isoformat()
    week_answers: list[dict[str, Any]] = []
    for e in events:
        if e.get("eventType") != "answer":
            continue
        day = _day(e.get("createdAt"))
        if day and start <= day <= end:
            week_answers.append(e)
    tiles = len({e.get("blockId") for e in week_answers if e.get("blockId")})
    raw_ms = [e.get("durationMs") for e in week_answers]
    if not week_answers:
        minutes: int | None = 0
    elif any(not isinstance(ms, int) or ms < 0 for ms in raw_ms):
        minutes = None
    else:
        minutes = int(round(sum(min(int(ms), _MAX_ANSWER_MS) for ms in raw_ms) / 60000))
    has_target = (
        isinstance(weekly_tiles, int) and weekly_tiles > 0
        and isinstance(weekly_minutes, int) and weekly_minutes > 0
    )
    goal = _parse_date(goal_date)
    on_track: bool | None = None
    if goal and has_target and road_total > 0:
        remaining = max(0, int(road_total) - int(road_done))
        days_left = (goal - now.date()).days
        if remaining == 0:
            on_track = True
        elif days_left < 0:
            on_track = False
        else:
            weeks_left = max(days_left, 1) / 7
            on_track = remaining <= int(weekly_tiles) * weeks_left
    if not has_target:
        pace_empty = "target"
    elif goal is None:
        pace_empty = "date"
    else:
        pace_empty = None
    return {
        "weekStart": start,
        "weekEnd": end,
        "targetTiles": int(weekly_tiles) if has_target else None,
        "targetMinutes": int(weekly_minutes) if has_target else None,
        "doneTiles": tiles,
        "doneMinutes": minutes,
        "goalDate": goal.isoformat() if goal else None,
        "onTrack": on_track,
        "hasTarget": has_target,
        "paceEmpty": pace_empty,
    }


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
    plan: dict[str, Any] | None = None,
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
    plan = plan or {}
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
        "week": weekly_progress(
            events or [],
            weekly_tiles=plan.get("weeklyTiles"),
            weekly_minutes=plan.get("weeklyMinutes"),
            goal_date=plan.get("goalDate"),
            road_done=len(mastered),
            road_total=total,
            today=today,
        ),
    }


def trend_svg_points(points: list[dict[str, Any]], width: int = 400, height: int = 130) -> str:
    """Polyline points for the accuracy chart, oldest on the left (as in mockup 01)."""
    if len(points) < 2:
        return ""
    step = width / (len(points) - 1)
    return " ".join(f"{round(i * step, 1)},{round(height - height * p['pct'] / 100, 1)}" for i, p in enumerate(points))


__all__ = [
    "uses_road_view", "is_public_catalog", "split_levels", "first_try", "trend",
    "build_road", "trend_svg_points", "weekly_progress", "LEVEL_COUNT", "PUBLIC_CATALOG_SUBJECTS",
]
