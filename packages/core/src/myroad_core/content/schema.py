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
    "math": {"he": "מתמטיקה", "color": "#5b8def", "emoji": "🔢"},
    "english": {"he": "אנגלית", "color": "#3db88a", "emoji": "🔤"},
    "physics": {"he": "פיזיקה", "color": "#9b7bde", "emoji": "🔬"},
    "piano": {"he": "פסנתר", "color": "#e08a4d", "emoji": "🎹"},
    "general": {"he": "כללי", "color": "#6b7280", "emoji": "📚"},
}

GROUPS: dict[str, dict[str, str]] = {
    "grade3": {
        "id": "grade3",
        "title_he": "דרכים לתלמידי כיתה ג׳",
        "blurb_he": "אוסף קצר של דרכי למידה לדוגמה — מתמטיקה, אנגלית, פיזיקה ופסנתר.",
    },
}


class ContentChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    emoji: str | None = None


class ContentNode(BaseModel):
    """One step in a learning path (learn / practice / check / …)."""

    model_config = ConfigDict(extra="forbid")

    type: NodeType
    title: str
    body_he: str
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


class ContentPath(BaseModel):
    """Sample path document stored as JSON under content/."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title_he: str
    subject: SubjectId
    grade: int | None = None
    group_ids: list[str] = Field(default_factory=lambda: ["grade3"])
    emoji: str
    blurb_he: str
    estimated_minutes: int = Field(ge=1, le=60)
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


def validate_content_path(data: dict[str, Any]) -> ContentPath:
    return ContentPath.model_validate(data)
