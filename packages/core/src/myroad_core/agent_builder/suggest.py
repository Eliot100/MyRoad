"""Find existing published paths that match a learner's goal (before building a new one).

Deterministic and cheap: no model call. The goal text is matched against each
published path's titles, blurbs, subject, audience groups and topic titles, in
every locale the path has (Hebrew, English, Arabic). A match that requires other
paths (schema v2 ``prerequisite_path_ids``) brings those paths along, and the
ones the learner has not completed yet are listed.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from myroad_core.content.schema import GROUPS, SUBJECTS

MAX_MATCHES = 3
MIN_SCORE = 2.0
# Keep matches that score at least this share of the best match.
RELATIVE_CUTOFF = 0.5

# Weight of a goal term found in each kind of field (best field counts once per term).
FIELD_WEIGHTS: dict[str, float] = {
    "title": 3.0,
    "subject": 2.0,
    "group": 1.5,
    "blurb": 1.5,
    "topic": 1.0,
}
SUBJECT_BONUS = 1.0
AUDIENCE_BONUS = 1.0

_STOPWORDS = frozenset(
    """
    a an the and or of to from for in on at by with about into up is are be am i me my we our you
    want would like need learn learning study studying teach teaching how what course path paths
    please some start starting begin beginner beginners new
    של את עם על אני אנחנו רוצה רוצים צריך ללמוד לימוד למידה איך מה עד גם או זה זו זאת אל מן כל
    דרך דרכים קורס בבקשה להתחיל
    في من الى إلى على عن مع أريد اريد تعلم أتعلم كيف ما هذا هذه
    """.split()
)
_HEB_PREFIXES = frozenset("ובכלמשה")
_NIQQUD = re.compile(r"[\u0591-\u05C7]")
_TOKEN = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", str(text or "")).lower()
    text = _NIQQUD.sub("", text).replace("׳", "").replace("״", "").replace("'", "").replace('"', "")
    out = []
    for tok in _TOKEN.findall(text):
        tok = tok.strip("_")
        if not tok or (len(tok) < 2 and not tok.isdigit()):
            continue
        out.append(tok)
    return out


def _variants(tok: str) -> set[str]:
    """Light, language-agnostic normalisation: Hebrew one/two-letter prefixes, English plural s."""
    forms = {tok}
    if tok.isascii():
        if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
            forms.add(tok[:-1])
    elif "\u0590" <= tok[0] <= "\u05FF":
        for k in (1, 2):
            if len(tok) - k >= 3 and all(ch in _HEB_PREFIXES for ch in tok[:k]):
                forms.add(tok[k:])
    return forms


def goal_terms(goal: str) -> list[str]:
    """Distinct, meaningful terms of the goal text, in order."""
    return list(dict.fromkeys(t for t in _tokens(goal) if t not in _STOPWORDS))


@dataclass
class PathEntry:
    """A published path prepared for matching."""

    path_id: str
    version_id: str
    title: str
    subject: str
    group_ids: list[str]
    prerequisite_path_ids: list[str]
    card: dict[str, Any]
    fields: dict[str, set[str]] = field(default_factory=dict)


def _field_forms(texts: list[str]) -> set[str]:
    forms: set[str] = set()
    for text in texts:
        for tok in _tokens(text):
            forms |= _variants(tok)
    return forms


def _locale_values(*maps: Any) -> list[str]:
    out: list[str] = []
    for m in maps:
        if isinstance(m, dict):
            out.extend(str(v) for v in m.values() if v)
        elif isinstance(m, str) and m:
            out.append(m)
    return out


def make_entry(card: dict[str, Any], doc: dict[str, Any], prerequisites: list[str] | None = None) -> PathEntry:
    subject = str(doc.get("subject") or card.get("subject") or "general")
    groups = list(doc.get("groupIds") or card.get("groupIds") or [])
    subject_meta = SUBJECTS.get(subject, {})
    topics = doc.get("topics") or []
    topic_texts: list[str] = []
    for t in topics:
        topic_texts.extend(_locale_values(t.get("titles"), t.get("title_he"), t.get("title_en"), t.get("title_ar")))
    fields = {
        "title": _field_forms(
            _locale_values(doc.get("titles"), card.get("titles"), doc.get("name"), doc.get("titleEn"))
        ),
        "subject": _field_forms([subject] + _locale_values({k: v for k, v in subject_meta.items() if k != "color"})),
        "group": _field_forms(
            [g for g in groups]
            + [txt for g in groups for txt in _locale_values((GROUPS.get(g) or {}).get("titles"))]
        ),
        "blurb": _field_forms(
            _locale_values(doc.get("blurbs"), card.get("blurbs"), doc.get("description"), doc.get("blurbHe"))
        ),
        "topic": _field_forms(topic_texts),
    }
    prereqs = list(
        prerequisites
        if prerequisites is not None
        else (doc.get("prerequisitePathIds") or doc.get("prerequisite_path_ids") or [])
    )
    return PathEntry(
        path_id=str(card.get("pathId") or doc.get("pathId")),
        version_id=str(card.get("versionId") or doc.get("versionId") or ""),
        title=str(card.get("title") or doc.get("name") or card.get("pathId")),
        subject=subject,
        group_ids=groups,
        prerequisite_path_ids=[p for p in prereqs if isinstance(p, str) and p],
        card=card,
        fields=fields,
    )


def _score(entry: PathEntry, terms: list[str]) -> tuple[float, list[str], list[str]]:
    total = 0.0
    matched: list[str] = []
    where: list[str] = []
    has_word = False
    for term in terms:
        forms = _variants(term)
        best = None
        for name, weight in FIELD_WEIGHTS.items():
            if forms & entry.fields.get(name, set()):
                if best is None or weight > FIELD_WEIGHTS[best]:
                    best = name
        if best is None:
            continue
        total += FIELD_WEIGHTS[best]
        matched.append(term)
        if best not in where:
            where.append(best)
        if not term.isdigit():
            has_word = True
    if not has_word:  # numbers alone ("3") never make a match
        return 0.0, [], []
    return total, matched, where


def rank_existing(
    goal: str,
    entries: list[PathEntry],
    *,
    subject: str | None = None,
    audience: str | None = None,
    completed: set[str] | None = None,
    limit: int = MAX_MATCHES,
) -> list[dict[str, Any]]:
    """Up to ``limit`` matches, best first, each followed by the paths it still requires.

    Each item: pathId, versionId, title, score, reason {code, terms, fields,
    required_by}, prerequisites [{pathId, title, done, available}],
    missing_prerequisites [pathId], card.
    """
    completed = set(completed or ())
    terms = goal_terms(goal)
    by_id = {e.path_id: e for e in entries}
    scored: list[tuple[float, int, PathEntry, list[str], list[str]]] = []
    for idx, entry in enumerate(entries):
        score, matched, where = _score(entry, terms)
        if score <= 0:
            continue
        if subject and subject != "general" and entry.subject == subject:
            score += SUBJECT_BONUS
        if audience and audience in entry.group_ids:
            score += AUDIENCE_BONUS
        scored.append((score, idx, entry, matched, where))
    if not scored:
        return []
    # Best first; on a tie, the path with fewer prerequisites first; then catalog order.
    scored.sort(key=lambda s: (-s[0], len(s[2].prerequisite_path_ids), s[1]))
    best = scored[0][0]
    direct = [s for s in scored if s[0] >= MIN_SCORE and s[0] >= RELATIVE_CUTOFF * best]

    def prereq_rows(entry: PathEntry) -> list[dict[str, Any]]:
        rows = []
        for pid in entry.prerequisite_path_ids:
            pre = by_id.get(pid)
            rows.append(
                {
                    "pathId": pid,
                    "title": pre.title if pre else pid,
                    "done": pid in completed,
                    "available": pre is not None,
                }
            )
        return rows

    def item(entry: PathEntry, score: float, reason: dict[str, Any]) -> dict[str, Any]:
        rows = prereq_rows(entry)
        return {
            "pathId": entry.path_id,
            "versionId": entry.version_id,
            "title": entry.title,
            "score": round(score, 2),
            "reason": reason,
            "prerequisites": rows,
            "missing_prerequisites": [r["pathId"] for r in rows if not r["done"]],
            "card": entry.card,
        }

    direct_by_id = {s[2].path_id: s for s in scored}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for score, _idx, entry, matched, where in direct:
        if len(out) >= limit:
            break
        if entry.path_id in seen:
            continue
        seen.add(entry.path_id)
        out.append(item(entry, score, {"code": "goal_match", "terms": matched, "fields": where, "required_by": None}))
        # Surface what this path requires (and the learner has not completed) right after it.
        for pid in entry.prerequisite_path_ids:
            pre = by_id.get(pid)
            if len(out) >= limit or pre is None or pid in seen or pid in completed:
                continue
            seen.add(pid)
            hit = direct_by_id.get(pid)
            if hit:  # it also matches the goal on its own: keep that reason, note the link
                reason = {"code": "goal_match", "terms": hit[3], "fields": hit[4], "required_by": entry.path_id}
                out.append(item(pre, hit[0], reason))
            else:
                reason = {"code": "required_by", "terms": [], "fields": [], "required_by": entry.path_id}
                out.append(item(pre, 0.0, reason))
    return out


# --- prerequisites declared in content files (the store copy may not carry them) ---

_CONTENT_CACHE: dict[str, tuple[tuple[tuple[str, float], ...], dict[str, list[str]]]] = {}


def content_prerequisites(content_dir: Path | None = None) -> dict[str, list[str]]:
    """{path id: prerequisite_path_ids} read from the content JSON files (cached by mtime)."""
    if content_dir is None:
        from myroad_core.content.loader import default_content_dir

        content_dir = default_content_dir()
    root = Path(content_dir)
    if not root.is_dir():
        return {}
    files = sorted(root.rglob("*.json"))
    stamp = tuple((str(f), f.stat().st_mtime) for f in files)
    cached = _CONTENT_CACHE.get(str(root))
    if cached and cached[0] == stamp:
        return cached[1]
    out: dict[str, list[str]] = {}
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and isinstance(data.get("id"), str):
            pre = data.get("prerequisite_path_ids") or []
            if isinstance(pre, list):
                out[data["id"]] = [p for p in pre if isinstance(p, str)]
    _CONTENT_CACHE[str(root)] = (stamp, out)
    return out


def catalog_entries(store, *, locale: str | None = None, content_dir: Path | None = None) -> list[PathEntry]:
    """Every published catalog path as a PathEntry (titles localized for display)."""
    from myroad_core.content.loader import list_catalog_cards

    file_prereqs = content_prerequisites(content_dir)
    entries: list[PathEntry] = []
    for card in list_catalog_cards(store, locale=locale):
        if card.get("status") != "published":
            continue
        try:
            doc = store.get_version(card["pathId"], card["versionId"]).model_dump(mode="json", by_alias=True)
        except Exception:  # a broken row must not break the builder
            doc = {}
        prereqs = doc.get("prerequisitePathIds") or doc.get("prerequisite_path_ids")
        if not prereqs:
            prereqs = file_prereqs.get(card["pathId"], [])
        entries.append(make_entry(card, doc, list(prereqs)))
    return entries


def completed_path_ids(store, user_id: str | None) -> set[str]:
    if not user_id or not hasattr(store, "list_user_progress"):
        return set()
    try:
        rows = store.list_user_progress(user_id)
    except Exception:
        return set()
    return {r["pathId"] for r in rows if r.get("progressStatus") == "completed" or r.get("completedAt")}
