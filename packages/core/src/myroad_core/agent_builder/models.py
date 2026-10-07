"""Pydantic models for the agent path builder (goal, outline, filled topics).

The model is asked for strict JSON. Everything it returns is validated here
before anything is saved to the PathStore.
"""
from __future__ import annotations

from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from myroad_core.content.schema import (
    GROUPS,
    NODE_STAGE,
    NODE_TYPES,
    STEP_KINDS,  # noqa: F401  (re-exported for the builder UI and prompts)
    ScoreLink,
    StepKind,
    SubjectId,
)

# Step types and subjects come from content/schema.py (the single source of truth).
# Builder stage types are the distinct NODE_STAGE values, in schema order.
STAGE_TYPES: tuple[str, ...] = tuple(dict.fromkeys(NODE_STAGE[n] for n in NODE_TYPES))
# Stage type -> the node type the player gets (first schema node type for that stage).
STAGE_NODE_TYPE: dict[str, str] = {}
for _node_type in NODE_TYPES:
    STAGE_NODE_TYPE.setdefault(NODE_STAGE[_node_type], _node_type)
SUBJECT_IDS: tuple[str, ...] = get_args(SubjectId)

LocaleCode = Literal["he", "en", "ar"]
LevelId = Literal["beginner", "elementary", "intermediate", "advanced"]
LengthId = Literal["short", "medium", "long"]
StageType = Literal[STAGE_TYPES]  # type: ignore[valid-type]
Channel = Literal["write", "read", "listen", "record", "mouse"]

LOCALE_CODES: tuple[str, ...] = ("he", "en", "ar")
LEVEL_IDS: tuple[str, ...] = ("beginner", "elementary", "intermediate", "advanced")
LENGTH_IDS: tuple[str, ...] = ("short", "medium", "long")
CHANNELS: tuple[str, ...] = ("write", "read", "listen", "record", "mouse")
# Optional extra audience for agent paths (schema groups; "agent" is always added).
AUDIENCE_IDS: tuple[str, ...] = tuple(g for g in GROUPS if g != "agent")

# Completeness rule for agent drafts (outline and filled path).
MIN_TOPICS = 3
MIN_STAGES = 12
REQUIRED_STAGE_TYPES: tuple[str, ...] = ("explanation", "practice", "check")

# Targets per requested length: (topics, stages per topic). All meet the minimum.
LENGTH_TARGETS: dict[str, tuple[int, int]] = {
    "short": (3, 4),
    "medium": (4, 5),
    "long": (6, 5),
}

_TYPE_ALIASES = {
    "explain": "explanation",
    "learn": "explanation",
    "lesson": "explanation",
    "exercise": "practice",
    "assessment": "check",
    "quiz": "check",
    "test": "check",
    "activity": "experience",
    "experiment": "experience",
}
_CHANNEL_ALIASES = {
    "writing": "write",
    "reading": "read",
    "listening": "listen",
    "speak": "record",
    "speaking": "record",
    "voice": "record",
    "click": "mouse",
    "tap": "mouse",
}


def _norm(value: Any, aliases: dict[str, str]) -> Any:
    if isinstance(value, str):
        low = value.strip().lower()
        return aliases.get(low, low)
    return value


class GoalSpec(BaseModel):
    """What the signed-in user asked for on the goal step."""

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=3, max_length=400)
    subject: SubjectId = "general"
    level: LevelId = "beginner"
    ui_locale: LocaleCode = "he"
    content_language: LocaleCode = "he"
    length: LengthId = "medium"
    # Optional audience group from the schema (e.g. adult, psychometric). Old specs omit it.
    audience: str | None = None

    @field_validator("audience", mode="before")
    @classmethod
    def _audience_known(cls, v: Any) -> Any:
        if v in (None, ""):
            return None
        if v not in AUDIENCE_IDS:
            raise ValueError(f"unknown audience: {v}")
        return v

    @field_validator("goal")
    @classmethod
    def _strip_goal(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 3:
            raise ValueError("goal is too short")
        return v

    def targets(self) -> tuple[int, int]:
        return LENGTH_TARGETS[self.length]


class OutlineStage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=160)
    type: StageType
    channel: Channel
    objective: str = Field(min_length=1, max_length=400)
    order: int = Field(ge=0)
    # Schema v2: why the step exists. Review steps mix EARLIER topics (topic keys).
    kind: StepKind = "understanding"
    review_topic_ids: list[str] = Field(default_factory=list)

    @field_validator("kind", mode="before")
    @classmethod
    def _kind_default(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "understanding"
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("review_topic_ids", mode="before")
    @classmethod
    def _review_list(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, (str, int)):
            return [str(v)]
        if isinstance(v, list):
            return list(dict.fromkeys(str(x).strip() for x in v if str(x).strip()))
        return v

    @model_validator(mode="after")
    def _review_needs_kind(self) -> OutlineStage:
        # A stage that lists review topics is a review step (the model may omit kind).
        if self.review_topic_ids and self.kind != "review":
            self.kind = "review"
        return self

    @field_validator("type", mode="before")
    @classmethod
    def _type_alias(cls, v: Any) -> Any:
        return _norm(v, _TYPE_ALIASES)

    @field_validator("channel", mode="before")
    @classmethod
    def _channel_alias(cls, v: Any) -> Any:
        return _norm(v, _CHANNEL_ALIASES)

    @field_validator("title", "objective", mode="before")
    @classmethod
    def _strip(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v


class OutlineTopic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str = ""
    title: str = Field(min_length=1, max_length=160)
    emoji: str | None = None
    order: int = Field(ge=0)
    requires: list[str] = Field(default_factory=list)
    stages: list[OutlineStage] = Field(min_length=1)

    @field_validator("title", mode="before")
    @classmethod
    def _strip(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v

    @field_validator("requires", mode="before")
    @classmethod
    def _requires_list(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, (str, int)):
            return [str(v)]
        if isinstance(v, list):
            return [str(x) for x in v if str(x).strip()]
        return v

    @model_validator(mode="after")
    def _sort_stages(self) -> OutlineTopic:
        ordered = sorted(self.stages, key=lambda s: s.order)
        for i, stage in enumerate(ordered, start=1):
            stage.order = i
        self.stages = ordered
        return self

    def stage_types(self) -> set[str]:
        return {s.type for s in self.stages}


class PathOutline(BaseModel):
    """Structured outline returned by one model call."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(default="", max_length=600)
    emoji: str | None = None
    topics: list[OutlineTopic] = Field(min_length=1)
    # Schema v2 path-level fields (optional; old outlines omit them).
    prerequisite_path_ids: list[str] = Field(default_factory=list)
    score: ScoreLink | None = None

    @field_validator("prerequisite_path_ids", mode="before")
    @classmethod
    def _prereq_list(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, str):
            v = [v]
        if isinstance(v, list):
            # Same shape rule as the schema: path_ ids, no duplicates.
            return list(dict.fromkeys(str(x).strip() for x in v if str(x).strip().startswith("path_")))
        return v

    @field_validator("score", mode="before")
    @classmethod
    def _score_empty(cls, v: Any) -> Any:
        # The score link is optional: an empty or invalid one is dropped rather than
        # failing the whole outline (the schema's ScoreLink decides what is valid).
        if v in ({}, "", None):
            return None
        try:
            return ScoreLink.model_validate(v)
        except ValidationError:
            return None

    @model_validator(mode="after")
    def _normalize_and_check(self) -> PathOutline:
        ordered = sorted(self.topics, key=lambda t: t.order)
        used: set[str] = set()
        for i, topic in enumerate(ordered, start=1):
            topic.order = i
            key = (topic.key or "").strip() or f"t{i}"
            if key in used:
                key = f"t{i}"
            used.add(key)
            topic.key = key
        # Prerequisites and review topics may only point at earlier topics (keeps the
        # map acyclic and matches the schema's review rule).
        earlier: set[str] = set()
        for topic in ordered:
            topic.requires = list(dict.fromkeys(r for r in topic.requires if r in earlier))
            for stage in topic.stages:
                if stage.kind == "review":
                    stage.review_topic_ids = [r for r in stage.review_topic_ids if r in earlier]
            earlier.add(topic.key)
        self.topics = ordered
        problems = outline_problems(self)
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def stage_count(self) -> int:
        return sum(len(t.stages) for t in self.topics)


def outline_problems(outline: PathOutline) -> list[str]:
    """Completeness problems of an outline (empty list = OK)."""
    problems: list[str] = []
    if len(outline.topics) < MIN_TOPICS:
        problems.append(f"need at least {MIN_TOPICS} topics, got {len(outline.topics)}")
    total = sum(len(t.stages) for t in outline.topics)
    if total < MIN_STAGES:
        problems.append(f"need at least {MIN_STAGES} stages, got {total}")
    for topic in outline.topics:
        missing = [x for x in REQUIRED_STAGE_TYPES if x not in topic.stage_types()]
        if missing:
            problems.append(f"topic '{topic.title}' is missing stage types: {', '.join(missing)}")
    return problems


class StageChoice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=200)

    @field_validator("id", "label", mode="before")
    @classmethod
    def _to_str(cls, v: Any) -> Any:
        if isinstance(v, (int, float)):
            return str(v)
        return v.strip() if isinstance(v, str) else v


class StageMastery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = Field(min_length=1, max_length=60)
    passingCriterion: str | None = Field(default=None, max_length=200)


class FilledStage(BaseModel):
    """Content for one stage, returned by the per-topic fill call."""

    model_config = ConfigDict(extra="ignore")

    order: int = Field(ge=1)
    body: str = Field(min_length=1, max_length=4000)
    content_token: str | None = Field(default=None, max_length=200)
    choices: list[StageChoice] = Field(default_factory=list)
    correct: str | None = None
    feedback_ok: str | None = Field(default=None, max_length=300)
    feedback_try: str | None = Field(default=None, max_length=300)
    mastery: StageMastery | None = None

    @field_validator("correct", mode="before")
    @classmethod
    def _correct_str(cls, v: Any) -> Any:
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, list) and len(v) == 1:
            return str(v[0])
        return v

    @model_validator(mode="after")
    def _choices_consistent(self) -> FilledStage:
        if self.choices:
            ids = [c.id for c in self.choices]
            if len(set(ids)) != len(ids):
                raise ValueError(f"stage {self.order}: duplicate choice ids")
            if self.correct is not None and self.correct not in ids:
                raise ValueError(f"stage {self.order}: correct id '{self.correct}' is not a choice id")
        return self


class FilledTopic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    stages: list[FilledStage] = Field(min_length=1)

    @model_validator(mode="after")
    def _sort(self) -> FilledTopic:
        self.stages = sorted(self.stages, key=lambda s: s.order)
        return self


def check_filled_against_outline(topic: OutlineTopic, filled: FilledTopic) -> list[str]:
    """A filled topic must cover every outline stage; quizzes need a correct choice."""
    problems: list[str] = []
    by_order = {s.order: s for s in filled.stages}
    for stage in topic.stages:
        got = by_order.get(stage.order)
        if got is None:
            problems.append(f"stage {stage.order} ('{stage.title}') is missing")
            continue
        if stage.type in ("practice", "check"):
            if len(got.choices) < 2:
                problems.append(f"stage {stage.order} ('{stage.title}') needs at least 2 choices")
            elif not got.correct:
                problems.append(f"stage {stage.order} ('{stage.title}') needs a correct choice id")
    return problems
