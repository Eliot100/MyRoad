"""View model for the road page timeline (map view of /play/{path_id}).

One pure function turns the road's topics (שלבים) and steps (משבצות) plus the learner's
position into what the template draws: one vertical line of שלבים, each with its משבצות,
the single next action, and calm totals. Any road shape in the content schema goes
through here: one שלב or twenty, two משבצות or a hundred, free order or a linear chain
that cannot skip ahead of the פער. Nothing touches the store; the route passes data in.

Tile states:  done | here | open | ahead (linear chain, past the פער) | view (read only)
Stage states: done | here | started | open | ahead | view
A stage is ``walked`` once the learner's position is past it (the line behind them is solid,
the line ahead is dashed); a finished road is walked end to end, a read-only road not at all.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

# A road this short opens every שלב: the whole road fits on one screen without a tap.
OPEN_ALL_MAX_TILES = 12


def _tile_state(*, done: bool, here: bool, ahead: bool, read_only: bool) -> str:
    if read_only:
        return "view"
    if done:
        return "done"
    if here:
        return "here"
    return "ahead" if ahead else "open"


def _stage_state(tiles: list[dict[str, Any]], read_only: bool) -> str:
    if read_only:
        return "view"
    states = [t["state"] for t in tiles]
    if states and all(s == "done" for s in states):
        return "done"
    if "here" in states:
        return "here"
    if "done" in states:
        return "started"
    if states and all(s == "ahead" for s in states):
        return "ahead"
    return "open"


def road_timeline(
    topics: Iterable[Mapping[str, Any]] | None,
    *,
    mastered: Iterable[str] | None,
    current_block: str | None,
    linear: bool = False,
    read_only: bool = False,
    subject: str = "",
    path_title: str = "",
) -> dict[str, Any]:
    """Stages, tiles, totals and the next tile for the road timeline template.

    ``topics`` is the ``_topics_for_ui`` list (steps carry blockId, index, title, titleLang, kind).
    ``linear`` locks every tile after the first unfinished one (the פער) in road order.
    ``subject`` and ``path_title`` are optional; the journey style uses them for
    on-stone symbols. The timeline template ignores the extra fields.
    """
    topics = list(topics or [])
    done_ids = set(mastered or [])
    ordered = [st for tp in topics for st in (tp.get("steps") or [])]
    total = len(ordered)
    done_total = sum(1 for st in ordered if st.get("blockId") in done_ids)
    gap = next((int(st.get("index", i)) for i, st in enumerate(ordered) if st.get("blockId") not in done_ids), None)
    if read_only or current_block not in {st.get("blockId") for st in ordered} or current_block in done_ids:
        # The saved position is gone, finished or not this road's: the next tile is the first open one.
        current_block = None if read_only else next(
            (st.get("blockId") for st in ordered if st.get("blockId") not in done_ids), None
        )

    stages: list[dict[str, Any]] = []
    next_tile: dict[str, Any] | None = None
    for n, tp in enumerate(topics, start=1):
        steps = list(tp.get("steps") or [])
        tiles = []
        for i, st in enumerate(steps):
            bid = st.get("blockId")
            here = bid == current_block
            title = st.get("title") or ""
            mark = stone_mark(
                title,
                subject=subject,
                kind=st.get("kind") or "",
                type_=st.get("type") or "",
                topic_title=tp.get("title") or "",
                topic_id=str(tp.get("id") or ""),
            )
            tile = {
                "id": bid,
                "title": title,
                "titleLang": st.get("titleLang") or "",
                "type": st.get("type") or "",
                "kind": st.get("kind") or "",
                "review": st.get("kind") == "review",
                "check": i == len(steps) - 1 and len(steps) > 1 and st.get("kind") != "review",
                "state": _tile_state(
                    done=bid in done_ids,
                    here=here,
                    ahead=linear and gap is not None and int(st.get("index", 0)) > gap,
                    read_only=read_only,
                ),
                "symbol": mark["symbol"],
                "markKind": mark["markKind"],
            }
            tiles.append(tile)
            if here:
                next_tile = {**tile, "stageN": n, "stageTitle": tp.get("title") or "",
                             "stageLang": tp.get("titleLang") or ""}
        done = sum(1 for t in tiles if t["state"] == "done")
        stages.append({
            "n": n,
            "id": tp.get("id"),
            "title": tp.get("title") or "",
            "titleLang": tp.get("titleLang") or "",
            "review": bool(tp.get("isReview")),
            "tiles": tiles,
            "done": done,
            "total": len(tiles),
            "state": _stage_state(tiles, read_only),
        })

    open_all = total <= OPEN_ALL_MAX_TILES
    finished = total > 0 and done_total == total
    here_n = next_tile["stageN"] if next_tile else None
    for st in stages:
        st["open"] = open_all or st["state"] == "here" or (read_only and st["n"] == 1)
        st["pct"] = round(100 * st["done"] / st["total"]) if st["total"] else 0
        st["walked"] = finished or (here_n is not None and st["n"] < here_n)
    stages_done = sum(1 for st in stages if st["state"] == "done")
    result = {
        "stages": stages,
        "next": next_tile,
        "done": done_total,
        "total": total,
        "pct": round(100 * done_total / total) if total else 0,
        "stagesDone": stages_done,
        "stagesTotal": len(stages),
        "hereStage": here_n,
        "finished": finished,
        "first": ordered[0].get("blockId") if ordered else None,
        "linear": linear,
        "readOnly": read_only,
        "subject": subject or "",
        "pathTitle": path_title or "",
    }
    annotate_journey(result)
    return result

# Journey / hopscotch helpers. Extra fields on each stage; the timeline template
# ignores them. Levels follow the existing content convention (stage_metrics.py):
# a topic id ending in ``_lN`` is level N of a named prefix (one שלב). Topics
# without that suffix are shown as רמה 1 of their own שלב; we never invent a
# higher level.
#
# Row grouping is driven by the data, not a fixed 1-2-3-2-1 diamond. Symmetry
# is around the vertical centre line: every row is centred, stones share one
# fixed size, and a row's width is (count × size) + gaps. Stones that can be
# done in any order (practice or review peers) share a row, up to three.
# Learn and check nodes are gates and sit on their own row of one.

_LEVEL_ID = re.compile(r"^(.*)_l(\d+)$")
MAX_ROW = 3
GATE_TYPES = frozenset({"learn", "check", "explanation", "assessment"})


def _is_gate(tile: Any) -> bool:
    """A learn or check node opens or closes a stretch; it gets its own row."""
    if not isinstance(tile, dict):
        return False
    return (tile.get("type") or "").lower() in GATE_TYPES


def hop_rows(tiles: list[Any]) -> list[list[Any]]:
    """Group a block's tiles into centred rows of 1–3, from the data.

    Consecutive practice or review stones share rows (packed to ``MAX_ROW``);
    a leftover 1 or 2 ends the run as a shorter centred row. Gate stones
    (learn, check) each get a row of one. When tiles have no ``type`` (tests
    or a topic with no node types), the whole block is packed as peers.
    """
    rows: list[list[Any]] = []
    run: list[Any] = []

    def flush() -> None:
        nonlocal run
        for i in range(0, len(run), MAX_ROW):
            rows.append(list(run[i:i + MAX_ROW]))
        run = []

    for tile in tiles:
        if _is_gate(tile):
            flush()
            rows.append([tile])
        else:
            run.append(tile)
    flush()
    return rows


# Deterministic subject marks for hopscotch stones (correction 3).
# Each stone and stage shows a readable title and/or a subject-fitting
# symbol drawn from real title/id data. Nothing is invented: the symbol
# comes from a fixed keyword map, then the first letters of the title,
# then a subject default. The title on the stone is the real session title.

def _compile_rules(rows: list[tuple[str, str, str]]) -> list[tuple[re.Pattern[str], str, str]]:
    return [(re.compile(pat, re.IGNORECASE | re.UNICODE), sym, kind) for pat, sym, kind in rows]


_MATH_RULES = _compile_rules([
    (r"אינטגרל|integral|קדומה", "∫", "text"),
    (r"נגזרת|derivative", "f′", "text"),
    (r"שורש|root|radical", "√", "text"),
    (r"זווית|angle|פיתגורס|pythag|משולש|triangle|גיאומטר|geometry", "∠", "text"),
    (r"סינוס|קוסינוס|טנגנס|sin\b|cos\b|tan\b|טריגו|trigon", "θ", "text"),
    (r"סדרה|sequence|חשבונית|הנדסית|אינדוק", "Σ", "text"),
    (r"הסתברות|probability|קובי|קלף|\bdice\b|\bcard\b", "P", "text"),
    (r"שבר|fraction", "½", "text"),
    (r"אחוז|percent", "%", "text"),
    (r"וקטור|vector", "→", "text"),
    (r"מרוכב|complex|צמוד|ממשי|\bimag", "i", "text"),
    (r"לוג|לוגרית|מעריכ|exponent|\blog\b", "eˣ", "text"),
    (r"ריבוע|חזק|quadratic|x\s*\^?\s*2", "x²", "text"),
    (r"אנליט|משוואת ישר|מאונך|מקביל|analytic", "xy", "text"),
    (r"קיצון|מקסימום|מינימום|extrema|קודקוד", "Δ", "text"),
    (r"אי.?שוויון|inequal", "≠", "text"),
    (r"משוואה|equation|אלגבר|לינאר", "=", "text"),
    (r"פונקצי|function", "f", "text"),
    (r"כפל|חילוק|multiply|division", "×", "text"),
    (r"חיבור|חיסור|addition|subtract", "+", "text"),
    (r"מספר|number|ספרה|ערך מקום", "n", "text"),
    (r"\balg[_-]|\bאלגבר", "=", "text"),
    (r"\bgeo[_-]|\bגיאומטר", "∠", "text"),
    (r"\btrig[_-]", "θ", "text"),
    (r"\bseq[_-]", "Σ", "text"),
    (r"\bprob[_-]", "P", "text"),
    (r"\bvec[_-]", "→", "text"),
    (r"\bint[_-]|\bintegral", "∫", "text"),
    (r"\bcomp[_-]|\bcomplex", "i", "text"),
    (r"\bexp[_-]|\blog[_-]", "eˣ", "text"),
])

_ENGLISH_RULES = _compile_rules([
    (r"דיבור|oral|listen|שמע|spoken|speech|שיחה|listening", "", "speech"),
    (r"קריאה|read|\bpassage\b|קטע|סיפור|שיר|literature|חיבור|essay|כתב|writing", "", "book"),
    (r"אות|letter|alphabet|צליל|sound|אוצר|vocab|מילה|word|דקדוק|grammar|"
     r"present|past|future|הווה|עבר|עתיד|משפט|sentence|am,? is,? are|"
     r"tense|there is|שלילה|accurate|module", "Aa", "text"),
])

_ARABIC_RULES = _compile_rules([
    (r"כתב|אות|script|ערבית|arabic|מילה|מילים", "ا", "text"),
])

_SUBJECT_DEFAULT = {
    "math": ("x", "text"),
    "english": ("Aa", "text"),
    "arabic": ("ا", "text"),
}

_SUBJECT_RULES = {
    "math": _MATH_RULES,
    "english": _ENGLISH_RULES,
    "arabic": _ARABIC_RULES,
}


def first_letters(title: str, *, max_letters: int = 2) -> str:
    """Initials of the first words of a real title; never invented text."""
    raw = " ".join((title or "").split())
    if not raw:
        return ""
    words = []
    for w in re.split(r"\s+", raw):
        # Skip pure numbers and lone punctuation so "משוואה 1" yields "מ".
        core = re.sub(r"^[^\w]+|[^\w]+$", "", w, flags=re.UNICODE)
        if not core or core.isdigit():
            continue
        words.append(core)
    # A single short word (e.g. "he", "you") is itself the mark.
    if len(words) == 1 and 1 <= len(words[0]) <= 3:
        return words[0]
    letters: list[str] = []
    for w in words[:max_letters]:
        for ch in w:
            if ch.isalnum():
                letters.append(ch)
                break
    if letters:
        return "".join(letters)[:max_letters]
    # Title was only numbers or marks: take the first two characters as-is.
    return raw[:max_letters]


def stone_mark(
    title: str,
    *,
    subject: str = "",
    kind: str = "",
    type_: str = "",
    topic_title: str = "",
    topic_id: str = "",
) -> dict[str, str]:
    """Map real title/id/subject data to a visible on-stone symbol.

    Returns ``{"symbol", "markKind"}``. ``markKind`` is ``text``, ``book``,
    or ``speech``. The symbol is never empty: a title's first letters, then a
    subject default, then a single middle-dot, in that order.
    """
    hay = " ".join(
        part for part in (title, topic_title, topic_id, kind, type_) if part
    )
    subj = (subject or "").strip().lower()
    rules = _SUBJECT_RULES.get(subj)
    if rules is None:
        rules = _MATH_RULES + _ENGLISH_RULES + _ARABIC_RULES
    for pat, symbol, mark_kind in rules:
        if pat.search(hay):
            return {"symbol": symbol, "markKind": mark_kind}
    letters = first_letters(title or topic_title or "")
    if letters:
        return {"symbol": letters, "markKind": "text"}
    if subj in _SUBJECT_DEFAULT:
        symbol, mark_kind = _SUBJECT_DEFAULT[subj]
        return {"symbol": symbol, "markKind": mark_kind}
    # Last resort: a visible middle-dot so the stone is never blank.
    return {"symbol": "·", "markKind": "text"}


def _prefix_level(topic_id: str | None) -> tuple[str | None, int | None]:
    match = _LEVEL_ID.match(str(topic_id or ""))
    if match:
        return match.group(1), int(match.group(2))
    return None, None


def _same_family(topic_id: str | None, prefix: str | None) -> bool:
    if not prefix or not topic_id:
        return False
    if topic_id == prefix:
        return True
    return topic_id.startswith(prefix + "_") or topic_id.startswith(prefix)


def _pick_current_member(members: list[dict[str, Any]]) -> dict[str, Any]:
    """The learner's current level in a stage: the lowest _lN not yet completed.

    After every level is done, a trailing review (if any) is current. If the
    whole stage is done, the last member is shown, all walked.
    """
    levels = [m for m in members if not m.get("review") and m.get("level") is not None]
    levels = sorted(levels, key=lambda m: int(m.get("level") or 0))
    for member in levels:
        if member.get("state") != "done":
            return member
    reviews = [m for m in members if m.get("review")]
    for member in reviews:
        if member.get("state") != "done":
            return member
    if reviews:
        return reviews[-1]
    if levels:
        return levels[-1]
    return members[-1]


def annotate_journey(tl: dict[str, Any]) -> dict[str, Any]:
    """Attach hopscotch rows, real levels, and journey-only stage blocks.

    Mutates ``tl["stages"]`` with extra fields the timeline template ignores.
    Builds ``tl["jyStages"]``: one block per שלב, whose stones are the current
    רמה only (Eliot, 2026-11-12 correction 2). No inter-level blocks or lines.
    """
    stages = list(tl.get("stages") or [])
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for st in stages:
        prefix, level = _prefix_level(st.get("id"))
        is_review = bool(st.get("review"))
        if current is None:
            current = {
                "prefix": prefix,
                "stageGroup": 1,
                "members": [st],
                "levels": [level] if level is not None else [],
            }
            groups.append(current)
            continue
        same_level_family = prefix is not None and prefix == current["prefix"]
        same_review_family = (
            prefix is None
            and current["prefix"] is not None
            and (is_review or _same_family(st.get("id"), current["prefix"]))
        )
        if same_level_family or same_review_family:
            current["members"].append(st)
            if level is not None:
                current["levels"].append(level)
        else:
            current = {
                "prefix": prefix,
                "stageGroup": groups[-1]["stageGroup"] + 1,
                "members": [st],
                "levels": [level] if level is not None else [],
            }
            groups.append(current)

    for g in groups:
        level_total = max(g["levels"]) if g["levels"] else 1
        prev_level: int | None = None
        first_in_group = True
        for st in g["members"]:
            _p, raw_level = _prefix_level(st.get("id"))
            has_real_level = raw_level is not None
            level = raw_level if has_real_level else (None if st.get("review") else 1)
            st["stageGroup"] = g["stageGroup"]
            st["level"] = level
            st["levelTotal"] = level_total
            st["hasRealLevels"] = bool(g["levels"])
            st["stageGroupTitle"] = st.get("title") or ""
            st["rows"] = hop_rows(list(st.get("tiles") or []))
            if first_in_group:
                st["boundary"] = "stage" if g["stageGroup"] > 1 else None
            elif has_real_level and prev_level is not None and raw_level > prev_level:
                st["boundary"] = "level-up"
            elif st.get("review"):
                st["boundary"] = "review"
            else:
                st["boundary"] = None
            first_in_group = False
            if has_real_level:
                prev_level = raw_level

    jy_stages: list[dict[str, Any]] = []
    for g in groups:
        chosen = _pick_current_member(g["members"])
        tiles = list(chosen.get("tiles") or [])
        subject = tl.get("subject") or ""
        # Stage label: path title for a real-level group (e.g. "אלגברה"),
        # otherwise the topic's own title. The symbol is derived from that
        # real name plus the topic id and subject.
        stage_title = (tl.get("pathTitle") if g["levels"] else "") or (chosen.get("title") or "")
        stage_mark = stone_mark(
            stage_title,
            subject=subject,
            topic_title=chosen.get("title") or "",
            topic_id=str(chosen.get("id") or ""),
        )
        for tile in tiles:
            if not tile.get("symbol"):
                tile.update(stone_mark(
                    tile.get("title") or "",
                    subject=subject,
                    kind=tile.get("kind") or "",
                    type_=tile.get("type") or "",
                    topic_title=chosen.get("title") or "",
                    topic_id=str(chosen.get("id") or ""),
                ))
        jy_stages.append({
            "n": chosen.get("n"),
            "id": chosen.get("id"),
            "title": chosen.get("title") or "",
            "titleLang": chosen.get("titleLang") or "",
            "topicTitle": "" if g["levels"] else (chosen.get("title") or ""),
            "usePathTitle": bool(g["levels"]),
            "review": bool(chosen.get("review")),
            "tiles": tiles,
            "rows": hop_rows(tiles),
            "done": chosen.get("done"),
            "total": chosen.get("total"),
            "pct": chosen.get("pct"),
            "state": chosen.get("state"),
            "walked": chosen.get("walked"),
            "open": chosen.get("open"),
            "stageGroup": g["stageGroup"],
            "level": chosen.get("level"),
            "levelTotal": max(g["levels"]) if g["levels"] else 1,
            "hasRealLevels": bool(g["levels"]),
            # Only topic (new-שלב) boundaries; never a line between levels.
            "boundary": "stage" if g["stageGroup"] > 1 else None,
            "symbol": stage_mark["symbol"],
            "markKind": stage_mark["markKind"],
        })
    tl["jyStages"] = jy_stages
    tl["stageGroups"] = len(groups)
    nxt = tl.get("next")
    if nxt and jy_stages:
        for js in jy_stages:
            if any(tile.get("id") == nxt.get("id") for tile in (js.get("tiles") or [])):
                nxt["jyStageGroup"] = js.get("stageGroup")
                nxt["jyLevel"] = js.get("level")
                break
    return tl
