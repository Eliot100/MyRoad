"""Shared request/response helpers for AgentTools."""
from __future__ import annotations

from typing import Any

from myroad_core.errors import StoreError
from myroad_core.models import OpResponse, PathStatus, RbacDecision

__all__ = ["ToolsHelpersMixin"]


class ToolsHelpersMixin:
    def _err(
        self,
        *,
        correlation_id: str,
        code: str,
        message: str,
        audit_event_id: str | None = None,
        path_id: str | None = None,
        version_id: str | None = None,
        warnings: list[dict[str, Any]] | None = None,
    ) -> OpResponse:
        return OpResponse(
            ok=False,
            correlationId=correlation_id,
            pathId=path_id,
            versionId=version_id,
            errors=[{"code": code, "message": message}],
            validationWarnings=warnings or [],
            auditEventId=audit_event_id,
        )
    def _catch(
        self,
        *,
        correlation_id: str,
        path_id: str | None = None,
        version_id: str | None = None,
    ) -> Any:
        """Context-free exception → OpResponse converter."""
        def convert(exc: BaseException) -> OpResponse:
            if isinstance(exc, StoreError):
                return self._err(
                    correlation_id=correlation_id,
                    code=exc.code,
                    message=exc.message,
                    path_id=path_id,
                    version_id=version_id,
                )
            return self._err(
                correlation_id=correlation_id,
                code="INTERNAL",
                message=str(exc),
                path_id=path_id,
                version_id=version_id,
            )
        return convert
    def _require_ids(
        self, *, correlation_id: str, path_id: str | None, version_id: str | None
    ) -> OpResponse | None:
        if not path_id or not version_id:
            return self._err(
                correlation_id=correlation_id,
                code="MISSING_IDS",
                message="pathId and versionId are required",
                path_id=path_id,
                version_id=version_id,
            )
        return None
    def _load_mutable(
        self, path_id: str, version_id: str, *, correlation_id: str,
        actor_id: str, agent_id: str | None, event_type: str,
    ):
        doc = self.store.get_version(path_id, version_id)
        if doc.status == PathStatus.published:
            evt = self.store._emit(
                event_type=event_type, actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                rbac=RbacDecision.deny, detail={"reason": "published_immutable"},
            )
            return None, self._err(
                correlation_id=correlation_id, code="IMMUTABLE",
                message=f"version {version_id} is published and immutable",
                audit_event_id=evt.eventId, path_id=path_id, version_id=version_id,
            )
        if doc.status == PathStatus.archived:
            evt = self.store._emit(
                event_type=event_type, actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                rbac=RbacDecision.deny, detail={"reason": "archived"},
            )
            return None, self._err(
                correlation_id=correlation_id, code="IMMUTABLE",
                message=f"version {version_id} is archived",
                audit_event_id=evt.eventId, path_id=path_id, version_id=version_id,
            )
        return doc, None
