"""Live completeness check for agent drafts: draft_problems + data passed to add_path.html."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from myroad_core.agent_builder import (
    AgentPathBuilder,
    FakePathGenerator,
    GoalSpec,
    assemble_document,
    draft_problems,
    preview_document,
)
from myroad_core.agent_builder.completeness import PROBLEM_CODES, PROBLEM_KEY_PREFIX
from myroad_core.content.schema import ContentPath
from myroad_core.store import PathStore
from myroad_core.tools import AgentTools

_LOCALES = Path(__file__).resolve().parents[1] / "locales"


def _spec(**kw) -> GoalSpec:
    data = {"goal": "שברים פשוטים", "subject": "math", "level": "elementary", "length": "short"}
    data.update(kw)
    return GoalSpec.model_validate(data)


def _full_doc(**spec_kw) -> dict:
    spec = _spec(**spec_kw)
    gen = FakePathGenerator()
    outline = gen.outline(spec)
    filled = {str(i): gen.fill_topic(spec, outline, i).model_dump(mode="json") for i in range(len(outline.topics))}
    raw = {
        "subject": spec.subject,
        "agentBuild": {
            "spec": spec.model_dump(mode="json"),
            "outline": outline.model_dump(mode="json"),
            "filled": filled,
        },
    }
    return assemble_document(raw)


def _codes(doc: dict) -> list[str]:
    return [p.code for p in draft_problems(doc)]


def _kids(doc: dict, node_id: str) -> dict:
    blk = next(b for b in doc["blocks"] if b["content"]["kids"]["id"] == node_id)
    return blk["content"]["kids"]


# ---------- unit: draft_problems ----------

def test_clean_draft_has_no_problems() -> None:
    doc = _full_doc()
    assert len(doc["blocks"]) == 12
    assert draft_problems(doc) == []
    assert draft_problems(None) == []


def test_agent_draft_is_exempt_from_minutes_limit() -> None:
    doc = _full_doc(length="long")
    assert doc["estimatedMinutes"] > 60
    for minutes in (0, 61, 500, 1201, 100000, None):
        d = copy.deepcopy(doc)
        d["estimatedMinutes"] = minutes
        assert draft_problems(d) == [], minutes
    # Past the sample-content limit the schema rejects it, so the exemption is real
    # (the limit itself may change, e.g. 60 -> 1200 in schema v2).
    with pytest.raises(ValidationError):
        ContentPath.model_validate(
            {"id": "path_x", "titles": {"he": "x"}, "blurbs": {"he": "x"}, "subject": "math",
             "emoji": "x", "estimated_minutes": 100000,
             "nodes": [{"type": "learn", "title": "x", "body_he": "x"}]}
        )


def test_missing_required_path_fields() -> None:
    doc = _full_doc()
    doc["titles"] = {"en": "Fractions"}
    doc["blurbs"] = {"he": "  "}
    doc["emoji"] = ""
    doc["subject"] = "cooking"
    probs = draft_problems(doc)
    assert [(p.code, p.field) for p in probs] == [
        ("missing_title_he", "titles.he"),
        ("missing_blurb_he", "blurbs.he"),
        ("missing_emoji", "emoji"),
        ("bad_subject", "subject"),
    ]
    assert probs[3].params == {"subject": "cooking"}
    assert all(p.node_id is None for p in probs)

    doc.pop("subject")
    doc.pop("emoji")
    assert {"missing_emoji", "bad_subject"} <= set(_codes(doc))


def test_title_he_via_legacy_mirror_is_accepted() -> None:
    doc = _full_doc()
    doc["titles"] = {"en": "Fractions", "he": ""}
    doc["title_he"] = "שברים"
    assert "missing_title_he" not in _codes(doc)


def test_no_nodes_on_preview_before_any_topic_is_built() -> None:
    spec = _spec()
    doc = preview_document(spec, FakePathGenerator().outline(spec))
    probs = draft_problems(doc)
    assert [(p.code, p.field, p.message_key) for p in probs] == [
        ("no_nodes", "nodes", "draft_problem_no_nodes")
    ]


def test_node_without_body() -> None:
    doc = _full_doc()
    kids = _kids(doc, "t2_s01")
    kids["body_ui"] = ""
    kids.pop("body_he", None)
    probs = draft_problems(doc)
    assert len(probs) == 1
    p = probs[0].as_dict()
    assert p["code"] == "node_missing_body" and p["node_id"] == "t2_s01"
    assert p["topic_id"] == "t2" and p["topic_index"] == 1
    assert p["block_id"].startswith("blk_t2_s01_")
    assert p["params"]["title"] == kids["title"]
    assert p["message_key"] == "draft_problem_node_missing_body"
    # Any one of body_he / body_en / body_ui is enough (schema rule).
    kids["body_en"] = "Explained in English"
    assert draft_problems(doc) == []


def test_choices_correct_must_point_at_a_choice() -> None:
    doc = _full_doc()
    practice = _kids(doc, "t1_s02")
    check = _kids(doc, "t1_s04")
    assert practice["type"] == "practice" and check["type"] == "check"
    practice["correct"] = "z"
    check["correct"] = None
    probs = {p.node_id: p for p in draft_problems(doc)}
    assert probs["t1_s02"].code == "node_correct_not_in_choices"
    assert probs["t1_s02"].field == "correct"
    assert probs["t1_s02"].params["correct"] == "z"
    assert probs["t1_s02"].params["choices"] == ["a", "b", "c"]
    assert probs["t1_s04"].code == "node_correct_missing"
    assert probs["t1_s04"].topic_index == 0
    # A list of correct ids is allowed when every id is a choice.
    practice["correct"] = ["a", "b"]
    check["correct"] = "a"
    assert draft_problems(doc) == []


def test_unknown_step_type() -> None:
    doc = _full_doc()
    kids = _kids(doc, "t3_s01")
    kids["type"] = "dance"
    blk = next(b for b in doc["blocks"] if b["content"]["kids"]["id"] == "t1_s01")
    blk["content"]["stageType"] = "quiz-show"
    probs = draft_problems(doc)
    got = sorted((p.node_id, p.field, p.params["type"]) for p in probs)
    assert got == [("t1_s01", "stageType", "quiz-show"), ("t3_s01", "type", "dance")]
    assert {p.code for p in probs} == {"unknown_step_type"}


def test_topic_node_ids_must_exist() -> None:
    doc = _full_doc()
    doc["topics"][1]["node_ids"].append("ghost_s99")
    doc["topics"][2]["node_ids"] = []
    probs = draft_problems(doc)
    assert [(p.code, p.topic_id, p.topic_index, p.field) for p in probs] == [
        ("topic_unknown_nodes", "t2", 1, "topics[1].node_ids"),
        ("topic_no_nodes", "t3", 2, "topics[2].node_ids"),
    ]
    assert probs[0].params["ids"] == ["ghost_s99"]


def test_builder_problems_on_saved_draft(store: PathStore) -> None:
    builder = AgentPathBuilder(store, AgentTools(store))
    spec = _spec()
    gen = FakePathGenerator()
    pid, vid = builder.start_draft(
        actor_id="u", spec=spec, outline=gen.outline(spec), generator_name="demo", demo=True
    )
    assert [p.code for p in builder.problems(pid, vid)] == ["no_nodes"]
    builder.run_pending(gen, actor_id="u", path_id=pid, version_id=vid)
    assert builder.problems(pid, vid) == []
    # Publishing is unchanged: no approval gate, the agent may publish.
    assert builder.publish(actor_id="u", path_id=pid, version_id=vid, by_agent=True).ok


# ---------- locale keys ----------

def _pack(code: str) -> dict[str, str]:
    return json.loads((_LOCALES / f"{code}.json").read_text(encoding="utf-8"))


def test_problem_locale_keys_exist_in_he_en_ar() -> None:
    packs = {c: _pack(c) for c in ("he", "en", "ar")}
    assert set(packs["he"]) == set(packs["en"]) == set(packs["ar"])
    keys = [PROBLEM_KEY_PREFIX + c for c in PROBLEM_CODES] + [
        "draft_problems_heading",
        "draft_problems_none",
        "draft_problem_severity_error",
        "draft_problem_severity_warning",
        "builder_publish_blocked",
        "builder_and_more",
    ]
    for key in keys:
        en, he, ar = packs["en"][key], packs["he"][key], packs["ar"][key]
        assert any("\u0590" <= ch <= "\u05FF" for ch in he), key
        assert any("\u0600" <= ch <= "\u06FF" for ch in ar), key
        ph = set(re.findall(r"{(\w+)}", en))
        assert set(re.findall(r"{(\w+)}", he)) == ph == set(re.findall(r"{(\w+)}", ar)), key


# ---------- route: problems reach the template context ----------

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from myroad_core.ui.app import create_learner_app  # noqa: E402


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_GATEWAY_ID", "CLOUDFLARE_AI_GATEWAY_TOKEN",
                 "CLOUDFLARE_AI_GATEWAY_BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    def _no_network(*a, **kw):
        raise AssertionError("network must not be used in tests")

    monkeypatch.setattr("myroad_core.ui.cloudflare_gateway.urlopen", _no_network)
    db = tmp_path / "problems.db"
    store = PathStore(str(db))
    app = create_learner_app(store=store, db_path=str(db), seed=True, seed_content=True)
    with TestClient(app) as client:
        yield client, app, store
    store.close()


def test_route_passes_draft_problems_at_each_step(app_client) -> None:
    client, app, _store = app_client
    client.cookies.set("myroad_locale", "en")
    client.post("/login", data={"first_name": "Noa", "last_name": "Levi", "email": "p@example.com", "next": "/"})

    goal = client.get("/add-path")
    assert goal.status_code == 200 and goal.context["draft_problems"] == []

    client.post(
        "/add-path/goal",
        data={"goal": "Fractions", "subject": "math", "ui_locale": "he", "length": "short", "mode": "demo"},
    )
    assert client.get("/add-path/existing").context["draft_problems"] == []

    client.post("/add-path/outline")
    outline = client.get("/add-path/outline")
    probs = outline.context["draft_problems"]
    assert [p["code"] for p in probs] == ["no_nodes"]
    assert probs[0]["message"] == "The path has no steps yet."

    client.post("/add-path/outline/approve", data={})
    assert [p["code"] for p in client.get("/add-path/build").context["draft_problems"]] == ["no_nodes"]
    client.post("/add-path/build/all")
    assert client.get("/add-path/build").context["draft_problems"] == []
    assert client.get("/add-path/review").context["draft_problems"] == []

    # Break one stage in the saved draft: the build and review steps show it.
    builder = app.state.path_builder
    sess = next(iter(app.state.builder_sessions.values()))
    raw = builder.load(sess["pathId"], sess["versionId"])
    kids = next(b for b in raw["blocks"] if b["content"]["kids"]["id"] == "t1_s02")["content"]["kids"]
    kids["correct"] = "zz"
    builder._save(raw, actor_id="test", agent_id="agent_path_builder_demo", prefix="test")

    for path in ("/add-path/build", "/add-path/review"):
        page = client.get(path)
        assert page.status_code == 200
        (p,) = page.context["draft_problems"]
        assert p["code"] == "node_correct_not_in_choices"
        assert p["message_key"] == "draft_problem_node_correct_not_in_choices"
        assert p["node_id"] == "t1_s02" and p["topic_id"] == "t1" and p["topic_index"] == 0
        assert p["field"] == "correct" and p["params"]["correct"] == "zz"
        assert "zz" in p["message"] and "not one of the choices" in p["message"]

    # Messages follow the UI locale (Hebrew, RTL-safe isolates around values).
    he = client.post("/locale", data={"locale": "he", "next": "/add-path/review"}, follow_redirects=True)
    (p,) = he.context["draft_problems"]
    assert "התשובה הנכונה" in p["message"] and "\u2068zz\u2069" in p["message"]
