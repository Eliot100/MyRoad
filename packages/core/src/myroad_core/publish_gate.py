"""Publish gate run inside ``PathStore.publish`` (issue #42).

Publishing must be blocked by the same rules on every route, not only in the
path builder. This module does NOT define rules. It calls the existing checks
owned by Path Builder (``agent_builder/completeness.py``, #30/#32):

- format check: ``blocking_problems`` (the severity "error" subset of
  ``draft_problems``: step without body, ``correct`` not in choices / missing,
  topic pointing to missing steps);
- completeness rule: ``check_path_completeness`` (>=3 topics, >=12 stages,
  explanation+practice+check per topic, no pending topic).

Scope:
- Agent drafts (this version, or any version of the same path, carries
  ``agentBuild``): format check + completeness rule. Checking the whole path
  history stops an agent from dropping ``agentBuild`` in a revision to skip
  the rule.
- Other documents in the player/content node format (any block has
  ``content.kids``, e.g. the content-repo paths): format check only.
- Legacy freeze-format documents (no ``content.kids`` anywhere, e.g. the golden
  quadratic seed): not checked. ``draft_problems`` is defined over the
  ``kids`` node format and would flag every legacy block.

Layering note: the checks live in ``myroad_core.agent_builder`` (a higher
layer than the store). They are imported lazily here to avoid an import cycle
and to keep the store importable without the builder's generator stack. The
clean fix is to move the check functions into a shared module (see PR #42).
"""
from __future__ import annotations

import json
from typing import Any

from myroad_core.errors import StoreError
from myroad_core.models import PathVersion

__all__ = [
    "PUBLISH_FORMAT_ERROR",
    "PUBLISH_NOT_COMPLETE",
    "PublishBlockedError",
    "publish_block",
]

# Same codes as the builder (agent_builder.builder.PUBLISH_*); asserted equal in tests.
PUBLISH_FORMAT_ERROR = "PATH_FORMAT_ERROR"
PUBLISH_NOT_COMPLETE = "PATH_NOT_COMPLETE"


class PublishBlockedError(StoreError):
    """Raised by ``PathStore.publish`` when the gate refuses; nothing changed."""

    def __init__(self, errors: list[dict[str, Any]], data: dict[str, Any]) -> None:
        self.errors = errors
        self.data = data
        codes = ", ".join(e["code"] for e in errors)
        super().__init__("PUBLISH_BLOCKED", f"publish blocked: {codes}")


def _raw(doc: PathVersion | dict[str, Any]) -> dict[str, Any]:
    if isinstance(doc, PathVersion):
        return doc.model_dump(mode="json", by_alias=True)
    return doc


def _uses_node_format(raw: dict[str, Any]) -> bool:
    for block in raw.get("blocks") or []:
        content = (block or {}).get("content") or {}
        if isinstance(content.get("kids"), dict):
            return True
    return False


def _path_has_agent_build(conn: Any, path_id: str) -> bool:
    for row in conn.execute("SELECT document_json FROM versions WHERE path_id = ?", (path_id,)):
        try:
            if json.loads(row[0]).get("agentBuild"):
                return True
        except (TypeError, ValueError):
            continue
    return False


def publish_block(
    doc: PathVersion | dict[str, Any], *, conn: Any | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Return (errors, data) when publishing must be refused, else None.

    ``data`` has the same shape as the builder's refusal:
    ``blockingProblems`` (draft_problems items) and/or ``issues``
    (completeness issues).
    """
    raw = _raw(doc)
    agent_draft = bool(raw.get("agentBuild")) or (
        conn is not None and bool(raw.get("pathId")) and _path_has_agent_build(conn, raw["pathId"])
    )
    if not agent_draft and not _uses_node_format(raw):
        return None

    # Lazy import: Path Builder owns these rules (see module docstring).
    from myroad_core.agent_builder.completeness import blocking_problems, check_path_completeness

    errors: list[dict[str, Any]] = []
    data: dict[str, Any] = {}
    blockers = blocking_problems(raw)
    if blockers:
        errors.append(
            {
                "code": PUBLISH_FORMAT_ERROR,
                "message": "path has format errors that block publishing",
                "count": len(blockers),
            }
        )
        data["blockingProblems"] = [p.as_dict() for p in blockers]
    if agent_draft:
        report = check_path_completeness(raw)
        if not report.complete:
            errors.append(
                {"code": PUBLISH_NOT_COMPLETE, "message": "path does not meet the completeness rule"}
            )
            data["issues"] = report.issues
    return (errors, data) if errors else None
