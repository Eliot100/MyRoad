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
_SHORT_MAX = 16

# Deterministic keyword → symbol maps. First match wins. These are marks,
# not invented lesson content: the session title itself is always shown.
_MATH_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"אינטגרל|integral|קדומה|\bint_"), "∫"),
    (re.compile(r"נגזרת|derivative|קיצון|extrema"), "f′"),
    (re.compile(r"שורש|sqrt|\broot\b"), "√"),
    (re.compile(r"אחוז|percent|%"), "%"),
    (re.compile(r"הסתברות|probability|\bprb_"), "%"),
    (re.compile(r"שבר|שברים|fraction|חצי"), "½"),
    (re.compile(r"זווית|angle|סינוס|קוסינוס|טנגנס|\bsin\b|\bcos\b|\btan\b|\btrg_|טריגונ"), "∠"),
    (re.compile(r"חזק|ריבוע|square|power"), "x²"),
    (re.compile(r"לוג|log|מעריכ|exp_log|\bexp_"), "eˣ"),
    (re.compile(r"וקטור|vector|\bvec_"), "→"),
    (re.compile(r"מרוכב|complex|\bcpx_|\bcmp_"), "i"),
    (re.compile(r"סדרה|סדרות|sequence|אינדוק|\bseq_"), "aₙ"),
    (re.compile(r"פונקצ|function|\bfun_"), "f(x)"),
    (re.compile(r"מעגל|circle"), "○"),
    (re.compile(r"משוואה|equation|לינאר|אלגבר|\balg_"), "x"),
    (re.compile(r"גיאומטר|geometry|\bgeo_|analytic|\banl_"), "∠"),
    (re.compile(r"שיפוע|slope"), "m"),
]

# Topic-stem marks used when a session title has no keyword of its own.
_STEM_SYMBOL = {
    "alg": "x", "geo": "∠", "trg": "∠", "seq": "aₙ", "prb": "%",
    "fun": "f(x)", "ext": "f′", "int": "∫", "anl": "∠", "vec": "→",
    "cpx": "i", "cmp": "i", "exp": "eˣ",
}

_EN_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(
        r"listen|האזנ|שמע|oral|speak|דיבור|speech|קול|spoken|שיחה|פנייה",
        re.I,
    ), "💬"),
    (re.compile(
        r"read|קריאה|literature|ספרות|story|סיפור|poem|שיר|essay|חיבור|קטע|"
        r"text|book|ספר",
        re.I,
    ), "📖"),
    (re.compile(r"vocab|מילים|אוצר|word|letter|אות|אבג", re.I), "Aa"),
    (re.compile(
        r"grammar|present|tense|question|שאל|שלילה|תדירות|there is|simple|"
        r"past|future|דיוק|accuracy|משפט|don't|doesn't|always",
        re.I,
    ), "Aa"),
]


def shorten_title(title: str, max_chars: int = _SHORT_MAX) -> str:
    """A clean two-line short form of a real title. Never invents words."""
    raw = " ".join((title or "").split())
    text = re.sub(r"\s+\d+$", "", raw)
    text = re.sub(r"\s*\([^)]{0,24}\)\s*", " ", text)
    text = " ".join(text.split())
    if not text:
        text = raw
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if " " in cut:
        word = cut.rsplit(" ", 1)[0]
        if len(word) >= min(4, max_chars // 2):
            return word
    return cut.rstrip(".,;:·-–—") + "…"


def first_letters(title: str) -> str:
    """Safe fallback mark: first letters of the real title, nothing invented."""
    words = [w for w in re.split(r"\s+", (title or "").strip()) if w]
    cleaned: list[str] = []
    for word in words:
        chars = "".join(c for c in word if c.isalpha() or ("\u0590" <= c <= "\u05ff") or ("\u0600" <= c <= "\u06ff"))
        # isalpha already covers Hebrew/Arabic in Python 3; keep digits out so
        # a title that is only a number does not become a numeric-only mark.
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


def map_symbol(
    title: str = "",
    *,
    subject: str = "",
    topic_id: str = "",
    tile_id: str = "",
    topic_title: str = "",
    path_title: str = "",
    path_id: str = "",
) -> str:
    """Subject-fitting symbol from a deterministic keyword map, else first letters."""
    subj = infer_subject(subject, path_id=path_id, path_title=path_title, topic_id=topic_id)
    # Closest text wins: session title, then topic, then path. A path named
    # "ספרות ודיבור" must not override a session called "סיפור קצר".
    layers = (
        _hay(title, tile_id),
        _hay(topic_title, topic_id),
        _hay(path_title, path_id),
    )
    rules = _MATH_RULES if subj == "math" else _EN_RULES if subj == "english" else ()
    for hay in layers:
        if not hay:
            continue
        for pat, sym in rules:
            if pat.search(hay):
                return sym
    if subj == "math":
        stem = parse_topic(topic_id).get("stem") or ""
        if stem in _STEM_SYMBOL:
            return _STEM_SYMBOL[stem]
    return first_letters(title) or first_letters(topic_title) or first_letters(path_title)


def face_for(
    title: str = "",
    *,
    subject: str = "",
    topic_id: str = "",
    tile_id: str = "",
    topic_title: str = "",
    path_title: str = "",
    path_id: str = "",
) -> dict[str, str]:
    """Short title + symbol for a stone. Full title stays in ``title`` / aria."""
    full = " ".join((title or "").split())
    symbol = map_symbol(
        full,
        subject=subject,
        topic_id=topic_id,
        tile_id=tile_id,
        topic_title=topic_title,
        path_title=path_title,
        path_id=path_id,
    )
    short = shorten_title(full)
    if not short or re.fullmatch(r"\d+", short):
        short = symbol or first_letters(full) or first_letters(topic_title)
    if not symbol:
        symbol = first_letters(full) or (short[:2] if short else "")
    return {"shortTitle": short, "symbol": symbol, "fullTitle": full}


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
        symbol = map_symbol(
            title,
            subject=subject,
            topic_id=str(src.get("id") or ""),
            topic_title=str(src.get("title") or ""),
            path_title=path_title,
            path_id=path_id,
        )
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
