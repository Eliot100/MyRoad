"""View model for the journey-style hopscotch road (Eliot, 2026-11-12).

The timeline's ``road_timeline()`` is left untouched and still drives the
timeline style. This module takes the same inputs and regroups topics into
*stages* (topics) and *levels* (רמות) so the journey template can draw a
centered hopscotch of square stones, bottom to top, each row centered on the vertical midline.

Levels come only from real content: a topic id that ends in ``_lN`` (the
convention already used by ``stage_metrics.level_of``, e.g. ``alg_l1``,
``alg_l2``, ``alg_l3`` on the math bagrut 5 roads). Consecutive ``_lN``
topics that share a stem form levels of one stage (same topic, harder).
A following topic whose id starts with ``{stem}_`` and has no ``_lN``
(typically a review, e.g. ``alg_review``) is attached as a review block of
that stage, not invented as a new level.

A road with no ``_lN`` ids is drawn as one level-1 block per topic. Extra
levels are never invented.

Tile states (done / here / open / ahead / view) are the same as the
timeline, including the linear-gap lock. Unlock rules are not changed:
``_clamp_to_gap`` on start snaps any skip past the first unfinished tile,
and changing that would break linear bagrut roads and the timeline tests.
"Any order within a row" is therefore visual only when the existing rules
already allow it (non-linear, tiles already ``open``).

Row grouping (Eliot, 2026-11-12, correction): symmetry is around the
vertical center line of the screen, not a bottom-to-top 1-2-3-2-1 diamond.
Consecutive sessions that share a role (same type, same review/check flag)
are any-order peers and share a row of at most 3. A type change (learn to
practice to check) starts a new run. Every row is centered; stone size is
fixed and does not grow or shrink with the count in the row.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from myroad_core.ui.road_timeline import road_timeline

MAX_ROW = 3
_LEVEL = re.compile(r"^(.*)_l(\d+)$")


def _row_role(tile: Mapping[str, Any] | Any) -> tuple[Any, ...]:
    """Peer key: consecutive tiles with the same role share a row.

    Practice (or review-practice) items of one type are treated as any-order
    peers. A learn, a check, a speak or a celebrate starts its own run, as
    does a change of type. The timeline's ``check`` flag (last tile of a
    multi-step topic) also splits a run, so a closing משבצת sits on its own
    row when the data marks it that way.
    """
    if not isinstance(tile, Mapping):
        return ("item",)
    kind = "review" if tile.get("review") else "check" if tile.get("check") else "step"
    return (kind, tile.get("type") or "")


def pack_row_counts(n: int, max_n: int = MAX_ROW) -> list[int]:
    """Split ``n`` peer stones into rows of 1–``max_n``.

    A remainder of 1 after full rows of 3 becomes 2+2 (not 3+1), so the
    last rows stay balanced and every stone keeps the same size.
    """
    if n <= 0:
        return []
    if n <= max_n:
        return [n]
    if n % max_n == 1 and n > max_n:
        return pack_row_counts(n - 4, max_n) + [2, 2]
    full, rem = divmod(n, max_n)
    return [max_n] * full + ([rem] if rem else [])


def hop_rows(tiles: list[Any]) -> list[list[Any]]:
    """Group a block's sessions into centered rows of 1, 2 or 3.

    Row counts come from the data: any-order peers (same role) share a
    row, packed at most three wide. Each row is later centered on the
    vertical midline with a fixed stone size, so a 1-stone row is not
    giant and a 3-stone row is not tiny.
    """
    if not tiles:
        return []
    runs: list[list[Any]] = [[tiles[0]]]
    role = _row_role(tiles[0])
    for tile in tiles[1:]:
        r = _row_role(tile)
        if r == role:
            runs[-1].append(tile)
        else:
            runs.append([tile])
            role = r
    rows: list[list[Any]] = []
    for run in runs:
        i = 0
        for count in pack_row_counts(len(run)):
            rows.append(list(run[i : i + count]))
            i += count
    return rows


def topic_level(topic_id: str | None) -> tuple[str, int] | tuple[None, None]:
    """Return ``(stem, level)`` when ``topic_id`` ends in ``_lN``, else ``(None, None)``."""
    match = _LEVEL.search(str(topic_id or ""))
    if not match:
        return None, None
    return match.group(1), int(match.group(2))


def _same_family(topic_id: str, stem: str) -> bool:
    tid = str(topic_id or "")
    return tid == stem or tid.startswith(stem + "_")


def _group_topics(tl_stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Walk timeline stages (one per ContentTopic) into stage/level groups."""
    groups: list[dict[str, Any]] = []
    i = 0
    n = 0
    while i < len(tl_stages):
        stage = tl_stages[i]
        stem, level = topic_level(stage.get("id"))
        n += 1
        blocks: list[dict[str, Any]] = []
        if stem is not None:
            while i < len(tl_stages):
                other = tl_stages[i]
                ostem, olevel = topic_level(other.get("id"))
                if ostem != stem:
                    break
                blocks.append(_block_from_stage(other, level=olevel, kind="level"))
                i += 1
            while i < len(tl_stages):
                other = tl_stages[i]
                ostem, olevel = topic_level(other.get("id"))
                if olevel is not None or not _same_family(str(other.get("id") or ""), stem):
                    break
                blocks.append(_block_from_stage(other, level=None, kind="review"))
                i += 1
            title = _family_title(blocks, stage)
            groups.append({
                "n": n,
                "id": stem,
                "title": title,
                "titleLang": stage.get("titleLang") or "",
                "tint": ((n - 1) % 5) + 1,
                "hasRealLevels": True,
                "blocks": blocks,
            })
        else:
            blocks.append(_block_from_stage(stage, level=1, kind="level", invented=False))
            groups.append({
                "n": n,
                "id": stage.get("id"),
                "title": stage.get("title") or "",
                "titleLang": stage.get("titleLang") or "",
                "tint": ((n - 1) % 5) + 1,
                "hasRealLevels": False,
                "blocks": blocks,
            })
            i += 1
    return groups


def _family_title(blocks: list[dict[str, Any]], first: dict[str, Any]) -> str:
    """Prefer a level-block title that is not just 'רמה N, …'; ignore review titles.

    The topic name for a leveled family usually lives on the path (passed in
    later as ``path_title``). Review blocks like "חזרה מעורבת" are not the
    stage name.
    """
    for block in blocks:
        if block.get("kind") == "review":
            continue
        raw = (block.get("title") or "").strip()
        if raw and not re.match(r"^(רמה|Level|المستوى)\s*\d+", raw):
            return raw
    return (first.get("title") or "").strip()


def _block_from_stage(
    stage: dict[str, Any],
    *,
    level: int | None,
    kind: str,
    invented: bool = False,
) -> dict[str, Any]:
    tiles = [dict(tile) for tile in (stage.get("tiles") or [])]
    rows = hop_rows(tiles)
    return {
        "id": stage.get("id"),
        "level": 1 if level is None and kind == "level" else level,
        "kind": kind,
        "title": stage.get("title") or "",
        "titleLang": stage.get("titleLang") or "",
        "review": bool(stage.get("review")) or kind == "review",
        "rows": rows,
        "tiles": tiles,
        "done": stage.get("done") or 0,
        "total": stage.get("total") or len(tiles),
        "pct": stage.get("pct") or 0,
        "state": stage.get("state"),
        "walked": bool(stage.get("walked")),
        "invented": invented,
    }


def _block_gateway_state(prev: dict[str, Any], nxt: dict[str, Any]) -> str:
    if prev.get("state") == "view" or nxt.get("state") == "view":
        return "view"
    if prev.get("state") == "done":
        if nxt.get("state") in ("done", "here", "started"):
            return "passed"
        return "open"
    return "locked"


def _finish_groups(
    groups: list[dict[str, Any]],
    *,
    path_title: str,
    here_stage_n: int | None,
    finished: bool,
) -> None:
    for group in groups:
        blocks = group["blocks"]
        if group.get("hasRealLevels") and path_title:
            # Leveled family titles in content are "רמה 1, בסיס"; the path title
            # is the topic name (e.g. אלגברה) and belongs on the stage.
            group["title"] = path_title
        group["done"] = sum(int(b.get("done") or 0) for b in blocks)
        group["total"] = sum(int(b.get("total") or 0) for b in blocks)
        group["pct"] = round(100 * group["done"] / group["total"]) if group["total"] else 0
        states = [b.get("state") for b in blocks]
        if states and all(s == "done" for s in states):
            group["state"] = "done"
        elif "here" in states or "started" in states:
            group["state"] = "here"
        elif states and all(s == "ahead" for s in states):
            group["state"] = "ahead"
        elif states and all(s == "view" for s in states):
            group["state"] = "view"
        else:
            group["state"] = "open"
        group["walked"] = finished or (here_stage_n is not None and group["n"] < here_stage_n)
        for i, block in enumerate(blocks):
            block["stageN"] = group["n"]
            block["tint"] = group["tint"]
            block["gateway"] = None
            if i < len(blocks) - 1 and blocks[i + 1].get("kind") == "level" and block.get("kind") == "level":
                nxt = blocks[i + 1]
                block["gateway"] = {
                    "kind": "levelup",
                    "fromLevel": block.get("level"),
                    "toLevel": nxt.get("level"),
                    "state": _block_gateway_state(block, nxt),
                    "stageN": group["n"],
                    "title": group.get("title") or "",
                }


def road_hopscotch(
    topics: Iterable[Mapping[str, Any]] | None,
    *,
    mastered: Iterable[str] | None,
    current_block: str | None,
    linear: bool = False,
    read_only: bool = False,
    path_title: str = "",
) -> dict[str, Any]:
    """Stages, level blocks, hopscotch rows and the next tile for the journey template.

    Same contract as ``road_timeline`` plus ``path_title`` (used as the topic
    name on a leveled stage whose ContentTopic titles are only "רמה N, …").
    """
    tl = road_timeline(
        topics,
        mastered=mastered,
        current_block=current_block,
        linear=linear,
        read_only=read_only,
    )
    # Copy node type from the content steps onto each tile so hop_rows can
    # group any-order peers (same type) without changing the timeline model.
    types = {
        st.get("blockId"): st.get("type") or ""
        for tp in (topics or [])
        for st in (tp.get("steps") or [])
    }
    stages = []
    for stage in list(tl.get("stages") or []):
        copied = dict(stage)
        copied["tiles"] = [
            {**dict(tile), "type": tile.get("type") or types.get(tile.get("id")) or ""}
            for tile in (stage.get("tiles") or [])
        ]
        stages.append(copied)
    groups = _group_topics(stages)
    here_level = None
    here_stage = tl.get("hereStage")
    # hereStage from the timeline is the ContentTopic index, not the grouped stage.
    # Recompute from tiles.
    here_stage_n = None
    next_tile = tl.get("next")
    for group in groups:
        for block in group["blocks"]:
            if any(t.get("state") == "here" for t in block.get("tiles") or []):
                here_stage_n = group["n"]
                here_level = block.get("level")
                if next_tile is not None:
                    next_tile = {
                        **next_tile,
                        "stageN": group["n"],
                        "level": block.get("level"),
                        "stageTitle": group.get("title") or next_tile.get("stageTitle") or "",
                    }
                break
    _finish_groups(groups, path_title=path_title, here_stage_n=here_stage_n, finished=bool(tl.get("finished")))

    # Stage boundaries: a line *before* stage n+1 (the next topic).
    for i, group in enumerate(groups[:-1]):
        nxt = groups[i + 1]
        group["boundary"] = {
            "kind": "stage",
            "toStage": nxt["n"],
            "title": nxt.get("title") or "",
            "titleLang": nxt.get("titleLang") or "",
            "state": "passed" if nxt.get("walked") or nxt.get("state") in ("here", "done", "started") else (
                "open" if group.get("state") == "done" else "locked"
            ),
        }

    has_levels = any(g.get("hasRealLevels") for g in groups)
    return {
        "stages": groups,
        "next": next_tile,
        "done": tl.get("done") or 0,
        "total": tl.get("total") or 0,
        "pct": tl.get("pct") or 0,
        "stagesDone": sum(1 for g in groups if g.get("state") == "done"),
        "stagesTotal": len(groups),
        "hereStage": here_stage_n,
        "hereLevel": here_level,
        "finished": tl.get("finished"),
        "first": tl.get("first"),
        "linear": tl.get("linear"),
        "readOnly": tl.get("readOnly"),
        "hasLevels": has_levels,
        # Expose the timeline model for anything that still wants per-topic stages.
        "topics": tl.get("stages") or [],
    }
