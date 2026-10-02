"""Optional thin FastAPI wrapper over AgentTools.

Install with: pip install -e ".[api]"
Run: uvicorn myroad_core.api:app --reload
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from myroad_core.models import OpResponse
from myroad_core.store import PathStore
from myroad_core.tools import AgentTools

try:
    from fastapi import FastAPI
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "FastAPI is required for the HTTP layer. Install with: pip install -e '.[api]'"
    ) from exc


class Envelope(BaseModel):
    actorId: str
    agentId: str | None = None
    correlationId: str
    pathId: str | None = None
    versionId: str | None = None


class CreateDraftBody(Envelope):
    name: str
    description: str | None = None
    goal: str | None = None
    audience: dict[str, Any] | None = None
    prerequisites: list[dict[str, Any]] | None = None
    contentLanguage: str = "he"
    uiLocale: str = "he-IL"
    topicHint: str | None = None


class AddBlockBody(Envelope):
    type: str
    title: str
    learningObjective: str | None = None
    concept: str | None = None
    content: dict[str, Any] | None = None
    masteryRule: dict[str, Any] | None = None
    prerequisites: list[str] | None = None
    sourceRefs: list[str] | None = None
    blockId: str | None = None


class EditBlockBody(Envelope):
    blockId: str
    patch: dict[str, Any] = Field(default_factory=dict)


class AddEdgeBody(Envelope):
    from_: str = Field(alias="from")
    to: str
    relationship: str
    condition: dict[str, Any] | None = None
    edgeId: str | None = None

    model_config = {"populate_by_name": True}


class ReviseDraftBody(Envelope):
    baseVersionId: str
    feedbackIds: list[str] | None = None
    changeSet: dict[str, Any] | None = None


class RecordFeedbackBody(Envelope):
    targetBlockId: str | None = None
    rating: int | None = None
    comment: str | None = None
    structuredIssue: dict[str, Any] | None = None
    proposedChange: str | None = None


class RequestPublishBody(Envelope):
    evidenceSnapshotRef: str | None = None
    requireValid: bool = True


class PublishBody(Envelope):
    publisherId: str | None = None
    humanPublisher: bool = False


def create_app(store: PathStore | None = None, *, db_path: str = ":memory:") -> FastAPI:
    path_store = store or PathStore(db_path)
    tools = AgentTools(path_store)
    app = FastAPI(title="MyRoad Agent Tools API", version="0.1.0")
    app.state.store = path_store
    app.state.tools = tools

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/tools/createDraft", response_model=OpResponse)
    def create_draft(body: CreateDraftBody) -> OpResponse:
        return tools.create_draft(
            actor_id=body.actorId, agent_id=body.agentId,
            correlation_id=body.correlationId, name=body.name,
            description=body.description, goal=body.goal, audience=body.audience,
            prerequisites=body.prerequisites, content_language=body.contentLanguage,
            ui_locale=body.uiLocale, topic_hint=body.topicHint,
        )

    @app.post("/tools/getPath", response_model=OpResponse)
    def get_path(body: Envelope) -> OpResponse:
        if not body.pathId:
            return OpResponse(
                ok=False, correlationId=body.correlationId,
                errors=[{"code": "MISSING_IDS", "message": "pathId required"}],
            )
        return tools.get_path(
            actor_id=body.actorId, agent_id=body.agentId,
            correlation_id=body.correlationId, path_id=body.pathId,
            version_id=body.versionId,
        )

    @app.post("/tools/getVersion", response_model=OpResponse)
    def get_version(body: Envelope) -> OpResponse:
        if not body.pathId or not body.versionId:
            return OpResponse(
                ok=False, correlationId=body.correlationId,
                errors=[{"code": "MISSING_IDS", "message": "pathId and versionId required"}],
            )
        return tools.get_version(
            actor_id=body.actorId, agent_id=body.agentId,
            correlation_id=body.correlationId, path_id=body.pathId,
            version_id=body.versionId,
        )

    @app.post("/tools/addBlock", response_model=OpResponse)
    def add_block(body: AddBlockBody) -> OpResponse:
        return tools.add_block(
            actor_id=body.actorId, agent_id=body.agentId,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "", type=body.type, title=body.title,
            learning_objective=body.learningObjective, concept=body.concept,
            content=body.content, mastery_rule=body.masteryRule,
            prerequisites=body.prerequisites, source_refs=body.sourceRefs,
            block_id=body.blockId,
        )

    @app.post("/tools/editBlock", response_model=OpResponse)
    def edit_block(body: EditBlockBody) -> OpResponse:
        return tools.edit_block(
            actor_id=body.actorId, agent_id=body.agentId,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "", block_id=body.blockId, patch=body.patch,
        )

    @app.post("/tools/addEdge", response_model=OpResponse)
    def add_edge(body: AddEdgeBody) -> OpResponse:
        return tools.add_edge(
            actor_id=body.actorId, agent_id=body.agentId,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "", from_=body.from_, to=body.to,
            relationship=body.relationship, condition=body.condition,
            edge_id=body.edgeId,
        )

    @app.post("/tools/reviseDraft", response_model=OpResponse)
    def revise_draft(body: ReviseDraftBody) -> OpResponse:
        return tools.revise_draft(
            actor_id=body.actorId, agent_id=body.agentId,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            base_version_id=body.baseVersionId, change_set=body.changeSet,
            feedback_ids=body.feedbackIds,
        )

    @app.post("/tools/validatePath", response_model=OpResponse)
    def validate_path(body: Envelope) -> OpResponse:
        return tools.validate_path(
            actor_id=body.actorId, agent_id=body.agentId,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "",
        )

    @app.post("/tools/recordFeedback", response_model=OpResponse)
    def record_feedback(body: RecordFeedbackBody) -> OpResponse:
        return tools.record_feedback(
            actor_id=body.actorId, agent_id=body.agentId,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "", target_block_id=body.targetBlockId,
            rating=body.rating, comment=body.comment,
            structured_issue=body.structuredIssue, proposed_change=body.proposedChange,
        )

    @app.post("/tools/requestPublish", response_model=OpResponse)
    def request_publish(body: RequestPublishBody) -> OpResponse:
        return tools.request_publish(
            actor_id=body.actorId, agent_id=body.agentId,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "",
            evidence_snapshot_ref=body.evidenceSnapshotRef,
            require_valid=body.requireValid,
        )

    @app.post("/tools/publish", response_model=OpResponse)
    def publish(body: PublishBody) -> OpResponse:
        return tools.publish(
            actor_id=body.actorId, agent_id=body.agentId,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "", publisher_id=body.publisherId,
            human_publisher=body.humanPublisher,
        )

    return app


# Default in-memory app for `uvicorn myroad_core.api:app`
app = create_app()
