"""Feedback / requestPublish / publish ops for AgentTools."""
from __future__ import annotations

from typing import Any

from myroad_core.errors import RbacDenyError, StoreError
from myroad_core.models import Feedback, OpResponse, PathStatus, RbacDecision, new_id, utc_now
from myroad_core.store_schema import _iso_now

__all__ = ["ToolsPublishMixin"]


class ToolsPublishMixin:
    def record_feedback(
        self,
        *,
        actor_id: str,
        correlation_id: str,
        path_id: str,
        version_id: str,
        agent_id: str | None = None,
        target_block_id: str | None = None,
        rating: int | None = None,
        comment: str | None = None,
        structured_issue: dict[str, Any] | None = None,
        proposed_change: str | None = None,
    ) -> OpResponse:
        missing = self._require_ids(
            correlation_id=correlation_id, path_id=path_id, version_id=version_id
        )
        if missing:
            return missing
        try:
            doc = self.store.get_version(path_id, version_id)
        except StoreError as exc:
            evt = self.store._emit(
                event_type="feedback.record", actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                rbac=RbacDecision.deny, detail={"reason": exc.code},
            )
            return self._err(
                correlation_id=correlation_id, code=exc.code, message=exc.message,
                audit_event_id=evt.eventId, path_id=path_id, version_id=version_id,
            )
        fid = new_id("fb")
        fb = Feedback(
            feedbackId=fid, actorId=actor_id, targetPathId=path_id,
            targetVersionId=version_id, targetBlockId=target_block_id,
            rating=rating, comment=comment, structuredIssue=structured_issue,
            proposedChange=proposed_change, createdAt=utc_now().isoformat(),
        )
        # Feedback must not mutate published content; store on draft/in_review only.
        mutated = False
        if doc.status in (PathStatus.draft, PathStatus.in_review):
            feedback = list(doc.feedback)
            feedback.append(fb)
            doc.feedback = feedback
            doc.updatedAt = _iso_now()
            self.store._write_version(doc, insert=False)
            mutated = True
        evt = self.store._emit(
            event_type="feedback.record", actor_id=actor_id, agent_id=agent_id,
            correlation_id=correlation_id, path_id=path_id, version_id=version_id,
            rbac=RbacDecision.allow,
            payload={"feedbackId": fid, "rating": rating, "targetBlockId": target_block_id},
            detail={
                "feedbackId": fid,
                "attachedToDocument": mutated,
                "status": doc.status.value,
            },
        )
        return OpResponse(
            ok=True, correlationId=correlation_id, pathId=path_id,
            versionId=version_id, changedObjectIds=[fid] if mutated else [],
            status=doc.status, auditEventId=evt.eventId,
            data={
                "feedbackId": fid,
                "feedback": fb.model_dump(mode="json"),
                "attachedToDocument": mutated,
            },
        )
    def request_publish(
        self,
        *,
        actor_id: str,
        correlation_id: str,
        path_id: str,
        version_id: str,
        agent_id: str | None = None,
        evidence_snapshot_ref: str | None = None,
        require_valid: bool = True,
    ) -> OpResponse:
        if require_valid:
            validation = self.validate_path(
                actor_id=actor_id, correlation_id=correlation_id,
                path_id=path_id, version_id=version_id, agent_id=agent_id,
            )
            if not validation.ok:
                return OpResponse(
                    ok=False, correlationId=correlation_id, pathId=path_id,
                    versionId=version_id, errors=validation.errors or [
                        {"code": "VALIDATION_FAILED", "message": "path is not valid"}
                    ],
                    validationWarnings=validation.validationWarnings,
                    auditEventId=validation.auditEventId,
                    data={"valid": False},
                )
        try:
            return self.store.request_publish(
                actor_id=actor_id, correlation_id=correlation_id,
                path_id=path_id, version_id=version_id, agent_id=agent_id,
                evidence_snapshot_ref=evidence_snapshot_ref,
            )
        except StoreError as exc:
            return self._err(
                correlation_id=correlation_id, code=exc.code, message=exc.message,
                path_id=path_id, version_id=version_id,
            )
    def publish(
        self,
        *,
        actor_id: str,
        correlation_id: str,
        path_id: str,
        version_id: str,
        agent_id: str | None = None,
        publisher_id: str | None = None,
        human_publisher: bool = False,
    ) -> OpResponse:
        """Human-only publish. Deny when agentId present without human_publisher flag."""
        if agent_id and not human_publisher:
            evt = self.store._emit(
                event_type="path.publish", actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                rbac=RbacDecision.deny, detail={"reason": "agent_auto_publish_forbidden"},
            )
            return self._err(
                correlation_id=correlation_id, code="RBAC_DENY",
                message="agents cannot publish; human publisher required",
                audit_event_id=evt.eventId, path_id=path_id, version_id=version_id,
            )
        # Strip agent_id for the store gate when a human publisher explicitly confirms.
        try:
            return self.store.publish(
                actor_id=actor_id,
                correlation_id=correlation_id,
                path_id=path_id,
                version_id=version_id,
                agent_id=None,
                publisher_id=publisher_id or actor_id,
            )
        except RbacDenyError as exc:
            return self._err(
                correlation_id=correlation_id, code=exc.code, message=exc.message,
                path_id=path_id, version_id=version_id,
            )
        except StoreError as exc:
            return self._err(
                correlation_id=correlation_id, code=exc.code, message=exc.message,
                path_id=path_id, version_id=version_id,
            )
