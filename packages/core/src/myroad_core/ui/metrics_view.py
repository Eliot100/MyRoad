"""Separate metrics screen. Every number is an answer event or the saved weekly plan.

There is one plan, not a history of plans. A past week is judged against the plan
that is saved now. No plan, or a week whose minutes were not all recorded, is not
marked met or missed when the tile count alone does not already miss the target.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from myroad_core.ui.road_view import _MAX_ANSWER_MS, _as_utc, _day, first_try, trend

_HISTORY_WEEKS = 26


def _has_target(weekly_tiles: int | None, weekly_minutes: int | None) -> bool:
    return (
        isinstance(weekly_tiles, int) and weekly_tiles > 0
        and isinstance(weekly_minutes, int) and weekly_minutes > 0
    )


def _week_counts(events: Iterable[dict[str, Any]], start: str, end: str) -> tuple[int, int | None]:
    answers = []
    for event in events:
        if event.get("eventType") != "answer":
            continue
        day = _day(event.get("createdAt"))
        if day and start <= day <= end:
            answers.append(event)
    tiles = len({event.get("blockId") for event in answers if event.get("blockId")})
    raw = [event.get("durationMs") for event in answers]
    if not answers:
        return tiles, 0
    if any(not isinstance(ms, int) or ms < 0 for ms in raw):
        return tiles, None
    minutes = int(round(sum(min(int(ms), _MAX_ANSWER_MS) for ms in raw) / 60000))
    return tiles, minutes


def _met(tiles: int, minutes: int | None, target_tiles: int, target_minutes: int) -> bool | None:
    if tiles < target_tiles:
        return False
    if minutes is None:
        return None
    return minutes >= target_minutes


def weekly_history(
    events: Iterable[dict[str, Any]],
    *,
    weekly_tiles: int | None,
    weekly_minutes: int | None,
    today: datetime | None = None,
) -> list[dict[str, Any]]:
    """ISO weeks from the first answer through the later of today and the last answer."""
    events = list(events)
    now = _as_utc(today).date()
    days = [
        _day(event.get("createdAt"))
        for event in events
        if event.get("eventType") == "answer" and _day(event.get("createdAt"))
    ]
    current = now - timedelta(days=now.weekday())
    if days:
        first = datetime.fromisoformat(min(days)).date()
        last = datetime.fromisoformat(max(days)).date()
        start = first - timedelta(days=first.weekday())
        end = last - timedelta(days=last.weekday())
        if current < start:
            start = current
        if current > end:
            end = current
    else:
        start = end = current
    starts: list = []
    cursor = start
    while cursor <= end:
        starts.append(cursor)
        cursor += timedelta(days=7)
    if len(starts) > _HISTORY_WEEKS:
        starts = starts[-_HISTORY_WEEKS:]
    has_target = _has_target(weekly_tiles, weekly_minutes)
    out = []
    for monday in starts:
        sunday = monday + timedelta(days=6)
        tiles, minutes = _week_counts(events, monday.isoformat(), sunday.isoformat())
        out.append({
            "start": monday.isoformat(),
            "end": sunday.isoformat(),
            "tiles": tiles,
            "minutes": minutes,
            "met": _met(tiles, minutes, int(weekly_tiles), int(weekly_minutes)) if has_target else None,
        })
    return out


def _block_titles(topics: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for topic in topics:
        for step in topic.get("steps") or []:
            bid = step.get("blockId")
            if bid and bid not in found:
                found[bid] = {
                    "title": step.get("title") or bid,
                    "titleLang": step.get("titleLang"),
                    "stageId": topic.get("id"),
                    "level": topic.get("level") if topic.get("level") in (1, 2, 3) else None,
                }
    return found


def stage_accuracy(topics: list[dict[str, Any]], events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """First-try accuracy per stage. A stage with no answer stays empty, not 0."""
    tries = first_try(events)
    by_block = {event.get("blockId"): event for event in tries}
    rows = []
    for topic in topics:
        ids = [bid for bid in (topic.get("blockIds") or []) if bid]
        answered = [by_block[bid] for bid in ids if bid in by_block]
        total = len(answered)
        ok = sum(1 for event in answered if event.get("ok"))
        rows.append({
            "id": topic.get("id"),
            "title": topic.get("title") or topic.get("id"),
            "titleLang": topic.get("titleLang"),
            "level": topic.get("level") if topic.get("level") in (1, 2, 3) else None,
            "correct": ok if total else None,
            "answered": total,
            "accuracy": int(round(100 * ok / total)) if total else None,
        })
    return rows


def level_accuracy(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pooled first-try accuracy per content level, not an average of stage percentages."""
    groups: dict[int | None, list[dict[str, Any]]] = {}
    order: list[int | None] = []
    for stage in stages:
        level = stage.get("level")
        if level not in groups:
            groups[level] = []
            order.append(level)
        groups[level].append(stage)
    order.sort(key=lambda level: (level is None, level or 0))
    rows = []
    for level in order:
        members = groups[level]
        answered = sum(stage["answered"] for stage in members)
        correct = sum(stage["correct"] or 0 for stage in members)
        rows.append({
            "level": level,
            "stages": len(members),
            "answered": answered,
            "accuracy": int(round(100 * correct / answered)) if answered else None,
        })
    return rows


def tile_times(topics: list[dict[str, Any]], events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mean recorded duration per tile. An answer with no duration is skipped, not treated as zero."""
    titles = _block_titles(topics)
    buckets: dict[str, list[int]] = {}
    for event in events:
        if event.get("eventType") != "answer":
            continue
        ms = event.get("durationMs")
        bid = event.get("blockId")
        if not bid or not isinstance(ms, int) or ms < 0:
            continue
        buckets.setdefault(bid, []).append(min(ms, _MAX_ANSWER_MS))
    rows = []
    for bid, samples in buckets.items():
        info = titles.get(bid) or {"title": bid, "titleLang": None, "level": None}
        mean = int(round(sum(samples) / len(samples)))
        rows.append({
            "blockId": bid,
            "title": info["title"],
            "titleLang": info.get("titleLang"),
            "level": info.get("level"),
            "samples": len(samples),
            "ms": mean,
            "minutes": mean // 60000,
            "seconds": (mean % 60000) // 1000,
        })
    rows.sort(key=lambda row: row["title"] or "")
    return rows


def build_metrics(
    topics: list[dict[str, Any]],
    events: Iterable[dict[str, Any]],
    plan: dict[str, Any] | None = None,
    *,
    today: datetime | None = None,
) -> dict[str, Any]:
    plan = plan or {}
    events = list(events)
    tiles = plan.get("weeklyTiles")
    minutes = plan.get("weeklyMinutes")
    stages = stage_accuracy(topics, events)
    tries = first_try(events)
    levels = level_accuracy(stages)
    numbered = [row["level"] for row in levels if row["level"]]
    return {
        "hasTarget": _has_target(tiles if isinstance(tiles, int) else None, minutes if isinstance(minutes, int) else None),
        "weeks": weekly_history(
            events,
            weekly_tiles=tiles if isinstance(tiles, int) else None,
            weekly_minutes=minutes if isinstance(minutes, int) else None,
            today=today,
        ),
        "trend": trend(tries, today=today),
        "stages": stages,
        "levels": levels,
        "levelCount": max(numbered) if numbered else len(levels),
        "tiles": tile_times(topics, events),
    }
