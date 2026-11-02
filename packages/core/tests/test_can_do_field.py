"""Optional can_do line per step: schema field, loader kids, engagement preference."""

from __future__ import annotations

from myroad_core.content.loader import _node_to_block
from myroad_core.content.schema import ContentNode
from myroad_core.engagement import engagement_for
from test_engagement import Clock, _doc, _event, _progress, store  # noqa: F401


def _node(**kw):
    return ContentNode.model_validate({"type": "learn", "title": "T", "body_he": "B", **kw})


def test_can_do_optional_and_exposed_in_kids():
    assert _node().can_do is None
    assert "can_do" not in _node_to_block(_node(), 0).content["kids"]
    n = _node(can_do="לקרוא שעה")
    assert n.can_do == "לקרוא שעה"
    assert _node_to_block(n, 0).content["kids"]["can_do"] == "לקרוא שעה"


def test_engagement_can_do_prefers_field_then_title(store, monkeypatch):  # noqa: F811
    Clock(monkeypatch, "2026-11-02T08:00:00+02:00")
    doc = _doc(n=3)
    doc["blocks"][0]["content"] = {"kids": {"can_do": "Tell the time"}}
    engagement_for(store, "u_eng", doc)  # freeze today's session first
    _event(store, "b0", at="2026-11-02T08:05:00+02:00")
    _event(store, "b1", at="2026-11-02T08:01:00+02:00")
    _progress(store, {"b0", "b1"})
    assert sorted(engagement_for(store, "u_eng", doc)["session"]["can_do"]) == ["Step 1", "Tell the time"]
