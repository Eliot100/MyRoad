"""Template filters for the road metrics screen (dates stored as ISO-8601 UTC)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

# The app's local day (active days, sessions): learners are in Israel.
LOCAL_TZ = ZoneInfo("Asia/Jerusalem")


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def short_date(value: Any) -> str:
    """'2026-10-20T08:00:00+00:00' -> '20.10' (adds the year when it is not this year)."""
    dt = _parse(value)
    if not dt:
        return ""
    if dt.year != datetime.now(timezone.utc).year:
        return f"{dt.day:02d}.{dt.month:02d}.{dt.year}"
    return f"{dt.day:02d}.{dt.month:02d}"


def days_ago(value: Any, now: datetime | None = None) -> int | None:
    """Whole days between the timestamp and now (None when missing or unparsable)."""
    dt = _parse(value)
    if not dt:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0, (now.date() - dt.astimezone(timezone.utc).date()).days)


def local_date(value: Any, tz=LOCAL_TZ):
    """Calendar date of a stored UTC timestamp in the app's local timezone (None if unparsable)."""
    dt = _parse(value)
    return dt.astimezone(tz).date() if dt else None
