"""Agent path builder on content schema v2: types/subjects from the schema, step kind,
interleaved review, path prerequisites, unified score, and review warnings."""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import get_args

import pytest

from myroad_core.agent_builder import (
    AgentPathBuilder,
    FakePathGenerator,
    GatewayPathGenerator,
    GoalSpec,
    PathOutline,
    assemble_document,
    draft_problems,
)
from myroad_core.agent_builder import builder as builder_mod
from myroad_core.agent_builder import completeness as completeness_mod
from myroad_core.agent_builder import models as models_mod
from myroad_core.agent_builder.generator import fill_messages, outline_messages
from myroad_core.content import schema
from myroad_core.store import PathStore
from myroad_core.tools import AgentTools

_LOCALES = Path(__file__).resolve().parents[1] / "locales"
EXISTING = [{"pathId": "path_grade3_math_add20", "title": "חיבור עד 20"}]


def _spec(**kw) -> GoalSpec:
    data = {"goal": "שברים פשוטים", "subject": "math", "level": "elementary", "length": "medium"}
    data.update(kw)
    return GoalSpec.model_validate(data)


def _doc(spec: GoalSpec, existing=None) -> dict:
    gen = FakePathGenerator()
    outline = gen.outline(spec, existing_paths=existing)
    filled = {str(i): gen.fill_topic(spec, outline, i).model_dump(mode="json") for i in range(len(outline.topics))}
    raw = {
        "pathId": "path_agent_draft_1",
        "subject": spec.subject,
        "groupIds": ["agent"],
        "agentBuild": {"spec": spec.model_dump(mode="json"), "outline": outline.model_dump(mode="json"),
                       "filled": filled},
    }
    return assemble_document(raw)


def _kids_list(doc: dict) -> list[dict]:
    return [b["content"]["kids"] for b in doc["blocks"]]


def _as_content_path(doc: dict) -> dict:
    """The agent draft as a schema v2 ContentPath (only schema fields)."""
    node_fields = set(schema.ContentNode.model_fields)
    nodes = []
    for kids in _kids_list(doc):
        node = {k: v for k, v in kids.items() if k in node_fields}
        if node.get("choices"):
            node["choices"] = [{"id": c["id"], "label": c["label"]} for c in node["choices"]]
        nodes.append(node)
    return {
        "id": "path_agent_probe",
        "titles": {"he": doc["titles"].get("he") or "x"},
        "blurbs": {"he": doc["blurbs"].get("he") or "x"},
        "subject": doc["subject"],
        "group_ids": [g for g in doc["groupIds"] if g in schema.GROUPS],
        "emoji": doc["emoji"],
        "estimated_minutes": min(max(doc["estimatedMinutes"], 1), 1200),
        "prerequisite_path_ids": doc["prerequisitePathIds"],
        "score": doc["score"],
        "topics": [{"id": t["id"], "titles": {"he": "x"}, "node_ids": t["node_ids"]} for t in doc["topics"]],
        "nodes": nodes,
    }


# ---------- step types and subjects come from the schema ----------

def test_stage_types_and_subjects_are_imported_from_schema() -> None:
    assert models_mod.STAGE_TYPES == tuple(dict.fromkeys(schema.NODE_STAGE[n] for n in schema.NODE_TYPES))
    assert models_mod.SUBJECT_IDS == get_args(schema.SubjectId)
    assert "hebrew" in models_mod.SUBJECT_IDS
    assert models_mod.SubjectId is schema.SubjectId
    assert models_mod.STEP_KINDS == schema.STEP_KINDS
    assert set(models_mod.AUDIENCE_IDS) == set(schema.GROUPS) - {"agent"}
    assert {"adult", "psychometric"} <= set(models_mod.AUDIENCE_IDS)
    # No local copies of the lists in the builder package.
    for mod in (models_mod, builder_mod, completeness_mod):
        src = inspect.getsource(mod)
        assert '"math", "english"' not in src
        assert '("explanation", "practice", "check", "experience")' not in src
        assert not re.search(r'"explanation":\s*BlockType', src)
    assert not re.search(r'"assessment":\s*"check"', inspect.getsource(completeness_mod))
    # Model-reply aliases (e.g. "quiz" -> "check") only map onto schema stage types.
    assert set(models_mod._TYPE_ALIASES.values()) <= set(models_mod.STAGE_TYPES)


def test_stage_to_node_and_block_maps_follow_schema() -> None:
    for stage, node_type in builder_mod._KIDS_TYPE.items():
        assert node_type in schema.NODE_TYPES and schema.NODE_STAGE[node_type] == stage
        assert builder_mod._BLOCK_TYPE[stage].value == schema.NODE_BLOCK[node_type]
    assert set(builder_mod._KIDS_TYPE) == set(models_mod.STAGE_TYPES)
    for block_type, stage in completeness_mod._BLOCK_TO_STAGE.items():
        assert any(schema.NODE_BLOCK[n] == block_type and schema.NODE_STAGE[n] == stage for n in schema.NODE_TYPES)


def test_new_subject_hebrew_builds_a_clean_draft() -> None:
    doc = _doc(_spec(subject="hebrew", goal="הבנת הנקרא"))
    assert doc["subject"] == "hebrew"
    assert doc["emoji"] == "🧪"  # demo outline emoji
    assert draft_problems(doc) == []
    schema.validate_content_path(_as_content_path(doc))


# ---------- step kind + interleaved review ----------

def test_every_step_has_kind_and_review_steps_mix_earlier_topics() -> None:
    doc = _doc(_spec())
    kinds = [k["kind"] for k in _kids_list(doc)]
    assert set(kinds) == {"understanding", "review"}
    order = [t["id"] for t in doc["topics"]]
    home = {nid: i for i, t in enumerate(doc["topics"]) for nid in t["node_ids"]}
    reviews = [k for k in _kids_list(doc) if k["kind"] == "review"]
    assert len(reviews) == 3  # topics 2-4
    assert any(len(k["review_topic_ids"]) == 2 for k in reviews)  # mixes several topics
    for k in reviews:
        assert k["type"] == "practice" and k["choices"] and k["correct"]
        for tid in k["review_topic_ids"]:
            assert order.index(tid) < home[k["id"]]
    for k in _kids_list(doc):
        if k["kind"] == "understanding":
            assert "review_topic_ids" not in k
    # The whole draft passes the schema v2 rules (review order, kind, score, prerequisites).
    schema.validate_content_path(_as_content_path(doc))


def test_outline_review_rules() -> None:
    data = {
        "title": "P",
        "topics": [
            {"key": f"t{i}", "title": f"T{i}", "order": i, "stages": [
                {"title": "e", "type": "explanation", "channel": "read", "objective": "o", "order": 1},
                {"title": "p", "type": "practice", "channel": "mouse", "objective": "o", "order": 2},
                {"title": "c", "type": "check", "channel": "mouse", "objective": "o", "order": 3},
                {"title": "x", "type": "experience", "channel": "record", "objective": "o", "order": 4},
            ]}
            for i in (1, 2, 3)
        ],
    }
    data["topics"][2]["stages"][1]["review_topic_ids"] = ["t1", "t3", "nope", "t2", "t1"]
    out = PathOutline.model_validate(data)
    st = out.topics[2].stages[1]
    # Listing review topics makes it a review step; only EARLIER, known topics stay.
    assert st.kind == "review" and st.review_topic_ids == ["t1", "t2"]
    assert out.topics[0].stages[0].kind == "understanding"
    with pytest.raises(ValueError):
        models_mod.OutlineStage.model_validate(
            {"title": "x", "type": "practice", "channel": "mouse", "objective": "o", "order": 1, "kind": "drill"}
        )


# ---------- prerequisites + score ----------

def test_prerequisites_and_score_on_psychometric_demo() -> None:
    doc = _doc(_spec(subject="english", audience="psychometric"), existing=EXISTING)
    assert doc["prerequisitePathIds"] == ["path_grade3_math_add20"]
    assert doc["score"] == {"group_id": "psychometric_800", "part_id": "english", "weight": 1.0}
    assert doc["groupIds"] == ["agent", "psychometric"]
    schema.validate_content_path(_as_content_path(doc))


def test_no_score_or_prerequisites_by_default() -> None:
    doc = _doc(_spec())
    assert doc["prerequisitePathIds"] == [] and doc["score"] is None
    assert doc["groupIds"] == ["agent"]


def test_psychometric_parts_per_subject() -> None:
    parts = {
        subj: (FakePathGenerator().outline(_spec(subject=subj, audience="psychometric")).score or None)
        for subj in ("math", "hebrew", "english", "general", "piano")
    }
    assert {k: (v.part_id if v else None) for k, v in parts.items()} == {
        "math": "quantitative", "hebrew": "verbal", "english": "english", "general": "writing", "piano": None,
    }
    assert set(schema.SCORE_GROUPS["psychometric_800"]["parts"]) == {"quantitative", "verbal", "english", "writing"}


def test_audience_must_be_a_schema_group() -> None:
    assert _spec(audience="adult").audience == "adult"
    assert _spec(audience="").audience is None
    with pytest.raises(ValueError):
        _spec(audience="martians")
    with pytest.raises(ValueError):
        _spec(audience="agent")


def test_outline_drops_bad_prerequisites_and_invalid_score() -> None:
    out = PathOutline.model_validate(
        {**_outline_json(), "prerequisite_path_ids": ["path_a", "not_a_path", "path_a"],
         "score": {"group_id": "psychometric_800", "part_id": "chemistry"}}
    )
    assert out.prerequisite_path_ids == ["path_a"]
    assert out.score is None
    ok = PathOutline.model_validate({**_outline_json(), "score": {"group_id": "psychometric_800", "part_id": "verbal"}})
    assert ok.score is not None and ok.score.weight == 1.0


def _outline_json() -> dict:
    return FakePathGenerator().outline(_spec()).model_dump(mode="json") | {"prerequisite_path_ids": [], "score": None}


def test_gateway_generator_asks_for_new_fields_and_keeps_only_offered_prerequisites() -> None:
    sent: list = []
    reply = _outline_json()
    reply["prerequisite_path_ids"] = ["path_grade3_math_add20", "path_made_up"]
    reply["score"] = {"group_id": "psychometric_800", "part_id": "quantitative", "weight": 1}
    for t in reply["topics"]:
        for s in t["stages"]:
            s.pop("kind", None)  # the model may omit kind; review ids imply it

    def chat(messages):
        sent.append(messages)
        return json.dumps(reply, ensure_ascii=False)

    gen = GatewayPathGenerator(chat_fn=chat)
    out = gen.outline(_spec(audience="psychometric"), existing_paths=EXISTING)
    assert out.prerequisite_path_ids == ["path_grade3_math_add20"]
    assert out.score is not None and out.score.part_id == "quantitative"
    assert any(s.kind == "review" for t in out.topics for s in t.stages)
    prompt = sent[0][1]["content"]
    for needle in ("kind is understanding", "review_topic_ids", "EARLIER", "prerequisite_path_ids",
                   "path_grade3_math_add20", "psychometric_800", "quantitative, verbal, english, writing",
                   "Audience: psychometric"):
        assert needle in prompt, needle


def test_fill_prompt_names_reviewed_topics() -> None:
    spec = _spec()
    outline = FakePathGenerator().outline(spec)
    msg = fill_messages(spec, outline, 2)[1]["content"]
    assert '"kind": "review"' in msg and "reviews_topics" in msg
    assert outline.topics[0].title in msg and outline.topics[1].title in msg
    assert "interleaved" in outline_messages(spec)[1]["content"] or "mixes" in outline_messages(spec)[1]["content"]


# ---------- old drafts stay valid ----------

def test_old_outline_and_spec_without_new_fields_still_assemble() -> None:
    spec = _spec(length="short")
    outline = FakePathGenerator().outline(spec).model_dump(mode="json")
    old_spec = spec.model_dump(mode="json")
    old_spec.pop("audience")
    outline.pop("prerequisite_path_ids")
    outline.pop("score")
    for t in outline["topics"]:
        for s in t["stages"]:
            s.pop("kind")
            s.pop("review_topic_ids")
    gen = FakePathGenerator()
    o = PathOutline.model_validate(outline)
    filled = {str(i): gen.fill_topic(spec, o, i).model_dump(mode="json") for i in range(len(o.topics))}
    doc = assemble_document({"subject": "math", "agentBuild": {"spec": old_spec, "outline": outline, "filled": filled}})
    assert all(k["kind"] == "understanding" for k in _kids_list(doc))
    assert doc["prerequisitePathIds"] == [] and doc["score"] is None
    assert draft_problems(doc) == []


def test_old_draft_without_kind_has_no_review_problems() -> None:
    doc = _doc(_spec())
    for kids in _kids_list(doc):
        kids.pop("kind", None)
        kids.pop("review_topic_ids", None)
    assert draft_problems(doc) == []


# ---------- draft_problems: review warnings (schema error surfaced) ----------

def _review_kids(doc: dict) -> dict:
    return next(k for k in _kids_list(doc) if k["kind"] == "review" and k["id"].startswith("t3_"))


def test_review_topic_not_earlier_surfaces_schema_error() -> None:
    doc = _doc(_spec())
    kids = _review_kids(doc)
    kids["review_topic_ids"] = ["t1", "t4"]
    (p,) = draft_problems(doc)
    assert p.code == "review_topic_not_earlier" and p.field == "review_topic_ids"
    assert p.node_id == kids["id"] and p.topic_id == "t3" and p.topic_index == 2
    assert p.params["topic"] == "t4" and "earlier" in p.params["schema_error"]
    kids["review_topic_ids"] = ["t3"]  # its own topic is not earlier either
    assert [x.code for x in draft_problems(doc)] == ["review_topic_not_earlier"]


def test_review_topic_unknown_surfaces_schema_error() -> None:
    doc = _doc(_spec())
    kids = _review_kids(doc)
    kids["review_topic_ids"] = ["t1", "ghost"]
    (p,) = draft_problems(doc)
    assert p.code == "review_topic_unknown" and p.params["topic"] == "ghost"
    assert "unknown review topic" in p.params["schema_error"]


def test_review_ids_need_review_kind() -> None:
    doc = _doc(_spec())
    kids = _review_kids(doc)
    kids["kind"] = "understanding"
    (p,) = draft_problems(doc)
    assert p.code == "review_kind_invalid" and "kind 'review'" in p.params["schema_error"]
    kids["kind"] = "drill"
    assert [x.code for x in draft_problems(doc)] == ["review_kind_invalid"]


def test_review_of_topic_not_built_yet_is_a_warning_and_does_not_block_publish(store: PathStore) -> None:
    builder = AgentPathBuilder(store, AgentTools(store))
    spec = _spec()
    gen = FakePathGenerator(fail_topics={1})
    pid, vid = builder.start_draft(actor_id="u", spec=spec, outline=gen.outline(spec), generator_name="demo",
                                   demo=True)
    builder.run_pending(gen, actor_id="u", path_id=pid, version_id=vid)
    codes = [p.code for p in builder.problems(pid, vid)]
    # t3 reviews t1+t2, t4 reviews t2+t3; t2 failed so it is not in the draft yet.
    assert codes == ["review_topic_unknown", "review_topic_unknown"]
    gen.fail_topics.clear()
    builder.run_pending(gen, actor_id="u", path_id=pid, version_id=vid, retry_failed=True)
    assert builder.problems(pid, vid) == []

    # A review warning alone never blocks publishing (agent may publish).
    raw = builder.load(pid, vid)
    next(k for k in _kids_list(raw) if k["kind"] == "review")["review_topic_ids"] = ["ghost"]
    builder._save(raw, actor_id="u", agent_id="agent_path_builder_demo", prefix="t")
    assert [p.code for p in builder.problems(pid, vid)] == ["review_topic_unknown"]
    assert builder.publish(actor_id="u", path_id=pid, version_id=vid, by_agent=True).ok


# ---------- locale keys ----------

def test_new_locale_keys_in_he_en_ar() -> None:
    packs = {c: json.loads((_LOCALES / f"{c}.json").read_text(encoding="utf-8")) for c in ("he", "en", "ar")}
    keys = ["draft_problem_review_kind_invalid", "draft_problem_review_topic_unknown",
            "draft_problem_review_topic_not_earlier", "step_kind_understanding", "step_kind_review"]
    for key in keys:
        en, he, ar = packs["en"][key], packs["he"][key], packs["ar"][key]
        assert any("\u0590" <= ch <= "\u05FF" for ch in he), key
        assert any("\u0600" <= ch <= "\u06FF" for ch in ar), key
        ph = set(re.findall(r"{(\w+)}", en))
        assert set(re.findall(r"{(\w+)}", he)) == ph == set(re.findall(r"{(\w+)}", ar)), key


# ---------- route ----------

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from auth_helpers import login_with_code

from myroad_core.ui.app import create_learner_app  # noqa: E402


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_GATEWAY_ID", "CLOUDFLARE_AI_GATEWAY_TOKEN",
                 "CLOUDFLARE_AI_GATEWAY_BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    def _no_network(*a, **kw):
        raise AssertionError("network must not be used in tests")

    monkeypatch.setattr("myroad_core.ui.cloudflare_gateway.urlopen", _no_network)
    db = tmp_path / "v2.db"
    store = PathStore(str(db))
    app = create_learner_app(store=store, db_path=str(db), seed=True, seed_content=True)
    with TestClient(app) as client:
        yield client, app, store
    store.close()


def test_route_builds_v2_fields_end_to_end(app_client) -> None:
    client, app, store = app_client
    client.cookies.set("myroad_locale", "en")
    login_with_code(client, data={"first_name": "Noa", "last_name": "Levi", "email": "v2@example.com", "next": "/"})
    goal = client.get("/add-path")
    assert "hebrew" in goal.context["subject_ids"]
    assert goal.context["step_kinds"] == ("understanding", "review")
    assert "psychometric" in goal.context["audience_ids"]

    client.post(
        "/add-path/goal",
        data={"goal": "Quantitative reasoning", "subject": "math", "ui_locale": "he", "length": "medium",
              "mode": "demo", "audience": "psychometric"},
    )
    existing_ids = [c["pathId"] for c in client.get("/add-path/existing").context["existing"]]
    assert existing_ids, "sample math paths are offered as possible prerequisites"
    client.post("/add-path/outline")
    client.post("/add-path/outline/approve", data={})
    client.post("/add-path/build/all")
    review = client.get("/add-path/review")
    assert review.status_code == 200
    doc = review.context["doc"]
    assert doc["score"]["part_id"] == "quantitative"
    assert doc["prerequisitePathIds"] == existing_ids[:1]
    assert "psychometric" in doc["groupIds"]
    rows = [s for t in review.context["topics_view"] for s in t["stages"]]
    assert {r["kind"] for r in rows} == {"understanding", "review"}
    assert all(r["review_topic_ids"] for r in rows if r["kind"] == "review")
    assert review.context["draft_problems"] == []
    assert client.post("/add-path/publish", data={"by": "agent"}, follow_redirects=False).headers[
        "location"
    ] == "/add-path/review?published=1"

    # Old goal form (no audience field) still works.
    client.get("/add-path?new=1")
    r = client.post(
        "/add-path/goal", data={"goal": "Fractions", "subject": "math", "mode": "demo"}, follow_redirects=False
    )
    assert r.status_code == 303
