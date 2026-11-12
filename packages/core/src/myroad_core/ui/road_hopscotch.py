"""Hopscotch view of the journey-style road.

One block per stage (topic). Its stones are the steps of the learner's
current level: the lowest ``_lN`` topic not yet completed (the convention
in ``stage_metrics.py``). Paths with no level ids are shown as רמה 1
blocks only; nothing is invented. Level 2 is not a separate block and
does not get its own line; only a new topic gets a stage boundary.

Rows follow the data, not a decorative diamond: consecutive sessions in a
block fill rows of at most ``MAX_ROW`` (3). A leftover of 1 or 2 opens
the block, still centered. Every row is centered on the vertical midline;
stone size is fixed (Eliot, 2026-11-12).

The timeline view model is not modified. Unlock rules stay those of the
timeline: this module only arranges tiles that already have a state.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable, Mapping

# Widest a single row may be. Stones that share a block fill rows of this
# width; a leftover 1 or 2 is its own centered row, same stone size.
MAX_ROW = 3

_LEVEL = re.compile(r"^(.+)_l(\d+)$")
_REVIEW = re.compile(r"^(.+)_review$")

_RING_R = 14.0
_RING_C = 2 * math.pi * _RING_R


def _row(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    take = len(items)
    for col, tile in enumerate(items):
        tile["col"] = col
        tile["rowSpan"] = take
    return items


def chunk_rows(tiles: Iterable[Mapping[str, Any]], max_row: int = MAX_ROW) -> list[list[dict[str, Any]]]:
    """Fill rows of ``max_row`` stones; a leftover 1 or 2 opens the block.

    The short row sits at the start (visual bottom, or the right in horizontal
    RTL) so a new block begins with 1 or 2 and then full rows, rather than
    tapering to a single stone at the top like a diamond. Row width is
    ``count * stone size + gaps``, from a fixed stone size, and each row is
    centered on the vertical midline.
    """
    items = [dict(t) for t in tiles]
    width = max(1, int(max_row))
    if not items:
        return []
    rows: list[list[dict[str, Any]]] = []
    lead = len(items) % width
    i = 0
    if lead:
        rows.append(_row(items[:lead]))
        i = lead
    while i < len(items):
        rows.append(_row(items[i : i + width]))
        i += width
    return rows


def parse_topic(topic_id: str | None) -> dict[str, Any]:
    """Stem, real level number (or None), and whether this is a ``_review`` topic."""
    sid = str(topic_id or "")
    match = _LEVEL.match(sid)
    if match:
        return {"stem": match.group(1), "level": int(match.group(2)), "review": False, "real": True}
    match = _REVIEW.match(sid)
    if match:
        return {"stem": match.group(1), "level": None, "review": True, "real": True}
    return {"stem": sid, "level": None, "review": False, "real": False}


def _ring(pct: int) -> dict[str, float | int]:
    pct = max(0, min(100, int(pct or 0)))
    return {
        "c": round(_RING_C, 3),
        "offset": round(_RING_C * (1 - pct / 100), 3),
        "pct": pct,
    }


def _same_stage(prev_parsed: dict[str, Any] | None, parsed: dict[str, Any]) -> bool:
    if not prev_parsed:
        return False
    if not prev_parsed["real"] or not parsed["real"]:
        return False
    return prev_parsed["stem"] == parsed["stem"]


def _pick_current(members: list[dict[str, Any]]) -> dict[str, Any]:
    """The lowest level not yet completed; if all are done, the last member."""
    for member in members:
        if member["src"].get("state") != "done":
            return member
    return members[-1]



# Two-line short title at a ~80px stone, legible at 375px.
# Exercise numbers stay ("משוואה לינארית 5"); only a leading "רמה N," is trimmed.
_SHORT_MAX = 18
_LEVEL_PREFIX = re.compile(
    r"^(?:רמה|Level|المستوى)\s*\d+\s*[,،.]?\s*",
    re.IGNORECASE,
)

# Subject-scoped mark rules from C3, with a few extra English reading
# needles so a literature topic still gets a book. Kind is "text",
# "book" or "speech" (the last two are line-drawn SVGs in the template).
_MARK_RULES: tuple[tuple[tuple[str, ...] | None, tuple[str, ...], str, str], ...] = (
    (("math",), ("אינטגר", "integral", "antideriv", "קדומה"), "∫", "text"),
    (("math",), ("נגזרת", "derivativ", "extrema", "קיצון"), "f′", "text"),
    (("math",), ("שורש", "sqrt"), "√", "text"),
    (("math",), ("אחוז", "percent", "הסתברות", "probab", "סיכוי"), "%", "text"),
    (("math",), ("שברים", "שבר", "fraction"), "½", "text"),
    (("math",), ("זווית", "טריגו", "trig", "סינוס", "קוסינוס", "טנגנס", "sine", "cosine"), "∠", "text"),
    (("math",), ("ריבועית", "ריבועיות", "ריבועים", "quadrat", "parabola", "פרבול"), "x²", "text"),
    (("math",), ("חזקות", "חזקה"), "xⁿ", "text"),
    (("math",), ("מלבן", "rectangle"), "□", "text"),
    (("math",), ("משולש", "triangle"), "△", "text"),
    (("math",), ("מעגל", "circle"), "○", "text"),
    (("math",), ("גיאומט", "geo_", "geometry"), "△", "text"),
    (("math",), ("וקטור", "vector"), "→", "text"),
    (("math",), ("מרוכב", "complex"), "i", "text"),
    (("math",), ("לוגרית", "מעריכ", "logarithm", "exp_log", "exp_"), "eˣ", "text"),
    (("math",), ("פונקצי", "function", "fun_"), "f", "text"),
    (("math",), ("סדרות", "seq_", "sequence", "אינדוק"), "aₙ", "text"),
    (("math",), ("סדרה",), "aₙ", "text"),
    (("math",), ("אנליט", "analytic"), "xy", "text"),
    (("math",), ("מערכת", "systems"), "xy", "text"),
    (("math",), ("אי שוויון", "אי-שוויון", "inequal"), "<", "text"),
    (("math",), ("כפל", "muldiv", "multiply"), "×", "text"),
    (("math",), ("חילוק", "division"), "÷", "text"),
    (("math",), ("חיבור", "addsub", "addition"), "+", "text"),
    (("math",), ("חיסור", "subtract"), "−", "text"),
    (("math",), ("סדר פעול",), "( )", "text"),
    (("math",), ("מספר", "ספרה", "numbers"), "n", "text"),
    (("math",), ("משווא", "אלגבר", "algebra", "alg_", "לינאר", "שוויון"), "x", "text"),
    # English: book and speech are drawn as line SVGs, not emoji.
    (("english",), (
        "הבנת הנקרא", "reading", "passage", "קטע קריאה", "קריאה",
        "סיפור", "ספרות", "שיר", "poem", "story", "literature", "essay",
        "חיבור", "קטע", "text", "book", "ספר",
    ), "book", "book"),
    (("english",), ("listening", "האזנה", "שמיעה", "listen", "speak", "oral", "אמרו", "דיבור", "speech", "קול", "שיחה", "פנייה"), "speech", "speech"),
    (("english",), ("אוצר מילים", "vocab", "vocabulary", "מילים"), "Aa", "text"),
    (("english",), ("אותיות", "letters", "letter"), "Aa", "text"),
    (("english",), (
        "דקדוק", "grammar", "tense", "הווה", "am is are", "שלילה",
        "present", "simple", "past", "future", "דיוק", "accuracy", "משפט",
        "there is", "don't", "doesn't", "always", "question", "שאל", "תדירות",
    ), "Aa", "text"),
    (("english",), ("השלמת משפט", "sentence complet", "restat", "ניסוח", "משפטים"), "…", "text"),
    (("english",), ("כתב", "writing", "write"), "Aa", "text"),
    (("arabic",), ("אותיות", "letters", "script", "כתב", "الحرف"), "ع", "text"),
)

_SUBJECT_DEFAULT: dict[str, tuple[str, str]] = {
    "math": ("x", "text"),
    "english": ("Aa", "text"),
    "arabic": ("ع", "text"),
}

_STEM_SYMBOL = {
    "alg": ("x", "text"), "geo": ("△", "text"), "trg": ("∠", "text"),
    "seq": ("aₙ", "text"), "prb": ("%", "text"), "fun": ("f", "text"),
    "ext": ("f′", "text"), "int": ("∫", "text"), "anl": ("xy", "text"),
    "vec": ("→", "text"), "cpx": ("i", "text"), "cmp": ("i", "text"),
    "exp": ("eˣ", "text"),
}


def shorten_title(title: str, max_chars: int = _SHORT_MAX) -> str:
    """A clean two-line short form of a real title. Keeps exercise numbers."""
    raw = _LEVEL_PREFIX.sub("", " ".join((title or "").split())).strip()
    if not raw:
        raw = " ".join((title or "").split())
    # Drop a short parenthetical variant (בלי שמע) but keep "משוואה לינארית 5".
    text = re.sub(r"\s*\([^)]{0,24}\)\s*", " ", raw)
    text = " ".join(text.split()) or raw
    if len(text) <= max_chars:
        return text
    window = text[: max_chars + 1]
    for sep in (" ", ",", "،", ":", "·"):
        i = window.rfind(sep)
        if i >= max(4, max_chars // 2):
            return text[:i].rstrip(" ,،:·")
    return text[:max_chars].rstrip(".,;:·-–—")


def first_letters(title: str) -> str:
    """Safe fallback mark: first letters of the real title, nothing invented."""
    raw = _LEVEL_PREFIX.sub("", (title or "").strip()).strip()
    words = [w for w in re.split(r"\s+", raw) if w]
    cleaned: list[str] = []
    for word in words:
        chars = "".join(c for c in word if c.isalpha())
        if chars:
            cleaned.append(chars)
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0][:2]
    return cleaned[0][:1] + cleaned[1][:1]


def infer_subject(
    subject: str = "",
    *,
    path_id: str = "",
    path_title: str = "",
    topic_id: str = "",
) -> str:
    if subject:
        return subject.lower().strip()
    pid = (path_id or "").lower()
    if "english" in pid or "amir" in pid:
        return "english"
    if "arabic" in pid:
        return "arabic"
    if "math" in pid or "algebra" in pid:
        return "math"
    if parse_topic(topic_id).get("real"):
        return "math"
    hay = f"{path_title} {topic_id}"
    if re.search(r"אלגבר|מתמט|גיאומ|חשבון|algebra|math|geometry|trig", hay, re.I):
        return "math"
    if re.search(r"english|אנגלית|amirnet|Present|literature", hay, re.I):
        return "english"
    return ""


def _hay(*parts: str) -> str:
    return " ".join(p for p in parts if p)


def stone_mark(
    title: str = "",
    *,
    subject: str = "",
    topic_id: str = "",
    tile_id: str = "",
    topic_title: str = "",
    path_title: str = "",
    path_id: str = "",
    session_type: str = "",
) -> tuple[str, str]:
    """Deterministic (mark, kind) from real data. Never invented, never blank.

    Kind is ``text``, ``book`` or ``speech``. Book and speech are line SVGs.
    Closest text wins: session, then topic, then path.
    """
    subj = infer_subject(subject, path_id=path_id, path_title=path_title, topic_id=topic_id)
    stype = (session_type or "").strip().lower()
    if stype == "speak" and subj in ("english", ""):
        return "speech", "speech"
    layers = (
        _hay(title, tile_id, session_type),
        _hay(topic_title, topic_id),
        _hay(path_title, path_id),
    )
    for hay in layers:
        if not hay:
            continue
        hay_l = hay.lower()
        for subjects, needles, mark, kind in _MARK_RULES:
            if subjects is not None and subj and subj not in subjects:
                continue
            if subjects is not None and not subj and subjects in (("english",), ("arabic",)):
                continue
            if any(needle.lower() in hay_l for needle in needles):
                return mark, kind
    stem = parse_topic(topic_id).get("stem") or ""
    if stem in _STEM_SYMBOL:
        return _STEM_SYMBOL[stem]
    if subj in _SUBJECT_DEFAULT:
        return _SUBJECT_DEFAULT[subj]
    initials = first_letters(title) or first_letters(topic_title) or first_letters(path_title)
    return (initials or "·"), "text"


def map_symbol(
    title: str = "",
    *,
    subject: str = "",
    topic_id: str = "",
    tile_id: str = "",
    topic_title: str = "",
    path_title: str = "",
    path_id: str = "",
    session_type: str = "",
) -> str:
    """Mark glyph (or 'book' / 'speech' kind token) for tests and labels."""
    mark, _kind = stone_mark(
        title,
        subject=subject,
        topic_id=topic_id,
        tile_id=tile_id,
        topic_title=topic_title,
        path_title=path_title,
        path_id=path_id,
        session_type=session_type,
    )
    return mark


def face_for(
    title: str = "",
    *,
    subject: str = "",
    topic_id: str = "",
    tile_id: str = "",
    topic_title: str = "",
    path_title: str = "",
    path_id: str = "",
    session_type: str = "",
) -> dict[str, str]:
    """Short title + mark for a stone. Full title stays in ``title`` / aria."""
    full = " ".join((title or "").split())
    mark, kind = stone_mark(
        full,
        subject=subject,
        topic_id=topic_id,
        tile_id=tile_id,
        topic_title=topic_title,
        path_title=path_title,
        path_id=path_id,
        session_type=session_type,
    )
    short = shorten_title(full)
    if not short or re.fullmatch(r"\d+", short):
        short = (mark if kind == "text" else "") or first_letters(full) or first_letters(topic_title)
    if not mark:
        mark, kind = (first_letters(full) or (short[:2] if short else "·")), "text"
    return {
        "shortTitle": short,
        "symbol": mark,
        "mark": mark,
        "markKind": kind,
        "fullTitle": full,
    }


def _decorate_tiles(
    tiles: list[dict[str, Any]],
    *,
    level_n: int | None,
    review: bool,
    subject: str = "",
    topic_id: str = "",
    topic_title: str = "",
    path_title: str = "",
    path_id: str = "",
) -> list[dict[str, Any]]:
    out = []
    for tile in tiles:
        item = dict(tile)
        if item.get("state") == "done":
            item["leveled"] = True
            item["levelBadge"] = None if review else level_n
        else:
            item["leveled"] = False
            item["levelBadge"] = None
        item["recommended"] = item.get("state") == "here"
        face = face_for(
            item.get("title") or "",
            subject=subject,
            topic_id=topic_id,
            tile_id=str(item.get("id") or ""),
            topic_title=topic_title,
            path_title=path_title,
            path_id=path_id,
            session_type=str(item.get("type") or ""),
        )
        item.update(face)
        out.append(item)
    return out


def road_hopscotch(
    tl: Mapping[str, Any] | None,
    *,
    path_title: str = "",
    path_title_lang: str = "",
    subject: str = "",
    path_id: str = "",
) -> dict[str, Any]:
    """One hopscotch block per stage, showing only the current level's steps.

    A run of ``{stem}_l1``, ``_l2``, … plus an optional ``{stem}_review`` is
    one שלב. The stones are those of the lowest level that is not fully
    done. A later level is never drawn as its own block or line; only a
    new topic produces a stage boundary.
    """
    tl = tl or {}
    stages = list(tl.get("stages") or [])

    groups: list[dict[str, Any]] = []
    has_real_levels = False
    for src in stages:
        parsed = parse_topic(src.get("id"))
        if parsed["real"] and parsed["level"] is not None:
            has_real_levels = True
        member = {"src": src, "parsed": parsed}
        if groups and _same_stage(groups[-1]["members"][-1]["parsed"], parsed):
            groups[-1]["members"].append(member)
        else:
            groups.append({"members": [member]})

    blocks: list[dict[str, Any]] = []
    prev_block: dict[str, Any] | None = None
    for stage_n, group in enumerate(groups, start=1):
        current = _pick_current(group["members"])
        src = current["src"]
        parsed = current["parsed"]
        if parsed["real"] and not parsed["review"]:
            title = path_title or src.get("title") or ""
            title_lang = path_title_lang or src.get("titleLang") or ""
            level_n = parsed["level"]
            kind = "level"
        elif parsed["review"]:
            title = path_title or src.get("title") or ""
            title_lang = path_title_lang or src.get("titleLang") or ""
            level_n = None
            kind = "review"
        else:
            title = src.get("title") or ""
            title_lang = src.get("titleLang") or ""
            level_n = 1
            kind = "review" if src.get("review") else "level"

        tiles = _decorate_tiles(
            [dict(t) for t in (src.get("tiles") or [])],
            level_n=level_n,
            review=kind == "review",
            subject=subject,
            topic_id=str(src.get("id") or ""),
            topic_title=str(src.get("title") or ""),
            path_title=path_title,
            path_id=path_id,
        )
        mark, mark_kind = stone_mark(
            title,
            subject=subject,
            topic_id=str(src.get("id") or ""),
            topic_title=str(src.get("title") or ""),
            path_title=path_title,
            path_id=path_id,
        )
        symbol = mark
        rows = chunk_rows(tiles)
        done = int(src.get("done") or 0)
        total = int(src.get("total") or len(tiles))
        pct = int(src.get("pct") or 0)
        state = src.get("state") or "open"

        # Highest completed real level in this stage, for the "leveled up" reading.
        completed_level = 0
        for member in group["members"]:
            p = member["parsed"]
            if p["real"] and p["level"] is not None and member["src"].get("state") == "done":
                completed_level = max(completed_level, p["level"])

        boundary: dict[str, Any] | None = None
        if prev_block is not None:
            boundary = {
                "kind": "stage",
                "stageN": stage_n,
                "levelN": level_n if level_n is not None else 1,
                "review": kind == "review",
                "title": title,
                "titleLang": title_lang,
                "symbol": symbol,
                "mark": mark,
                "markKind": mark_kind,
                "crossed": prev_block["state"] == "done",
                "open": state in ("here", "started", "open", "done"),
            }

        block = {
            "n": src.get("n"),
            "id": src.get("id"),
            "stageN": stage_n,
            "levelN": level_n,
            "kind": kind,
            "realLevel": bool(parsed["real"] and parsed["level"] is not None),
            "title": title,
            "titleLang": title_lang,
            "symbol": symbol,
            "mark": mark,
            "markKind": mark_kind,
            "topicTitle": src.get("title") or "",
            "topicTitleLang": src.get("titleLang") or "",
            "review": kind == "review" or bool(src.get("review")),
            "tiles": tiles,
            "rows": rows,
            "done": done,
            "total": total,
            "pct": pct,
            "ring": _ring(pct),
            "state": state,
            "walked": bool(src.get("walked")),
            "open": bool(src.get("open")),
            "boundary": boundary,
            "completedLevel": completed_level,
            "levelCount": sum(
                1 for m in group["members"] if m["parsed"]["real"] and m["parsed"]["level"] is not None
            ),
        }
        blocks.append(block)
        prev_block = block

    next_tile = tl.get("next")
    next_block = None
    nid = (next_tile or {}).get("id") if isinstance(next_tile, dict) else None
    if nid:
        for block in blocks:
            if any(tile.get("id") == nid for tile in block["tiles"]):
                next_block = block
                break
    return {
        "blocks": blocks,
        "stagesTotal": int(tl.get("stagesTotal") or len(stages)),
        "blockTotal": len(blocks),
        "stageCount": len(groups),
        "hasRealLevels": has_real_levels,
        "done": int(tl.get("done") or 0),
        "total": int(tl.get("total") or 0),
        "finished": bool(tl.get("finished")),
        "linear": bool(tl.get("linear")),
        "readOnly": bool(tl.get("readOnly")),
        "hereStage": tl.get("hereStage"),
        "next": next_tile,
        "nextBlock": next_block,
    }


def row_mates(tiles: list[Mapping[str, Any]], block_id: str) -> list[str]:
    """Ids of every tile that shares a hopscotch row with ``block_id``."""
    rows = chunk_rows(tiles)
    for row in rows:
        ids = [str(t.get("id")) for t in row]
        if block_id in ids:
            return ids
    return [block_id] if block_id else []
