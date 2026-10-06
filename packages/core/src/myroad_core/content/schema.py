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

GROUPS: dict[str, dict[str, Any]] = {
    "grade3": {
        "id": "grade3",
        "titles": {
            "he": "דרכים לתלמידי כיתה ג׳",
            "en": "Paths for Grade 3",
            "ar": "مسارات للصف الثالث",
        },
        "blurbs": {
            "he": "אוסף קצר של דרכי למידה לדוגמה — מתמטיקה, אנגלית, פיזיקה ופסנתר.",
            "en": "A short set of sample learning paths — math, English, physics, and piano.",
            "ar": "مجموعة قصيرة من مسارات التعلم التجريبية — رياضيات وإنجليزي وفيزياء وبيانو.",
        },
        # Legacy aliases (templates/tests may still read title_he)
        "title_he": "דרכים לתלמידי כיתה ג׳",
        "title_en": "Paths for Grade 3",
        "title_ar": "مسارات للصف الثالث",
        "blurb_he": "אוסף קצר של דרכי למידה לדוגמה — מתמטיקה, אנגלית, פיזיקה ופסנתר.",
        "blurb_en": "A short set of sample learning paths — math, English, physics, and piano.",
        "blurb_ar": "مجموعة قصيرة من مسارات التعلم التجريبية — رياضيات وإنجليزي وفيزياء وبيانو.",
    },
    "agent": {
        "id": "agent",
        "titles": {
            "he": "דרכים שנבנו עם הסוכן",
            "en": "Agent-built paths",
            "ar": "مسارات بناها الوكيل",
        },
        "blurbs": {
            "he": "דרכי למידה מלאות שנבנו עם סוכן בניית הדרכים ופורסמו.",
            "en": "Full learning paths built with the path-building agent and published.",
            "ar": "مسارات تعلم كاملة بُنيت مع وكيل بناء المسارات ونُشرت.",
        },
        "title_he": "דרכים שנבנו עם הסוכן",
        "title_en": "Agent-built paths",
        "title_ar": "مسارات بناها الوكيل",
        "blurb_he": "דרכי למידה מלאות שנבנו עם סוכן בניית הדרכים ופורסמו.",
        "blurb_en": "Full learning paths built with the path-building agent and published.",
        "blurb_ar": "مسارات تعلم كاملة بُنيت مع وكيل بناء المسارات ونُشرت.",
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
    """One step in a learning path (learn / practice / check / …).

    Locale split:
      - body_he / body_en / body_ui — explanations follow platform UI locale
      - body_content / speak_text — target vocabulary in content_locale
      - speak_ui — optional TTS for the explanation (UI locale)
    """

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    type: NodeType
    title: str
    title_en: str | None = None
    body_he: str = ""
    body_en: str | None = None
    body_ui: str | None = None
    body_content: str | None = None
    speak_text: str | None = None
    speak_ui: str | None = None
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
    def _require_explanation(self) -> ContentNode:
        if not (self.body_he or self.body_ui or self.body_en):
            raise ValueError(f"node '{self.title}': need body_he, body_ui, or body_en explanation")
        return self

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
    titles: dict[str, str] = Field(default_factory=dict)
    # Legacy flat fields — merged into titles on validate
    title_he: str | None = None
    title_en: str | None = None
    title_ar: str | None = None
    emoji: str | None = None
    node_ids: list[str] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _merge_titles(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        from myroad_core.ui.i18n import merge_locale_fields

        titles = merge_locale_fields(data, map_key="titles", legacy_prefix="title")
        data = dict(data)
        data["titles"] = titles
        # Keep legacy mirrors for callers/tests
        data["title_he"] = titles.get("he") or data.get("title_he")
        data["title_en"] = titles.get("en") or data.get("title_en")
        data["title_ar"] = titles.get("ar") or data.get("title_ar")
        return data

    @model_validator(mode="after")
    def _require_he_title(self) -> ContentTopic:
        if not (self.titles.get("he") or self.title_he or "").strip():
            raise ValueError(f"topic '{self.id}': titles.he (or title_he) required")
        if not self.title_he:
            object.__setattr__(self, "title_he", self.titles.get("he"))
        return self


class ContentPath(BaseModel):
    """Sample path document stored as JSON under content/.

    Locale fields:
      titles / blurbs — catalog/card chrome maps keyed by UI locale code
      legacy title_he / title_en / title_ar + blurb_* still accepted and merged into maps
      explain_locale — language of authored explanations (matches UI when possible)
      content_locale — language of tokens being taught (e.g. en for English paths)
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    titles: dict[str, str] = Field(default_factory=dict)
    blurbs: dict[str, str] = Field(default_factory=dict)
    # Legacy flat fields (optional) — merged into titles/blurbs
    title_he: str | None = None
    title_en: str | None = None
    title_ar: str | None = None
    subject: SubjectId
    grade: int | None = None
    group_ids: list[str] = Field(default_factory=lambda: ["grade3"])
    emoji: str
    blurb_he: str | None = None
    blurb_en: str | None = None
    blurb_ar: str | None = None
    explain_locale: str = "he"
    content_locale: str = "he"
    estimated_minutes: int = Field(ge=1, le=60)
    topics: list[ContentTopic] | None = None
    nodes: list[ContentNode] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _merge_chrome_maps(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        from myroad_core.ui.i18n import merge_locale_fields

        data = dict(data)
        titles = merge_locale_fields(data, map_key="titles", legacy_prefix="title")
        blurbs = merge_locale_fields(data, map_key="blurbs", legacy_prefix="blurb")
        data["titles"] = titles
        data["blurbs"] = blurbs
        data["title_he"] = titles.get("he") or data.get("title_he")
        data["title_en"] = titles.get("en") or data.get("title_en")
        data["title_ar"] = titles.get("ar") or data.get("title_ar")
        data["blurb_he"] = blurbs.get("he") or data.get("blurb_he")
        data["blurb_en"] = blurbs.get("en") or data.get("blurb_en")
        data["blurb_ar"] = blurbs.get("ar") or data.get("blurb_ar")
        return data

    @model_validator(mode="after")
    def _require_he_chrome(self) -> ContentPath:
        if not (self.titles.get("he") or self.title_he or "").strip():
            raise ValueError(f"{self.id}: titles.he (or title_he) required")
        if not (self.blurbs.get("he") or self.blurb_he or "").strip():
            raise ValueError(f"{self.id}: blurbs.he (or blurb_he) required")
        # Keep mirrors populated for older callers
        if not self.title_he:
            object.__setattr__(self, "title_he", self.titles.get("he"))
        if not self.blurb_he:
            object.__setattr__(self, "blurb_he", self.blurbs.get("he"))
        return self

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
    def _default_locales_for_subject(self) -> ContentPath:
        # English-learning demos teach EN tokens; explanations default to HE.
        if self.subject == "english":
            updates: dict[str, Any] = {}
            if self.content_locale == "he":
                updates["content_locale"] = "en"
            if not self.explain_locale:
                updates["explain_locale"] = "he"
            if updates:
                object.__setattr__(self, "content_locale", updates.get("content_locale", self.content_locale))
                object.__setattr__(self, "explain_locale", updates.get("explain_locale", self.explain_locale))
        return self

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
                titles={
                    "he": title_he or first.title,
                    "en": title_en or first.title_en or first.title,
                },
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
