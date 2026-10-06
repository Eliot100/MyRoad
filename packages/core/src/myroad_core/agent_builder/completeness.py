"""Completeness rule for agent-built paths.

A path is complete when it has at least MIN_TOPICS topics, at least MIN_STAGES
stages, every topic includes explanation, practice, and check stages, and no
outline topic is still waiting to be filled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from myroad_core.agent_builder.models import MIN_STAGES, MIN_TOPICS, REQUIRED_STAGE_TYPES
from myroad_core.models import PathVersion

_BLOCK_TO_STAGE = {
    "explanation": "explanation",
    "practice": "practice",
    "assessment": "check",
    "experience": "experience",
}


@dataclass
class CompletenessReport:
    complete: bool
    topic_count: int
    stage_count: int
    issues: list[dict[str, Any]] = field(default_factory=list)


def _as_dict(doc: PathVersion | dict[str, Any]) -> dict[str, Any]:
    if isinstance(doc, PathVersion):
        return doc.model_dump(mode="json", by_alias=True)
    return doc


def check_path_completeness(doc: PathVersion | dict[str, Any]) -> CompletenessReport:
    raw = _as_dict(doc)
    blocks = raw.get("blocks") or []
    by_id = {b.get("blockId"): b for b in blocks}
    node_to_block = raw.get("nodeToBlock") or {}
    topics = raw.get("topics") or []
    issues: list[dict[str, Any]] = []

    stage_count = 0
    for topic in topics:
        types: set[str] = set()
        for nid in topic.get("node_ids") or []:
            block = by_id.get(node_to_block.get(nid))
            if block is None:
                continue
            stage_count += 1
            content = block.get("content") or {}
            stage_type = content.get("stageType") or _BLOCK_TO_STAGE.get(str(block.get("type")))
            if stage_type:
                types.add(stage_type)
        missing = [x for x in REQUIRED_STAGE_TYPES if x not in types]
        if missing:
            titles = topic.get("titles") or {}
            label = next((v for v in titles.values() if v), None) or topic.get("id") or "?"
            issues.append({"code": "topic_missing_types", "topic": label, "types": missing})

    if len(topics) < MIN_TOPICS:
        issues.insert(0, {"code": "min_topics", "need": MIN_TOPICS, "got": len(topics)})
    if stage_count < MIN_STAGES:
        issues.insert(0, {"code": "min_stages", "need": MIN_STAGES, "got": stage_count})

    build = raw.get("agentBuild") or {}
    statuses = build.get("topicStatus") or []
    pending = [i + 1 for i, s in enumerate(statuses) if (s or {}).get("status") != "done"]
    if pending:
        issues.append({"code": "topics_pending", "topics": pending})

    return CompletenessReport(
        complete=not issues,
        topic_count=len(topics),
        stage_count=stage_count,
        issues=issues,
    )
