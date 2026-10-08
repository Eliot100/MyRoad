"""Agent path builder: outline validation, per-topic saves, completeness, HTTP flow.

No network: the gateway is replaced by FakePathGenerator or a fake urlopen.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from myroad_core.agent_builder import (
    AGENT_ID_DEMO,
    AgentPathBuilder,
    FakePathGenerator,
    GatewayPathGenerator,
    GenerationError,
    GoalSpec,
    PathOutline,
    ReplyParseError,
    check_path_completeness,
    extract_json_object,
    parse_reply,
)
from myroad_core.content.loader import list_catalog_cards
from myroad_core.models import PathStatus
from myroad_core.store import PathStore
from myroad_core.tools import AgentTools

GATEWAY_ENV = (
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_GATEWAY_ID",
    "CLOUDFLARE_AI_GATEWAY_TOKEN",
    "CLOUDFLARE_AI_GATEWAY_BASE_URL",
)


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in GATEWAY_ENV:
        monkeypatch.delenv(name, raising=False)


def _spec(**kw) -> GoalSpec:
    data = {
        "goal": "שברים פשוטים",
        "subject": "math",
        "level": "elementary",
        "ui_locale": "he",
        "content_language": "he",
        "length": "medium",
    }
    data.update(kw)
    return GoalSpec.model_validate(data)


def _stage(title, type_, channel="mouse", order=1):
    return {"title": title, "type": type_, "channel": channel, "objective": f"obj {title}", "order": order}


def _topic(n, types=("explanation", "practice", "check", "experience")):
    return {
        "key": f"t{n}",
        "title": f"Topic {n}",
        "order": n,
        "requires": [f"t{n - 1}"] if n > 1 else [],
        "stages": [_stage(f"S{n}.{i}", ty, order=i + 1) for i, ty in enumerate(types)],
    }


def _outline_dict(n_topics=3, types=("explanation", "practice", "check", "experience")):
    return {"title": "Fractions", "summary": "s", "topics": [_topic(i + 1, types) for i in range(n_topics)]}


# ---------- outline validation ----------

def test_outline_validation_accepts_full_outline_and_normalizes() -> None:
    data = _outline_dict()
    data["topics"][0]["stages"][1]["type"] = "Exercise"  # alias -> practice
    data["topics"][0]["stages"][3]["channel"] = "SPEAKING"  # alias -> record
    data["topics"][2]["requires"] = ["t3", "zzz", "t1"]  # self/unknown dropped
    outline = PathOutline.model_validate(data)
    assert len(outline.topics) == 3
    assert outline.stage_count() == 12
    assert outline.topics[0].stages[1].type == "practice"
    assert outline.topics[0].stages[3].channel == "record"
    assert outline.topics[2].requires == ["t1"]


def test_outline_validation_rejects_short_or_partial() -> None:
    with pytest.raises(ValueError, match="at least 3 topics"):
        PathOutline.model_validate(_outline_dict(n_topics=2))
    with pytest.raises(ValueError, match="at least 12 stages"):
        PathOutline.model_validate(_outline_dict(types=("explanation", "practice", "check")))
    with pytest.raises(ValueError, match="missing stage types: check"):
        PathOutline.model_validate(
            _outline_dict(n_topics=4, types=("explanation", "practice", "experience"))
        )
    bad = _outline_dict()
    bad["topics"][0]["stages"][0]["channel"] = "telepathy"
    with pytest.raises(ValueError):
        PathOutline.model_validate(bad)


def test_outline_orders_topics_and_stages() -> None:
    data = _outline_dict()
    data["topics"][0]["order"] = 9
    data["topics"][1]["stages"][0]["order"] = 7
    outline = PathOutline.model_validate(data)
    assert [t.key for t in outline.topics] == ["t2", "t3", "t1"]
    assert [t.order for t in outline.topics] == [1, 2, 3]
    assert outline.topics[0].stages[-1].title == "S2.0"
    # t1 moved last, so t2's requirement on it is dropped (prerequisites point backwards only)
    assert outline.topics[0].requires == []


def test_defensive_parse_strips_fences_and_trailing_commas() -> None:
    text = "Here you go:\n```json\n" + json.dumps(_outline_dict()) + "\n```\nthanks"
    assert parse_reply(text, PathOutline).title == "Fractions"
    assert extract_json_object('noise {"a": [1, 2,],} tail') == {"a": [1, 2]}
    with pytest.raises(ReplyParseError):
        extract_json_object("no json at all")
    with pytest.raises(ReplyParseError, match="topics"):
        parse_reply('{"title": "x", "topics": []}', PathOutline)


def test_gateway_generator_repairs_once_then_gives_readable_error() -> None:
    good = json.dumps(_outline_dict())
    replies = iter(["not json", "```json\n" + good + "\n```"])
    seen: list[list[dict]] = []

    def chat(messages):
        seen.append(messages)
        return next(replies)

    gen = GatewayPathGenerator(chat_fn=chat)
    outline = gen.outline(_spec())
    assert outline.stage_count() == 12
    assert gen.calls == 2
    assert "could not be used" in seen[1][-1]["content"]
    assert seen[1][-2] == {"role": "assistant", "content": "not json"}

    gen2 = GatewayPathGenerator(chat_fn=lambda m: "still not json")
    with pytest.raises(GenerationError) as exc:
        gen2.outline(_spec())
    assert exc.value.code == "bad_reply"
    assert gen2.calls == 2
    assert "JSON" in exc.value.detail or "json" in exc.value.detail.lower()


def test_gateway_generator_fill_requires_correct_choice() -> None:
    outline = FakePathGenerator().outline(_spec(length="short"))
    filled = FakePathGenerator().fill_topic(_spec(length="short"), outline, 0)
    broken = filled.model_dump(mode="json")
    for st in broken["stages"]:
        st["choices"] = []
    replies = iter([json.dumps(broken), json.dumps(filled.model_dump(mode="json"))])
    gen = GatewayPathGenerator(chat_fn=lambda m: next(replies))
    out = gen.fill_topic(_spec(length="short"), outline, 0)
    assert len(out.stages) == 4
    assert gen.calls == 2


# ---------- builder: batch save + failure mid-way ----------

def _builder(store: PathStore) -> AgentPathBuilder:
    return AgentPathBuilder(store, AgentTools(store))


def test_batch_save_keeps_topics_when_one_fails_midway(store: PathStore) -> None:
    builder = _builder(store)
    spec = _spec()
    gen = FakePathGenerator(fail_topics={1})
    outline = gen.outline(spec)
    pid, vid = builder.start_draft(
        actor_id="user_a", spec=spec, outline=outline, generator_name=gen.name, demo=True
    )
    draft = store.get_version(pid, vid)
    assert draft.status == PathStatus.draft
    assert draft.actors.agentId == AGENT_ID_DEMO  # type: ignore[union-attr]

    # Topic 0 fills and is saved before topic 1 fails.
    r0 = builder.fill_topic(gen, actor_id="user_a", path_id=pid, version_id=vid, topic_index=0)
    assert r0.ok
    saved = builder.load(pid, vid)
    assert len(saved["topics"]) == 1 and len(saved["blocks"]) == 5

    results = builder.run_pending(gen, actor_id="user_a", path_id=pid, version_id=vid)
    assert [r.ok for r in results] == [False, True, True]
    assert results[0].index == 1 and results[0].error_code == "bad_reply"
    raw = builder.load(pid, vid)
    statuses = [s["status"] for s in raw["agentBuild"]["topicStatus"]]
    assert statuses == ["done", "failed", "done", "done"]
    assert [t["id"] for t in raw["topics"]] == ["t1", "t3", "t4"]
    assert len(raw["blocks"]) == 15
    report = check_path_completeness(raw)
    assert not report.complete
    assert {"code": "topics_pending", "topics": [2]} in report.issues
    assert not builder.publish(actor_id="user_a", path_id=pid, version_id=vid).ok

    # Every topic save emitted an audited save_version with the agent id.
    events = store._conn.execute(
        "SELECT agent_id, rbac_decision FROM events WHERE event_type = 'path.save_version' "
        "AND path_id = ?",
        (pid,),
    ).fetchall()
    assert len(events) >= 5
    assert all(e["agent_id"] == AGENT_ID_DEMO and e["rbac_decision"] == "allow" for e in events)

    # Retry just the failed topic.
    gen.fail_topics.clear()
    retry = builder.fill_topic(gen, actor_id="user_a", path_id=pid, version_id=vid, topic_index=1)
    assert retry.ok
    raw = builder.load(pid, vid)
    assert [t["id"] for t in raw["topics"]] == ["t1", "t2", "t3", "t4"]
    assert check_path_completeness(raw).complete


def test_unexpected_generator_exception_marks_topic_failed(store: PathStore) -> None:
    class Boom(FakePathGenerator):
        def fill_topic(self, *a, **kw):
            raise KeyError("secret-looking-body")

    builder = _builder(store)
    spec = _spec(length="short")
    outline = FakePathGenerator().outline(spec)
    pid, vid = builder.start_draft(
        actor_id="u", spec=spec, outline=outline, generator_name="x", demo=True
    )
    res = builder.fill_topic(Boom(), actor_id="u", path_id=pid, version_id=vid, topic_index=0)
    assert not res.ok and res.error_code == "internal" and res.detail == "KeyError"


# ---------- completeness ----------

def _doc_with(topics: list[list[str]]) -> dict:
    blocks, topic_rows, n2b = [], [], {}
    bt = {"explanation": "explanation", "practice": "practice", "check": "assessment", "experience": "experience"}
    for ti, types in enumerate(topics):
        nids = []
        for si, ty in enumerate(types):
            nid, bid = f"t{ti}_s{si}", f"b{ti}_{si}"
            blocks.append({"blockId": bid, "type": bt[ty], "title": nid, "content": {"stageType": ty}})
            n2b[nid] = bid
            nids.append(nid)
        topic_rows.append({"id": f"t{ti}", "titles": {"en": f"T{ti}"}, "node_ids": nids})
    return {"blocks": blocks, "topics": topic_rows, "nodeToBlock": n2b}


def test_completeness_rule() -> None:
    full = ["explanation", "practice", "check", "experience"]
    assert check_path_completeness(_doc_with([full] * 3)).complete
    two = check_path_completeness(_doc_with([full, full + ["practice"] * 4]))
    assert not two.complete and two.issues[0]["code"] == "min_topics"
    eleven = check_path_completeness(_doc_with([full, full, ["explanation", "practice", "check"]]))
    assert not eleven.complete and eleven.stage_count == 11
    assert eleven.issues[0] == {"code": "min_stages", "need": 12, "got": 11}
    no_check = check_path_completeness(
        _doc_with([full, full, ["explanation", "practice", "experience", "practice"]])
    )
    assert not no_check.complete
    assert no_check.issues == [{"code": "topic_missing_types", "topic": "T2", "types": ["check"]}]


def test_agent_draft_has_no_60_minute_cap_and_has_edges(store: PathStore) -> None:
    builder = _builder(store)
    spec = _spec(length="long")
    gen = FakePathGenerator()
    outline = gen.outline(spec)
    pid, vid = builder.start_draft(actor_id="u", spec=spec, outline=outline, generator_name="demo", demo=True)
    builder.run_pending(gen, actor_id="u", path_id=pid, version_id=vid)
    raw = builder.load(pid, vid)
    assert len(raw["topics"]) == 6 and len(raw["blocks"]) == 30
    assert raw["estimatedMinutes"] > 60
    rels = [e["relationship"] for e in raw["edges"]]
    assert rels.count("sequence") == 29
    assert rels.count("prerequisite") == 5
    first_t2 = raw["nodeToBlock"]["t2_s01"]
    last_t1 = raw["nodeToBlock"]["t1_s05"]
    blk = next(b for b in raw["blocks"] if b["blockId"] == first_t2)
    assert last_t1 in blk["prerequisites"]
    assert AgentTools(store).validate_path(actor_id="u", correlation_id="c", path_id=pid, version_id=vid).ok


# ---------- publish (agent allowed) + feedback ----------

def _complete_draft(store: PathStore, builder: AgentPathBuilder):
    spec = _spec(length="short")
    gen = FakePathGenerator()
    outline = gen.outline(spec)
    pid, vid = builder.start_draft(actor_id="user_a", spec=spec, outline=outline, generator_name="demo", demo=True)
    builder.run_pending(gen, actor_id="user_a", path_id=pid, version_id=vid)
    return pid, vid


def test_agent_publish_allowed(store: PathStore) -> None:
    builder = _builder(store)
    pid, vid = _complete_draft(store, builder)
    resp = builder.publish(actor_id="user_a", path_id=pid, version_id=vid, by_agent=True)
    assert resp.ok, resp.errors
    doc = store.get_version(pid, vid)
    assert doc.status == PathStatus.published
    assert doc.actors.publisherId == AGENT_ID_DEMO  # type: ignore[union-attr]
    evt = store._conn.execute(
        "SELECT actor_id, agent_id, rbac_decision FROM events WHERE event_type = 'path.publish' "
        "AND version_id = ?",
        (vid,),
    ).fetchone()
    assert evt["actor_id"] == AGENT_ID_DEMO and evt["agent_id"] == AGENT_ID_DEMO
    assert evt["rbac_decision"] == "allow"
    cards = [c for c in list_catalog_cards(store) if c["pathId"] == pid]
    assert cards and cards[0]["agentBuilt"] and cards[0]["demo"]


def test_feedback_creates_new_draft_and_keeps_published(store: PathStore) -> None:
    builder = _builder(store)
    pid, vid = _complete_draft(store, builder)
    assert builder.publish(actor_id="user_a", path_id=pid, version_id=vid).ok
    before = store.get_version(pid, vid).model_dump(mode="json")

    resp = builder.submit_feedback(
        actor_id="user_a", path_id=pid, version_id=vid, comment="More examples please", topic_index=1
    )
    assert resp.ok and resp.versionId != vid
    new = builder.load(pid, resp.versionId)
    assert new["status"] == "draft" and new["version"] == 2
    assert new["feedback"][-1]["comment"] == "More examples please"
    assert new["agentBuild"]["topicStatus"][1]["status"] == "pending"
    assert store.get_version(pid, vid).model_dump(mode="json") == before

    # Catalog and player still use the published v1 while v2 is a draft.
    card = next(c for c in list_catalog_cards(store) if c["pathId"] == pid)
    assert card["versionId"] == vid
    assert store.get_path_latest_published(pid).versionId == vid

    res = builder.fill_topic(FakePathGenerator(), actor_id="user_a", path_id=pid, version_id=resp.versionId, topic_index=1)
    assert res.ok
    body = builder.load(pid, resp.versionId)["blocks"][4]["content"]["kids"]["body_ui"]
    assert "More examples please" in body


# ---------- HTTP: demo mode end to end, missing env ----------

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from auth_helpers import login_with_code

from myroad_core.ui.app import create_learner_app  # noqa: E402
from myroad_core.ui.cloudflare_gateway import missing_gateway_env  # noqa: E402


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _clear_env(monkeypatch)

    def _no_network(*a, **kw):
        raise AssertionError("network must not be used in tests")

    monkeypatch.setattr("myroad_core.ui.cloudflare_gateway.urlopen", _no_network)
    db = tmp_path / "builder.db"
    store = PathStore(str(db))
    app = create_learner_app(store=store, db_path=str(db), seed=True, seed_content=True)
    with TestClient(app) as client:
        yield client, app, store
    store.close()


def _login(client: TestClient, email: str = "builder@example.com", locale: str = "en") -> None:
    client.cookies.set("myroad_locale", locale)
    r = login_with_code(
        client,
        data={"first_name": "Noa", "last_name": "Levi", "email": email, "next": "/"},
        follow_redirects=True,
    )
    assert r.status_code == 200


def test_add_path_requires_login(app_client) -> None:
    client, _app, _store = app_client
    r = client.get("/add-path", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")


def test_missing_env_message_names_exact_variable(app_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _app, _store = app_client
    _login(client)
    assert missing_gateway_env() == ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_GATEWAY_ID"]
    page = client.get("/add-path")
    assert "Missing on the server: CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_GATEWAY_ID." in page.text
    assert "demo mode" in page.text
    assert 'value="gateway" disabled' in page.text

    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct_only")
    assert missing_gateway_env() == ["CLOUDFLARE_GATEWAY_ID"]
    page = client.get("/add-path")
    assert "Missing on the server: CLOUDFLARE_GATEWAY_ID." in page.text
    assert "acct_only" not in page.text

    # Asking for the gateway while it is missing keeps the user on the goal step.
    r = client.post("/add-path/goal", data={"goal": "Fractions", "subject": "math", "mode": "gateway"})
    assert r.status_code == 200
    assert "Missing on the server: CLOUDFLARE_GATEWAY_ID." in r.text

    he = client.post("/locale", data={"locale": "he", "next": "/add-path"}, follow_redirects=True)
    assert "חסר בשרת: CLOUDFLARE_GATEWAY_ID" in he.text
    ar = client.post("/locale", data={"locale": "ar", "next": "/add-path"}, follow_redirects=True)
    assert "ينقص على الخادم: CLOUDFLARE_GATEWAY_ID" in ar.text


def test_demo_mode_end_to_end_over_http(app_client) -> None:
    client, app, store = app_client
    _login(client)

    goal = client.post(
        "/add-path/goal",
        data={
            "goal": "Fractions for beginners",
            "subject": "math",
            "level": "elementary",
            "ui_locale": "he",
            "content_language": "he",
            "length": "medium",
            "mode": "demo",
        },
        follow_redirects=True,
    )
    assert goal.status_code == 200
    assert str(goal.url).endswith("/add-path/existing")
    # Existing published math paths (sample catalog) are offered first.
    assert "/play/path_grade3_math_add20" in goal.text
    assert "Continue to a new draft" in goal.text

    outline_page = client.post("/add-path/outline", follow_redirects=True)
    assert str(outline_page.url).endswith("/add-path/outline")
    assert "4 topics · 20 stages" in outline_page.text
    assert 'name="topic_title_0"' in outline_page.text

    approve = client.post(
        "/add-path/outline/approve",
        data={
            "path_title": "דמו: שברים למתחילים",
            "topic_title_0": "Edited first topic",
            "topic_order_0": "1",
            "topic_order_1": "3",
            "topic_order_2": "2",
            "topic_order_3": "4",
        },
        follow_redirects=False,
    )
    assert approve.status_code == 303 and approve.headers["location"] == "/add-path/build?auto=1"
    sess = next(iter(app.state.builder_sessions.values()))
    pid, vid = sess["pathId"], sess["versionId"]
    draft = store.get_version(pid, vid).model_dump(mode="json")
    assert draft["status"] == "draft" and draft["demo"] is True
    assert draft["actors"]["agentId"] == AGENT_ID_DEMO
    assert draft["agentBuild"]["outline"]["topics"][0]["title"] == "Edited first topic"
    assert draft["agentBuild"]["outline"]["topics"][1]["key"] == "t3"  # reordered

    build = client.get("/add-path/build?auto=1")
    assert "build-next-form" in build.text and "0 of 4 topics built" in build.text
    step = client.post("/add-path/build/next", follow_redirects=True)
    assert "1 of 4 topics built" in step.text
    done = client.post("/add-path/build/all", follow_redirects=True)
    assert str(done.url).endswith("/add-path/review")
    assert "The path is complete" in done.text
    assert "Let the agent publish" in done.text
    assert "Demo" in done.text

    # Not in the catalog while it is a draft.
    assert pid not in {c["pathId"] for c in list_catalog_cards(store)}

    pub = client.post("/add-path/publish", data={"by": "user"}, follow_redirects=True)
    assert "Published." in pub.text
    assert f'href="/play/{pid}"' in pub.text
    doc = store.get_version(pid, vid)
    assert doc.status == PathStatus.published
    raw = doc.model_dump(mode="json")
    assert len(raw["topics"]) == 4 and len(raw["blocks"]) == 20
    assert raw["estimatedMinutes"] > 60

    catalog = client.get("/?group=agent&subject=all&tab=catalog&view=status")
    assert catalog.status_code == 200
    assert f'data-path-id="{pid}"' in catalog.text
    assert "דמו: שברים למתחילים" in catalog.text

    play_map = client.get(f"/play/{pid}")
    assert play_map.status_code == 200
    assert "Edited first topic" in play_map.text
    assert 'class="status-pill demo"' in play_map.text
    start = client.post(f"/play/{pid}/start", follow_redirects=True)
    assert start.status_code == 200
    assert 'data-node-type="learn"' in start.text
    ack = client.post(f"/play/{pid}/ack", follow_redirects=True)
    assert 'data-node-type="practice"' in ack.text
    kids = raw["blocks"][1]["content"]["kids"]
    answer = client.post(f"/play/{pid}/answer", data={"choice": kids["correct"]}, follow_redirects=True)
    assert answer.status_code == 200
    assert 'data-node-type="speak"' in answer.text

    # Feedback creates a new draft; the published version and catalog stay on v1.
    fb = client.post("/add-path/feedback", data={"comment": "Add a harder check", "topic": ""}, follow_redirects=True)
    assert fb.status_code == 200
    versions = store.list_versions(pid)
    assert [v["status"] for v in versions] == ["published", "draft"]
    card = next(c for c in list_catalog_cards(store) if c["pathId"] == pid)
    assert card["versionId"] == vid


def test_build_failure_shows_retry_over_http(app_client) -> None:
    client, app, store = app_client
    _login(client, email="retry@example.com")
    flaky = FakePathGenerator(fail_topics={1})
    app.state.path_generator_factory = lambda mode: flaky
    client.post("/add-path/goal", data={"goal": "Light and shadow", "subject": "physics", "length": "short", "mode": "demo"})
    client.post("/add-path/outline")
    client.post("/add-path/outline/approve", data={})
    page = client.post("/add-path/build/all", follow_redirects=True)
    assert str(page.url).endswith("/add-path/build")
    assert 'data-status="failed"' in page.text
    assert "Retry this topic" in page.text
    assert "2 of 3 topics built" in page.text
    flaky.fail_topics.clear()
    page = client.post("/add-path/build/topic/1", follow_redirects=True)
    assert "3 of 3 topics built" in page.text
    review = client.get("/add-path/review")
    assert "The path is complete" in review.text


def test_gateway_mode_over_http_uses_byok_gateway_without_provider_key(
    app_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, app, store = app_client
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct_test")
    monkeypatch.setenv("CLOUDFLARE_GATEWAY_ID", "gw_test")
    spec = _spec(length="short", goal="Present simple", subject="english", ui_locale="en", content_language="en")
    fake = FakePathGenerator()
    outline = fake.outline(spec)
    replies = ["```json\n" + outline.model_dump_json() + "\n```"]
    replies += [fake.fill_topic(spec, outline, i).model_dump_json() for i in range(len(outline.topics))]
    seen = []

    class _Resp:
        status = 200

        def __init__(self, content: str):
            self._body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake_urlopen(req, timeout=30):
        seen.append(req)
        return _Resp(replies[len(seen) - 1])

    monkeypatch.setattr("myroad_core.ui.cloudflare_gateway.urlopen", _fake_urlopen)
    _login(client, email="gw@example.com")
    page = client.get("/add-path")
    assert "Missing on the server" not in page.text
    client.post(
        "/add-path/goal",
        data={"goal": "Present simple", "subject": "english", "ui_locale": "en",
              "content_language": "en", "length": "short", "mode": "gateway"},
    )
    client.post("/add-path/outline")
    client.post("/add-path/outline/approve", data={})
    review = client.post("/add-path/build/all", follow_redirects=True)
    assert "The path is complete" in review.text
    assert len(seen) == 4  # one outline call + one call per topic
    for req in seen:
        headers = {k.lower(): v for k, v in req.header_items()}
        assert "authorization" not in headers
        body = json.loads(req.data.decode())
        assert body["response_format"] == {"type": "json_object"}
        assert req.full_url.endswith("/grok/v1/chat/completions")
    sess = next(iter(app.state.builder_sessions.values()))
    raw = store.get_version(sess["pathId"], sess["versionId"]).model_dump(mode="json")
    assert raw["demo"] is False and raw["agentBuild"]["mode"] == "gateway"
    assert raw["actors"]["agentId"] == "agent_path_builder_grok"


def test_gateway_bad_reply_shows_readable_error(app_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, app, _store = app_client
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct_test")
    monkeypatch.setenv("CLOUDFLARE_GATEWAY_ID", "gw_test")
    app.state.path_generator_factory = lambda mode: GatewayPathGenerator(chat_fn=lambda m: "sorry, no JSON")
    _login(client, email="bad@example.com")
    client.post("/add-path/goal", data={"goal": "Fractions", "subject": "math", "mode": "gateway"})
    page = client.post("/add-path/outline", follow_redirects=True)
    assert page.status_code == 200
    assert "could not be used, even after one repair attempt" in page.text
    assert re.search(r"no JSON object found|invalid JSON", page.text)
