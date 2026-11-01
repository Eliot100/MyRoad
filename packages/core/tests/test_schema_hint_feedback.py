"""Optional per-step ``hint`` and per-choice ``feedback`` (schema + step kids payload)."""
from __future__ import annotations

import pytest

from myroad_core.content.loader import _node_to_block
from myroad_core.content.schema import ContentChoice, ContentNode


def _node(**extra) -> dict:
    return {"id": "p1", "type": "practice", "title": "t", "body_he": "כמה?",
            "choices": [{"id": "a", "label": "1"}, {"id": "b", "label": "2"}], "correct": "b", **extra}


def test_fields_are_optional_and_default_none() -> None:
    node = ContentNode.model_validate(_node())
    assert node.hint is None
    assert all(c.feedback is None for c in node.choices or [])
    kids = _node_to_block(node, 1).content["kids"]
    assert "hint" not in kids
    assert all("feedback" not in c for c in kids["choices"])


def test_schema_accepts_hint_and_choice_feedback() -> None:
    doc = _node(hint="חשבו על חיבור.")
    doc["choices"][0]["feedback"] = "1 קטן מדי."
    node = ContentNode.model_validate(doc)
    assert node.hint == "חשבו על חיבור."
    assert node.choices[0].feedback == "1 קטן מדי."
    assert ContentChoice(id="x", label="y", feedback="z").feedback == "z"


def test_unknown_fields_still_rejected() -> None:
    with pytest.raises(ValueError):
        ContentNode.model_validate(_node(hints="x"))


def test_step_kids_expose_hint_and_choice_feedback() -> None:
    """Routes read step data via block.content.kids (_kids_payload), like media_hint/feedback_try."""
    pytest.importorskip("fastapi")
    from myroad_core.ui.platform_routes import _kids_payload

    doc = _node(hint="רמז", media_hint="img", feedback_try="נסו שוב")
    doc["choices"][1]["feedback"] = "נכון, 2."
    block = _node_to_block(ContentNode.model_validate(doc), 1)
    kids = _kids_payload(block.model_dump(mode="json", by_alias=True))
    assert kids["hint"] == "רמז"
    assert kids["media_hint"] == "img" and kids["feedback_try"] == "נסו שוב"
    assert kids["choices"][1]["feedback"] == "נכון, 2."
    assert "feedback" not in kids["choices"][0]
