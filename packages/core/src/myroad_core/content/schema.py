"""Age-agnostic content schema for sample learning paths (JSON files)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NodeType = Literal[
    "learn",
    "practice",
    "check",
    "celebrate",
    "speak",
    "piano_keys",
    "rhythm",
]

SubjectId = Literal["math", "english", "physics", "piano", "general"]

SUBJECTS: dict[str, dict[str, str]] = {
    "math": {"he": "מתמטיקה", "en": "Math", "ar": "رياضيات", "color": "#5b8def", "emoji": "🔢"},
    "english": {"he": "אנגלית", "en": "English", "ar": "إنجليزي", "color": "#3db88a", "emoji": "🔤"},
    "physics": {"he": "פיזיקה", "en": "Physics", "ar": "فيزياء", "color": "#9b7bde", "emoji": "🔬"},
    "piano": {"he": "פסנתר", "en": "Piano", "ar": "بيانو", "color": "#e08a4d", "emoji": "🎹"},
    "general": {"he": "כללי", "en": "General", "ar": "عام", "color": "#6b7280", "emoji": "📚"},
}

GROUPS: dict[str, dict[str, str]] = {
    "grade3": {
        "id": "grade3",
        "title_he": "דרכים לתלמידי כיתה ג׳",
        "title_en": "Paths for Grade 3",
        "title_ar": "مسارات للصف الثالث",
        "blurb_he": "אוסף קצר של דרכי למידה לדוגמה — מתמטיקה, אנגלית, פיזיקה ופסנתר.",
        "blurb_en": "A short set of sample learning paths — math, English, physics, and piano.",
        "blurb_ar": "مجموعة قصيرة من مسارات التعلم التجريبية — رياضيات وإنجليزي وفيزياء وبيانو.",
    },
}


class ContentChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    emoji: str | None = None
    label_en: str | None = None
    label_he: str | None = None


class ContentNode(BaseModel):
    """One step in a learning path (learn / practice / check / …)."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    type: NodeType
    title: str
    title_en: str | None = None
    body_he: str
    body_en: str | None = None
    speak_text: str | None = None
    choices: list[ContentChoice] | None = None
    correct: str | list[str] | None = None
    media_hint: str | None = None
    keys: list[str] | None = None
    target_sequence: list[str] | None = None
    pattern: list[int] | None = None
    record: bool = False
    feedback_ok: str | None = None
    feedback_try: str | None = None

    @model_validator(mode="after")
    def _validate_interactive(self) -> ContentNode:
        if self.type in ("practice", "check") and self.choices:
            if self.correct is None:
                raise ValueError(f"node '{self.title}': choices require 'correct'")
            ids = {c.id for c in self.choices}
            corrects = self.correct if isinstance(self.correct, list) else [self.correct]
            missing = [c for c in corrects if c not in ids]
            if missing:
                raise ValueError(f"node '{self.title}': correct ids not in choices: {missing}")
        if self.type == "piano_keys" and not self.keys:
            raise ValueError(f"node '{self.title}': piano_keys requires keys")
        if self.type == "rhythm" and not self.pattern:
            raise ValueError(f"node '{self.title}': rhythm requires pattern")
        return self


class ContentTopic(BaseModel):
    """A station on the visual path map (groups several learning steps)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title_he: str
    title_en: str | None = None
    title_ar: str | None = None
    emoji: str | None = None
    node_ids: list[str] = Field(min_length=1)


class ContentPath(BaseModel):
    """Sample path document stored as JSON under content/."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title_he: str
    title_en: str | None = None
    subject: SubjectId
    grade: int | None = None
    group_ids: list[str] = Field(default_factory=lambda: ["grade3"])
    emoji: str
    blurb_he: str
    blurb_en: str | None = None
    estimated_minutes: int = Field(ge=1, le=60)
    topics: list[ContentTopic] | None = None
    nodes: list[ContentNode] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not v.startswith("path_"):
            raise ValueError("path id must start with 'path_'")
        return v

    @field_validator("group_ids")
    @classmethod
    def _known_groups(cls, v: list[str]) -> list[str]:
        unknown = [g for g in v if g not in GROUPS]
        if unknown:
            raise ValueError(f"unknown group_ids: {unknown}")
        return v

    @model_validator(mode="after")
    def _assign_node_ids_and_topics(self) -> ContentPath:
        # Ensure every node has a stable id
        used: set[str] = set()
        new_nodes: list[ContentNode] = []
        for i, node in enumerate(self.nodes):
            nid = node.id or f"n{i:03d}_{node.type}"
            if nid in used:
                raise ValueError(f"duplicate node id: {nid}")
            used.add(nid)
            if node.id != nid:
                node = node.model_copy(update={"id": nid})
            new_nodes.append(node)
        object.__setattr__(self, "nodes", new_nodes)

        if self.topics:
            node_id_set = {n.id for n in self.nodes if n.id}
            for topic in self.topics:
                missing = [x for x in topic.node_ids if x not in node_id_set]
                if missing:
                    raise ValueError(f"topic '{topic.id}' references unknown node_ids: {missing}")
        return self


def infer_topics(path: ContentPath) -> list[ContentTopic]:
    """Group nodes into topic stations when content omits topics[]."""
    if path.topics:
        return list(path.topics)

    nodes = path.nodes
    if not nodes:
        return []

    topics: list[ContentTopic] = []
    bucket: list[ContentNode] = []
    topic_idx = 0

    def flush(title_he: str | None = None, title_en: str | None = None, emoji: str | None = None) -> None:
        nonlocal topic_idx, bucket
        if not bucket:
            return
        topic_idx += 1
        first = bucket[0]
        topics.append(
            ContentTopic(
                id=f"topic_{topic_idx:02d}",
                title_he=title_he or first.title,
                title_en=title_en or first.title_en or first.title,
                emoji=emoji or path.emoji,
                node_ids=[n.id for n in bucket if n.id],
            )
        )
        bucket = []

    for node in nodes:
        if node.type == "celebrate":
            flush()
            bucket = [node]
            flush(title_he="סיום", title_en="Finish", emoji="🎉")
            continue
        if node.type == "learn" and bucket:
            flush()
        bucket.append(node)
        # Keep stations small: learn + up to ~3 follow-ons
        if len(bucket) >= 4:
            flush()
    flush()
    return topics


def validate_content_path(data: dict[str, Any]) -> ContentPath:
    return ContentPath.model_validate(data)
