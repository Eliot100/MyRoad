"""Optional thin FastAPI wrapper over AgentTools.

Install with: pip install -e ".[api]"
Run: uvicorn myroad_core.api:app --reload

Auth (issue #40): every ``/tools/*`` call needs either
- a logged-in user's session cookie (``myroad_session``), or
- the server-side agent credential: ``Authorization: Bearer <MYROAD_AGENT_TOKEN>``.
Otherwise the answer is 401. The actor is taken from the session or the
credential. Cookie (session) calls must also send ``X-MyRoad-Request: 1``
(CSRF guard: a cross-site form cannot set it), else 403. A principal may act
only on paths it authored (agent: also ``MYROAD_AGENT_ALLOWED_PATHS``); any
other path id answers 404 (see ``myroad_core.auth.ownership``). A body ``actorId`` / ``agentId`` / ``publisherId`` is never used; if
one is sent and differs from the authenticated principal, the call gets 403.

To accept the UI's login sessions, point both apps at the same SQLite file
(``MYROAD_DB``) or pass the same ``PathStore`` to ``create_app``.
"""
from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from myroad_core.auth import Principal, may_act_on_path, resolve_principal
from myroad_core.models import OpResponse
from myroad_core.publish_gate import PUBLISH_GATE_CODES
from myroad_core.store import PathStore
from myroad_core.tools import AgentTools

try:
    from fastapi import Depends, FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "FastAPI is required for the HTTP layer. Install with: pip install -e '.[api]'"
    ) from exc


class Envelope(BaseModel):
    # Not trusted: the actor comes from the session / agent credential.
    # Accepted only so older clients keep working when it matches.
    actorId: str | None = None
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


TOOLS_PREFIX = "/tools/"
CSRF_HEADER = "X-MyRoad-Request"

_PUBLISH_GATE_CODES = PUBLISH_GATE_CODES


def _publish_http(resp: OpResponse) -> OpResponse | JSONResponse:
    """422 with the problem list when the publish gate refused (issue #42)."""
    if not resp.ok and any(e.get("code") in _PUBLISH_GATE_CODES for e in resp.errors):
        return JSONResponse(status_code=422, content=resp.model_dump(mode="json"))
    return resp


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": {"code": "UNAUTHENTICATED", "message": "session or agent credential required"}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if principal is None:  # middleware guarantees this; defence in depth
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHENTICATED", "message": "session or agent credential required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def _check_claimed_identity(body: BaseModel, principal: Principal) -> None:
    """Refuse a body that claims a different actor, agent, or publisher."""
    claims = {
        "actorId": (getattr(body, "actorId", None), principal.actor_id),
        "agentId": (getattr(body, "agentId", None), principal.agent_id),
        "publisherId": (getattr(body, "publisherId", None), principal.actor_id),
    }
    for field, (claimed, actual) in claims.items():
        if claimed is not None and claimed != actual:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "ACTOR_MISMATCH",
                    "message": f"{field} must match the authenticated principal (or be omitted)",
                },
            )


def create_app(store: PathStore | None = None, *, db_path: str = ":memory:") -> FastAPI:
    path_store = store or PathStore(db_path)
    tools = AgentTools(path_store)
    app = FastAPI(title="MyRoad Agent Tools API", version="0.2.0")
    app.state.store = path_store
    app.state.tools = tools

    @app.middleware("http")
    async def _tools_auth(request: Request, call_next):
        # Runs before body parsing / routing, so every /tools/* path
        # (known or not) answers 401 without a session or agent credential.
        if request.url.path.startswith(TOOLS_PREFIX) or request.url.path == TOOLS_PREFIX.rstrip("/"):
            principal = resolve_principal(request, path_store)
            if principal is None:
                return _unauthorized()
            if principal.kind == "user" and request.headers.get(CSRF_HEADER) != "1":
                # Cookie-authenticated: require a custom header (forces a CORS
                # preflight, which this API does not allow cross-origin).
                return JSONResponse(
                    status_code=403,
                    content={"detail": {"code": "CSRF_HEADER_REQUIRED",
                                        "message": f"cookie-authenticated calls must send {CSRF_HEADER}: 1"}},
                )
            request.state.principal = principal
        return await call_next(request)

    def actor(body: Any, principal: Principal) -> tuple[str, str | None]:
        _check_claimed_identity(body, principal)
        # Ownership: every op except createDraft targets an existing path.
        path_id = getattr(body, "pathId", None)
        if not isinstance(body, CreateDraftBody) and path_id and not may_act_on_path(
            path_store, principal, path_id
        ):
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "path not found"})
        return principal.actor_id, principal.agent_id

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/tools/createDraft", response_model=OpResponse)
    def create_draft(body: CreateDraftBody, principal: Principal = Depends(current_principal)) -> OpResponse:
        actor_id, agent_id = actor(body, principal)
        return tools.create_draft(
            actor_id=actor_id, agent_id=agent_id,
            correlation_id=body.correlationId, name=body.name,
            description=body.description, goal=body.goal, audience=body.audience,
            prerequisites=body.prerequisites, content_language=body.contentLanguage,
            ui_locale=body.uiLocale, topic_hint=body.topicHint,
        )

    @app.post("/tools/getPath", response_model=OpResponse)
    def get_path(body: Envelope, principal: Principal = Depends(current_principal)) -> OpResponse:
        actor_id, agent_id = actor(body, principal)
        if not body.pathId:
            return OpResponse(
                ok=False, correlationId=body.correlationId,
                errors=[{"code": "MISSING_IDS", "message": "pathId required"}],
            )
        return tools.get_path(
            actor_id=actor_id, agent_id=agent_id,
            correlation_id=body.correlationId, path_id=body.pathId,
            version_id=body.versionId,
        )

    @app.post("/tools/getVersion", response_model=OpResponse)
    def get_version(body: Envelope, principal: Principal = Depends(current_principal)) -> OpResponse:
        actor_id, agent_id = actor(body, principal)
        if not body.pathId or not body.versionId:
            return OpResponse(
                ok=False, correlationId=body.correlationId,
                errors=[{"code": "MISSING_IDS", "message": "pathId and versionId required"}],
            )
        return tools.get_version(
            actor_id=actor_id, agent_id=agent_id,
            correlation_id=body.correlationId, path_id=body.pathId,
            version_id=body.versionId,
        )

    @app.post("/tools/addBlock", response_model=OpResponse)
    def add_block(body: AddBlockBody, principal: Principal = Depends(current_principal)) -> OpResponse:
        actor_id, agent_id = actor(body, principal)
        return tools.add_block(
            actor_id=actor_id, agent_id=agent_id,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "", type=body.type, title=body.title,
            learning_objective=body.learningObjective, concept=body.concept,
            content=body.content, mastery_rule=body.masteryRule,
            prerequisites=body.prerequisites, source_refs=body.sourceRefs,
            block_id=body.blockId,
        )

    @app.post("/tools/editBlock", response_model=OpResponse)
    def edit_block(body: EditBlockBody, principal: Principal = Depends(current_principal)) -> OpResponse:
        actor_id, agent_id = actor(body, principal)
        return tools.edit_block(
            actor_id=actor_id, agent_id=agent_id,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "", block_id=body.blockId, patch=body.patch,
        )

    @app.post("/tools/addEdge", response_model=OpResponse)
    def add_edge(body: AddEdgeBody, principal: Principal = Depends(current_principal)) -> OpResponse:
        actor_id, agent_id = actor(body, principal)
        return tools.add_edge(
            actor_id=actor_id, agent_id=agent_id,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "", from_=body.from_, to=body.to,
            relationship=body.relationship, condition=body.condition,
            edge_id=body.edgeId,
        )

    @app.post("/tools/reviseDraft", response_model=OpResponse)
    def revise_draft(body: ReviseDraftBody, principal: Principal = Depends(current_principal)) -> OpResponse:
        actor_id, agent_id = actor(body, principal)
        return tools.revise_draft(
            actor_id=actor_id, agent_id=agent_id,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            base_version_id=body.baseVersionId, change_set=body.changeSet,
            feedback_ids=body.feedbackIds,
        )

    @app.post("/tools/validatePath", response_model=OpResponse)
    def validate_path(body: Envelope, principal: Principal = Depends(current_principal)) -> OpResponse:
        actor_id, agent_id = actor(body, principal)
        return tools.validate_path(
            actor_id=actor_id, agent_id=agent_id,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "",
        )

    @app.post("/tools/recordFeedback", response_model=OpResponse)
    def record_feedback(body: RecordFeedbackBody, principal: Principal = Depends(current_principal)) -> OpResponse:
        actor_id, agent_id = actor(body, principal)
        return tools.record_feedback(
            actor_id=actor_id, agent_id=agent_id,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "", target_block_id=body.targetBlockId,
            rating=body.rating, comment=body.comment,
            structured_issue=body.structuredIssue, proposed_change=body.proposedChange,
        )

    @app.post("/tools/requestPublish", response_model=OpResponse)
    def request_publish(body: RequestPublishBody, principal: Principal = Depends(current_principal)) -> OpResponse:
        actor_id, agent_id = actor(body, principal)
        return tools.request_publish(
            actor_id=actor_id, agent_id=agent_id,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "",
            evidence_snapshot_ref=body.evidenceSnapshotRef,
            require_valid=body.requireValid,
        )

    @app.post(
        "/tools/publish",
        response_model=OpResponse,
        responses={422: {"model": OpResponse, "description": "publish gate refused (problem list)"}},
    )
    def publish(body: PublishBody, principal: Principal = Depends(current_principal)):
        actor_id, agent_id = actor(body, principal)
        return _publish_http(tools.publish(
            actor_id=actor_id, agent_id=agent_id,
            correlation_id=body.correlationId, path_id=body.pathId or "",
            version_id=body.versionId or "", publisher_id=actor_id,
            human_publisher=body.humanPublisher,
        ))

    return app


# Default app for `uvicorn myroad_core.api:app`: in-memory unless MYROAD_DB is set
# (set it to the UI's SQLite file so UI login sessions are accepted here).
app = create_app(db_path=(os.environ.get("MYROAD_DB") or "").strip() or ":memory:")
