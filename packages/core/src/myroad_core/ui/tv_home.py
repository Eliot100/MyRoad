"""Netflix-TV style home rows, recommendation detail and preview-only mock metrics.

View glue only. Real data: roads, שלבים (content topics), משבצות (steps), progress, accuracy.
Stages unlock rules, levels, skills and goals do not exist in the data model yet; with
MYROAD_UI_PREVIEW=1 they are filled with clearly labelled sample data ("נתוני דוגמה").
"""
from __future__ import annotations

import hashlib
import os
from typing import Any


def preview_enabled() -> bool:
    return os.environ.get("MYROAD_UI_PREVIEW", "").strip() == "1"


def stage_states(topics: list[dict[str, Any]], mastered: set[str], node_index: int, blocks: list[dict]) -> list[dict[str, Any]]:
    """Real per-שלב state from mastered steps: done / current / next (no unlock rules exist)."""
    cur_bid = blocks[node_index]["blockId"] if 0 <= node_index < len(blocks) else None
    out = []
    for tp in topics:
        total = tp["stepCount"] or 0
        done = sum(1 for b in tp["blockIds"] if b in mastered)
        if total and done >= total:
            state = "done"
        elif cur_bid and cur_bid in tp["blockIds"]:
            state = "current"
        else:
            state = "next"
        out.append({"id": tp["id"], "title": tp["title"], "titleLang": tp.get("titleLang", ""),
                    "done": done, "total": total, "state": state,
                    "pct": int(round(100 * done / total)) if total else 0})
    if out and not any(s["state"] == "current" for s in out):
        for s in out:
            if s["state"] != "done":
                s["state"] = "current"
                break
    return out


_SKILLS = {
    "english": [
        ("אוצר מילים", "מילים שונות בשימוש", (30, 60, 100), False),
        ("קריאה", "קטעים קצרים שהובנו", (3, 8, 15), False),
        ("הבנת הנשמע", "הקלטות שהובנו", (5, 15, 30), False),
        ("כתיבה", "משפטים נכונים", (3, 10, 25), False),
        ("דקדוק", "תשובות נכונות", (15, 40, 80), True),
        ("דיבור", "משימות דיבור", (5, 12, 20), True),
    ],
    "math": [
        ("חשבון בעל פה", "תרגילים נכונים", (10, 30, 60), False),
        ("בעיות מילוליות", "בעיות שנפתרו", (3, 8, 15), False),
        ("הבנת מושגים", "הסברים שהובנו", (3, 6, 10), False),
        ("דיוק", "תשובות נכונות ברצף", (5, 10, 20), True),
    ],
}


def _seed(path_id: str) -> int:
    return int(hashlib.sha1(path_id.encode()).hexdigest()[:6], 16)


def mock_skills(path_id: str, subject: str, pct: int) -> list[dict[str, Any]]:
    """Sample skills (נתוני דוגמה). Deterministic per road, scaled by real progress."""
    base = _SKILLS.get(subject) or _SKILLS["math"]
    s = _seed(path_id)
    out = []
    for i, (name, unit, th, suggested) in enumerate(base):
        frac = max(0.0, min(1.0, (pct / 100) * 1.6 + ((s >> (i * 3)) % 7) / 20 - (0.35 if suggested and i == len(base) - 1 else 0)))
        amount = int(round(frac * th[1]))
        level = sum(1 for t in th if amount >= t)
        target = th[min(level, len(th) - 1)]
        if amount == 0:
            status = "none"
        elif target and amount / target >= 0.85:
            status = "almost"
        elif frac < 0.3:
            status = "practice"
        else:
            status = "on_way"
        out.append({"name": name, "unit": unit, "thresholds": list(th), "max": th[-1], "amount": amount,
                    "target": target, "level": level, "nextLevel": min(level + 1, len(th)),
                    "pct": int(round(100 * amount / target)) if target else 0,
                    "maxPct": round(100 * amount / th[-1], 1), "suggested": suggested, "status": status})
    return out


def mock_unlock(stages: list[dict[str, Any]], skills: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Sample unlock condition for the next שלב (נתוני דוגמה)."""
    nxt = None
    seen_current = False
    for st in stages:
        if st["state"] == "current":
            seen_current = True
            continue
        if seen_current and st["state"] != "done":
            nxt = st
            break
    if not nxt or not skills:
        return None
    sk = skills[0]
    need = max(0, sk["thresholds"][min(1, len(sk["thresholds"]) - 1)] - sk["amount"])
    return {"stage": nxt, "stageNo": stages.index(nxt) + 1, "skill": sk["name"], "level": 2,
            "need": need, "unit": sk["unit"]}


def apply_preview_lock(stages: list[dict[str, Any]]) -> None:
    """In preview, שלבים after the current one show as locked (sample rule)."""
    seen = False
    for st in stages:
        if st["state"] == "current":
            seen = True
        elif seen and st["state"] == "next":
            st["state"] = "locked"
