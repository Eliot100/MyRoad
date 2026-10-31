"""Step variant_of (decision 0003): schema, selection, no duplicate tiles, rollup, Arabic, routing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from myroad_core.content.loader import content_to_path_version
from myroad_core.content.schema import SUBJECTS, SubjectId, validate_content_path
from myroad_core.content.variants import route_by_band, select_variants
from myroad_core.store import PathStore

TAGS = {(True, False): "", (False, False): " (no audio)", (True, True): " (writing)", (False, True): " (no audio, writing)"}


def _node(nid, title, base=None, when=None):
    n = {"id": nid, "type": "learn", "title": title, "body_he": "הסבר."}
    if base:
        n["variant_of"], n["variant_when"] = base, when
    return n


def _path(nodes, pid="path_arabic_test", **extra):
    return {
        "id": pid, "subject": "arabic", "group_ids": ["adult"], "emoji": "ع", "estimated_minutes": 10,
        "titles": {"he": "ערבית"}, "blurbs": {"he": "בדיקה."},
        "topics": [{"id": "t0", "titles": {"he": "נושא"}, "emoji": "ع", "node_ids": [n["id"] for n in nodes]}],
        "nodes": nodes, **extra,
    }


def _tile(base, *, writing=True):
    out = []
    for (a, w), tag in TAGS.items():
        if w and not writing:
            continue
        nid = f"{base}__a{int(a)}w{int(w)}"
        if (a, w) == (True, False):
            out.append(_node(nid, base))
        else:
            out.append(_node(nid, base + tag, f"{base}__a1w0", {"audio": a, "writing": w}))
    return out


def _doc(nodes):
    return content_to_path_version(validate_content_path(_path(nodes))).model_dump(mode="json", by_alias=True)


# --- schema ---

def test_valid_variant_of():
    p = validate_content_path(_path(_tile("x")))
    assert p.nodes[1].variant_of == "x__a1w0" and p.nodes[1].variant_when.audio is False


def test_dangling_variant_of_rejected():
    with pytest.raises(ValidationError, match="not a step in this path"):
        validate_content_path(_path([_node("a", "A"), _node("b", "B", "missing", {"audio": False})]))


def test_chained_variant_of_rejected():
    nodes = [_node("a", "A"), _node("b", "B", "a", {"audio": False}), _node("c", "C", "b", {"writing": True})]
    with pytest.raises(ValidationError, match="no chains or cycles"):
        validate_content_path(_path(nodes))


def test_self_cycle_rejected():
    with pytest.raises(ValidationError, match="no chains or cycles"):
        validate_content_path(_path([_node("a", "A", "a", {"audio": False})]))


def test_variant_of_needs_when():
    with pytest.raises(ValidationError, match="go together"):
        validate_content_path(_path([_node("a", "A"), {**_node("b", "B"), "variant_of": "a"}]))


# --- selection ---

@pytest.mark.parametrize("audio,writing", list(TAGS))
def test_selection_all_four_settings(audio, writing):
    doc = select_variants(_doc(_tile("x")), {"audio": audio, "writing": writing})
    assert [b["title"] for b in doc["blocks"]] == ["x" + TAGS[(audio, writing)]]


@pytest.mark.parametrize("audio,writing", list(TAGS))
def test_fallback_to_base_when_no_variant_matches(audio, writing):
    # a speak-like tile: only base (a1w0) and a0w0 exist
    doc = select_variants(_doc(_tile("s", writing=False)), {"audio": audio, "writing": writing})
    expected = "s (no audio)" if (audio, writing) == (False, False) else "s"
    assert [b["title"] for b in doc["blocks"]] == [expected]


def test_no_duplicate_tiles():
    doc = select_variants(_doc(_tile("x") + _tile("y") + [_node("z", "Z")]))
    assert [b["title"] for b in doc["blocks"]] == ["x", "y", "Z"]
    ids = [b["blockId"] for b in doc["blocks"]]
    assert len(set(ids)) == 3 and doc["topics"][0]["node_ids"] == ["x__a1w0", "y__a1w0", "z"]
    assert len(doc["edges"]) == 2


def test_progress_rolls_up_to_base(tmp_path: Path):
    full = _doc(_tile("x"))
    base_bid = full["blocks"][0]["blockId"]
    for a, w in TAGS:
        assert select_variants(full, {"audio": a, "writing": w})["blocks"][0]["blockId"] == base_bid
    store = PathStore(str(tmp_path / "p.db"))
    try:
        store.upsert_learner("u1", "U")
        assert store.get_step_settings("u1") == {"audio": True, "writing": False}
        store.set_step_settings("u1", audio=False, writing=True)
        shown = select_variants(full, store.get_step_settings("u1"))["blocks"][0]
        assert shown["title"] == "x (no audio, writing)"
        store.record_step_event("u1", "path_arabic_test", shown["blockId"], "mastery")
        agg = store.step_aggregates("u1", "path_arabic_test")
        assert [(r["blockId"], r["mastered"]) for r in agg] == [(base_bid, True)]
    finally:
        store.close()


def test_vendored_arabic_path_has_no_duplicates_when_mapped():
    """PR #16 content mapped to variant_of (suffix != __a1w0) shows one tile per base."""
    import os

    root = Path(os.environ.get("CONTENT_DIR", "content")) / "adult" / "path_arabic_bagrut5_01_script.json"
    if not root.exists():
        pytest.skip("vendored content not present")
    data = json.loads(root.read_text(encoding="utf-8"))
    for n in data["nodes"]:
        base, _, suf = n["id"].rpartition("__")
        if base and suf != "a1w0":
            n["variant_of"] = f"{base}__a1w0"
            n["variant_when"] = {"audio": suf[1] == "1", "writing": suf[3] == "1"}
    doc = content_to_path_version(validate_content_path(data)).model_dump(mode="json", by_alias=True)
    for a, w in TAGS:
        shown = select_variants(doc, {"audio": a, "writing": w})["blocks"]
        bases = {(b["content"].get("baseNodeId") or b["content"]["nodeId"]) for b in shown}
        assert len(shown) == len(bases) == sum(1 for n in data["nodes"] if "variant_of" not in n)


# --- subject + routing ---

def test_arabic_subject_listed():
    from typing import get_args

    from myroad_core.agent_builder.models import SUBJECT_IDS
    from myroad_core.ui.i18n import subject_label

    assert "arabic" in get_args(SubjectId) and "arabic" in SUBJECT_IDS
    assert SUBJECTS["arabic"]["he"] == "ערבית" and subject_label("arabic", "en") == "Arabic"


def test_placement_route_schema_and_band_routing():
    route = {"from_placement": "path_arabic_test_00", "band_min": 1, "band_max": 2}
    p = validate_content_path(_path([_node("a", "A")], placement_route=route))
    doc = content_to_path_version(p).model_dump(mode="json", by_alias=True)
    assert doc["placementRoute"] == route
    other = {"pathId": "path_b", "placementRoute": {"from_placement": "path_arabic_test_00", "band_min": 3, "band_max": 8}}
    assert route_by_band([doc, other], "path_arabic_test_00", 1) == "path_arabic_test"
    assert route_by_band([doc, other], "path_arabic_test_00", 5) == "path_b"
    assert route_by_band([doc, other], "path_english_x", 1) is None
    with pytest.raises(ValidationError):
        validate_content_path(_path([_node("a", "A")], placement_route={**route, "band_min": 5}))
