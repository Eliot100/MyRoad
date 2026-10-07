"""PathGenerator interface + Cloudflare AI Gateway implementation.

GatewayPathGenerator calls Grok only through ui.cloudflare_gateway.call_grok_chat
(BYOK). It never reads or sends a provider API key.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Protocol, runtime_checkable

from myroad_core.agent_builder.models import (
    MIN_STAGES,
    MIN_TOPICS,
    FilledTopic,
    GoalSpec,
    PathOutline,
    check_filled_against_outline,
)
from myroad_core.agent_builder.parsing import ReplyParseError, parse_reply

LANGUAGE_NAMES = {"he": "Hebrew", "en": "English", "ar": "Arabic"}
LEVEL_NAMES = {
    "beginner": "a complete beginner",
    "elementary": "an elementary-school learner",
    "intermediate": "an intermediate learner",
    "advanced": "an advanced learner",
}


class GenerationError(RuntimeError):
    """Generation failed. ``code`` is stable; ``detail`` is short and secret-free."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


@runtime_checkable
class PathGenerator(Protocol):
    """Model behind the agent path builder."""

    name: str
    is_demo: bool

    def outline(self, spec: GoalSpec) -> PathOutline:
        """One call: structured outline (topics -> stages)."""

    def fill_topic(
        self,
        spec: GoalSpec,
        outline: PathOutline,
        topic_index: int,
        *,
        feedback: str | None = None,
    ) -> FilledTopic:
        """One call per topic: fill every stage of that topic."""


def validate_filled(outline: PathOutline, topic_index: int, filled: FilledTopic) -> FilledTopic:
    problems = check_filled_against_outline(outline.topics[topic_index], filled)
    if problems:
        raise ReplyParseError("; ".join(problems))
    return filled


SYSTEM_PROMPT = (
    "You are the MyRoad path-building agent. You design complete, long learning "
    "paths for a learning platform. You answer with exactly one JSON object and "
    "nothing else: no prose, no markdown, no code fences."
)

OUTLINE_SCHEMA = {
    "title": "path title",
    "summary": "one or two sentences for the catalog card",
    "emoji": "one emoji",
    "topics": [
        {
            "key": "t1",
            "title": "topic title",
            "emoji": "one emoji",
            "order": 1,
            "requires": [],
            "stages": [
                {
                    "title": "stage title",
                    "type": "explanation|practice|check|experience",
                    "channel": "write|read|listen|record|mouse",
                    "objective": "what the learner can do after this stage",
                    "order": 1,
                }
            ],
        }
    ],
}

FILL_SCHEMA = {
    "stages": [
        {
            "order": 1,
            "body": "explanation text, question, or activity instructions",
            "content_token": None,
            "choices": [{"id": "a", "label": "choice text"}],
            "correct": "a",
            "feedback_ok": "short praise",
            "feedback_try": "short hint for a wrong answer",
            "mastery": {"type": "tap_correct", "passingCriterion": "correct_choice"},
        }
    ]
}


def outline_messages(spec: GoalSpec) -> list[dict[str, str]]:
    topics, per_topic = spec.targets()
    ui = LANGUAGE_NAMES[spec.ui_locale]
    content = LANGUAGE_NAMES[spec.content_language]
    user = (
        f"Design a learning path outline.\n"
        f"Goal or topic: {spec.goal}\n"
        f"Subject: {spec.subject}\n"
        f"Learner: {LEVEL_NAMES[spec.level]}\n"
        f"Write titles and objectives in {ui}. Material being taught is in {content}.\n"
        f"Size: exactly {topics} topics with {per_topic} stages each "
        f"(never fewer than {MIN_TOPICS} topics or {MIN_STAGES} stages in total).\n"
        "Rules:\n"
        "- Every topic includes at least one explanation, one practice, and one check stage.\n"
        "- Usual stage order inside a topic: explanation, practice, experience, check.\n"
        "- type is one of explanation, practice, check, experience.\n"
        "- channel is one of write, read, listen, record, mouse (how the learner works).\n"
        "- order starts at 1 inside each topic; topics are ordered from 1.\n"
        "- requires lists keys of earlier topics that must be finished first.\n"
        "Return JSON with exactly this shape:\n"
        f"{json.dumps(OUTLINE_SCHEMA, ensure_ascii=False)}"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def fill_messages(
    spec: GoalSpec, outline: PathOutline, topic_index: int, feedback: str | None = None
) -> list[dict[str, str]]:
    topic = outline.topics[topic_index]
    ui = LANGUAGE_NAMES[spec.ui_locale]
    content = LANGUAGE_NAMES[spec.content_language]
    stages = [
        {
            "order": s.order,
            "title": s.title,
            "type": s.type,
            "channel": s.channel,
            "objective": s.objective,
        }
        for s in topic.stages
    ]
    earlier = [t.title for t in outline.topics[:topic_index]]
    user = (
        f"Path: {outline.title}\n"
        f"Goal: {spec.goal}\nSubject: {spec.subject}\nLearner: {LEVEL_NAMES[spec.level]}\n"
        f"Earlier topics: {json.dumps(earlier, ensure_ascii=False)}\n"
        f"Fill topic {topic.order}: {topic.title}\n"
        f"Stages: {json.dumps(stages, ensure_ascii=False)}\n"
        f"Write all learner-facing text in {ui}. When the taught material is in "
        f"{content} and differs from {ui}, put the target word or phrase in content_token; "
        "otherwise content_token is null.\n"
        "Rules:\n"
        "- One entry per stage, same order numbers.\n"
        "- explanation: body teaches the idea in 60-180 words; no choices; "
        'mastery {"type":"view_and_confirm","passingCriterion":"ack"}.\n'
        "- practice and check: body is the question; 3 or 4 choices with ids a, b, c, d; "
        'correct is exactly one choice id; mastery {"type":"tap_correct",'
        '"passingCriterion":"correct_choice"}.\n'
        "- experience: body gives hands-on instructions that fit the channel "
        "(record = say it aloud and record, write = write it down, listen = listen and "
        'repeat, read = read aloud, mouse = click through); no choices; mastery '
        '{"type":"complete_interaction","passingCriterion":"done"}.\n'
        "- feedback_ok and feedback_try are short and encouraging.\n"
    )
    if feedback:
        user += f"Reviewer feedback to apply to this topic: {feedback}\n"
    user += f"Return JSON with exactly this shape:\n{json.dumps(FILL_SCHEMA, ensure_ascii=False)}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


REPAIR_PROMPT = (
    "Your previous reply could not be used: {reason}. "
    "Reply again with only the corrected JSON object in the same shape. "
    "No prose and no code fences."
)


def _default_chat(timeout: float) -> Callable[[list[dict[str, str]]], str]:
    def chat(messages: list[dict[str, str]]) -> str:
        # Imported lazily so tests can monkeypatch the gateway module's urlopen.
        from myroad_core.ui import cloudflare_gateway as gw

        result = gw.call_grok_chat(
            messages, timeout=timeout, response_format={"type": "json_object"}
        )
        return str(result.get("content") or "")

    return chat


class GatewayPathGenerator:
    """Grok via Cloudflare AI Gateway BYOK. Strict JSON, one repair retry."""

    name = "gateway"
    is_demo = False

    def __init__(
        self,
        chat_fn: Callable[[list[dict[str, str]]], str] | None = None,
        *,
        timeout: float = 120.0,
    ) -> None:
        self._chat = chat_fn or _default_chat(timeout)
        self.calls = 0

    def _send(self, messages: list[dict[str, str]]) -> str:
        from myroad_core.ui.cloudflare_gateway import GatewayNotConfigured, GatewayRequestError

        self.calls += 1
        try:
            return self._chat(messages)
        except GatewayNotConfigured:
            raise GenerationError("gateway_not_configured") from None
        except GatewayRequestError as exc:
            raise GenerationError("gateway_request", f"HTTP {exc.status}") from None

    def _ask(self, messages: list[dict[str, str]], parse: Callable[[str], Any]) -> Any:
        reply = self._send(messages)
        try:
            return parse(reply)
        except ReplyParseError as first:
            repair = list(messages) + [
                {"role": "assistant", "content": reply[:8000]},
                {"role": "user", "content": REPAIR_PROMPT.format(reason=str(first)[:500])},
            ]
            second_reply = self._send(repair)
            try:
                return parse(second_reply)
            except ReplyParseError as second:
                raise GenerationError("bad_reply", str(second)[:300]) from None

    def outline(self, spec: GoalSpec) -> PathOutline:
        return self._ask(outline_messages(spec), lambda text: parse_reply(text, PathOutline))

    def fill_topic(
        self,
        spec: GoalSpec,
        outline: PathOutline,
        topic_index: int,
        *,
        feedback: str | None = None,
    ) -> FilledTopic:
        msgs = fill_messages(spec, outline, topic_index, feedback)
        return self._ask(
            msgs,
            lambda text: validate_filled(outline, topic_index, parse_reply(text, FilledTopic)),
        )
