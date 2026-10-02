"""Golden loop helper steps (seed/create, learn, revise)."""
from __future__ import annotations

import uuid
from typing import Any

from myroad_core.models import Event, RbacDecision, new_id
from myroad_core.seed import find_repo_freeze_dir, seed_golden_quadratic
from myroad_core.store import PathStore
from myroad_core.tools import AgentTools

ACTOR_AUTHOR = "user_author_poc"
ACTOR_LEARNER = "user_learner_poc"
ACTOR_PUBLISHER = "user_owner_poc"
AGENT_DRAFT = "agent_golden_loop_draft"
AGENT_REVISE = "agent_golden_loop_revise"


def _corr(step: str) -> str:
    return f"corr_golden_{step}_{uuid.uuid4().hex[:8]}"


def _seed_or_create(
    tools: AgentTools,
    store: PathStore,
    *,
    use_seed: bool,
) -> tuple[str, str, str]:
    """Return (path_id, version_id, origin)."""
    if use_seed:
        freeze = find_repo_freeze_dir()
        seeded = seed_golden_quadratic(store, freeze_dir=freeze)
        # Prefer v1 (before feedback) so the loop can record fresh feedback.
        path_id = seeded["pathId"]
        version_id = seeded["versionIds"][0]
        return path_id, version_id, "seed_golden_quadratic"

    created = tools.create_draft(
        actor_id=ACTOR_AUTHOR,
        agent_id=AGENT_DRAFT,
        correlation_id=_corr("create"),
        name="משוואות ריבועיות — demo golden loop",
        goal="Solve ax^2+bx+c=0 with discriminant and formula",
        audience={"level": "high_school"},
        topic_hint="quadratic equations",
        content_language="he",
        ui_locale="he-IL",
    )
    if not created.ok:
        raise RuntimeError(f"createDraft failed: {created.errors}")
    path_id = created.pathId  # type: ignore[assignment]
    version_id = created.versionId  # type: ignore[assignment]

    b1 = tools.add_block(
        actor_id=ACTOR_AUTHOR,
        agent_id=AGENT_DRAFT,
        correlation_id=_corr("b1"),
        path_id=path_id,
        version_id=version_id,
        type="explanation",
        title="מהי משוואה ריבועית?",
        learning_objective="Define ax^2+bx+c=0",
        content={"verifiedCore": {"definition": "ax² + bx + c = 0, a≠0"}},
    )
    b2 = tools.add_block(
        actor_id=ACTOR_AUTHOR,
        agent_id=AGENT_DRAFT,
        correlation_id=_corr("b2"),
        path_id=path_id,
        version_id=version_id,
        type="practice",
        title="תרגול דיסקרימיננטה",
        mastery_rule={"type": "practice_threshold", "minCorrect": 1, "total": 1},
        content={
            "verifiedCore": {
                "items": [
                    {
                        "itemId": "demo_prac_1",
                        "prompt": "D of x²-5x+6=0?",
                        "answer": 1,
                    }
                ]
            }
        },
    )
    if not b1.ok or not b2.ok:
        raise RuntimeError(f"addBlock failed: {b1.errors} / {b2.errors}")
    edge = tools.add_edge(
        actor_id=ACTOR_AUTHOR,
        agent_id=AGENT_DRAFT,
        correlation_id=_corr("edge"),
        path_id=path_id,
        version_id=version_id,
        from_=b1.changedObjectIds[0],
        to=b2.changedObjectIds[0],
        relationship="sequence",
    )
    if not edge.ok:
        raise RuntimeError(f"addEdge failed: {edge.errors}")
    return path_id, version_id, "createDraft"


def _simulate_learn(
    store: PathStore,
    tools: AgentTools,
    *,
    path_id: str,
    version_id: str,
) -> list[dict[str, Any]]:
    """Walk blocks and emit learner.attempt audit events (simulated mastery)."""
    got = tools.get_version(
        actor_id=ACTOR_LEARNER,
        correlation_id=_corr("get_learn"),
        path_id=path_id,
        version_id=version_id,
    )
    if not got.ok or not got.data:
        raise RuntimeError(f"getVersion failed: {got.errors}")
    blocks = got.data["document"].get("blocks") or []
    attempts: list[dict[str, Any]] = []
    for block in blocks:
        bid = block["blockId"]
        btype = block.get("type")
        passed = True  # demo: learner masters each block
        attempt_id = new_id("att")
        evt = Event(
            eventType="learner.attempt",
            actorId=ACTOR_LEARNER,
            agentId=None,
            correlationId=_corr("attempt"),
            pathId=path_id,
            versionId=version_id,
            rbacDecision=RbacDecision.allow,
            detail={
                "attemptId": attempt_id,
                "blockId": bid,
                "blockType": btype,
                "passed": passed,
                "simulated": True,
            },
        )
        store.append_event(evt)
        attempts.append(
            {
                "attemptId": attempt_id,
                "blockId": bid,
                "type": btype,
                "passed": passed,
                "eventId": evt.eventId,
            }
        )
    return attempts


def _revise_with_remediation(
    tools: AgentTools,
    *,
    path_id: str,
    base_version_id: str,
    feedback_id: str,
    proposed_change: str,
) -> Any:
    got = tools.get_version(
        actor_id=ACTOR_AUTHOR,
        correlation_id=_corr("get_pre_revise"),
        path_id=path_id,
        version_id=base_version_id,
    )
    if not got.ok or not got.data:
        raise RuntimeError(f"getVersion before revise failed: {got.errors}")
    doc = got.data["document"]
    blocks = list(doc.get("blocks") or [])
    edges = list(doc.get("edges") or [])
    rem_id = "blk_golden_remediation"
    remediation = {
        "blockId": rem_id,
        "type": "practice",
        "title": "תרגול תיקון — אחרי משוב",
        "learningObjective": "Strengthen weak spots flagged by learner feedback",
        "content": {
            "verifiedCore": {
                "items": [
                    {
                        "itemId": "rem_demo_1",
                        "prompt": "חישוב D ל-x²+4x+4=0",
                        "answer": 0,
                    }
                ]
            }
        },
        "masteryRule": {
            "type": "practice_threshold",
            "minCorrect": 1,
            "total": 1,
            "passingCriterion": "1/1",
        },
        "addedReason": proposed_change,
    }
    # Attach remediation after last assessment/practice if present
    anchor = None
    for b in reversed(blocks):
        if b.get("type") in ("assessment", "practice", "explanation"):
            anchor = b["blockId"]
            break
    blocks.append(remediation)
    if anchor:
        edges.append(
            {
                "edgeId": new_id("e"),
                "from": anchor,
                "to": rem_id,
                "relationship": "branch",
                "condition": {"note": "after learner feedback"},
            }
        )
    change_set = {
        "blocks": blocks,
        "edges": edges,
        "_diff": {
            "fromVersionId": base_version_id,
            "summary": proposed_change,
            "changedBlockIds": [
                {"blockId": rem_id, "change": "added", "why": proposed_change}
            ],
            "sourceFeedbackIds": [feedback_id],
        },
    }
    return tools.revise_draft(
        actor_id=ACTOR_AUTHOR,
        agent_id=AGENT_REVISE,
        correlation_id=_corr("revise"),
        path_id=path_id,
        base_version_id=base_version_id,
        feedback_ids=[feedback_id],
        change_set=change_set,
    )
