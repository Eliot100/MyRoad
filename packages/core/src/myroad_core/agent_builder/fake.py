"""Deterministic demo generator: builds a full Hebrew path without any model call."""
from __future__ import annotations

from typing import Any

from myroad_core.agent_builder.generator import GenerationError, keep_known_prerequisites
from myroad_core.agent_builder.models import (
    FilledStage,
    FilledTopic,
    GoalSpec,
    OutlineStage,
    OutlineTopic,
    PathOutline,
    StageChoice,
    StageMastery,
)
from myroad_core.content.schema import SCORE_GROUPS

DEMO_PREFIX = "דמו: "

# Demo score link for psychometric paths: subject -> part of the shared 200-800 score.
_PSYCHOMETRIC_PART = {"math": "quantitative", "hebrew": "verbal", "english": "english", "general": "writing"}

_TOPIC_THEMES: list[tuple[str, str]] = [
    ("מושגי יסוד", "🧱"),
    ("צעדים ראשונים", "👣"),
    ("תרגול מודרך", "🧭"),
    ("יישום בעולם האמיתי", "🌍"),
    ("טעויות נפוצות", "🔍"),
    ("סיכום ואתגר", "🏁"),
]

# (type, channel, title template, objective template)
_STAGE_PATTERNS: dict[int, list[tuple[str, str, str, str]]] = {
    4: [
        ("explanation", "read", "מה זה {topic}?", "להסביר במילים שלי את הרעיון של {topic}"),
        ("practice", "mouse", "תרגול: {topic}", "לבחור את התשובה הנכונה בשאלה על {topic}"),
        ("experience", "record", "אומרים בקול: {topic}", "להסביר בקול את {topic} ולהקליט"),
        ("check", "mouse", "בדיקה: {topic}", "להראות שליטה ב{topic} בשאלת בדיקה"),
    ],
    5: [
        ("explanation", "read", "מה זה {topic}?", "להסביר במילים שלי את הרעיון של {topic}"),
        ("practice", "mouse", "תרגול ראשון: {topic}", "לבחור את התשובה הנכונה בשאלה על {topic}"),
        ("experience", "write", "כותבים דוגמה: {topic}", "לכתוב דוגמה משלי ל{topic}"),
        ("practice", "mouse", "תרגול שני: {topic}", "לזהות שימוש נכון ב{topic}"),
        ("check", "mouse", "בדיקה: {topic}", "להראות שליטה ב{topic} בשאלת בדיקה"),
    ],
}

_MASTERY = {
    "explanation": StageMastery(type="view_and_confirm", passingCriterion="ack"),
    "practice": StageMastery(type="tap_correct", passingCriterion="correct_choice"),
    "check": StageMastery(type="tap_correct", passingCriterion="correct_choice"),
    "experience": StageMastery(type="complete_interaction", passingCriterion="done"),
}

_EXPERIENCE_BODY = {
    "record": "לחצו על כפתור ההקלטה והסבירו בקול, בשניים־שלושה משפטים, מה למדתם על {topic}. אחר כך האזינו להקלטה.",
    "write": "קחו דף ועט וכתבו דוגמה משלכם ל{topic}. בדקו שהדוגמה מתאימה להסבר שקראתם.",
    "listen": "הקשיבו להסבר על {topic} וחזרו עליו בקול במילים שלכם.",
    "read": "קראו בקול את ההסבר על {topic} וסמנו לעצמכם את המילה החשובה ביותר.",
    "mouse": "עברו בעכבר על השלבים של {topic} אחד אחרי השני ולחצו המשך בסוף.",
}


def _short_goal(goal: str, limit: int = 60) -> str:
    goal = " ".join(goal.split())
    return goal if len(goal) <= limit else goal[: limit - 1].rstrip() + "…"


class FakePathGenerator:
    """Deterministic, offline PathGenerator used by demo mode and tests.

    ``fail_topics`` holds topic indexes that raise GenerationError on fill, so
    tests can exercise a failure in the middle of a build.
    """

    name = "demo"
    is_demo = True

    def __init__(self, *, fail_topics: set[int] | None = None) -> None:
        self.fail_topics: set[int] = set(fail_topics or set())
        self.calls = 0

    def outline(self, spec: GoalSpec, *, existing_paths: list[dict[str, Any]] | None = None) -> PathOutline:
        self.calls += 1
        n_topics, per_topic = spec.targets()
        pattern = _STAGE_PATTERNS[5 if per_topic >= 5 else 4]
        goal = _short_goal(spec.goal)
        topics: list[OutlineTopic] = []
        for i in range(n_topics):
            theme, emoji = _TOPIC_THEMES[i % len(_TOPIC_THEMES)]
            topic_title = f"{theme} — {goal}"
            # Interleaved review: from the second topic on, the second practice stage
            # (5-stage pattern) or the experience stage (4-stage pattern) mixes up to
            # two EARLIER topics.
            review_at = None
            if i >= 1:
                review_at = 4 if len(pattern) >= 5 else 3
            earlier = [f"t{k + 1}" for k in range(max(0, i - 2), i)]
            stages = []
            for j, (stype, channel, title, objective) in enumerate(pattern):
                is_review = review_at == j + 1
                if is_review:
                    earlier_names = " + ".join(_TOPIC_THEMES[int(k[1:]) - 1][0] for k in earlier)
                    stype, channel = "practice", "mouse"
                    title = f"חזרה מעורבת: {earlier_names} + {theme}"
                    objective = f"לפתור שאלה שמערבבת את {earlier_names} עם {theme}"
                stages.append(
                    OutlineStage(
                        title=title.format(topic=theme),
                        type=stype,  # type: ignore[arg-type]
                        channel=channel,  # type: ignore[arg-type]
                        objective=objective.format(topic=theme),
                        order=j + 1,
                        kind="review" if is_review else "understanding",
                        review_topic_ids=list(earlier) if is_review else [],
                    )
                )
            topics.append(
                OutlineTopic(
                    key=f"t{i + 1}",
                    title=topic_title,
                    emoji=emoji,
                    order=i + 1,
                    requires=[f"t{i}"] if i > 0 else [],
                    stages=stages,
                )
            )
        score = None
        part = _PSYCHOMETRIC_PART.get(spec.subject)
        if spec.audience == "psychometric" and part:
            score = {"group_id": next(iter(SCORE_GROUPS)), "part_id": part, "weight": 1}
        # Realistic prerequisite: the first published path offered in the same subject.
        prereqs = [str(p["pathId"]) for p in (existing_paths or [])[:1] if p.get("pathId")]
        outline = PathOutline(
            title=f"{DEMO_PREFIX}{goal}",
            summary=f"דרך לימוד לדוגמה (מצב דמו) על {goal}: הסבר, תרגול, התנסות ובדיקה בכל נושא.",
            emoji="🧪",
            topics=topics,
            prerequisite_path_ids=prereqs,
            score=score,
        )
        return keep_known_prerequisites(outline, existing_paths)

    def fill_topic(
        self,
        spec: GoalSpec,
        outline: PathOutline,
        topic_index: int,
        *,
        feedback: str | None = None,
    ) -> FilledTopic:
        self.calls += 1
        if topic_index in self.fail_topics:
            raise GenerationError("bad_reply", f"demo failure for topic {topic_index + 1}")
        topic = outline.topics[topic_index]
        theme = topic.title.split(" — ")[0]
        goal = _short_goal(spec.goal)
        stages: list[FilledStage] = []
        for stage in topic.stages:
            correct_id = "abc"[(topic_index + stage.order) % 3]
            if stage.type == "explanation":
                body = (
                    f"בשלב הזה נכיר את {theme} בהקשר של {goal}. "
                    f"נתחיל מהרעיון המרכזי: {stage.objective}. "
                    "קראו את ההסבר לאט, חשבו על דוגמה מהחיים שלכם, ואז לחצו המשך."
                )
                if feedback:
                    body += f" (עודכן לפי משוב: {feedback})"
                stages.append(
                    FilledStage(order=stage.order, body=body, mastery=_MASTERY["explanation"],
                                feedback_ok="מצוין, ממשיכים!")
                )
            elif stage.type in ("practice", "check"):
                labels = {
                    "a": f"תשובה א׳ על {theme}",
                    "b": f"תשובה ב׳ על {theme}",
                    "c": f"תשובה ג׳ על {theme}",
                }
                labels[correct_id] = f"התשובה הנכונה: {stage.objective}"
                verb = "תרגול" if stage.type == "practice" else "בדיקה"
                body = f"{verb}: איזו מהתשובות מתארת נכון את {theme}?"
                if stage.kind == "review":
                    mixed = [t.title.split(" — ")[0] for t in outline.topics if t.key in stage.review_topic_ids]
                    body = (
                        f"חזרה מעורבת: השאלה הזאת משלבת את {' ואת '.join(mixed + [theme])}. "
                        "איזו תשובה נכונה?"
                    )
                stages.append(
                    FilledStage(
                        order=stage.order,
                        body=body,
                        choices=[StageChoice(id=k, label=v) for k, v in labels.items()],
                        correct=correct_id,
                        feedback_ok="נכון! כל הכבוד.",
                        feedback_try="כמעט. קראו שוב את ההסבר ונסו שוב.",
                        mastery=_MASTERY[stage.type],
                    )
                )
            else:
                body = _EXPERIENCE_BODY.get(stage.channel, _EXPERIENCE_BODY["mouse"]).format(topic=theme)
                stages.append(
                    FilledStage(order=stage.order, body=body, mastery=_MASTERY["experience"],
                                feedback_ok="יפה מאוד, סיימתם את ההתנסות.")
                )
        return FilledTopic(stages=stages)
