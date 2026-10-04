"""Revise / requestPublish / publish operations for PathStore."""
from __future__ import annotations

from typing import Any

from myroad_core.errors import StatusError
from myroad_core.models import OpResponse, PathStatus, PathVersion, RbacDecision, new_id
from myroad_core.store_schema import _iso_now

__all__ = ["PublishOpsMixin"]


class PublishOpsMixin:
    def revise_draft(
        self, *, actor_id: str, correlation_id: str, path_id: str,
        base_version_id: str, agent_id: str | None = None,
        change_set: dict[str, Any] | None = None, feedback_ids: list[str] | None = None,
        new_version_id: str | None = None,
        document_override: PathVersion | dict[str, Any] | None = None,
    ) -> OpResponse:
        """Create a new draft version from a base. Published base stays immutable."""
        base = self.get_version(path_id, base_version_id)
        now = _iso_now()
        new_vid = new_version_id or new_id("ver")
        # Allocate next version_num from the path max (seed may already hold v2+).
        row = self._conn.execute(
            "SELECT MAX(version_num) AS m FROM versions WHERE path_id = ?",
            (path_id,),
        ).fetchone()
        next_num = int(row["m"] or 0) + 1

        if document_override is not None:
            new_doc = (
                document_override if isinstance(document_override, PathVersion)
                else PathVersion.model_validate(document_override)
            )
            new_doc.pathId = path_id
            new_doc.versionId = new_vid
            new_doc.version = next_num
            new_doc.status = PathStatus.draft
            new_doc.updatedAt = now
            if not new_doc.createdAt:
                new_doc.createdAt = now
        else:
            raw = base.model_dump(mode="json", by_alias=True)
            raw["versionId"] = new_vid
            raw["version"] = next_num
            raw["status"] = PathStatus.draft.value
            raw["updatedAt"] = now
            raw["lineage"] = {
                "previousVersionId": base_version_id,
                "basedOnPublishedVersionId": (
                    base_version_id if base.status == PathStatus.published else None
                ),
                "publishedV1RemainsImmutable": True,
            }
            if change_set:
                for key, value in change_set.items():
                    raw[key] = value
            if feedback_ids:
                raw.setdefault("feedback", [])
            new_doc = PathVersion.model_validate(raw)

        self._write_version(new_doc, insert=True)
        changed = list(change_set.keys()) if change_set else []
        evt = self._emit(
            event_type="path.revise_draft", actor_id=actor_id, agent_id=agent_id,
            correlation_id=correlation_id, path_id=path_id, version_id=new_vid,
            rbac=RbacDecision.allow,
            payload={"baseVersionId": base_version_id, "feedbackIds": feedback_ids or []},
            detail={"previousVersionId": base_version_id, "newVersion": next_num},
        )
        return OpResponse(
            ok=True, correlationId=correlation_id, pathId=path_id, versionId=new_vid,
            status=PathStatus.draft, changedObjectIds=changed,
            diffRef=f"diff:{base_version_id}->{new_vid}", auditEventId=evt.eventId,
            data={"document": new_doc.model_dump(mode="json", by_alias=True)},
        )

    def request_publish(
        self, *, actor_id: str, correlation_id: str, path_id: str, version_id: str,
        agent_id: str | None = None, evidence_snapshot_ref: str | None = None,
    ) -> OpResponse:
        """Move draft -> in_review. Does NOT publish."""
        doc = self.get_version(path_id, version_id)
        if doc.status == PathStatus.published:
            evt = self._emit(
                event_type="path.request_publish", actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                rbac=RbacDecision.deny, detail={"reason": "already_published"},
            )
            raise StatusError(f"already published (audit={evt.eventId})")
        if doc.status == PathStatus.archived:
            raise StatusError("cannot request publish on archived version")

        doc.status = PathStatus.in_review
        doc.updatedAt = _iso_now()
        self._write_version(doc, insert=False)
        publish_request_id = new_id("preq")
        evt = self._emit(
            event_type="path.request_publish", actor_id=actor_id, agent_id=agent_id,
            correlation_id=correlation_id, path_id=path_id, version_id=version_id,
            rbac=RbacDecision.allow,
            payload={"evidenceSnapshotRef": evidence_snapshot_ref},
            detail={"publishRequestId": publish_request_id},
        )
        return OpResponse(
            ok=True, correlationId=correlation_id, pathId=path_id, versionId=version_id,
            status=PathStatus.in_review, publishRequestId=publish_request_id,
            auditEventId=evt.eventId,
        )

    def publish(
        self, *, actor_id: str, correlation_id: str, path_id: str, version_id: str,
        agent_id: str | None = None, publisher_id: str | None = None,
    ) -> OpResponse:
        """Publish a draft or in-review version. An agent may publish."""
        doc = self.get_version(path_id, version_id)
        if doc.status == PathStatus.published:
            evt = self._emit(
                event_type="path.publish", actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                rbac=RbacDecision.deny, detail={"reason": "already_published"},
            )
            raise StatusError(f"already published (audit={evt.eventId})")
        if doc.status not in (PathStatus.draft, PathStatus.in_review):
            raise StatusError(f"cannot publish from status {doc.status.value}")

        publisher = publisher_id or actor_id
        doc.status = PathStatus.published
        doc.updatedAt = _iso_now()
        actors = doc.actors
        if isinstance(actors, dict):
            doc.actors = {**actors, "publisherId": publisher}  # type: ignore[assignment]
        elif actors is not None:
            data = actors.model_dump()
            data["publisherId"] = publisher
            doc.actors = data  # type: ignore[assignment]

        self._write_version(doc, insert=False)
        evt = self._emit(
            event_type="path.publish", actor_id=actor_id, agent_id=agent_id,
            correlation_id=correlation_id, path_id=path_id, version_id=version_id,
            rbac=RbacDecision.allow, detail={"publisherId": publisher},
        )
        return OpResponse(
            ok=True, correlationId=correlation_id, pathId=path_id, versionId=version_id,
            status=PathStatus.published, auditEventId=evt.eventId,
            data={"publisherId": publisher},
        )
