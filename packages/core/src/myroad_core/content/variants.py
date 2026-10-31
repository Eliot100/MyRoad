"""Step variants and placement routing (docs/decisions/0003-step-variants.md).

``select_variants`` turns a stored path document (all variants) into what one learner
sees: one step per base step. The chosen variant takes the base step's blockId, so
progress, mastery and step events always count toward the base step.
"""

from __future__ import annotations

from typing import Any

DEFAULT_STEP_SETTINGS: dict[str, bool] = {"audio": True, "writing": False}


def _matches(when: dict[str, Any], settings: dict[str, bool]) -> bool:
    return all(v is None or settings.get(k) == v for k, v in when.items())


def select_variants(doc: dict[str, Any], settings: dict[str, bool] | None = None) -> dict[str, Any]:
    blocks = doc.get("blocks") or []
    if not any((b.get("content") or {}).get("variantOf") for b in blocks):
        return doc
    s = {**DEFAULT_STEP_SETTINGS, **{k: bool(v) for k, v in (settings or {}).items() if v is not None}}
    node_of = {b["blockId"]: (b.get("content") or {}).get("nodeId") for b in blocks}
    base_block = {nid: bid for bid, nid in node_of.items()}
    # Best variant per base node: the most specific match wins; ties keep content order.
    best: dict[str, tuple[int, dict[str, Any]]] = {}
    for b in blocks:
        c = b.get("content") or {}
        base = c.get("variantOf")
        if not base or base not in base_block:
            continue
        when = c.get("variantWhen") or {}
        if not _matches(when, s):
            continue
        score = sum(1 for v in when.values() if v is not None)
        if base not in best or score > best[base][0]:
            best[base] = (score, b)
    out_blocks: list[dict[str, Any]] = []
    dropped: set[str] = set()
    for b in blocks:
        c = b.get("content") or {}
        if c.get("variantOf"):
            dropped.add(c.get("nodeId"))
            continue
        nid = c.get("nodeId")
        if nid in best:
            chosen = dict(best[nid][1])
            chosen["content"] = {**chosen.get("content", {}), "baseNodeId": nid}
            chosen["blockId"] = b["blockId"]
            out_blocks.append(chosen)
        else:
            out_blocks.append(b)
    new = dict(doc)
    new["blocks"] = out_blocks
    new["nodeToBlock"] = {k: v for k, v in (doc.get("nodeToBlock") or {}).items() if k not in dropped}
    new["topics"] = [
        {**t, "node_ids": [n for n in (t.get("node_ids") or []) if n not in dropped]} for t in doc.get("topics") or []
    ]
    new["edges"] = [
        {"edgeId": f"edge_{i:03d}", "from": out_blocks[i]["blockId"], "to": out_blocks[i + 1]["blockId"],
         "relationship": "sequence"}
        for i in range(len(out_blocks) - 1)
    ]
    return new


def route_by_band(docs: list[dict[str, Any]], placement_id: str, band: int) -> str | None:
    """First path (in catalog order) whose placementRoute covers this band for this placement."""
    for d in docs:
        r = d.get("placementRoute") or {}
        if r.get("from_placement") == placement_id and int(r.get("band_min", 1)) <= band <= int(r.get("band_max", 8)):
            return d.get("pathId")
    return None
