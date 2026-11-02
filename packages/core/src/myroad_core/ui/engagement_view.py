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
    """The 'now you can' text for THIS step: its own can_do (``fallback``: kids.can_do or title).

    session.can_do is newest-first by completion time, not step order, so it cannot be indexed
    by a step's position. We only use it when the step's own text is missing and the session
    title for this step id is itself one of the can_do entries (derived path)."""
    if fallback:
        return str(fallback)
    sess = (engagement or {}).get("session") or {}
    for st in sess.get("steps") or []:
        if st.get("id") == block_id and st.get("done") and st.get("title") in (sess.get("can_do") or []):
            return str(st["title"])
    return ""


# --- Session end, stage end, week strip, mastered skills (#191, #193, #206) -----------------

# Short and full weekday names by wd (0=Sunday .. 6=Saturday), the same index #192 sends.
_WD_SHORT = {
    "he": ["א", "ב", "ג", "ד", "ה", "ו", "ש"],
    "ar": ["ح", "ن", "ث", "ر", "خ", "ج", "س"],
    "en": ["S", "M", "T", "W", "T", "F", "S"],
}
_WD_FULL = {
    "he": ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"],
    "ar": ["الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"],
    "en": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
}
WEEKLY_GOAL_CHOICES = (2, 3, 5)  # POST /api/settings/weekly-goal accepts only these
WEEKLY_GOAL_DEFAULT = 3


def week_view(week: Mapping[str, Any] | None, locale: str = "he") -> dict[str, Any] | None:
    """Display shape for the forgiving weekly days goal, or None when the server sent no week.

    Days stay in the order the server sent (locale week order). Each day carries a short and a
    full name so the strip never relies on colour alone."""
    if not isinstance(week, Mapping) or not week.get("days"):
        return None
    loc = locale if locale in _WD_SHORT else "he"
    days = []
    for d in week.get("days") or []:
        wd = int(d.get("wd") or 0) % 7
        days.append({"short": _WD_SHORT[loc][wd], "full": _WD_FULL[loc][wd],
                     "active": bool(d.get("active")), "today": bool(d.get("today"))})
    active = int(week.get("active_count") if week.get("active_count") is not None else sum(d["active"] for d in days))
    goal = int(week.get("goal") or WEEKLY_GOAL_DEFAULT)
    today_active = any(d["active"] and d["today"] for d in days)
    return {"days": days, "active_count": active, "goal": goal, "goal_set": bool(week.get("goal_set")),
            "met": active >= goal, "today_active": today_active, "choices": WEEKLY_GOAL_CHOICES}


def mastered_skills(engagement: Mapping[str, Any] | None, topics: Iterable[Mapping[str, Any]] | None,
                    mastered: Iterable[str] | None) -> list[str]:
    """Mastered skill lines for the goal meter (#206), newest first when the server knows.

    #192 does not send a list yet: prefer goal_meter.mastered_can_do when it appears, else
    derive from the page (mastered steps' can_do or title, later road steps first)."""
    gm = (engagement or {}).get("goal_meter") or {}
    server = gm.get("mastered_can_do")
    if isinstance(server, list):
        return [str(x) for x in server if x]
    done = set(mastered or [])
    out: list[str] = []
    for tp in topics or []:
        for s in tp.get("steps") or []:
            if s.get("blockId") in done:
                text = s.get("can_do") or s.get("title")
                if text and text not in out:
                    out.append(str(text))
    return list(reversed(out))


def stage_end(topics: Iterable[Mapping[str, Any]] | None, mastered: Iterable[str] | None,
              block_id: str | None) -> dict[str, Any] | None:
    """The שלב this step just closed (all its steps mastered), with what comes next; else None."""
    if not block_id:
        return None
    done = set(mastered or [])
    topics = list(topics or [])
    for i, tp in enumerate(topics):
        ids = list(tp.get("blockIds") or [s.get("blockId") for s in tp.get("steps") or []])
        if block_id in ids:
            if not ids or not set(ids) <= done:
                return None
            nxt = next((t for t in topics[i + 1:]
                        if set(t.get("blockIds") or [s.get("blockId") for s in t.get("steps") or []]) - done), None)
            return {"no": i + 1, "total": len(topics), "title": tp.get("title") or "",
                    "title_lang": tp.get("titleLang") or "", "has_next": nxt is not None,
                    "next_title": (nxt or {}).get("title") or ""}
    return None


def session_end(engagement: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Real numbers for the session end moment, only when the server says the session is complete.

    The derived fallback never claims a finished session (it cannot know right first time)."""
    if not isinstance(engagement, Mapping) or engagement.get("derived"):
        return None
    sess = engagement.get("session") or {}
    if not sess.get("complete") or not sess.get("steps"):
        return None
    week = engagement.get("week") or {}
    return {
        "no": sess.get("no") or 1,
        "done": int(sess.get("done_count") or 0),
        "size": int(sess.get("size") or len(sess.get("steps") or [])),
        "rft": int(sess.get("right_first_time") or 0),
        "can_do": [str(x) for x in (sess.get("can_do") or [])[:2] if x],
        "today_counted": any(d.get("today") and d.get("active") for d in week.get("days") or []),
    }
