"""Unit tests: save draft, revise new versionId, published immutable, events logged."""

from __future__ import annotations

import pytest

from myroad_core.errors import ImmutableError
from myroad_core.models import PathStatus, PathVersion
from myroad_core.seed import seed_golden_quadratic
from myroad_core.store import PathStore


def test_save_draft_creates_path_and_version(store: PathStore) -> None:
    resp = store.create_draft(
        actor_id="user_author",
        agent_id="agent_draft",
        correlation_id="corr_create_1",
        name="Test Path",
        goal="Learn something",
        audience={"level": "high_school"},
    )
    assert resp.ok is True
    assert resp.pathId
    assert resp.versionId
    assert resp.status == PathStatus.draft
    assert resp.auditEventId

    doc = store.get_version(resp.pathId, resp.versionId)
    assert doc.name == "Test Path"
    assert doc.status == PathStatus.draft
    assert doc.version == 1

    versions = store.list_versions(resp.pathId)
    assert len(versions) == 1
    assert versions[0]["status"] == "draft"

    events = store.query_events(path_id=resp.pathId)
    assert len(events) == 1
    assert events[0].eventType == "path.create_draft"
    assert events[0].actorId == "user_author"
    assert events[0].agentId == "agent_draft"
    assert events[0].correlationId == "corr_create_1"
    assert events[0].rbacDecision.value == "allow"


def test_revise_creates_new_version_id(store: PathStore) -> None:
    created = store.create_draft(
        actor_id="user_author",
        correlation_id="corr_rev_base",
        name="Revise Me",
        goal="g",
    )
    base_vid = created.versionId
    assert base_vid

    revised = store.revise_draft(
        actor_id="user_author",
        agent_id="agent_revise",
        correlation_id="corr_rev_1",
        path_id=created.pathId,  # type: ignore[arg-type]
        base_version_id=base_vid,
        change_set={
            "blocks": [
                {
                    "blockId": "blk_new",
                    "type": "practice",
                    "title": "Extra practice",
                }
            ]
        },
        feedback_ids=["fb_1"],
    )
    assert revised.ok
    assert revised.versionId != base_vid
    assert revised.status == PathStatus.draft
    assert revised.diffRef

    versions = store.list_versions(created.pathId)  # type: ignore[arg-type]
    assert len(versions) == 2
    assert versions[0]["versionId"] == base_vid
    assert versions[1]["versionId"] == revised.versionId
    assert versions[1]["version"] == 2

    new_doc = store.get_version(created.pathId, revised.versionId)  # type: ignore[arg-type]
    assert new_doc.version == 2
    assert new_doc.status == PathStatus.draft
    assert new_doc.lineage is not None
    assert new_doc.lineage["previousVersionId"] == base_vid
    assert len(new_doc.blocks) == 1

    # base unchanged
    base_doc = store.get_version(created.pathId, base_vid)  # type: ignore[arg-type]
    assert base_doc.blocks == [] or len(base_doc.blocks) == 0

    events = store.query_events(correlation_id="corr_rev_1")
    assert len(events) == 1
    assert events[0].eventType == "path.revise_draft"


def _add_node_block(store: PathStore, path_id: str, version_id: str) -> None:
    """One player-format block, so the publish gate (no empty / legacy paths) accepts it."""
    raw = store.get_version(path_id, version_id).model_dump(mode="json", by_alias=True)
    raw["blocks"] = [{
        "blockId": "blk_node_1", "type": "explanation", "title": "Intro",
        "content": {"kids": {"id": "n001", "type": "learn", "title": "Intro", "body_he": "הסבר קצר"}},
    }]
    store.save_version(actor_id="user_author", correlation_id="corr_add_node", document=raw)


def test_published_is_immutable(store: PathStore) -> None:
    created = store.create_draft(
        actor_id="user_author",
        correlation_id="corr_pub_base",
        name="Publish Me",
    )
    path_id = created.pathId
    version_id = created.versionId
    assert path_id and version_id
    _add_node_block(store, path_id, version_id)

    # agent may request publish
    req = store.request_publish(
        actor_id="user_author",
        agent_id="agent_helper",
        correlation_id="corr_req_pub",
        path_id=path_id,
        version_id=version_id,
    )
    assert req.status == PathStatus.in_review

    # human publishes (no agentId)
    pub = store.publish(
        actor_id="user_approver",
        correlation_id="corr_pub",
        path_id=path_id,
        version_id=version_id,
        publisher_id="user_approver",
    )
    assert pub.ok
    assert pub.status == PathStatus.published

    published = store.get_version(path_id, version_id)
    assert published.status == PathStatus.published

    # mutate attempt must fail
    mutated = published.model_copy(deep=True)
    mutated.name = "Hacked"
    with pytest.raises(ImmutableError):
        store.save_version(
            actor_id="user_author",
            correlation_id="corr_mutate_denied",
            document=mutated,
        )

    # denial still logged
    deny_events = store.query_events(correlation_id="corr_mutate_denied")
    assert len(deny_events) == 1
    assert deny_events[0].rbacDecision.value == "deny"

    # revise from published creates NEW draft; published stays
    revised = store.revise_draft(
        actor_id="user_author",
        correlation_id="corr_rev_after_pub",
        path_id=path_id,
        base_version_id=version_id,
        change_set={"name": "Publish Me (revised)"},
    )
    assert revised.versionId != version_id
    still = store.get_version(path_id, version_id)
    assert still.status == PathStatus.published
    assert still.name == "Publish Me"


def test_agent_can_publish(store: PathStore) -> None:
    created = store.create_draft(
        actor_id="user_author",
        correlation_id="corr_agent_pub",
        name="Agent Publish",
    )
    _add_node_block(store, created.pathId, created.versionId)  # type: ignore[arg-type]
    pub = store.publish(
        actor_id="user_author",
        agent_id="agent_author",
        correlation_id="corr_agent_pub_ok",
        path_id=created.pathId,  # type: ignore[arg-type]
        version_id=created.versionId,  # type: ignore[arg-type]
        publisher_id="user_author",
    )
    assert pub.ok
    assert pub.status == PathStatus.published
    events = store.query_events(correlation_id="corr_agent_pub_ok")
    assert len(events) == 1
    assert events[0].eventType == "path.publish"
    assert events[0].rbacDecision.value == "allow"
    assert events[0].agentId == "agent_author"
    doc = store.get_version(created.pathId, created.versionId)  # type: ignore[arg-type]
    assert doc.status == PathStatus.published


def test_events_query_by_path_and_correlation(store: PathStore) -> None:
    a = store.create_draft(
        actor_id="u1", correlation_id="corr_shared", name="A"
    )
    b = store.create_draft(
        actor_id="u1", correlation_id="corr_shared", name="B"
    )
    by_corr = store.query_events(correlation_id="corr_shared")
    assert len(by_corr) == 2
    by_path = store.query_events(path_id=a.pathId)
    assert len(by_path) == 1
    assert by_path[0].pathId == a.pathId
    assert b.pathId != a.pathId


def test_seed_golden_quadratic(store: PathStore, freeze_dir) -> None:
    summary = seed_golden_quadratic(store, freeze_dir=freeze_dir)
    assert summary["pathId"] == "path_quadratic_he_hs_001"
    assert summary["versionIds"] == ["ver_qeq_draft_001", "ver_qeq_draft_002"]

    v1 = store.get_version("path_quadratic_he_hs_001", "ver_qeq_draft_001")
    v2 = store.get_version("path_quadratic_he_hs_001", "ver_qeq_draft_002")
    assert v1.status == PathStatus.draft
    assert v2.status == PathStatus.draft
    assert v1.version == 1
    assert v2.version == 2
    assert len(v1.blocks) == 6
    assert len(v2.blocks) == 7  # remediation block added
    assert any(
        (b.blockId if hasattr(b, "blockId") else b["blockId"])
        == "blk_qeq_remediation_007"
        for b in v2.blocks
    )

    versions = store.list_versions("path_quadratic_he_hs_001")
    assert len(versions) == 2

    events = store.query_events(path_id="path_quadratic_he_hs_001")
    assert len(events) >= 2
    assert all(e.actorId for e in events)
    assert all(e.correlationId for e in events)
    assert all(e.rbacDecision for e in events)


def test_path_version_roundtrip_from_freeze(freeze_dir) -> None:
    raw = (freeze_dir / "01-path-before-feedback.json").read_text(encoding="utf-8")
    doc = PathVersion.model_validate_json(raw)
    assert doc.pathId == "path_quadratic_he_hs_001"
    assert doc.blocks[0].type == "explanation"
    assert doc.edges[0].relationship == "sequence"
