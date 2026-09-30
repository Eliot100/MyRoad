"""Domain types aligned with freeze/v0 agent-tool contract."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class PathStatus(str, Enum):
    draft = "draft"
    in_review = "in_review"
    published = "published"
    archived = "archived"


class BlockType(str, Enum):
    explanation = "explanation"
    practice = "practice"
    assessment = "assessment"
    experience = "experience"


class EdgeRelationship(str, Enum):
    prerequisite = "prerequisite"
    sequence = "sequence"
    optional = "optional"
    branch = "branch"


class RbacDecision(str, Enum):
    allow = "allow"
    deny = "deny"


class Audience(BaseModel):
    model_config = ConfigDict(extra="allow")

    level: str | None = None
    gradeHint: str | None = None
    ageRange: str | None = None
    priorKnowledge: str | None = None


class Prerequisite(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    label: str
    description: str | None = None


class RetrievalState(BaseModel):
    model_config = ConfigDict(extra="allow")

    retrieved: bool = False
    approved: bool = False
    approvedBy: str | None = None
    approvedAt: str | None = None
    note: str | None = None


class Source(BaseModel):
    model_config = ConfigDict(extra="allow")

    sourceId: str
    title: str
    uri: str | None = None
    citation: str | None = None
    coverage: list[str] = Field(default_factory=list)
    retrievalState: RetrievalState = Field(default_factory=RetrievalState)
    attribution: str | None = None


class MasteryRule(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    requiredEvidence: str | None = None
    passingCriterion: str | None = None


class Block(BaseModel):
    model_config = ConfigDict(extra="allow")

    blockId: str
    type: BlockType
    title: str
    learningObjective: str | None = None
    concept: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    masteryRule: MasteryRule | None = None
    prerequisites: list[str] = Field(default_factory=list)
    sourceRefs: list[str] = Field(default_factory=list)
    editable: bool = True


class Edge(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    edgeId: str
    from_: str = Field(alias="from")
    to: str
    relationship: EdgeRelationship
    condition: dict[str, Any] | None = None


class Actors(BaseModel):
    model_config = ConfigDict(extra="allow")

    authorId: str | None = None
    agentId: str | None = None
    lastEditorId: str | None = None


class Provenance(BaseModel):
    model_config = ConfigDict(extra="allow")

    origin: str | None = None
    credit: str | None = None
    basedOnPathId: str | None = None
    verifiedCoreBoundary: str | None = None


class Attempt(BaseModel):
    model_config = ConfigDict(extra="allow")

    attemptId: str
    pathId: str
    versionId: str
    blockId: str
    learnerId: str
    answers: Any = None
    evidence: Any = None
    masteryResult: str | None = None  # passed | failed | incomplete
    channel: str | None = None
    createdAt: str | None = None


class Feedback(BaseModel):
    model_config = ConfigDict(extra="allow")

    feedbackId: str
    actorId: str
    targetPathId: str
    targetVersionId: str
    targetBlockId: str | None = None
    rating: int | None = None
    comment: str | None = None
    structuredIssue: dict[str, Any] | None = None
    proposedChange: str | None = None
    createdAt: str | None = None
    resultedInVersionId: str | None = None


class PathVersion(BaseModel):
    """Full path document for one version (matches freeze JSON shape)."""

    model_config = ConfigDict(extra="allow")

    schemaVersion: str = "0.1.0"
    pathId: str
    versionId: str
    version: int = 1
    status: PathStatus = PathStatus.draft
    contentLanguage: str = "he"
    uiLocale: str = "he-IL"
    name: str
    description: str | None = None
    goal: str | None = None
    audience: Audience | dict[str, Any] | None = None
    prerequisites: list[Prerequisite] = Field(default_factory=list)
    createdAt: str | None = None
    updatedAt: str | None = None
    actors: Actors | dict[str, Any] | None = None
    provenance: Provenance | dict[str, Any] | None = None
    sources: list[Source] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    feedback: list[Feedback] = Field(default_factory=list)
    lineage: dict[str, Any] | None = None
    publishedImmutableNote: str | None = None


class Event(BaseModel):
    """Audit event emitted on every mutation (contract freeze)."""

    model_config = ConfigDict(extra="allow")

    eventId: str = Field(default_factory=lambda: new_id("evt"))
    eventType: str
    actorId: str
    agentId: str | None = None
    correlationId: str
    pathId: str | None = None
    versionId: str | None = None
    payloadDigest: str | None = None
    timestamp: str = Field(default_factory=lambda: utc_now().isoformat())
    rbacDecision: RbacDecision
    detail: dict[str, Any] | None = None


class OpRequest(BaseModel):
    """Shared request envelope fields."""

    actorId: str
    agentId: str | None = None
    correlationId: str
    pathId: str | None = None
    versionId: str | None = None


class OpResponse(BaseModel):
    """Shared response envelope fields."""

    ok: bool
    correlationId: str
    pathId: str | None = None
    versionId: str | None = None
    changedObjectIds: list[str] = Field(default_factory=list)
    diffRef: str | None = None
    validationWarnings: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    auditEventId: str | None = None
    status: PathStatus | None = None
    publishRequestId: str | None = None
    data: dict[str, Any] | None = None
