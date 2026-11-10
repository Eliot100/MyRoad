"""Per-stage level, last-N accuracy, and a correct-answer trend.

A stage is one road. Levels are topics whose id ends with ``_l1``, ``_l2``, ...
The level shown is the highest N whose topics ``_l1`` .. ``_lN`` are fully
mastered, in order. A gap stops the count. Accuracy uses answer events only.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

_LEVEL = re.compile(r"_l(\d+)$")


def _ids(topic: dict[str, Any]) -> list[str]:
    return list(topic.get("blockIds") or topic.get("node_ids") or [])


def level_of(topics: list[dict[str, Any]], mastered: set[str] | list[str]) -> tuple[int, int]:
    rows: list[tuple[int, dict[str, Any]]] = []
    for topic in topics:
        match = _LEVEL.search(str(topic.get("id") or ""))
        if match:
            rows.append((int(match.group(1)), topic))
    if not rows:
        return 0, 0
    rows.sort(key=lambda row: row[0])
    done = set(mastered or [])
    level = 0
    for number, topic in rows:
        ids = _ids(topic)
        if ids and all(item in done for item in ids):
            level = number
        else:
            break
    return level, rows[-1][0]


def answer_rows(events: list[dict[str, Any]], path_id: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for event in events:
        if event.get("eventType") != "answer" or event.get("ok") is None:
            continue
        if path_id is not None and event.get("pathId") != path_id:
            continue
        rows.append(event)
    return rows


def accuracy_window(
    events: list[dict[str, Any]], path_id: str | None, size: int
) -> tuple[int | None, list[bool]]:
    rows = answer_rows(events, path_id)[-size:]
    if not rows:
        return None, []
    flags = [bool(row.get("ok")) for row in rows]
    return int(round(100 * sum(flags) / len(flags))), flags


def sparkline(flags: list[bool], width: float = 120, height: float = 36, pad: float = 4) -> str:
    """Cumulative accuracy inside the window, so the line is a trend rather than a barcode."""
    if len(flags) < 2:
        return ""
    total = 0
    values: list[float] = []
    for index, flag in enumerate(flags, 1):
        total += 1 if flag else 0
        values.append(100 * total / index)
    last = len(values) - 1
    points = []
    for index, value in enumerate(values):
        x = pad + (width - 2 * pad) * (index / last)
        y = pad + (height - 2 * pad) * (1 - value / 100)
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def daily_trend(
    events: list[dict[str, Any]], *, days: int = 30, today: date | None = None
) -> list[dict[str, Any]]:
    today = today or date.today()
    start = today - timedelta(days=days - 1)
    buckets: dict[date, list[int]] = {}
    for event in answer_rows(events):
        raw = str(event.get("createdAt") or "")[:10]
        try:
            day = date.fromisoformat(raw)
        except ValueError:
            continue
        if day < start or day > today:
            continue
        slot = buckets.setdefault(day, [0, 0])
        slot[1] += 1
        slot[0] += 1 if event.get("ok") else 0
    points = []
    for day in sorted(buckets):
        correct, count = buckets[day]
        points.append(
            {
                "day": day.isoformat(),
                "label": f"{day.day}.{day.month}",
                "pct": int(round(100 * correct / count)),
                "n": count,
            }
        )
    return points


def trend_polyline(points: list[dict[str, Any]], width: float = 320, height: float = 120, pad: float = 16, pad_x: float = 36) -> str:
    if len(points) < 2:
        return ""
    last = len(points) - 1
    drawn = []
    for index, point in enumerate(points):
        x = pad_x + (width - 2 * pad_x) * (index / last)
        y = pad + (height - 2 * pad) * (1 - int(point["pct"]) / 100)
        drawn.append(f"{x:.1f},{y:.1f}")
    return " ".join(drawn)


def trend_area(line: str, *, baseline: float = 104) -> str:
    """Close the polyline down to the 0% gridline. Empty when there is no line."""
    if not line:
        return ""
    pts = line.split()
    first_x = pts[0].split(",")[0]
    last_x = pts[-1].split(",")[0]
    return f"{line} {last_x},{baseline:.0f} {first_x},{baseline:.0f}"


def build_stage_board(
    rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    recent: int = 20,
    window: int = 15,
    trend_days: int = 30,
    today: date | None = None,
) -> dict[str, Any]:
    """rows items: pathId, title, topics, mastered."""
    board_rows = []
    levels: list[int] = []
    scales: list[int] = []
    for row in rows:
        level, total = level_of(list(row.get("topics") or []), set(row.get("mastered") or []))
        percent, flags = accuracy_window(events, row.get("pathId"), window)
        board_rows.append(
            {
                "pathId": row.get("pathId"),
                "title": row.get("title") or "",
                "level": level,
                "levels": total,
                "accuracy": percent,
                "window": window,
                "spark": sparkline(flags),
            }
        )
        if total:
            levels.append(level)
            scales.append(total)
    scale = scales[0] if scales and len(set(scales)) == 1 else (max(scales) if scales else 0)
    mean = None
    mean_pct = 0
    if levels and scale:
        value = sum(levels) / len(levels)
        mean = f"{value:.1f}"
        mean_pct = int(round(100 * value / scale))
    ids = {row.get("pathId") for row in rows}
    relevant = [event for event in answer_rows(events) if event.get("pathId") in ids]
    sample = relevant[-recent:]
    recent_accuracy = (
        int(round(100 * sum(1 for event in sample if event.get("ok")) / len(sample))) if sample else None
    )
    points = daily_trend(relevant, days=trend_days, today=today)
    line = trend_polyline(points)
    return {
        "rows": board_rows,
        "meanLevel": mean,
        "levelScale": scale,
        "meanPct": mean_pct,
        "recentAccuracy": recent_accuracy,
        "recentWindow": recent,
        "window": window,
        "trendDays": trend_days,
        "trendPoints": points,
        "trendLine": line,
        "trendArea": trend_area(line),
    }
