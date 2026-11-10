"""Engagement v1 (#192): session model, weekly active days, goal meter.

Decision record: docs/decisions/0004-session-model.md. Everything is derived from SQLite
(learner_progress, learner_events, learner_sessions); no external analytics.

``engagement_for`` returns the fixed shape the path view / step player / JSON API use::

    {"session": {...}, "week": {...}, "goal_meter": {...}, "gap_days": int|None,
     "warmup_suggested": bool}
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from myroad_core.content.english_bagrut import placement_band
from myroad_core.ui.dates import LOCAL_TZ, local_date

SESSION_SIZE = 6
WARMUP_GAP_DAYS = 3
# Locales whose week starts on Sunday (Israel); others start on Monday.
SUNDAY_FIRST = ("he", "ar")

# target_label by path id marker (first match wins); no match -> the path title.
_TARGETS: tuple[tuple[str, str], ...] = (
    ("psychometric", "800"),
    ("bagrut5", '5 יח"ל'),
    ("bagrut_5_units", '5 יח"ל'),
    ("bagrut_4_units", '4 יח"ל'),
    ("bagrut_3_units", '3 יח"ל'),
)


def _now() -> datetime:
    """Clock seam (tests monkeypatch this)."""
    return datetime.now(timezone.utc)


def today_local(now: datetime | None = None) -> date:
    return (now or _now()).astimezone(LOCAL_TZ).date()


# --- session ------------------------------------------------------------------------------


def _step_state(events: list[dict[str, Any]], mastered: set[str]) -> dict[str, dict[str, Any]]:
    """Per block: done, right_first_time, last_done_at (event order)."""
    out: dict[str, dict[str, Any]] = {}
    for i, e in enumerate(events):
        st = out.setdefault(e["blockId"], {"done": False, "rft": False, "first": None, "at": -1})
        if e["eventType"] == "answer" and st["first"] is None:
            st["first"] = bool(e["ok"])
            st["rft"] = bool(e["ok"])
        if e["eventType"] == "mastery" or (e["eventType"] == "answer" and e["ok"]):
            st["done"] = True
            st["at"] = i
    for bid in mastered:
        out.setdefault(bid, {"done": False, "rft": False, "first": None, "at": -1})["done"] = True
    return out


def _pick_steps(blocks: list[dict[str, Any]], done: set[str], position: int, n: int) -> list[str]:
    """Next n un-done steps in path order from position, then earlier gaps."""
    ids = [b["blockId"] for b in blocks]
    position = max(0, min(position, len(ids)))
    order = ids[position:] + ids[:position]
    return [bid for bid in order if bid not in done][:n]


def _progress_bits(store, user_id: str, path_id: str) -> tuple[set[str], int]:
    prog = store.get_progress(user_id, path_id) or {}
    return set(prog.get("mastered") or ()), int(prog.get("nodeIndex") or 0)


def session_for(store, user_id: str, doc: dict[str, Any], *, n: int = SESSION_SIZE,
                new: bool = False) -> dict[str, Any]:
    """Today's session for this path (frozen per user/path/local day). ``new`` starts the next one.

    ``doc`` is the variant-selected document (select_variants), so there is one block per base step.
    """
    path_id = doc.get("pathId") or doc.get("id")
    blocks = doc.get("blocks") or []
    title = {b["blockId"]: b.get("title") or "" for b in blocks}
    can_do = {b["blockId"]: ((b.get("content") or {}).get("kids") or {}).get("can_do") or title[b["blockId"]]
              for b in blocks}
    mastered, position = _progress_bits(store, user_id, path_id)
    state = _step_state(store.answer_events(user_id, path_id), mastered)
    done_ids = {bid for bid, s in state.items() if s["done"]}
    day = today_local().isoformat()
    sess = store.latest_learner_session(user_id, path_id)
    if new or not sess or sess["day"] != day:
        sess = store.add_learner_session(user_id, path_id, day, _pick_steps(blocks, done_ids, position, n))
    steps = []
    for bid in sess["step_ids"]:
        s = state.get(bid) or {}
        steps.append({
            "id": bid,
            "title": title.get(bid, ""),
            "done": bool(s.get("done")),
            "right_first_time": bool(s.get("rft")),
        })
    done_steps = sorted((st for st in steps if st["done"]), key=lambda st: state[st["id"]]["at"], reverse=True)
    return {
        "no": sess["no"],
        "steps": steps,
        "size": len(steps),
        "done_count": len(done_steps),
        "right_first_time": sum(1 for st in steps if st["right_first_time"]),
        "complete": all(st["done"] for st in steps),
        "can_do": [can_do.get(st["id"]) or st["title"] for st in done_steps[:2]],
        "can_do_ids": [st["id"] for st in done_steps[:2]],  # #247: same order as can_do
    }


# --- week ---------------------------------------------------------------------------------


def active_dates(store, user_id: str) -> set[date]:
    """Local dates with at least one answer event (any path)."""
    out = set()
    for e in store.answer_events(user_id):
        if e["eventType"] == "answer":
            d = local_date(e["createdAt"])
            if d:
                out.add(d)
    return out


def week_start(day: date, locale: str) -> date:
    # date.weekday(): Mon=0 .. Sun=6. Sunday-first: days since Sunday = (weekday+1) % 7.
    back = (day.weekday() + 1) % 7 if locale in SUNDAY_FIRST else day.weekday()
    return day - timedelta(days=back)


def active_days(store, user_id: str, week: date | None = None, locale: str = "he",
                *, dates: set[date] | None = None) -> dict[str, Any]:
    """The week containing ``week`` (default today). wd: 0=Sunday .. 6=Saturday."""
    today = today_local()
    start = week_start(week or today, locale)
    dates = active_dates(store, user_id) if dates is None else dates
    goal = store.get_weekly_goal(user_id)
    days = []
    for i in range(7):
        d = start + timedelta(days=i)
        days.append({"date": d.isoformat(), "wd": (d.weekday() + 1) % 7, "active": d in dates, "today": d == today})
    return {
        "start": start.isoformat(),
        "days": days,
        "active_count": sum(1 for d in days if d["active"]),
        "goal": goal["goal"],
        "goal_set": goal["goal_set"],
    }


# --- goal meter ---------------------------------------------------------------------------


def stations(doc: dict[str, Any]) -> list[list[str]]:
    """Block ids per topic (the map's stations), same mapping as the path view."""
    node_to_block = doc.get("nodeToBlock") or {}
    known = {b["blockId"] for b in doc.get("blocks") or []}
    out = []
    for tp in doc.get("topics") or []:
        bids = [node_to_block.get(nid) for nid in tp.get("node_ids") or []]
        out.append([b for b in bids if b and b in known])
    return out


def target_label(doc: dict[str, Any], locale: str) -> str:
    pid = str(doc.get("pathId") or doc.get("id") or "")
    for marker, label in _TARGETS:
        if marker in pid:
            return label
    titles = doc.get("titles") or {}
    return titles.get(locale) or titles.get("he") or doc.get("name") or pid


def start_stage(store, user_id: str, doc: dict[str, Any], total: int) -> int | None:
    """Stage implied by the placement band (placement_route on this path), None without one.

    Band inside the route -> 1 (placement sent the learner to the start of this road);
    band above it -> total (placed past this road); band below -> 0 (not reached yet).
    """
    route = doc.get("placementRoute") or doc.get("placement_route") or {}
    pid = route.get("from_placement")
    if not pid:
        return None
    progress = store.get_progress(user_id, pid)
    level = None
    try:
        detail = store.get_placement_detail(user_id, pid) or {}
        if isinstance(detail.get("startingLevel"), int):
            level = detail["startingLevel"]
    except Exception:
        level = None
    band = placement_band(progress, level=level)
    if not band:
        return None
    lo, hi = int(route.get("band_min", 1)), int(route.get("band_max", 8))
    if band < lo:
        return 0
    if band > hi:
        return total
    return 1 if total else 0


def goal_meter(store, user_id: str, doc: dict[str, Any], locale: str) -> dict[str, Any]:
    mastered, _ = _progress_bits(store, user_id, doc.get("pathId") or doc.get("id"))
    st = [s for s in stations(doc) if s]
    done = sum(1 for s in st if all(b in mastered for b in s))
    first = start_stage(store, user_id, doc, len(st))
    return {
        "target_label": target_label(doc, locale),
        "stage": done,
        "stages_total": len(st),
        "start_stage": first,
        "from_placement": first is not None,
    }


# --- all together -------------------------------------------------------------------------


def gap_days(dates: set[date]) -> int | None:
    if not dates:
        return None
    return max(0, (today_local() - max(dates)).days)


def engagement_for(store, user_id: str, doc: dict[str, Any], locale: str = "he", *,
                   n: int = SESSION_SIZE, new_session: bool = False) -> dict[str, Any]:
    dates = active_dates(store, user_id)
    gap = gap_days(dates)
    return {
        "session": session_for(store, user_id, doc, n=n, new=new_session),
        "week": active_days(store, user_id, locale=locale, dates=dates),
        "goal_meter": goal_meter(store, user_id, doc, locale),
        "gap_days": gap,
        "warmup_suggested": gap is not None and gap >= WARMUP_GAP_DAYS,
    }
