"""Starting level 1-5 from a placement score. One rule for every subject.

Item bands are five equal slices of the 1PL difficulty line [-4, 4]. A 5-unit
placement keeps at least two scored items in each band, so the score is not a
guess from three or four questions.

The starting level is the percent of first-try answers, not a short list of
wrong-count buckets:

  1: [0, 20)
  2: [20, 40)
  3: [40, 60)
  4: [60, 80)
  5: [80, 100]

20, 40, 60 and 80 are ties between two levels. The hardest answered item
breaks the tie: a correct answer takes the higher level, a miss takes the
lower one. With no item to judge, the lower level wins. A finished placement
with no scored answers and no mistakes stays at 5 (nothing was marked wrong).
"""

from __future__ import annotations

from typing import Any, Sequence

EDGES: tuple[int, ...] = (20, 40, 60, 80)
# Width of one band on [-4, 4]. Band 5 starts at 2.4 and includes 4.
_SLICE = 1.6
_BAND5 = 2.4


def item_band(difficulty: float) -> int:
    """Band 1-5 for a difficulty in [-4, 4]."""
    x = max(-4.0, min(4.0, float(difficulty)))
    if x >= _BAND5:
        return 5
    return 1 + int((x + 4.0) / _SLICE)


def level_from_counts(correct: int, incorrect: int, *, tie_up: bool | None = None) -> int:
    """Starting level 1-5. ``tie_up`` is only read on an exact edge."""
    correct_n = max(0, int(correct))
    incorrect_n = max(0, int(incorrect))
    total = correct_n + incorrect_n
    if total <= 0:
        return 5
    level = 1
    for index, edge in enumerate(EDGES, start=2):
        lhs = correct_n * 100
        rhs = edge * total
        if lhs > rhs:
            level = index
        elif lhs == rhs:
            return index if tie_up else index - 1
        else:
            break
    return level


def tie_up_from_answers(items: Sequence[Any], answers: Sequence[tuple[str, bool]]) -> bool | None:
    """True when the hardest answered item was correct. None when none matched.

    Hardest means the highest difficulty, then the later content order.
    """
    ranked: dict[str, tuple[float, int]] = {}
    for it in items:
        if isinstance(it, dict):
            bid = it.get("block_id") or it.get("id")
            diff = it.get("b", it.get("difficulty"))
            order = it.get("order", 0)
        else:
            bid = getattr(it, "block_id", None) or getattr(it, "id", None)
            diff = getattr(it, "b", None)
            if diff is None:
                diff = getattr(it, "difficulty", None)
            order = getattr(it, "order", 0)
        if bid is not None and diff is not None:
            ranked[str(bid)] = (float(diff), int(order or 0))
    best: tuple[float, int] | None = None
    best_ok: bool | None = None
    for bid, ok in answers:
        key = ranked.get(str(bid))
        if key is None:
            continue
        if best is None or key > best:
            best = key
            best_ok = bool(ok)
    if best is None:
        return None
    return best_ok


def band_counts(nodes: Sequence[Any]) -> dict[int, int]:
    """Scored base items per band. Variants are the same item, counted once."""
    counts = {band: 0 for band in range(1, 6)}
    for node in nodes:
        get = node.get if isinstance(node, dict) else lambda key, _n=node: getattr(_n, key, None)
        if get("type") not in ("practice", "check") or not get("choices") or get("variant_of"):
            continue
        diff = get("difficulty")
        if diff is None:
            continue
        counts[item_band(float(diff))] += 1
    return counts


def placement_band_gaps(path_id: str, nodes: Sequence[Any]) -> list[str]:
    """Empty when a 5-unit placement has two scored items in every band."""
    if "_bagrut5_" not in path_id or not str(path_id).endswith("_placement"):
        return []
    scored = []
    for node in nodes:
        get = node.get if isinstance(node, dict) else lambda key, _n=node: getattr(_n, key, None)
        if get("type") in ("practice", "check") and get("choices") and not get("variant_of"):
            scored.append(node)
    missing_diff = []
    for node in scored:
        get = node.get if isinstance(node, dict) else lambda key, _n=node: getattr(_n, key, None)
        if get("difficulty") is None:
            missing_diff.append(str(get("id") or get("title") or "?"))
    if missing_diff:
        return [f"{path_id}: placement items without difficulty: {missing_diff}"]
    counts = band_counts(nodes)
    short = [band for band, count in counts.items() if count < 2]
    if short:
        return [f"{path_id}: need at least 2 items in each band 1-5, short {short}, counts {counts}"]
    return []
