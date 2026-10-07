"""Publish gate: format errors block builder publishes; everything else stays a warning."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from myroad_core.agent_builder import (
    PUBLISH_FORMAT_ERROR,
    PUBLISH_NOT_COMPLETE,
    AgentPathBuilder,
    FakePathGenerator,
    GoalSpec,
    blocking_problems,
    check_path_completeness,
    draft_problems,
)
from myroad_core.agent_builder.completeness import BLOCKING_CODES
from myroad_core.models import PathStatus
from myroad_core.store import PathStore
from myroad_core.tools import AgentTools

AGENT = "agent_path_builder_demo"


def _builder(store: PathStore) -> AgentPathBuilder:
    return AgentPathBuilder(store, AgentTools(store))


def _complete_draft(builder: AgentPathBuilder) -> tuple[str, str]:
    spec = GoalSpec.model_validate({"goal": "שברים פשוטים", "subject": "math", "length": "short"})
    gen = FakePathGenerator()
    pid, vid = builder.start_draft(
        actor_id="user_a", spec=spec, outline=gen.outline(spec), generator_name="demo", demo=True
    )
    builder.run_pending(gen, actor_id="user_a", path_id=pid, version_id=vid)
    return pid, vid


def _kids(raw: dict, node_id: str) -> dict:
    return next(b for b in raw["blocks"] if b["content"]["kids"]["id"] == node_id)["content"]["kids"]


def _break_body(raw: dict) -> None:
    kids = _kids(raw, "t2_s01")
    kids["body_ui"] = ""
    kids["body_he"] = ""


def _break_correct(raw: dict) -> None:
    _kids(raw, "t1_s02")["correct"] = "zz"


def _drop_correct(raw: dict) -> None:
    _kids(raw, "t3_s04")["correct"] = None


def _ghost_topic_node(raw: dict) -> None:
    raw["topics"][1]["node_ids"].append("ghost_s99")


def _edit(builder: AgentPathBuilder, pid: str, vid: str, fn: Callable[[dict], None]) -> None:
    raw = builder.load(pid, vid)
    fn(raw)
    # Saving a draft with format errors is never blocked.
    builder._save(raw, actor_id="user_a", agent_id=AGENT, prefix="test_edit")


def _publish_events(store: PathStore, vid: str) -> list:
    return store._conn.execute(
        "SELECT rbac_decision FROM events WHERE event_type = 'path.publish' AND version_id = ?", (vid,)
    ).fetchall()


def test_blocking_codes_are_exactly_the_format_errors() -> None:
    assert BLOCKING_CODES == {
        "node_missing_body",
        "node_correct_not_in_choices",
        "node_correct_missing",
        "topic_unknown_nodes",
    }


@pytest.mark.parametrize(
    ("breaker", "code", "where"),
    [
        (_break_body, "node_missing_body", ("node_id", "t2_s01")),
        (_break_correct, "node_correct_not_in_choices", ("node_id", "t1_s02")),
        (_drop_correct, "node_correct_missing", ("node_id", "t3_s04")),
        (_ghost_topic_node, "topic_unknown_nodes", ("topic_id", "t2")),
    ],
)
@pytest.mark.parametrize("by_agent", [True, False])
def test_format_error_blocks_publish_and_publishes_nothing(
    store: PathStore, breaker, code: str, where: tuple[str, str], by_agent: bool
) -> None:
    builder = _builder(store)
    pid, vid = _complete_draft(builder)
    _edit(builder, pid, vid, breaker)
    raw = builder.load(pid, vid)
    # Completeness alone would allow it: the format gate is what blocks.
    assert check_path_completeness(raw).complete

    resp = builder.publish(actor_id="user_a", path_id=pid, version_id=vid, by_agent=by_agent)
    assert not resp.ok
    assert [e["code"] for e in resp.errors] == [PUBLISH_FORMAT_ERROR]
    probs = resp.data["blockingProblems"]
    assert [p["code"] for p in probs] == [code]
    # Listed once: in data, not repeated inside the error entry.
    assert "problems" not in resp.errors[0] and resp.errors[0]["count"] == 1
    p = probs[0]
    assert p["severity"] == "error" and p[where[0]] == where[1]
    assert set(p) >= {"code", "message_key", "severity", "field", "node_id", "topic_id", "topic_index", "params"}

    assert store.get_version(pid, vid).status == PathStatus.draft
    assert store.get_path_latest_published(pid) is None
    assert _publish_events(store, vid) == []


def test_warning_only_draft_still_publishes_by_agent(store: PathStore) -> None:
    builder = _builder(store)
    pid, vid = _complete_draft(builder)

    def _warnings_only(raw: dict) -> None:
        raw["titles"] = {"en": "Fractions"}
        raw["blurbs"] = {"en": "About fractions"}
        raw["emoji"] = ""
        raw["estimatedMinutes"] = 500  # agent drafts: no minutes limit

    _edit(builder, pid, vid, _warnings_only)
    raw = builder.load(pid, vid)
    probs = draft_problems(raw)
    assert [p.code for p in probs] == ["missing_title_he", "missing_blurb_he", "missing_emoji"]
    assert all(p.severity == "warning" for p in probs)
    assert blocking_problems(raw) == []

    resp = builder.publish(actor_id="user_a", path_id=pid, version_id=vid, by_agent=True)
    assert resp.ok, resp.errors
    assert store.get_version(pid, vid).status == PathStatus.published


def test_completeness_rule_behaviour_is_unchanged(store: PathStore) -> None:
    builder = _builder(store)
    spec = GoalSpec.model_validate({"goal": "שברים", "subject": "math", "length": "short"})
    gen = FakePathGenerator()
    pid, vid = builder.start_draft(
        actor_id="u", spec=spec, outline=gen.outline(spec), generator_name="demo", demo=True
    )
    builder.fill_topic(gen, actor_id="u", path_id=pid, version_id=vid, topic_index=0)
    raw = builder.load(pid, vid)
    assert blocking_problems(raw) == []
    resp = builder.publish(actor_id="u", path_id=pid, version_id=vid, by_agent=True)
    # Same response as before the format gate existed.
    assert not resp.ok
    assert resp.errors == [{"code": PUBLISH_NOT_COMPLETE, "message": "path does not meet the completeness rule"}]
    assert resp.data == {"issues": check_path_completeness(raw).issues}


def test_format_error_and_incomplete_report_both(store: PathStore) -> None:
    builder = _builder(store)
    spec = GoalSpec.model_validate({"goal": "שברים", "subject": "math", "length": "short"})
    gen = FakePathGenerator()
    pid, vid = builder.start_draft(
        actor_id="u", spec=spec, outline=gen.outline(spec), generator_name="demo", demo=True
    )
    builder.fill_topic(gen, actor_id="u", path_id=pid, version_id=vid, topic_index=0)
    _edit(builder, pid, vid, _break_correct)
    resp = builder.publish(actor_id="u", path_id=pid, version_id=vid)
    assert [e["code"] for e in resp.errors] == [PUBLISH_FORMAT_ERROR, PUBLISH_NOT_COMPLETE]
    assert set(resp.data) == {"blockingProblems", "issues"}
    assert store.get_version(pid, vid).status == PathStatus.draft


def test_fixing_the_format_error_unblocks_publish(store: PathStore) -> None:
    builder = _builder(store)
    pid, vid = _complete_draft(builder)
    _edit(builder, pid, vid, _break_correct)
    assert not builder.publish(actor_id="user_a", path_id=pid, version_id=vid, by_agent=True).ok
    _edit(builder, pid, vid, lambda raw: _kids(raw, "t1_s02").update(correct="a"))
    assert builder.publish(actor_id="user_a", path_id=pid, version_id=vid, by_agent=True).ok


# ---------- route: blocked publish redirects back to review ----------

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
    db = tmp_path / "gate.db"
    store = PathStore(str(db))
    app = create_learner_app(store=store, db_path=str(db), seed=True, seed_content=True)
    with TestClient(app) as client:
        yield client, app, store
    store.close()


def _built_draft_over_http(client: TestClient) -> None:
    client.cookies.set("myroad_locale", "en")
    client.post("/login", data={"first_name": "Noa", "last_name": "Levi", "email": "g@example.com", "next": "/"})
    client.post(
        "/add-path/goal",
        data={"goal": "Fractions", "subject": "math", "ui_locale": "he", "length": "short", "mode": "demo"},
    )
    client.post("/add-path/outline")
    client.post("/add-path/outline/approve", data={})
    client.post("/add-path/build/all")


@pytest.mark.parametrize("by", ["agent", "user"])
def test_blocked_publish_redirects_to_review_with_problems(app_client, by: str) -> None:
    client, app, store = app_client
    _built_draft_over_http(client)

    review = client.get("/add-path/review")
    assert review.context["publish_blocked"] is False
    assert review.context["blocking_problems"] == []

    builder = app.state.path_builder
    sess = next(iter(app.state.builder_sessions.values()))
    pid, vid = sess["pathId"], sess["versionId"]
    _edit(builder, pid, vid, _break_correct)

    r = client.post("/add-path/publish", data={"by": by}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/add-path/review?blocked=1"
    assert store.get_version(pid, vid).status == PathStatus.draft
    assert store.get_path_latest_published(pid) is None

    page = client.get(r.headers["location"])
    assert page.status_code == 200
    ctx = page.context
    assert ctx["publish_blocked"] is True
    (p,) = ctx["blocking_problems"]
    assert p["code"] == "node_correct_not_in_choices" and p["severity"] == "error"
    assert p["node_id"] == "t1_s02"
    assert [x for x in ctx["draft_problems"] if x["severity"] == "error"] == ctx["blocking_problems"]
    assert "Publishing is blocked by format errors (1)" in ctx["error"]
    assert "Publishing is blocked by format errors (1)" in page.text  # existing flash slot
    assert "not one of the choices" in page.text

    # Without ?blocked=1 the problem is listed but no blocked flash is shown.
    plain = client.get("/add-path/review")
    assert plain.context["publish_blocked"] is False and len(plain.context["blocking_problems"]) == 1

    # Hebrew flash follows the UI locale.
    he = client.post("/locale", data={"locale": "he", "next": "/add-path/review?blocked=1"}, follow_redirects=True)
    assert "הפרסום נחסם" in he.context["error"]


def test_blocked_flash_escapes_html_and_caps_the_list(app_client) -> None:
    client, app, store = app_client
    _built_draft_over_http(client)
    builder = app.state.path_builder
    sess = next(iter(app.state.builder_sessions.values()))
    pid, vid = sess["pathId"], sess["versionId"]
    evil = '<script>alert("x")</script><b>bold</b>'

    def _many_errors(raw: dict) -> None:
        for block in raw["blocks"]:
            kids = block["content"]["kids"]
            kids["title"] = evil
            if kids.get("choices"):
                kids["correct"] = "zz"
        raw["topics"][0]["node_ids"] += [f"ghost_{i}" for i in range(8)]

    _edit(builder, pid, vid, _many_errors)
    r = client.post("/add-path/publish", data={"by": "agent"}, follow_redirects=True)
    assert str(r.url).endswith("/add-path/review?blocked=1")
    assert store.get_path_latest_published(pid) is None
    blocking = r.context["blocking_problems"]
    quiz_steps = sum(1 for b in builder.load(pid, vid)["blocks"] if b["content"]["kids"].get("choices"))
    assert quiz_steps >= 6
    assert len(blocking) == quiz_steps + 1  # every quiz step + 1 topic
    flash = r.context["error"]
    assert f"Publishing is blocked by format errors ({quiz_steps + 1})" in flash
    assert flash.count("not one of the choices") == 5 and f"and {quiz_steps + 1 - 5} more" in flash
    # Long id lists inside one message are capped too.
    topic_msg = next(p["message"] for p in blocking if p["code"] == "topic_unknown_nodes")
    assert "ghost_4" in topic_msg and "ghost_5" not in topic_msg and "and 3 more" in topic_msg
    # The title is HTML-escaped in the rendered flash, never injected.
    assert "<script>alert" not in r.text and "<b>bold</b>" not in r.text
    assert "&lt;script&gt;alert(" in r.text and "&lt;b&gt;bold&lt;/b&gt;" in r.text

