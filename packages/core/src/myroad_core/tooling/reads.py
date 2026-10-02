"""Read ops for AgentTools."""
from __future__ import annotations

from myroad_core.errors import StoreError
from myroad_core.models import OpResponse, RbacDecision

__all__ = ["ToolsReadMixin"]


class ToolsReadMixin:
    def get_version(
        self,
        *,
        actor_id: str,
        correlation_id: str,
        path_id: str,
        version_id: str,
        agent_id: str | None = None,
    ) -> OpResponse:
        try:
            doc = self.store.get_version(path_id, version_id)
        except StoreError as exc:
            evt = self.store._emit(
                event_type="path.get_version", actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                rbac=RbacDecision.deny, detail={"reason": exc.code},
            )
            return self._err(
                correlation_id=correlation_id, code=exc.code, message=exc.message,
                audit_event_id=evt.eventId, path_id=path_id, version_id=version_id,
            )
        evt = self.store._emit(
            event_type="path.get_version", actor_id=actor_id, agent_id=agent_id,
            correlation_id=correlation_id, path_id=path_id, version_id=version_id,
            rbac=RbacDecision.allow,
        )
        return OpResponse(
            ok=True, correlationId=correlation_id, pathId=path_id,
            versionId=version_id, status=doc.status, auditEventId=evt.eventId,
            data={"document": doc.model_dump(mode="json", by_alias=True)},
        )
    def get_path(
        self,
        *,
        actor_id: str,
        correlation_id: str,
        path_id: str,
        agent_id: str | None = None,
        version_id: str | None = None,
    ) -> OpResponse:
        """Return a specific version or the latest version for a path."""
        try:
            if version_id:
                return self.get_version(
                    actor_id=actor_id, correlation_id=correlation_id,
                    path_id=path_id, version_id=version_id, agent_id=agent_id,
                )
            doc = self.store.get_path_latest(path_id)
            versions = self.store.list_versions(path_id)
        except StoreError as exc:
            evt = self.store._emit(
                event_type="path.get_path", actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                rbac=RbacDecision.deny, detail={"reason": exc.code},
            )
            return self._err(
                correlation_id=correlation_id, code=exc.code, message=exc.message,
                audit_event_id=evt.eventId, path_id=path_id, version_id=version_id,
            )
        evt = self.store._emit(
            event_type="path.get_path", actor_id=actor_id, agent_id=agent_id,
            correlation_id=correlation_id, path_id=path_id, version_id=doc.versionId,
            rbac=RbacDecision.allow,
        )
        return OpResponse(
            ok=True, correlationId=correlation_id, pathId=path_id,
            versionId=doc.versionId, status=doc.status, auditEventId=evt.eventId,
            data={
                "document": doc.model_dump(mode="json", by_alias=True),
                "versions": versions,
            },
        )
