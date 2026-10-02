"""Simple answer checking for practice / assessment / experience blocks."""
from __future__ import annotations

import ast
import json
import re
from typing import Any


def _normalize_token(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    text = str(value).strip()
    lower = text.lower()
    # Hebrew / English yes-no and true-false
    if lower in {"true", "yes", "כן", "נכון", "אמת"}:
        return "true"
    if lower in {"false", "no", "לא", "שגוי"}:
        return "false"
    # numeric-ish
    try:
        num = float(text.replace(",", ""))
        if num.is_integer():
            return str(int(num))
        return str(num)
    except ValueError:
        pass
    return re.sub(r"\s+", " ", lower)


def _parse_user_list(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw:
        return []
    # Try JSON / Python literal first
    for candidate in (raw, raw.replace(";", ",")):
        try:
            parsed = ast.literal_eval(candidate)
            if isinstance(parsed, (list, tuple, set)):
                return [_normalize_token(x) for x in parsed]
        except (ValueError, SyntaxError):
            pass
    parts = re.split(r"[,;\s]+", raw)
    return [_normalize_token(p) for p in parts if p.strip()]


def answers_match(expected: Any, given: Any) -> bool:
    """Loose equality for POC: scalars, lists (order-insensitive), small dicts."""
    if isinstance(expected, dict):
        if isinstance(given, str):
            try:
                given = json.loads(given)
            except json.JSONDecodeError:
                # allow "6,8" style for width/length dicts with 2 numeric values
                nums = _parse_user_list(given)
                vals = [_normalize_token(v) for v in expected.values()]
                return sorted(nums) == sorted(vals)
        if not isinstance(given, dict):
            return False
        if set(expected.keys()) != set(given.keys()):
            # still allow value-only match
            return sorted(_normalize_token(v) for v in expected.values()) == sorted(
                _normalize_token(v) for v in given.values()
            )
        return all(answers_match(expected[k], given[k]) for k in expected)

    if isinstance(expected, (list, tuple)):
        exp = [_normalize_token(x) for x in expected]
        if isinstance(given, str):
            got = _parse_user_list(given)
        elif isinstance(given, (list, tuple)):
            got = [_normalize_token(x) for x in given]
        else:
            got = [_normalize_token(given)]
        return sorted(exp) == sorted(got)

    return _normalize_token(expected) == _normalize_token(given)


def grade_items(
    items: list[dict[str, Any]],
    submissions: dict[str, str],
) -> tuple[int, int, list[dict[str, Any]]]:
    """Grade practice/assessment items. Returns (correct, total, details)."""
    details: list[dict[str, Any]] = []
    correct = 0
    for item in items:
        item_id = item.get("itemId") or item.get("id") or ""
        expected = item.get("answer")
        given = submissions.get(item_id, "")
        ok = answers_match(expected, given)
        if ok:
            correct += 1
        details.append(
            {
                "itemId": item_id,
                "ok": ok,
                "prompt": item.get("prompt"),
                "given": given,
                "expected": expected,
                "solution": item.get("solution") or item.get("rubric"),
            }
        )
    return correct, len(items), details


def mastery_passed(mastery_rule: dict[str, Any] | None, correct: int, total: int) -> bool:
    if not mastery_rule:
        return correct == total and total > 0
    min_correct = mastery_rule.get("minCorrect")
    if min_correct is not None:
        return correct >= int(min_correct)
    # fall back to all correct
    return total > 0 and correct == total
