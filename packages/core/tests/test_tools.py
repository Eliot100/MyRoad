"""AgentTools facade: happy path, agent may publish, revise creates new version."""

from __future__ import annotations

from myroad_core.models import PathStatus
from myroad_core.store import PathStore
from myroad_core.tools import AgentTools


def test_happy_path_create_block_edge_validate_publish(store: PathStore) -> None:
    tools = AgentTools(store)

    created = tools.create_draft(
        actor_id="user_author",
        agent_id="agent_draft",
        correlation_id="corr_hp_create",
        name="Quadratic intro",
        goal="Solve ax^2+bx+c=0",
        audience={"level": "high_school"},
    )
    assert created.ok is True
    path_id = created.pathId
    version_id = created.versionId
    assert path_id and version_id
    assert created.auditEventId

    b1 = tools.add_block(
        actor_id="user_author",
        agent_id="agent_draft",
        correlation_id="corr_hp_b1",
        path_id=path_id,
        version_id=version_id,
        type="explanation",
        title="What is a quadratic?",
        learning_objective="Define quadratic equation",
        content={"verifiedCore": {"formula": "ax^2+bx+c=0"}},
    )
    assert b1.ok
    block1_id = b1.changedObjectIds[0]

    b2 = tools.add_block(
        actor_id="user_author",
        agent_id="agent_draft",
        correlation_id="corr_hp_b2",
        path_id=path_id,
        version_id=version_id,
        type="practice",
        title="Practice factoring",
        mastery_rule={"type": "all_correct", "passingCriterion": "2/2"},
    )
    assert b2.ok
    block2_id = b2.changedObjectIds[0]

    edge = tools.add_edge(
        actor_id="user_author",
        agent_id="agent_draft",
        correlation_id="corr_hp_edge",
        path_id=path_id,
        version_id=version_id,
        from_=block1_id,
        to=block2_id,
        relationship="sequence",
    )
    assert edge.ok
    assert edge.changedObjectIds

    edited = tools.edit_block(
        actor_id="user_author",
        correlation_id="corr_hp_edit",
        path_id=path_id,
        version_id=version_id,
        block_id=block1_id,
        patch={"title": "Quadratic equations defined"},
    )
    assert edited.ok
    assert edited.data["block"]["title"] == "Quadratic equations defined"
    assert edited.data["block"]["blockId"] == block1_id

    got = tools.get_version(
        actor_id="user_author",
        correlation_id="corr_hp_get",
        path_id=path_id,
        version_id=version_id,
    )
    assert got.ok
    assert len(got.data["document"]["blocks"]) == 2
    assert len(got.data["document"]["edges"]) == 1

    path_resp = tools.get_path(
        actor_id="user_author",
        correlation_id="corr_hp_path",
        path_id=path_id,
    )
    assert path_resp.ok
    assert path_resp.versionId == version_id
    assert len(path_resp.data["versions"]) == 1

    validated = tools.validate_path(
        actor_id="user_author",
        agent_id="agent_draft",
        correlation_id="corr_hp_val",
        path_id=path_id,
        version_id=version_id,
    )
    assert validated.ok is True
    assert validated.data["valid"] is True

    fb = tools.record_feedback(
        actor_id="user_learner",
        correlation_id="corr_hp_fb",
        path_id=path_id,
        version_id=version_id,
        target_block_id=block2_id,
        rating=4,
        comment="Need more examples",
    )
    assert fb.ok
    assert fb.data["feedbackId"]
    assert fb.data["attachedToDocument"] is True

    req = tools.request_publish(
        actor_id="user_author",
        agent_id="agent_draft",
        correlation_id="corr_hp_req",
        path_id=path_id,
        version_id=version_id,
    )
    assert req.ok
    assert req.status == PathStatus.in_review

    pub = tools.publish(
        actor_id="user_approver",
        correlation_id="corr_hp_pub",
        path_id=path_id,
        version_id=version_id,
        publisher_id="user_approver",
        allow_legacy=True,  # in-process: blocks from add_block are the legacy format
    )
    assert pub.ok
    assert pub.status == PathStatus.published

    events = store.query_events(path_id=path_id)
    types = [e.eventType for e in events]
    assert "path.create_draft" in types
    assert "block.add" in types
    assert "edge.add" in types
    assert "block.edit" in types
    assert "feedback.record" in types
    assert "path.validate" in types
    assert "path.request_publish" in types
    assert "path.publish" in types


def test_agent_can_publish(store: PathStore) -> None:
    tools = AgentTools(store)
    created = tools.create_draft(
        actor_id="user_author",
        correlation_id="corr_agent_create",
        name="Agent may publish",
        goal="g",
    )
    tools.add_block(
        actor_id="user_author",
        correlation_id="corr_agent_blk",
        path_id=created.pathId,  # type: ignore[arg-type]
        version_id=created.versionId,  # type: ignore[arg-type]
        type="explanation",
        title="Intro",
    )

    published = tools.publish(
        actor_id="user_author",
        agent_id="agent_author",
        correlation_id="corr_agent_pub",
        path_id=created.pathId,  # type: ignore[arg-type]
        version_id=created.versionId,  # type: ignore[arg-type]
        publisher_id="user_author",
        allow_legacy=True,  # in-process: blocks from add_block are the legacy format
    )
    assert published.ok is True
    assert published.status == PathStatus.published
    assert published.auditEventId

    doc = store.get_version(created.pathId, created.versionId)  # type: ignore[arg-type]
    assert doc.status == PathStatus.published

    events = store.query_events(correlation_id="corr_agent_pub")
    assert len(events) == 1
    assert events[0].rbacDecision.value == "allow"
    assert events[0].eventType == "path.publish"
    assert events[0].agentId == "agent_author"


def test_revise_creates_new_version(store: PathStore) -> None:
    tools = AgentTools(store)
    created = tools.create_draft(
        actor_id="user_author",
        agent_id="agent_draft",
        correlation_id="corr_rev_create",
        name="Revise via tools",
        goal="g",
    )
    path_id = created.pathId
    base_vid = created.versionId
    assert path_id and base_vid

    tools.add_block(
        actor_id="user_author",
        correlation_id="corr_rev_blk",
        path_id=path_id,
        version_id=base_vid,
        type="practice",
        title="Original practice",
        mastery_rule={"type": "score", "passingCriterion": ">=0.8"},
    )

    fb = tools.record_feedback(
        actor_id="user_learner",
        correlation_id="corr_rev_fb",
        path_id=path_id,
        version_id=base_vid,
        rating=2,
        comment="Too hard",
        proposed_change="Add remediation block",
    )
    assert fb.ok
    feedback_id = fb.data["feedbackId"]

    revised = tools.revise_draft(
        actor_id="user_author",
        agent_id="agent_revise",
        correlation_id="corr_rev_do",
        path_id=path_id,
        base_version_id=base_vid,
        feedback_ids=[feedback_id],
        change_set={
            "blocks": [
                {
                    "blockId": "blk_remediation",
                    "type": "explanation",
                    "title": "Remediation",
                }
            ]
        },
    )
    assert revised.ok
    assert revised.versionId != base_vid
    assert revised.status == PathStatus.draft
    assert revised.diffRef
    assert revised.auditEventId

    versions = store.list_versions(path_id)
    assert len(versions) == 2
    assert versions[0]["versionId"] == base_vid
    assert versions[1]["versionId"] == revised.versionId
    assert versions[1]["version"] == 2

    new_doc = store.get_version(path_id, revised.versionId)  # type: ignore[arg-type]
    assert new_doc.version == 2
    assert new_doc.lineage["previousVersionId"] == base_vid
    assert any(b.blockId == "blk_remediation" for b in new_doc.blocks)

    base_doc = store.get_version(path_id, base_vid)
    assert all(b.blockId != "blk_remediation" for b in base_doc.blocks)
