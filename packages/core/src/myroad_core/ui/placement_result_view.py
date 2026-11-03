"""Placement result inside the first step of the recommended road (#212, #200; decision 0013).

Pure view helper: turns the stored adaptive placement detail (#211: ``domains``, ``overall``,
``weights``) into what ``_placement_result.html`` shows. No store writes, no route logic.
Missing or partial fields never raise: invalid domain rows are skipped, scores are clamped,
and a result with no usable domain returns ``None`` so the template keeps the plain hint.
"""

from __future__ import annotations

from typing import Any, Mapping

LEVELS = 5


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def placement_result_view(
    detail: Mapping[str, Any] | None,
    labels: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    """``{domains: [{id, label, level, score}], overall, gaps: [{id, label}]}`` or ``None``.

    level is 1-5 (from the API, else score // 20 + 1); score 0-100. ``gaps`` are the domains
    the weights point at most: weight above an even share, highest first, at most 3. With one
    domain or even weights there is no gap to name.
    """
    if not isinstance(detail, Mapping):
        return None
    labels = labels or {}
    rows = []
    for d in detail.get("domains") or []:
        if not isinstance(d, Mapping) or not d.get("id"):
            continue
        score = _num(d.get("score"))
        if score is None:
            continue
        score = int(round(min(max(score, 0), 100)))
        level = _num(d.get("level"))
        level = int(min(max(level, 1), LEVELS)) if level is not None else min(score // 20 + 1, LEVELS)
        did = str(d["id"])
        rows.append({"id": did, "label": labels.get(did) or did.removeprefix("t_").replace("_", " "),
                     "level": level, "score": score})
    if not rows:
        return None
    overall = _num(detail.get("overall"))
    overall = int(round(min(max(overall, 0), 100))) if overall is not None else None
    weights = detail.get("weights") if isinstance(detail.get("weights"), Mapping) else {}
    w = {r["id"]: _num(weights.get(r["id"])) for r in rows}
    gaps: list[dict[str, Any]] = []
    if len(rows) > 1:
        share = 1 / len(rows)
        if all(v is not None for v in w.values()):
            ranked = sorted(rows, key=lambda r: -w[r["id"]])
            gaps = [r for r in ranked if w[r["id"]] > share + 1e-9][:3]
        else:  # no weights: lower score = more practice, same rule as the API
            ranked = sorted(rows, key=lambda r: r["score"])
            gaps = [r for r in ranked if r["score"] < ranked[-1]["score"]][:3]
    return {"domains": rows, "overall": overall, "gaps": [{"id": g["id"], "label": g["label"]} for g in gaps]}


def domain_labels(topics: list[Mapping[str, Any]] | None, locale: str) -> dict[str, str]:
    """Domain id -> the placement topic title in the UI locale (he fallback)."""
    out: dict[str, str] = {}
    for tp in topics or []:
        tid = tp.get("id")
        if not tid:
            continue
        titles = tp.get("titles") or {}
        title = titles.get(locale) or tp.get(f"title_{locale}") or titles.get("he") or tp.get("title_he") or tp.get("title")
        if title:
            out[str(tid)] = str(title)
    return out
