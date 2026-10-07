"""Defensive JSON parsing for model replies (code fences, prose, trailing commas)."""
from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.S)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


class ReplyParseError(ValueError):
    """The reply was not usable JSON for the expected model. Message is readable."""


def strip_code_fences(text: str) -> str:
    raw = (text or "").strip()
    match = _FENCE_RE.search(raw)
    if match:
        return match.group(1).strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    return raw.strip()


def _outer_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def extract_json_object(text: str) -> dict[str, Any]:
    """Return the first top-level JSON object found in a model reply."""
    cleaned = strip_code_fences(text)
    if not cleaned:
        raise ReplyParseError("the model returned an empty reply")
    candidates = [cleaned]
    outer = _outer_object(cleaned)
    if outer and outer != cleaned:
        candidates.append(outer)
    last_error = "no JSON object found"
    for cand in candidates:
        for attempt in (cand, _TRAILING_COMMA_RE.sub(r"\1", cand)):
            try:
                data = json.loads(attempt)
            except json.JSONDecodeError as exc:
                last_error = f"invalid JSON ({exc.msg} at line {exc.lineno})"
                continue
            if isinstance(data, dict):
                return data
            last_error = "the reply is JSON but not an object"
    raise ReplyParseError(last_error)


def _short_validation(exc: ValidationError, limit: int = 4) -> str:
    parts: list[str] = []
    for err in exc.errors()[:limit]:
        loc = ".".join(str(x) for x in err.get("loc") or ()) or "root"
        msg = str(err.get("msg") or "invalid")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        parts.append(f"{loc}: {msg}")
    more = len(exc.errors()) - limit
    if more > 0:
        parts.append(f"(+{more} more)")
    return "; ".join(parts)


def parse_reply(text: str, model: type[T]) -> T:
    """Parse and validate a reply. Raises ReplyParseError with a short, readable reason."""
    data = extract_json_object(text)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ReplyParseError(_short_validation(exc)) from None
