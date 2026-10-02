"""Golden loop end-to-end demo for MyRoad POC.

Flow: topic → draft (or seed quadratic) → simulate learn/attempts →
recordFeedback → reviseDraft → requestPublish → publish ONLY with
human_publisher=True.

Never auto-publishes. Asserts that agentId alone is denied.

Run from packages/core (with package installed):

  python scripts/golden_loop.py
  python scripts/golden_loop.py --create-draft
  python scripts/golden_loop.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from myroad_core.golden_loop_steps import (
    AGENT_REVISE,
    ACTOR_AUTHOR,
    ACTOR_LEARNER,
    ACTOR_PUBLISHER,
    _corr,
    _revise_with_remediation,
    _seed_or_create,
    _simulate_learn,
)
from myroad_core.models import PathStatus
from myroad_core.store import PathStore
from myroad_core.tools import AgentTools


def run_golden_loop(
    *,
    use_seed: bool = True,
    db_path: str = ":memory:",
) -> dict[str, Any]:
    """Execute the full golden loop; raise on unexpected failure."""
    store = PathStore(db_path)
    tools = AgentTools(store)
    summary: dict[str, Any] = {
        "product": "MyRoad",
        "neverAutoPublish": True,
        "steps": [],
    }

    path_id, version_id, origin = _seed_or_create(tools, store, use_seed=use_seed)
    summary["origin"] = origin
    summary["pathId"] = path_id
    summary["baseVersionId"] = version_id
    summary["steps"].append({"op": "createDraft_or_seed", "ok": True, "origin": origin})

    attempts = _simulate_learn(store, tools, path_id=path_id, version_id=version_id)
    summary["attempts"] = attempts
    summary["steps"].append(
        {"op": "simulate_learn", "ok": True, "attemptCount": len(attempts)}
    )

    target_block = attempts[-1]["blockId"] if attempts else None
    proposed = "הוסף תרגול תיקון אחרי משוב לומד (golden loop)"
    fb = tools.record_feedback(
        actor_id=ACTOR_LEARNER,
        agent_id=None,
        correlation_id=_corr("feedback"),
        path_id=path_id,
        version_id=version_id,
        target_block_id=target_block,
        rating=2,
        comment="נכשלתי / חסר תרגול נוסף לפני פרסום",
        proposed_change=proposed,
    )
    if not fb.ok:
        raise RuntimeError(f"recordFeedback failed: {fb.errors}")
    feedback_id = fb.data["feedbackId"]
    summary["feedbackId"] = feedback_id
    summary["steps"].append({"op": "recordFeedback", "ok": True, "feedbackId": feedback_id})

    revised = _revise_with_remediation(
        tools,
        path_id=path_id,
        base_version_id=version_id,
        feedback_id=feedback_id,
        proposed_change=proposed,
    )
    if not revised.ok or not revised.versionId:
        raise RuntimeError(f"reviseDraft failed: {revised.errors}")
    new_version_id = revised.versionId
    summary["revisedVersionId"] = new_version_id
    summary["diffRef"] = revised.diffRef
    summary["steps"].append(
        {
            "op": "reviseDraft",
            "ok": True,
            "versionId": new_version_id,
            "diffRef": revised.diffRef,
        }
    )

    # Assert: agentId alone cannot publish
    denied = tools.publish(
        actor_id=ACTOR_AUTHOR,
        agent_id=AGENT_REVISE,
        correlation_id=_corr("deny_pub"),
        path_id=path_id,
        version_id=new_version_id,
        human_publisher=False,
    )
    if denied.ok:
        raise AssertionError("agent publish must fail without human_publisher=True")
    if not denied.errors or denied.errors[0].get("code") != "RBAC_DENY":
        raise AssertionError(f"expected RBAC_DENY, got {denied.errors}")
    summary["steps"].append(
        {
            "op": "publish_agent_denied",
            "ok": True,
            "denied": True,
            "code": "RBAC_DENY",
            "auditEventId": denied.auditEventId,
        }
    )

    req = tools.request_publish(
        actor_id=ACTOR_AUTHOR,
        agent_id=AGENT_REVISE,
        correlation_id=_corr("reqpub"),
        path_id=path_id,
        version_id=new_version_id,
        require_valid=True,
    )
    if not req.ok:
        raise RuntimeError(f"requestPublish failed: {req.errors}")
    summary["steps"].append(
        {
            "op": "requestPublish",
            "ok": True,
            "status": req.status.value if req.status else None,
            "publishRequestId": req.publishRequestId,
        }
    )

    # Human publish only
    pub = tools.publish(
        actor_id=ACTOR_PUBLISHER,
        agent_id=None,
        correlation_id=_corr("pub"),
        path_id=path_id,
        version_id=new_version_id,
        publisher_id=ACTOR_PUBLISHER,
        human_publisher=True,
    )
    if not pub.ok:
        raise RuntimeError(f"human publish failed: {pub.errors}")
    if pub.status != PathStatus.published:
        raise AssertionError(f"expected published, got {pub.status}")
    summary["publishedVersionId"] = new_version_id
    summary["status"] = PathStatus.published.value
    summary["steps"].append(
        {
            "op": "publish_human",
            "ok": True,
            "status": PathStatus.published.value,
            "publisherId": ACTOR_PUBLISHER,
            "auditEventId": pub.auditEventId,
        }
    )

    # Final guard: document stays published; agent still cannot "re-publish"
    doc = store.get_version(path_id, new_version_id)
    summary["finalStatus"] = doc.status.value
    summary["blockCount"] = len(doc.blocks)
    summary["eventCount"] = len(store.query_events(path_id=path_id))

    store.close()
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MyRoad golden loop E2E demo")
    parser.add_argument(
        "--create-draft",
        action="store_true",
        help="Use createDraft instead of seeding freeze/v0 quadratic path",
    )
    parser.add_argument(
        "--db",
        default=":memory:",
        help="SQLite path (default :memory:)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print summary as JSON only",
    )
    args = parser.parse_args(argv)

    summary = run_golden_loop(use_seed=not args.create_draft, db_path=args.db)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("MyRoad golden loop OK — never auto-publish")
        print(f"  origin:            {summary['origin']}")
        print(f"  pathId:            {summary['pathId']}")
        print(f"  baseVersionId:     {summary['baseVersionId']}")
        print(f"  feedbackId:        {summary['feedbackId']}")
        print(f"  revisedVersionId:  {summary['revisedVersionId']}")
        print(f"  diffRef:           {summary['diffRef']}")
        print(f"  published:         {summary['publishedVersionId']} ({summary['status']})")
        print(f"  attempts:          {len(summary['attempts'])}")
        print(f"  events:            {summary['eventCount']}")
        print("  agent publish:     DENIED (RBAC_DENY)")
        print("  human publish:     OK (human_publisher=True)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — demo CLI surface
        print(f"golden_loop FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
