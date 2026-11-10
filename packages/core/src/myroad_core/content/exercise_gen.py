"""Exercise generators for 5-unit teaching stages.

Each stage (topic) has one level. Fixed practice and check items stay in the
content files. They are the seeds and the fallback. A generated item carries
parameters, the answer, and distractors. ``check`` accepts only the answer
that those parameters produce.

The stream for a stage is, in order: every seed, cloze items whose prefix
already determines one answer inside that stage, then verbatim fragments of
the stage's own text with a new choice order when the stage does not hold
1,000 different questions. Nothing here adds a stage or a fact that is not
in the stage text.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass

from myroad_core.content.loader import load_content_paths
from myroad_core.content.schema import ContentNode, ContentPath, ContentTopic

_BLANK = re.compile(r"^(?P<pre>.*?)___(?P<post>.*)$", re.DOTALL)


@dataclass(frozen=True)
class Exercise:
    topic_id: str
    level: int
    parameters: tuple
    prompt: str
    choices: tuple[str, ...]
    answer: str

    @property
    def distractors(self) -> tuple[str, ...]:
        return tuple(c for c in self.choices if c != self.answer)


def _label(node: ContentNode) -> str | None:
    if not node.choices or isinstance(node.correct, list) or node.correct is None:
        return None
    for choice in node.choices:
        if choice.id == node.correct:
            return choice.label
    return None


def _labels(node: ContentNode) -> tuple[str, ...]:
    return tuple(choice.label for choice in (node.choices or []))


def _node_text(node: ContentNode) -> str:
    parts: list[str] = []
    for value in (
        node.title,
        node.body_he,
        node.body_en,
        node.body_ui,
        node.body_content,
        node.speak_text,
        node.hint,
        node.worked_method,
        node.feedback_ok,
        node.feedback_try,
        node.can_do,
    ):
        if value and value.strip():
            parts.append(value.strip())
    for choice in node.choices or []:
        if choice.label and choice.label.strip():
            parts.append(choice.label.strip())
    return "\n".join(parts)


def _seed_prompt(node: ContentNode) -> str:
    he = (node.body_he or "").strip()
    content = (node.body_content or "").strip()
    if he and content and he != content:
        return he + "\n" + content
    return content or he or (node.title or "").strip()


def _rotate(options: list[str], shift: int) -> tuple[str, ...]:
    n = len(options)
    shift %= n
    return tuple(options[shift:] + options[:shift])


class StageGenerator:
    """One stage. ``samples`` draws without replacement."""

    def __init__(self, path: ContentPath, topic: ContentTopic) -> None:
        self.path_id = path.id
        self.topic_id = topic.id
        self.level = int(topic.level or 0)
        by_id = {n.id: n for n in path.nodes if n.id}
        self._nodes: list[ContentNode] = [by_id[nid] for nid in topic.node_ids if nid in by_id]
        self._by_id = {n.id: n for n in self._nodes if n.id}
        self.source = "\n".join(piece for piece in (_node_text(n) for n in self._nodes) if piece)
        self._seeds = [n for n in self._nodes if n.type in ("practice", "check") and _label(n)]
        self._answer_for_prefix, self._posts, self._cloze_distractors = self._cloze_rule()

    def _cloze_rule(self) -> tuple[dict[str, str], tuple[str, ...], tuple[str, ...]]:
        """Prefix -> answer, only when every seed with that prefix agrees."""
        grouped: dict[str, set[str]] = {}
        posts: list[str] = []
        labels: list[str] = []
        for node in self._seeds:
            body = (node.body_content or "").strip()
            match = _BLANK.match(body)
            answer = _label(node)
            if not match or not answer or not match.group("pre").strip():
                continue
            prefix = re.sub(r"\s+", " ", match.group("pre")).strip()
            post = re.sub(r"\s+", " ", match.group("post")).strip()
            grouped.setdefault(prefix, set()).add(answer)
            if post:
                posts.append(post)
            labels.extend(_labels(node))
        usable = {prefix: next(iter(answers)) for prefix, answers in grouped.items() if len(answers) == 1}
        pool = tuple(dict.fromkeys(labels))
        # Distractors are choice labels already printed in this stage, minus the answer.
        return usable, tuple(dict.fromkeys(posts)), tuple(dict.fromkeys(pool))

    def check(self, exercise: Exercise, response: str) -> bool:
        return response == self.recompute(exercise)

    def recompute(self, exercise: Exercise) -> str:
        kind = exercise.parameters[0]
        if kind == "seed":
            node = self._by_id[exercise.parameters[1]]
            label = _label(node)
            if label is None:
                raise KeyError(exercise.parameters[1])
            return label
        if kind == "cloze":
            prefix = exercise.parameters[1]
            return self._answer_for_prefix[prefix]
        if kind == "span":
            start, length = exercise.parameters[1], exercise.parameters[2]
            return self.source[start : start + length]
        if kind == "order":
            base = Exercise(exercise.topic_id, exercise.level, exercise.parameters[1], "", (), "")
            return self.recompute(base)
        raise KeyError(kind)

    def _seed_exercises(self) -> list[Exercise]:
        out: list[Exercise] = []
        for node in self._seeds:
            answer = _label(node)
            choices = _labels(node)
            if answer is None or answer not in choices or len(choices) != len(set(choices)):
                continue
            out.append(
                Exercise(
                    topic_id=self.topic_id,
                    level=self.level,
                    parameters=("seed", node.id or ""),
                    prompt=_seed_prompt(node),
                    choices=choices,
                    answer=answer,
                )
            )
        return out

    def _cloze_exercises(self) -> list[Exercise]:
        if len(self._posts) < 1 or len(self._answer_for_prefix) < 1:
            return []
        out: list[Exercise] = []
        for prefix, post in itertools.product(self._answer_for_prefix, self._posts):
            answer = self._answer_for_prefix[prefix]
            distractors = [label for label in self._cloze_distractors if label != answer]
            # Keep the order stable and drop duplicates.
            picked: list[str] = []
            for label in distractors:
                if label not in picked:
                    picked.append(label)
                if len(picked) == 3:
                    break
            if len(picked) < 2:
                continue
            options = [answer, *picked[:3]]
            if len(set(options)) != len(options):
                continue
            prompt = f"{prefix} ___ {post}"
            out.append(
                Exercise(
                    topic_id=self.topic_id,
                    level=self.level,
                    parameters=("cloze", prefix, post),
                    prompt=prompt,
                    choices=_rotate(options, (len(prefix) + len(post)) % len(options)),
                    answer=answer,
                )
            )
        return out

    def _span_exercises(self, limit: int) -> list[Exercise]:
        text = self.source
        if len(text) < 8 or limit <= 0:
            return []
        instruction = "איזה קטע מופיע בשלב, כלשונו?"
        prompt = instruction + "\n" + text
        out: list[Exercise] = []
        seen_frag: set[str] = set()
        for length in (8, 12, 16, 20, 24, 32):
            if length >= len(text):
                continue
            for start in range(0, len(text) - length + 1):
                if len(out) >= limit:
                    return out
                frag = text[start : start + length]
                if frag in seen_frag or "\n" in frag or frag.strip() != frag:
                    continue
                distractors = _mutated(text, frag)
                if len(distractors) < 3:
                    continue
                seen_frag.add(frag)
                options = [frag, *distractors[:3]]
                out.append(
                    Exercise(
                        topic_id=self.topic_id,
                        level=self.level,
                        parameters=("span", start, length),
                        prompt=prompt,
                        choices=_rotate(options, start % 4),
                        answer=frag,
                    )
                )
        return out

    def _with_orders(self, base: list[Exercise], need: int) -> list[Exercise]:
        """Same checked answer, different choice order. Used only to fill the domain."""
        extra: list[Exercise] = []
        for exercise in base:
            n = len(exercise.choices)
            if n < 2:
                continue
            for perm in itertools.permutations(exercise.choices):
                if perm == exercise.choices:
                    continue
                extra.append(
                    Exercise(
                        topic_id=exercise.topic_id,
                        level=exercise.level,
                        parameters=("order", exercise.parameters, perm),
                        prompt=exercise.prompt,
                        choices=perm,
                        answer=exercise.answer,
                    )
                )
                if len(base) + len(extra) >= need:
                    return extra
        return extra

    def samples(self, n: int = 1000) -> list[Exercise]:
        pool = self._seed_exercises() + self._cloze_exercises()
        unique: list[Exercise] = []
        seen: set[tuple] = set()
        for exercise in pool:
            key = (exercise.prompt, exercise.choices, exercise.answer)
            if key in seen or exercise.answer not in exercise.choices:
                continue
            if len(set(exercise.choices)) != len(exercise.choices):
                continue
            seen.add(key)
            unique.append(exercise)
        if len(unique) < n:
            for exercise in self._span_exercises(n - len(unique)):
                key = (exercise.prompt, exercise.choices, exercise.answer)
                if key in seen:
                    continue
                seen.add(key)
                unique.append(exercise)
                if len(unique) >= n:
                    break
        if len(unique) < n:
            for exercise in self._with_orders(unique, n):
                key = (exercise.prompt, exercise.choices, exercise.answer)
                if key in seen:
                    continue
                seen.add(key)
                unique.append(exercise)
                if len(unique) >= n:
                    break
        return unique[:n]


def _mutated(source: str, frag: str) -> list[str]:
    """Three strings that are one character off and do not occur in the stage."""
    alphabet: list[str] = []
    for ch in frag:
        if ch.isspace() or ch in alphabet:
            continue
        alphabet.append(ch)
        if len(alphabet) == 8:
            break
    if len(alphabet) < 2:
        return []
    found: list[str] = []
    positions = [0, len(frag) // 2, len(frag) - 1]
    for index in positions:
        ch = frag[index]
        for repl in alphabet:
            if repl == ch:
                continue
            bad = frag[:index] + repl + frag[index + 1 :]
            if bad in source or bad in found:
                continue
            found.append(bad)
            if len(found) == 3:
                return found
    return found


def teaching_generators(paths: list[ContentPath] | None = None) -> list[StageGenerator]:
    loaded = paths if paths is not None else load_content_paths()
    out: list[StageGenerator] = []
    for path in loaded:
        if getattr(path, "unavailable", False) or "_bagrut5_" not in path.id or "placement" in path.id:
            continue
        for topic in path.topics or []:
            if topic.level not in (1, 2, 3):
                continue
            out.append(StageGenerator(path, topic))
    return out
