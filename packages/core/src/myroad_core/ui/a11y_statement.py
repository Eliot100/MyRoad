"""Accessibility statement page (#60): what is true of MyRoad today, plus real-world details.

The statement follows Israeli regulation 35E (accessibility of service, 2013): the
accessibility measures taken, the accessibility coordinator and how to reach them,
and a way to report a problem or ask for an accessible alternative. Its sections follow
the W3C WAI statement format (standard and status, measures, known limitations,
assessment approach, feedback, dates). The text lives in ``locales/*.json`` (``a11y_*``).

Real-world details we cannot know (coordinator, phone, email, dates of review) come
from the environment. Unset ones render as a clearly marked placeholder naming the
variable, so they are easy to spot and fill in; nothing here is ever made up.

    MYROAD_A11Y_ORG_NAME           operator of the service (legal name)
    MYROAD_A11Y_COORDINATOR_NAME   accessibility coordinator
    MYROAD_A11Y_PHONE              coordinator phone
    MYROAD_A11Y_EMAIL              coordinator email
    MYROAD_A11Y_STATEMENT_DATE     date this statement was last updated
    MYROAD_A11Y_AUDIT_DATE         date of the last accessibility review/audit
    MYROAD_A11Y_ADDRESS            postal address (optional: hidden when unset)

When the product changes, update the ``DONE`` / ``GAPS`` keys and their strings.
"""
from __future__ import annotations

import os
import re
from typing import Any, Mapping

# (context key, env var, label key) — shown as a placeholder when unset.
REQUIRED_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("org", "MYROAD_A11Y_ORG_NAME", "a11y_operator"),
    ("coordinator", "MYROAD_A11Y_COORDINATOR_NAME", "a11y_coordinator"),
    ("phone", "MYROAD_A11Y_PHONE", "a11y_phone"),
    ("email", "MYROAD_A11Y_EMAIL", "a11y_email"),
    ("updated", "MYROAD_A11Y_STATEMENT_DATE", "a11y_updated"),
    ("reviewed", "MYROAD_A11Y_AUDIT_DATE", "a11y_reviewed"),
)
# Shown only when set.
OPTIONAL_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("address", "MYROAD_A11Y_ADDRESS", "a11y_address"),
)

# What has been done, in the product as it is now (keys in locales/*.json).
DONE: tuple[str, ...] = (
    "a11y_done_lang",
    "a11y_done_mixed",
    "a11y_done_math",
    "a11y_done_answer",
    "a11y_done_nojs",
    "a11y_done_focus",
    "a11y_done_map",
    "a11y_done_motion",
    "a11y_done_mobile",
    "a11y_done_forms",
    "a11y_done_speak",
    "a11y_done_overlay",
)
# Known gaps, true today.
GAPS: tuple[str, ...] = (
    "a11y_gap_audit",
    "a11y_gap_ci",
    "a11y_gap_sr",
    "a11y_gap_skip",
    "a11y_gap_builder",
    "a11y_gap_math",
    "a11y_gap_lang",
    "a11y_gap_speak",
)

_EMAIL = re.compile(r"[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+")
_PHONE_CHARS = re.compile(r"[^0-9+]")


def _field(key: str, env_name: str, label: str, env: Mapping[str, str]) -> dict[str, Any]:
    value = (env.get(env_name) or "").strip()[:200]
    href = ""
    if value and key == "email" and _EMAIL.fullmatch(value):
        href = "mailto:" + value
    elif value and key == "phone":
        digits = _PHONE_CHARS.sub("", value)
        if len(digits.lstrip("+")) >= 3:
            href = "tel:" + digits
    return {"key": key, "env": env_name, "label": label, "value": value, "href": href}


def statement_details(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Context for ``accessibility.html``; reads the environment on every call."""
    env = os.environ if env is None else env
    fields = {k: _field(k, name, label, env) for k, name, label in REQUIRED_FIELDS}
    for k, name, label in OPTIONAL_FIELDS:
        f = _field(k, name, label, env)
        if f["value"]:
            fields[k] = f
    return {
        "fields": fields,
        "contact": [fields[k] for k in ("coordinator", "phone", "email", "address") if k in fields],
        "missing": [f["env"] for f in fields.values() if not f["value"]],
        "done": DONE,
        "gaps": GAPS,
    }
