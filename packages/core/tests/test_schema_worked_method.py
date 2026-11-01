"""Optional per-step ``worked_method`` (schema + step kids payload), same pattern as ``hint``."""
from __future__ import annotations

import pytest

from myroad_core.content.loader import _node_to_block
from myroad_core.content.schema import ContentNode


def _node(**extra) -> dict:
    return {"id": "p1", "type": "practice", "title": "t", "body_he": "כמה?", **extra}


def test_worked_method_is_optional() -> None:
    node = ContentNode.model_validate(_node())
    assert node.worked_method is None
    assert "worked_method" not in _node_to_block(node, 1).content["kids"]


def test_schema_accepts_worked_method() -> None:
    assert ContentNode.model_validate(_node(worked_method="2+3=5")).worked_method == "2+3=5"


def test_step_kids_expose_worked_method() -> None:
    pytest.importorskip("fastapi")
    from myroad_core.ui.platform_routes import _kids_payload

    block = _node_to_block(ContentNode.model_validate(_node(worked_method="שלב 1\nשלב 2")), 1)
    kids = _kids_payload(block.model_dump(mode="json", by_alias=True))
    assert kids["worked_method"] == "שלב 1\nשלב 2"
