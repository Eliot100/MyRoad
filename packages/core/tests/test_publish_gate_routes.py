"""Issue #42: every publish route runs the same gate as the path builder.

Routes: PathStore.publish, AgentTools.publish, POST /tools/publish.
The rules are Path Builder's (#30/#32), now in content/publish_rules.py: format errors (blocking_problems) and,
for agent drafts, the completeness rule (check_path_completeness).
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from myroad_core import agent_builder
from myroad_core.agent_builder import AgentPathBuilder, FakePathGenerator, GoalSpec
from myroad_core.models import PathStatus
from myroad_core.publish_gate import (
    PUBLISH_FORMAT_ERROR,
    PUBLISH_NOT_COMPLETE,
    PublishBlockedError,
)
from myroad_core.seed import find_repo_freeze_dir, seed_golden_quadratic
from myroad_core.store import PathStore
from myroad_core.tools import AgentTools

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from myroad_core.api import create_app  # noqa: E402
from myroad_core.auth import SESSION_COOKIE  # noqa: E402

AGENT = "agent_path_builder_demo"
ROUTES = ("store", "tools", "http")


@pytest.fixture
def owner(store: PathStore) -> str:
    return store.register_or_login(email="owner@example.com", first_name="O", last_name="W")["userId"]


def _builder(store: PathStore) -> AgentPathBuilder:
    return AgentPathBuilder(store, AgentTools(store))


def _draft(store: PathStore, actor: str, *, fill: bool = True) -> tuple[str, str]:
    builder = _builder(store)
    spec = GoalSpec.model_validate({"goal": "שברים פשוטים", "subject": "math", "length": "short"})
    gen = FakePathGenerator()
    pid, vid = builder.start_draft(
        actor_id=actor, spec=spec, outline=gen.outline(spec), generator_name="demo", demo=True
    )
    if fill:
        builder.run_pending(gen, actor_id=actor, path_id=pid, version_id=vid)
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


BREAKERS = [
    (_break_body, "node_missing_body"),
    (_break_correct, "node_correct_not_in_choices"),
    (_drop_correct, "node_correct_missing"),
    (_ghost_topic_node, "topic_unknown_nodes"),
]


def _edit(store: PathStore, actor: str, pid: str, vid: str, fn: Callable[[dict], None]) -> None:
    builder = _builder(store)
    raw = builder.load(pid, vid)
    fn(raw)
    builder._save(raw, actor_id=actor, agent_id=AGENT, prefix="test_edit")


def _publish(route: str, store: PathStore, actor: str, pid: str, vid: str):
    """Publish via one route. Returns (ok, error_codes, data)."""
    if route == "store":
        try:
            store.publish(actor_id=actor, correlation_id="corr_gate", path_id=pid, version_id=vid)
        except PublishBlockedError as exc:
            assert exc.code == "PUBLISH_BLOCKED"
            return False, [e["code"] for e in exc.errors], exc.data
        return True, [], {}
    if route == "tools":
        resp = AgentTools(store).publish(actor_id=actor, correlation_id="corr_gate", path_id=pid, version_id=vid)
        return resp.ok, [e["code"] for e in resp.errors], resp.data or {}
    with TestClient(create_app(store)) as client:
        client.cookies.set(SESSION_COOKIE, store.create_session(actor))
        r = client.post(
            "/tools/publish",
            json={"correlationId": "corr_gate", "pathId": pid, "versionId": vid},
            headers={"X-MyRoad-Request": "1"},
        )
    body = r.json()
    if r.status_code == 422:
        return False, [e["code"] for e in body["errors"]], body["data"]
    assert r.status_code == 200, r.text
    return body["ok"], [e["code"] for e in body["errors"]], body.get("data") or {}


def _deny_and_allow(store: PathStore, vid: str) -> tuple[int, int]:
    rows = store._conn.execute(
        "SELECT rbac_decision FROM events WHERE event_type = 'path.publish' AND version_id = ?", (vid,)
    ).fetchall()
    return sum(r[0] == "deny" for r in rows), sum(r[0] == "allow" for r in rows)


def test_gate_codes_match_the_builder() -> None:
    assert PUBLISH_FORMAT_ERROR == agent_builder.PUBLISH_FORMAT_ERROR
    assert PUBLISH_NOT_COMPLETE == agent_builder.PUBLISH_NOT_COMPLETE


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize(("breaker", "code"), BREAKERS)
def test_format_error_blocks_every_route(store, owner, route, breaker, code) -> None:
    pid, vid = _draft(store, owner)
    _edit(store, owner, pid, vid, breaker)
    ok, codes, data = _publish(route, store, owner, pid, vid)
    assert not ok
    assert codes == [PUBLISH_FORMAT_ERROR]
    assert [p["code"] for p in data["blockingProblems"]] == [code]
    assert all(p["severity"] == "error" for p in data["blockingProblems"])
    assert store.get_version(pid, vid).status == PathStatus.draft
    assert store.get_path_latest_published(pid) is None
    assert _deny_and_allow(store, vid) == (1, 0)


@pytest.mark.parametrize("route", ROUTES)
def test_incomplete_agent_draft_blocks_every_route(store, owner, route) -> None:
    pid, vid = _draft(store, owner, fill=False)  # outline only: topics pending, no stages
    ok, codes, data = _publish(route, store, owner, pid, vid)
    assert not ok
    assert PUBLISH_NOT_COMPLETE in codes
    issue_codes = {i["code"] for i in data["issues"]}
    assert {"min_stages", "topics_pending"} <= issue_codes
    assert store.get_version(pid, vid).status == PathStatus.draft
    assert store.get_path_latest_published(pid) is None


@pytest.mark.parametrize("route", ROUTES)
def test_in_review_draft_is_also_checked(store, owner, route) -> None:
    pid, vid = _draft(store, owner)
    _edit(store, owner, pid, vid, _break_correct)
    store.request_publish(actor_id=owner, correlation_id="corr_req", path_id=pid, version_id=vid)
    ok, codes, _ = _publish(route, store, owner, pid, vid)
    assert not ok and codes == [PUBLISH_FORMAT_ERROR]
    assert store.get_version(pid, vid).status == PathStatus.in_review


@pytest.mark.parametrize("route", ROUTES)
def test_clean_complete_agent_draft_publishes_on_every_route(store, owner, route) -> None:
    pid, vid = _draft(store, owner)
    ok, codes, _ = _publish(route, store, owner, pid, vid)
    assert ok and codes == []
    assert store.get_version(pid, vid).status == PathStatus.published
    assert _deny_and_allow(store, vid) == (0, 1)


@pytest.mark.parametrize("route", ROUTES)
def test_dropping_agent_build_in_a_revision_does_not_skip_the_rule(store, owner, route) -> None:
    pid, vid = _draft(store, owner, fill=False)
    rev = store.revise_draft(
        actor_id=owner, correlation_id="corr_rev", path_id=pid, base_version_id=vid,
        change_set={"agentBuild": None},
    )
    assert not rev.data["document"].get("agentBuild")
    ok, codes, _ = _publish(route, store, owner, pid, rev.versionId)
    assert not ok and PUBLISH_NOT_COMPLETE in codes
    assert store.get_version(pid, rev.versionId).status == PathStatus.draft


def test_http_gate_refusal_is_422_with_problem_list(store, owner) -> None:
    pid, vid = _draft(store, owner)
    _edit(store, owner, pid, vid, _ghost_topic_node)
    with TestClient(create_app(store)) as client:
        client.cookies.set(SESSION_COOKIE, store.create_session(owner))
        r = client.post(
            "/tools/publish",
            json={"correlationId": "corr_gate", "pathId": pid, "versionId": vid},
            headers={"X-MyRoad-Request": "1"},
        )
    assert r.status_code == 422
    body = r.json()
    assert body["ok"] is False
    assert body["errors"][0]["code"] == PUBLISH_FORMAT_ERROR
    prob = body["data"]["blockingProblems"][0]
    assert prob["code"] == "topic_unknown_nodes" and prob["topic_id"] == "t2"


def test_http_other_publish_errors_are_not_422(store, owner) -> None:
    pid, vid = _draft(store, owner)
    store.publish(actor_id=owner, correlation_id="c1", path_id=pid, version_id=vid)
    with TestClient(create_app(store)) as client:
        client.cookies.set(SESSION_COOKIE, store.create_session(owner))
        r = client.post(
            "/tools/publish",
            json={"correlationId": "corr_gate", "pathId": pid, "versionId": vid},
            headers={"X-MyRoad-Request": "1"},
        )
    assert r.status_code == 200 and r.json()["ok"] is False
    assert r.json()["errors"][0]["code"] == "INVALID_STATUS"


def test_content_format_path_gets_format_check_but_not_completeness(store, owner) -> None:
    from myroad_core.content.loader import content_to_path_version, default_content_dir, load_content_paths

    paths = load_content_paths(default_content_dir())
    assert paths
    doc = content_to_path_version(paths[0]).model_dump(mode="json", by_alias=True)
    assert not doc.get("agentBuild")
    # A small content path (fails the agent completeness rule) still publishes when clean.
    store.save_version(actor_id=owner, correlation_id="c_save", document=doc)
    store.publish(actor_id=owner, correlation_id="c_pub", path_id=doc["pathId"], version_id=doc["versionId"])
    assert store.get_version(doc["pathId"], doc["versionId"]).status == PathStatus.published

    broken = content_to_path_version(paths[1]).model_dump(mode="json", by_alias=True)
    kids = broken["blocks"][0]["content"]["kids"]
    for key in ("body_he", "body_en", "body_ui"):
        kids[key] = ""
    store.save_version(actor_id=owner, correlation_id="c_save2", document=broken)
    with pytest.raises(PublishBlockedError) as exc:
        store.publish(actor_id=owner, correlation_id="c_pub2", path_id=broken["pathId"], version_id=broken["versionId"])
    assert [e["code"] for e in exc.value.errors] == [PUBLISH_FORMAT_ERROR]
    assert "issues" not in exc.value.data
    assert store.get_version(broken["pathId"], broken["versionId"]).status == PathStatus.draft


def test_legacy_freeze_format_path_still_publishes(store: PathStore, freeze_dir: Path) -> None:
    seeded = seed_golden_quadratic(store, freeze_dir=freeze_dir)
    vid = seeded["versionIds"][-1]
    resp = AgentTools(store).publish(
        actor_id="user_author", agent_id="agent_revise", correlation_id="c_legacy",
        path_id=seeded["pathId"], version_id=vid,
    )
    assert resp.ok and resp.status == PathStatus.published


def test_builder_publish_route_unchanged(store, owner) -> None:
    pid, vid = _draft(store, owner)
    _edit(store, owner, pid, vid, _break_body)
    resp = _builder(store).publish(actor_id=owner, path_id=pid, version_id=vid)
    assert not resp.ok and [e["code"] for e in resp.errors] == [PUBLISH_FORMAT_ERROR]
    assert store.get_path_latest_published(pid) is None


# ---------- /tools/publish: the gate sits behind ownership and CSRF (#46) ----------

AGENT_CRED = "test-agent-credential-0123456789"


def _http_publish(client, pid: str, vid: str, headers: dict | None = None):
    return client.post(
        "/tools/publish",
        json={"correlationId": "corr_gate", "pathId": pid, "versionId": vid},
        headers=headers or {},
    )


def _assert_untouched(store: PathStore, pid: str, vid: str) -> None:
    assert store.get_version(pid, vid).status == PathStatus.draft
    assert store.get_path_latest_published(pid) is None
    assert _deny_and_allow(store, vid) == (0, 0)  # the gate never ran


@pytest.mark.parametrize("broken", [True, False])
def test_http_publish_without_csrf_header_is_403_before_the_gate(store, owner, broken) -> None:
    pid, vid = _draft(store, owner)
    if broken:
        _edit(store, owner, pid, vid, _break_body)
    with TestClient(create_app(store)) as client:
        client.cookies.set(SESSION_COOKIE, store.create_session(owner))
        r = _http_publish(client, pid, vid)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "CSRF_HEADER_REQUIRED"
    assert "blockingProblems" not in r.text
    _assert_untouched(store, pid, vid)


@pytest.mark.parametrize("broken", [True, False])
def test_http_publish_by_non_owner_is_404_and_leaks_no_problem_list(store, owner, broken) -> None:
    pid, vid = _draft(store, owner)
    if broken:
        _edit(store, owner, pid, vid, _ghost_topic_node)
    other = store.register_or_login(email="other@example.com", first_name="X", last_name="Y")["userId"]
    with TestClient(create_app(store)) as client:
        client.cookies.set(SESSION_COOKIE, store.create_session(other))
        r = _http_publish(client, pid, vid, {"X-MyRoad-Request": "1"})
    assert r.status_code == 404
    assert "blockingProblems" not in r.text and "issues" not in r.text
    _assert_untouched(store, pid, vid)


def test_http_publish_by_agent_respects_scope_then_gate(store, owner, monkeypatch) -> None:
    pid, vid = _draft(store, owner)
    _edit(store, owner, pid, vid, _break_correct)
    monkeypatch.setenv("MYROAD_AGENT_TOKEN", AGENT_CRED)
    monkeypatch.delenv("MYROAD_AGENT_ALLOWED_PATHS", raising=False)
    bearer = {"Authorization": f"Bearer {AGENT_CRED}"}  # bearer calls need no CSRF header
    with TestClient(create_app(store)) as client:
        r = _http_publish(client, pid, vid, bearer)
        assert r.status_code == 404  # not the agent's path
        _assert_untouched(store, pid, vid)
        monkeypatch.setenv("MYROAD_AGENT_ALLOWED_PATHS", pid)
        r = _http_publish(client, pid, vid, bearer)
    assert r.status_code == 422
    body = r.json()
    assert [e["code"] for e in body["errors"]] == [PUBLISH_FORMAT_ERROR]
    assert [p["code"] for p in body["data"]["blockingProblems"]] == ["node_correct_not_in_choices"]
    assert store.get_version(pid, vid).status == PathStatus.draft
    assert _deny_and_allow(store, vid) == (1, 0)


def test_owner_with_csrf_header_gets_422_problem_items_in_builder_shape(store, owner) -> None:
    pid, vid = _draft(store, owner)
    _edit(store, owner, pid, vid, _drop_correct)
    with TestClient(create_app(store)) as client:
        client.cookies.set(SESSION_COOKIE, store.create_session(owner))
        r = _http_publish(client, pid, vid, {"X-MyRoad-Request": "1"})
    assert r.status_code == 422
    (prob,) = r.json()["data"]["blockingProblems"]
    assert {"code", "message_key", "field", "node_id", "block_id", "topic_id", "topic_index", "params"} <= set(prob)
    assert prob["code"] == "node_correct_missing" and prob["node_id"] == "t3_s04"


# ---------- shared module: one copy of the rules ----------

def test_rules_live_in_the_shared_module_and_old_imports_still_work() -> None:
    from myroad_core import publish_gate
    from myroad_core.agent_builder import builder, completeness, models
    from myroad_core.content import publish_rules

    for name in (
        "draft_problems", "blocking_problems", "check_path_completeness", "DraftProblem",
        "CompletenessReport", "BLOCKING_CODES", "PROBLEM_CODES", "PROBLEM_KEY_PREFIX",
        "SEVERITY_ERROR", "SEVERITY_WARNING", "MIN_TOPICS", "MIN_STAGES",
        "REQUIRED_STAGE_TYPES", "STAGE_TYPES",
    ):
        assert getattr(completeness, name) is getattr(publish_rules, name), name
    for name in ("MIN_TOPICS", "MIN_STAGES", "REQUIRED_STAGE_TYPES", "STAGE_TYPES"):
        assert getattr(models, name) is getattr(publish_rules, name), name
    assert publish_gate.blocking_problems is publish_rules.blocking_problems
    assert publish_gate.check_path_completeness is publish_rules.check_path_completeness
    assert builder.PUBLISH_FORMAT_ERROR == publish_rules.PUBLISH_FORMAT_ERROR == publish_gate.PUBLISH_FORMAT_ERROR
    assert builder.PUBLISH_NOT_COMPLETE == publish_rules.PUBLISH_NOT_COMPLETE == publish_gate.PUBLISH_NOT_COMPLETE


def test_store_imports_without_the_builder_package() -> None:
    import subprocess
    import sys

    code = (
        "import sys, myroad_core.store, myroad_core.publish_gate; "
        "assert 'myroad_core.agent_builder' not in sys.modules, sorted(m for m in sys.modules if 'agent_builder' in m)"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
