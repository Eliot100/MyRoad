"""Completeness rule and live draft problems for agent-built paths.

A path is complete when it has at least MIN_TOPICS topics, at least MIN_STAGES
stages, every topic includes explanation, practice, and check stages, and no
outline topic is still waiting to be filled.

``draft_problems`` lists concrete content problems (missing fields, bad nodes,
broken topic references) at every builder step, so they show before saving.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from myroad_core.agent_builder.models import MIN_STAGES, MIN_TOPICS, REQUIRED_STAGE_TYPES, STAGE_TYPES
from myroad_core.content.schema import ContentChoice, ContentNode, ContentPath
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


# ---------------------------------------------------------------------------
# Live draft problems (shown at every builder step, before save/publish).
#
# The rules live in content/schema.py (ContentPath / ContentNode / ContentTopic).
# To keep one source of truth, each check validates a known-good probe document
# with the schema model and swaps in ONE value from the draft. If the schema then
# rejects the probe, that value is the problem. This also lets several problems on
# the same node be reported at once (the schema itself stops at the first one).
#
# Agent drafts are exempt from the 1-60 estimated_minutes limit (it belongs to the
# sample content files only), so the probe always uses a placeholder for minutes
# and never looks at the draft's estimatedMinutes.
# ---------------------------------------------------------------------------

PROBLEM_KEY_PREFIX = "draft_problem_"
PROBLEM_CODES: tuple[str, ...] = (
    "missing_title_he",
    "missing_blurb_he",
    "missing_emoji",
    "bad_subject",
    "no_nodes",
    "node_missing_body",
    "node_correct_missing",
    "node_correct_not_in_choices",
    "node_invalid",
    "unknown_step_type",
    "topic_unknown_nodes",
    "topic_no_nodes",
)

# Format errors that block publishing (product rule). Everything else, and the
# completeness rule above, stays as it is today. Saving a draft is never blocked.
BLOCKING_CODES: frozenset[str] = frozenset(
    {
        "node_missing_body",
        "node_correct_not_in_choices",
        # Emitted only for practice/check nodes WITH choices and no correct id:
        # the same format error as a correct id that is not a choice.
        "node_correct_missing",
        "topic_unknown_nodes",
    }
)
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

_PROBE_TEXT = "x"
_PROBE_NODE: dict[str, Any] = {"type": "learn", "title": _PROBE_TEXT, "body_he": _PROBE_TEXT}
_NODE_FIELDS = tuple(ContentNode.model_fields)
_CHOICE_FIELDS = tuple(ContentChoice.model_fields)


def _probe_path(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "path_live_check_probe",
        "titles": {"he": _PROBE_TEXT},
        "blurbs": {"he": _PROBE_TEXT},
        "subject": "general",
        "group_ids": [],
        "emoji": _PROBE_TEXT,
        # Placeholder on purpose: agent drafts are exempt from the minutes limit.
        "estimated_minutes": 1,
        "nodes": [dict(_PROBE_NODE)],
    }
    base.update(overrides)
    return base


def _rejects(model: type[BaseModel], data: dict[str, Any]) -> bool:
    try:
        model.model_validate(data)
    except ValidationError:
        return True
    return False


@dataclass
class DraftProblem:
    """One concrete problem in an agent draft, structured for per-step rendering."""

    code: str
    field: str
    node_id: str | None = None
    topic_id: str | None = None
    topic_index: int | None = None
    block_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def message_key(self) -> str:
        return PROBLEM_KEY_PREFIX + self.code

    @property
    def severity(self) -> str:
        """Severity: "error" blocks publishing, "warning" is shown only."""
        return SEVERITY_ERROR if self.code in BLOCKING_CODES else SEVERITY_WARNING

    @property
    def blocking(self) -> bool:
        return self.severity == SEVERITY_ERROR

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message_key": self.message_key,
            "severity": self.severity,
            "field": self.field,
            "node_id": self.node_id,
            "topic_id": self.topic_id,
            "topic_index": self.topic_index,
            "block_id": self.block_id,
            "params": dict(self.params),
        }


def _nodes_of(raw: dict[str, Any]) -> list[tuple[str | None, str | None, dict[str, Any], dict[str, Any]]]:
    """(node_id, block_id, kids, content) for every block in the draft."""
    out = []
    for i, block in enumerate(raw.get("blocks") or []):
        content = block.get("content") or {}
        kids = content.get("kids")
        kids = kids if isinstance(kids, dict) else {}
        nid = kids.get("id") or content.get("nodeId") or f"n{i:03d}"
        out.append((nid, block.get("blockId"), kids, content))
    return out


def _node_problems(nid: str | None, kids: dict[str, Any], content: dict[str, Any]) -> list[DraftProblem]:
    title = kids.get("title") or nid or "?"
    problems: list[DraftProblem] = []

    def add(code: str, fld: str, **params: Any) -> None:
        problems.append(DraftProblem(code=code, field=fld, node_id=nid, params={"title": title, **params}))

    # Step type: the player's node type (schema NodeType) and the agent stage type.
    node_type = kids.get("type")
    type_ok = not _rejects(ContentNode, {**_PROBE_NODE, "type": node_type})
    if not type_ok:
        add("unknown_step_type", "type", type=str(node_type))
    stage_type = content.get("stageType")
    if stage_type is not None and stage_type not in STAGE_TYPES:
        add("unknown_step_type", "stageType", type=str(stage_type))

    # Explanation body: schema needs body_he, body_en, or body_ui.
    body = {k: kids.get(k) for k in ("body_en", "body_ui") if kids.get(k) is not None}
    body["body_he"] = kids.get("body_he") or ""
    probe = {k: v for k, v in _PROBE_NODE.items() if k != "body_he"}
    if _rejects(ContentNode, {**probe, **body}):
        add("node_missing_body", "body_ui")

    # Choices: schema rules for practice/check (correct must point at a choice id).
    choices = kids.get("choices")
    if type_ok and node_type in ("practice", "check") and choices:
        sliced = [
            {k: c.get(k) for k in _CHOICE_FIELDS if c.get(k) is not None} if isinstance(c, dict) else c
            for c in choices
        ]
        data = {**_PROBE_NODE, "type": node_type, "choices": sliced, "correct": kids.get("correct")}
        if _rejects(ContentNode, data):
            if any(_rejects(ContentChoice, c) if isinstance(c, dict) else True for c in sliced):
                add("node_invalid", "choices")
            elif kids.get("correct") in (None, "", []):
                add("node_correct_missing", "correct")
            else:
                ids = [c.get("id") for c in sliced]
                add("node_correct_not_in_choices", "correct", correct=str(kids.get("correct")), choices=ids)

    # Anything else the schema rejects on this node (only known fields; the agent
    # adds extra keys such as channel/objective that the sample schema forbids).
    if not problems:
        sliced_node = {k: kids.get(k) for k in _NODE_FIELDS if kids.get(k) is not None}
        if _rejects(ContentNode, sliced_node):
            add("node_invalid", "kids")
    return problems


def draft_problems(doc: PathVersion | dict[str, Any] | None) -> list[DraftProblem]:
    """Concrete problems in an agent draft, in display order (empty list = clean).

    Checks: titles.he, blurbs.he, emoji, subject, at least one node; per node a
    body (body_he/body_en/body_ui), a known step type, and for practice/check a
    ``correct`` that points at a choice id; per topic, node_ids that exist.
    estimated_minutes is never checked for agent drafts.
    """
    if doc is None:
        return []
    raw = _as_dict(doc)
    problems: list[DraftProblem] = []

    # --- path-level required fields (ContentPath rules) ---
    # Legacy flat mirrors (title_he, blurb_he, ...) count too, as in the schema.
    for map_key, prefix, code in (("titles", "title", "missing_title_he"), ("blurbs", "blurb", "missing_blurb_he")):
        legacy = {
            k: raw[k] for k in ContentPath.model_fields
            if k.startswith(prefix + "_") and isinstance(raw.get(k), str)
        }
        if _rejects(ContentPath, _probe_path(**{map_key: dict(raw.get(map_key) or {})}, **legacy)):
            problems.append(DraftProblem(code=code, field=f"{map_key}.he"))
    emoji = raw.get("emoji")
    # The schema only requires a string; an empty one is still missing for the UI.
    if _rejects(ContentPath, _probe_path(emoji=emoji)) or not str(emoji or "").strip():
        problems.append(DraftProblem(code="missing_emoji", field="emoji"))
    if _rejects(ContentPath, _probe_path(subject=raw.get("subject"))):
        problems.append(
            DraftProblem(code="bad_subject", field="subject", params={"subject": str(raw.get("subject") or "")})
        )
    nodes = _nodes_of(raw)
    if _rejects(ContentPath, _probe_path(nodes=[dict(_PROBE_NODE) for _ in nodes])):
        problems.append(DraftProblem(code="no_nodes", field="nodes"))

    # --- topics: node_ids must exist (ContentPath topic rule) ---
    topics = raw.get("topics") or []
    outline_keys = [
        t.get("key") for t in (((raw.get("agentBuild") or {}).get("outline") or {}).get("topics") or [])
    ]
    node_topic: dict[str, tuple[str | None, int | None]] = {}
    ordered_ids = list(dict.fromkeys(n[0] for n in nodes if n[0]))
    known_ids = set(ordered_ids)
    probe_nodes = [{**_PROBE_NODE, "id": nid} for nid in ordered_ids] or [dict(_PROBE_NODE)]
    topic_problems: list[DraftProblem] = []
    for pos, topic in enumerate(topics):
        tid = topic.get("id") or f"topic_{pos + 1}"
        t_index = outline_keys.index(tid) if tid in outline_keys else pos
        titles = topic.get("titles") or {}
        label = next((v for v in titles.values() if v), None) or tid
        node_ids = list(topic.get("node_ids") or [])
        for nid in node_ids:
            node_topic.setdefault(nid, (tid, t_index))
        probe_topic = {"id": tid, "titles": {"he": _PROBE_TEXT}, "node_ids": node_ids}
        if not _rejects(ContentPath, _probe_path(nodes=probe_nodes, topics=[probe_topic])):
            continue
        missing = [x for x in node_ids if x not in known_ids]
        code = "topic_unknown_nodes" if missing else "topic_no_nodes"
        topic_problems.append(
            DraftProblem(
                code=code, field=f"topics[{pos}].node_ids", topic_id=tid, topic_index=t_index,
                params={"topic": label, "ids": missing},
            )
        )

    # --- per node ---
    for nid, block_id, kids, content in nodes:
        tid, t_index = node_topic.get(nid or "", (content.get("topicKey"), None))
        if t_index is None and tid in outline_keys:
            t_index = outline_keys.index(tid)
        for p in _node_problems(nid, kids, content):
            p.block_id, p.topic_id, p.topic_index = block_id, tid, t_index
            problems.append(p)

    problems.extend(topic_problems)
    return problems


def blocking_problems(doc: PathVersion | dict[str, Any] | None) -> list[DraftProblem]:
    """The draft problems that block publishing (severity "error")."""
    return [p for p in draft_problems(doc) if p.blocking]
