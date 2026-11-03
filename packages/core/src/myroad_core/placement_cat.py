"""Adaptive English placement (issue #211, docs/decisions/0012-adaptive-placement.md).

A short computerized adaptive test on a 1PL (Rasch) model. Estimation and item information
come from catsim (pinned in pyproject); this module only picks which domain to test next
and maps estimates to scores.

Rules:
- Scoring uses first-try answers only (#199): ``store.first_try_answers``.
- Next item is harder (higher b) after a first-try correct and easier after a miss, when such
  an item is left in the domains being tested; among those, the most informative at the
  current ability estimate (catsim ``irt.inf``). If none is left, the hardest (easiest) one.
- Every domain is tested at least ``MIN_PER_DOMAIN`` times; the test stops at ``MAX_ITEMS``,
  or earlier once every domain's standard error is <= ``SE_STABLE``.
- Domain = the node's ``area`` tag. A placement with no tags at all falls back to its topic
  id per item (reported by ``untagged_placement_items``); partial tagging is a content error.
- Difficulty = the node's ``difficulty`` (1PL b); else items are spread evenly from
  ``-B_SPREAD`` to ``+B_SPREAD`` in content order (placement content is ordered easy to hard).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

MAX_ITEMS = 15
MIN_PER_DOMAIN = 2
SE_STABLE = 1.5
B_SPREAD = 2.5
THETA_MIN, THETA_MAX = -4.0, 4.0

ENGLISH_PLACEMENT_ID = "path_english_bagrut5_00_placement"


def is_placement_id(path_id: str) -> bool:
    return path_id == ENGLISH_PLACEMENT_ID or path_id.endswith("_placement")


def untagged_placement_items(nodes: Iterable[Any]) -> list[str]:
    """Ids of scored placement items (practice/check with choices, not variants) without area."""
    out = []
    for i, n in enumerate(nodes):
        get = n.get if isinstance(n, dict) else lambda k, _n=n: getattr(_n, k, None)
        if get("type") in ("practice", "check") and get("choices") and not get("variant_of") and not get("area"):
            out.append(get("id") or f"#{i}")
    return out


@dataclass(frozen=True)
class Item:
    block_id: str
    node_id: str
    domain: str
    b: float
    order: int


def items_from_doc(doc: dict[str, Any]) -> list[Item]:
    """Scored items of a (variant-selected) placement doc, with domain and difficulty."""
    topic_of: dict[str, str] = {}
    for t in doc.get("topics") or []:
        for nid in t.get("node_ids") or []:
            topic_of[nid] = t.get("id")
    raw = []
    for block in doc.get("blocks") or []:
        content = block.get("content") or {}
        kids = content.get("kids") or {}
        if kids.get("type") not in ("practice", "check") or not kids.get("choices"):
            continue
        nid = content.get("baseNodeId") or content.get("nodeId") or kids.get("id") or block["blockId"]
        domain = kids.get("area") or topic_of.get(nid) or "general"
        raw.append((block["blockId"], nid, domain, kids.get("difficulty")))
    n = len(raw)
    items = []
    for i, (bid, nid, domain, diff) in enumerate(raw):
        b = float(diff) if diff is not None else (
            0.0 if n == 1 else -B_SPREAD + 2 * B_SPREAD * i / (n - 1)
        )
        items.append(Item(bid, nid, domain, b, i))
    return items


def _bank(bs: Sequence[float]):
    import numpy as np

    return np.column_stack([np.ones(len(bs)), np.asarray(bs, float), np.zeros(len(bs)), np.ones(len(bs))])


def _estimate(bs: Sequence[float], oks: Sequence[bool], *, dodd: bool, start: float = 0.0) -> float:
    """1PL ability estimate (catsim numerical search). Clamped to [THETA_MIN, THETA_MAX]."""
    if not bs:
        return start
    from catsim.estimation import NumericalSearchEstimator
    from catsim.item_bank import ItemBank

    est = NumericalSearchEstimator(dodd=dodd).estimate(
        item_bank=ItemBank(_bank(bs), validate=False),  # our 1PL bank is valid; catsim prints on validate
        administered_items=list(range(len(bs))),
        response_vector=list(oks),
        est_theta=start,
    )
    if est is None or math.isnan(est):
        return start
    return max(THETA_MIN, min(THETA_MAX, float(est)))


def _answered(items: list[Item], responses: Sequence[tuple[str, bool]]) -> list[tuple[Item, bool]]:
    by_id = {it.block_id: it for it in items}
    seen: set[str] = set()
    out = []
    for bid, ok in responses:
        if bid in by_id and bid not in seen:
            seen.add(bid)
            out.append((by_id[bid], bool(ok)))
    return out


def _running_theta(answered: list[tuple[Item, bool]]) -> float:
    """Ability after each response in turn (Dodd's step while all answers agree)."""
    theta = 0.0
    for k in range(1, len(answered) + 1):
        part = answered[:k]
        theta = _estimate([it.b for it, _ in part], [ok for _, ok in part], dodd=True, start=theta)
    return theta


def _se(answered_in_domain: list[tuple[Item, bool]], theta: float) -> float:
    if not answered_in_domain:
        return math.inf
    from catsim import irt

    return float(irt.see(theta, _bank([it.b for it, _ in answered_in_domain])))


def domain_ids(items: list[Item]) -> list[str]:
    seen: list[str] = []
    for it in items:
        if it.domain not in seen:
            seen.append(it.domain)
    return seen


def next_item(items: list[Item], responses: Sequence[tuple[str, bool]]) -> Item | None:
    """The next item to serve, or None when the test is over."""
    answered = _answered(items, responses)
    if len(answered) >= MAX_ITEMS:
        return None
    done = {it.block_id for it, _ in answered}
    remaining = [it for it in items if it.block_id not in done]
    if not remaining:
        return None
    by_domain: dict[str, list[tuple[Item, bool]]] = {d: [] for d in domain_ids(items)}
    for it, ok in answered:
        by_domain[it.domain].append((it, ok))
    open_domains = {it.domain for it in remaining}
    under = [d for d in by_domain if d in open_domains and len(by_domain[d]) < MIN_PER_DOMAIN]
    if under:
        low = min(len(by_domain[d]) for d in under)
        pool = {d for d in under if len(by_domain[d]) == low}
    else:
        unstable = set()
        for d in open_domains:
            ans = by_domain[d]
            theta_d = _estimate([i.b for i, _ in ans], [o for _, o in ans], dodd=True)
            if _se(ans, theta_d) > SE_STABLE:
                unstable.add(d)
        if not unstable:
            return None
        pool = unstable
    candidates = [it for it in remaining if it.domain in pool]
    if answered:
        last, last_ok = answered[-1]
        directed = [it for it in candidates if (it.b > last.b if last_ok else it.b < last.b)]
        if directed:
            candidates = directed
        else:
            # Nothing harder (easier) is left in these domains: serve the hardest (easiest) one.
            edge = max(it.b for it in candidates) if last_ok else min(it.b for it in candidates)
            candidates = [it for it in candidates if it.b == edge]
    theta = _running_theta(answered)
    from catsim import irt

    return max(candidates, key=lambda it: (irt.inf(theta, 1.0, it.b, 0.0, 1.0), -it.order))


def _score(theta: float) -> int:
    return int(round(100 * (theta - THETA_MIN) / (THETA_MAX - THETA_MIN)))


def _level(score: int) -> int:
    return min(5, 1 + score // 20)


def summarize(items: list[Item], responses: Sequence[tuple[str, bool]]) -> dict[str, Any]:
    """``{domains: [{id, level, score, items}], overall, weights}`` from first-try answers.

    score 0-100 maps the 1PL estimate from [-4, 4]; level 1-5 is score // 20 + 1. A domain
    with no answers scores 0. Weights: (101 - score) normalised to sum 1 (lower score =
    higher weight).
    """
    answered = _answered(items, responses)
    domains = []
    for d in domain_ids(items):
        ans = [(it, ok) for it, ok in answered if it.domain == d]
        score = _score(_estimate([i.b for i, _ in ans], [o for _, o in ans], dodd=False)) if ans else 0
        domains.append({"id": d, "level": _level(score), "score": score, "items": len(ans)})
    overall = (
        _score(_estimate([i.b for i, _ in answered], [o for _, o in answered], dodd=False)) if answered else 0
    )
    raw = {d["id"]: 101 - d["score"] for d in domains}
    total = sum(raw.values()) or 1
    weights = {k: round(v / total, 4) for k, v in raw.items()}
    if weights:
        top = max(weights, key=lambda k: weights[k])
        weights[top] = round(weights[top] + (1 - sum(weights.values())), 4)
    return {"domains": domains, "overall": overall, "weights": weights, "items": len(answered)}
