"""AgentPathBuilder: turn an approved outline into a saved, playable draft.

Every write goes through AgentTools / PathStore with an agentId, so each step
leaves an audit event. Each topic is saved right after it fills: a failure in
the middle of a build keeps every topic that was already saved.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from myroad_core.agent_builder.completeness import (
    CompletenessReport,
    DraftProblem,
    check_path_completeness,
    draft_problems,
)
from myroad_core.agent_builder.generator import GenerationError, PathGenerator
from myroad_core.agent_builder.models import (
    FilledTopic,
    GoalSpec,
    OutlineTopic,
    PathOutline,
)
from myroad_core.content.schema import SUBJECTS
from myroad_core.models import (
    Block,
    BlockType,
    Edge,
    EdgeRelationship,
    MasteryRule,
    OpResponse,
    PathStatus,
    PathVersion,
    new_id,
)
from myroad_core.store_schema import _iso_now

AGENT_ID_GATEWAY = "agent_path_builder_grok"
AGENT_ID_DEMO = "agent_path_builder_demo"
AGENT_GROUP_ID = "agent"

UI_LOCALE_TAGS = {"he": "he-IL", "en": "en-US", "ar": "ar-IL"}

# No 60-minute cap here: that limit belongs to sample content files only.
STAGE_MINUTES = {"explanation": 5, "practice": 4, "check": 4, "experience": 6}

_BLOCK_TYPE = {
    "explanation": BlockType.explanation,
    "practice": BlockType.practice,
    "check": BlockType.assessment,
    "experience": BlockType.experience,
}
# Node types understood by the existing /play player.
_KIDS_TYPE = {
    "explanation": "learn",
    "practice": "practice",
    "check": "check",
    "experience": "speak",
}
_DEFAULT_MASTERY = {
    "explanation": {"type": "view_and_confirm", "passingCriterion": "ack"},
    "practice": {"type": "tap_correct", "passingCriterion": "correct_choice"},
    "check": {"type": "tap_correct", "passingCriterion": "correct_choice"},
    "experience": {"type": "complete_interaction", "passingCriterion": "done"},
}


def _corr(prefix: str) -> str:
    return f"corr_{prefix}_{uuid.uuid4().hex[:10]}"


@dataclass
class TopicResult:
    index: int
    ok: bool
    error_code: str | None = None
    detail: str = ""


def estimated_minutes(outline: PathOutline) -> int:
    return sum(STAGE_MINUTES.get(s.type, 4) for t in outline.topics for s in t.stages)


def _topic_blocks(
    topic: OutlineTopic, filled: FilledTopic, *, ui_code: str
) -> tuple[list[Block], list[str]]:
    by_order = {s.order: s for s in filled.stages}
    blocks: list[Block] = []
    node_ids: list[str] = []
    for stage in topic.stages:
        fs = by_order[stage.order]
        node_id = f"{topic.key}_s{stage.order:02d}"
        block_id = f"blk_{topic.key}_s{stage.order:02d}_{stage.type}"
        kids: dict[str, Any] = {
            "id": node_id,
            "type": _KIDS_TYPE[stage.type],
            "title": stage.title,
            "body_ui": fs.body,
            "channel": stage.channel,
            "objective": stage.objective,
        }
        if ui_code == "he":
            kids["body_he"] = fs.body
        elif ui_code == "en":
            kids["body_en"] = fs.body
            kids["title_en"] = stage.title
        if fs.content_token:
            kids["body_content"] = fs.content_token
            kids["speak_text"] = fs.content_token
        if stage.type in ("practice", "check") and fs.choices:
            kids["choices"] = [c.model_dump() for c in fs.choices]
            kids["correct"] = fs.correct
        if stage.type == "experience":
            kids["record"] = stage.channel == "record"
        if fs.feedback_ok:
            kids["feedback_ok"] = fs.feedback_ok
        if fs.feedback_try:
            kids["feedback_try"] = fs.feedback_try
        content: dict[str, Any] = {
            "kids": kids,
            "nodeType": kids["type"],
            "nodeId": node_id,
            "stageType": stage.type,
            "channel": stage.channel,
            "topicKey": topic.key,
        }
        if "choices" in kids:
            content["verifiedCore"] = {
                "items": [
                    {
                        "itemId": "choice",
                        "prompt": fs.body,
                        "answer": fs.correct,
                        "choices": kids["choices"],
                    }
                ]
            }
        mastery = fs.mastery.model_dump() if fs.mastery else dict(_DEFAULT_MASTERY[stage.type])
        blocks.append(
            Block(
                blockId=block_id,
                type=_BLOCK_TYPE[stage.type],
                title=stage.title,
                learningObjective=stage.objective,
                concept=topic.title,
                content=content,
                masteryRule=MasteryRule.model_validate(mastery),
                editable=True,
            )
        )
        node_ids.append(node_id)
    return blocks, node_ids


def assemble_document(raw: dict[str, Any]) -> dict[str, Any]:
    """Rebuild blocks, topics, and edges from agentBuild (outline + filled topics)."""
    build = raw["agentBuild"]
    spec = GoalSpec.model_validate(build["spec"])
    outline = PathOutline.model_validate(build["outline"])
    filled_map = build.get("filled") or {}
    ui_code = spec.ui_locale

    blocks: list[Block] = []
    topics: list[dict[str, Any]] = []
    node_to_block: dict[str, str] = {}
    first_last: dict[str, tuple[str, str]] = {}
    for idx, topic in enumerate(outline.topics):
        data = filled_map.get(str(idx))
        if not data:
            continue
        filled = FilledTopic.model_validate(data)
        t_blocks, node_ids = _topic_blocks(topic, filled, ui_code=ui_code)
        for nid, blk in zip(node_ids, t_blocks):
            node_to_block[nid] = blk.blockId
        first_last[topic.key] = (t_blocks[0].blockId, t_blocks[-1].blockId)
        blocks.extend(t_blocks)
        titles = {ui_code: topic.title}
        topics.append(
            {
                "id": topic.key,
                "titles": titles,
                f"title_{ui_code}": topic.title,
                "emoji": topic.emoji or outline.emoji or "📍",
                "node_ids": node_ids,
                "requires": list(topic.requires),
            }
        )

    edges: list[Edge] = []
    for i in range(len(blocks) - 1):
        edges.append(
            Edge.model_validate(
                {
                    "edgeId": f"edge_seq_{i:03d}",
                    "from": blocks[i].blockId,
                    "to": blocks[i + 1].blockId,
                    "relationship": EdgeRelationship.sequence.value,
                }
            )
        )
    by_id = {b.blockId: b for b in blocks}
    for topic in outline.topics:
        if topic.key not in first_last:
            continue
        first_block = first_last[topic.key][0]
        for req in topic.requires:
            if req not in first_last:
                continue
            last_req = first_last[req][1]
            edges.append(
                Edge.model_validate(
                    {
                        "edgeId": f"edge_pre_{req}_{topic.key}",
                        "from": last_req,
                        "to": first_block,
                        "relationship": EdgeRelationship.prerequisite.value,
                        "condition": {"topicKey": req, "requires": "topic_mastered"},
                    }
                )
            )
            if last_req not in by_id[first_block].prerequisites:
                by_id[first_block].prerequisites.append(last_req)

    out = dict(raw)
    out["name"] = outline.title
    out["description"] = outline.summary
    out["titles"] = {ui_code: outline.title}
    out["blurbs"] = {ui_code: outline.summary or spec.goal}
    out["emoji"] = outline.emoji or SUBJECTS.get(spec.subject, SUBJECTS["general"])["emoji"]
    out["blocks"] = [b.model_dump(mode="json", by_alias=True) for b in blocks]
    out["edges"] = [e.model_dump(mode="json", by_alias=True) for e in edges]
    out["topics"] = topics
    out["nodeToBlock"] = node_to_block
    out["estimatedMinutes"] = estimated_minutes(outline)
    return out


def preview_document(spec: GoalSpec, outline: PathOutline) -> dict[str, Any]:
    """In-memory draft for an outline that is not saved yet (no store write).

    Used to show live problems on the steps before the draft exists.
    """
    raw: dict[str, Any] = {
        "subject": spec.subject,
        "agentBuild": {
            "spec": spec.model_dump(mode="json"),
            "outline": outline.model_dump(mode="json"),
            "filled": {},
        },
    }
    return assemble_document(raw)


class AgentPathBuilder:
    """Draft lifecycle for agent-built paths (create, fill per topic, publish, feedback)."""

    def __init__(self, store, tools) -> None:
        self.store = store
        self.tools = tools

    # --- reads ---
    def load(self, path_id: str, version_id: str) -> dict[str, Any]:
        doc = self.store.get_version(path_id, version_id)
        return doc.model_dump(mode="json", by_alias=True)

    @staticmethod
    def spec_of(raw: dict[str, Any]) -> GoalSpec:
        return GoalSpec.model_validate(raw["agentBuild"]["spec"])

    @staticmethod
    def outline_of(raw: dict[str, Any]) -> PathOutline:
        return PathOutline.model_validate(raw["agentBuild"]["outline"])

    def completeness(self, path_id: str, version_id: str) -> CompletenessReport:
        return check_path_completeness(self.load(path_id, version_id))

    def problems(self, path_id: str, version_id: str) -> list[DraftProblem]:
        return draft_problems(self.load(path_id, version_id))

    def _save(self, raw: dict[str, Any], *, actor_id: str, agent_id: str, prefix: str) -> OpResponse:
        resp = self.tools.save_version(
            actor_id=actor_id,
            agent_id=agent_id,
            correlation_id=_corr(prefix),
            document=PathVersion.model_validate(raw),
        )
        if not resp.ok:
            raise GenerationError("save_failed", "; ".join(e.get("code", "") for e in resp.errors))
        return resp

    # --- create ---
    def start_draft(
        self,
        *,
        actor_id: str,
        spec: GoalSpec,
        outline: PathOutline,
        generator_name: str,
        demo: bool,
    ) -> tuple[str, str]:
        agent_id = AGENT_ID_DEMO if demo else AGENT_ID_GATEWAY
        created = self.tools.create_draft(
            actor_id=actor_id,
            agent_id=agent_id,
            correlation_id=_corr("agent_create"),
            name=outline.title,
            goal=spec.goal,
            audience={"level": spec.level},
            content_language=spec.content_language,
            ui_locale=UI_LOCALE_TAGS[spec.ui_locale],
            description=outline.summary,
            topic_hint=spec.goal,
        )
        if not created.ok or not created.pathId or not created.versionId:
            raise GenerationError("save_failed", "create_draft refused")
        raw = self.load(created.pathId, created.versionId)
        subject_meta = SUBJECTS.get(spec.subject, SUBJECTS["general"])
        raw.update(
            {
                "subject": spec.subject,
                "subjectLabelHe": subject_meta["he"],
                "subjectLabelEn": subject_meta.get("en"),
                "subjectColor": subject_meta["color"],
                "groupIds": [AGENT_GROUP_ID],
                "kidsDemo": False,
                "demo": bool(demo),
                "agentBuilt": True,
                "explainLocale": spec.ui_locale,
                "contentLocale": spec.content_language,
                "contentSource": "agent_path_builder",
                "agentBuild": {
                    "mode": "demo" if demo else "gateway",
                    "generator": generator_name,
                    "agentId": agent_id,
                    "spec": spec.model_dump(mode="json"),
                    "outline": outline.model_dump(mode="json"),
                    "topicStatus": [
                        {"status": "pending", "error": None, "detail": ""} for _ in outline.topics
                    ],
                    "filled": {},
                    "feedback": None,
                },
            }
        )
        prov = dict(raw.get("provenance") or {})
        prov["origin"] = "agent_demo_draft" if demo else "agent_generated_draft"
        prov["credit"] = "MyRoad agent path builder" + (" (demo mode)" if demo else "")
        raw["provenance"] = prov
        raw = assemble_document(raw)
        self._save(raw, actor_id=actor_id, agent_id=agent_id, prefix="agent_outline")
        return created.pathId, created.versionId

    # --- fill ---
    def fill_topic(
        self,
        generator: PathGenerator,
        *,
        actor_id: str,
        path_id: str,
        version_id: str,
        topic_index: int,
    ) -> TopicResult:
        raw = self.load(path_id, version_id)
        if raw.get("status") not in (PathStatus.draft.value, PathStatus.in_review.value):
            return TopicResult(topic_index, False, "not_a_draft")
        build = raw["agentBuild"]
        agent_id = build.get("agentId") or AGENT_ID_GATEWAY
        spec = GoalSpec.model_validate(build["spec"])
        outline = PathOutline.model_validate(build["outline"])
        if not 0 <= topic_index < len(outline.topics):
            return TopicResult(topic_index, False, "bad_topic")
        fb = build.get("feedback") or {}
        feedback = fb.get("comment") if fb.get("topicIndex") == topic_index else None
        try:
            filled = generator.fill_topic(spec, outline, topic_index, feedback=feedback)
            error: GenerationError | None = None
        except GenerationError as exc:
            error = exc
        except Exception as exc:  # keep the build alive; never echo raw bodies
            error = GenerationError("internal", type(exc).__name__)
        status = build["topicStatus"][topic_index]
        status["updatedAt"] = _iso_now()
        if error is not None:
            status.update({"status": "failed", "error": error.code, "detail": error.detail[:300]})
            self._save(raw, actor_id=actor_id, agent_id=agent_id, prefix="agent_topic_failed")
            return TopicResult(topic_index, False, error.code, error.detail)
        build["filled"][str(topic_index)] = filled.model_dump(mode="json")
        status.update({"status": "done", "error": None, "detail": ""})
        raw = assemble_document(raw)
        self._save(raw, actor_id=actor_id, agent_id=agent_id, prefix="agent_topic_saved")
        return TopicResult(topic_index, True)

    def next_pending(self, path_id: str, version_id: str) -> int | None:
        raw = self.load(path_id, version_id)
        for i, s in enumerate(raw["agentBuild"]["topicStatus"]):
            if s.get("status") == "pending":
                return i
        return None

    def run_pending(
        self,
        generator: PathGenerator,
        *,
        actor_id: str,
        path_id: str,
        version_id: str,
        retry_failed: bool = False,
    ) -> list[TopicResult]:
        """Fill every pending topic in order. A failed topic does not stop the others."""
        raw = self.load(path_id, version_id)
        wanted = {"pending", "failed"} if retry_failed else {"pending"}
        indexes = [
            i for i, s in enumerate(raw["agentBuild"]["topicStatus"]) if s.get("status") in wanted
        ]
        return [
            self.fill_topic(
                generator, actor_id=actor_id, path_id=path_id, version_id=version_id, topic_index=i
            )
            for i in indexes
        ]

    # --- publish / feedback ---
    def publish(
        self, *, actor_id: str, path_id: str, version_id: str, by_agent: bool = False
    ) -> OpResponse:
        raw = self.load(path_id, version_id)
        report = check_path_completeness(raw)
        corr = _corr("agent_publish")
        if not report.complete:
            return OpResponse(
                ok=False,
                correlationId=corr,
                pathId=path_id,
                versionId=version_id,
                errors=[{"code": "PATH_NOT_COMPLETE", "message": "path does not meet the completeness rule"}],
                data={"issues": report.issues},
            )
        agent_id = (raw.get("agentBuild") or {}).get("agentId") or AGENT_ID_GATEWAY
        return self.tools.publish(
            actor_id=agent_id if by_agent else actor_id,
            agent_id=agent_id,
            correlation_id=corr,
            path_id=path_id,
            version_id=version_id,
            publisher_id=agent_id if by_agent else actor_id,
        )

    def submit_feedback(
        self,
        *,
        actor_id: str,
        path_id: str,
        version_id: str,
        comment: str,
        topic_index: int | None = None,
    ) -> OpResponse:
        """Feedback on a published version creates a new draft; the published one is untouched."""
        base = self.load(path_id, version_id)
        build = dict(base.get("agentBuild") or {})
        agent_id = build.get("agentId") or AGENT_ID_GATEWAY
        new_vid = new_id("ver")
        fid = new_id("fb")
        comment = " ".join((comment or "").split())[:1000]
        feedback = list(base.get("feedback") or [])
        feedback.append(
            {
                "feedbackId": fid,
                "actorId": actor_id,
                "targetPathId": path_id,
                "targetVersionId": version_id,
                "comment": comment,
                "createdAt": _iso_now(),
                "resultedInVersionId": new_vid,
            }
        )
        statuses = [dict(s) for s in build.get("topicStatus") or []]
        if topic_index is not None and 0 <= topic_index < len(statuses):
            statuses[topic_index] = {"status": "pending", "error": None, "detail": ""}
        build["topicStatus"] = statuses
        build["feedback"] = {"comment": comment, "topicIndex": topic_index, "feedbackId": fid}
        return self.store.revise_draft(
            actor_id=actor_id,
            agent_id=agent_id,
            correlation_id=_corr("agent_feedback"),
            path_id=path_id,
            base_version_id=version_id,
            change_set={
                "feedback": feedback,
                "agentBuild": build,
                "publishedImmutableNote": (
                    "status draft, created from feedback. The published version it came "
                    "from stays immutable."
                ),
            },
            feedback_ids=[fid],
            new_version_id=new_vid,
        )


def list_user_agent_drafts(store, user_id: str) -> list[dict[str, Any]]:
    """Agent-built draft versions authored by this user (newest first)."""
    rows = store._conn.execute(
        "SELECT path_id, version_id, version_num, status, document_json, updated_at "
        "FROM versions WHERE status IN ('draft', 'in_review') ORDER BY updated_at DESC"
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        doc = PathVersion.model_validate_json(row["document_json"])
        raw = doc.model_dump(mode="json", by_alias=True)
        if not raw.get("agentBuild"):
            continue
        actors = raw.get("actors") or {}
        if actors.get("authorId") != user_id:
            continue
        statuses = raw["agentBuild"].get("topicStatus") or []
        out.append(
            {
                "pathId": row["path_id"],
                "versionId": row["version_id"],
                "version": row["version_num"],
                "name": raw.get("name"),
                "demo": bool(raw.get("demo")),
                "done": sum(1 for s in statuses if s.get("status") == "done"),
                "total": len(statuses),
                "updatedAt": row["updated_at"],
            }
        )
    return out
