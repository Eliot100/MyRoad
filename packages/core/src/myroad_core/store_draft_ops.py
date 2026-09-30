"""Draft create/save operations for PathStore."""
from __future__ import annotations

from typing import Any

from myroad_core.errors import ImmutableError, StatusError
from myroad_core.models import OpResponse, PathStatus, PathVersion, RbacDecision, new_id
from myroad_core.store_schema import _iso_now

__all__ = ["DraftOpsMixin"]


class DraftOpsMixin:
    def create_draft(
        self, *, actor_id: str, correlation_id: str, name: str,
        goal: str | None = None, audience: dict[str, Any] | None = None,
        prerequisites: list[dict[str, Any]] | None = None,
        content_language: str = "he", ui_locale: str = "he-IL",
        description: str | None = None, agent_id: str | None = None,
        path_id: str | None = None, version_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> OpResponse:
        now = _iso_now()
        pid = path_id or new_id("path")
        vid = version_id or new_id("ver")
        doc_data: dict[str, Any] = {
            "schemaVersion": "0.1.0", "pathId": pid, "versionId": vid,
            "version": 1, "status": PathStatus.draft.value,
            "contentLanguage": content_language, "uiLocale": ui_locale,
            "name": name, "description": description, "goal": goal,
            "audience": audience or {}, "prerequisites": prerequisites or [],
            "createdAt": now, "updatedAt": now,
            "actors": {
                "authorId": actor_id, "agentId": agent_id,
                "lastEditorId": agent_id or actor_id,
            },
            "provenance": {
                "origin": "agent_generated_draft" if agent_id else "human_draft",
                "credit": "MyRoad POC", "basedOnPathId": None,
            },
            "sources": [], "blocks": [], "edges": [],
            "publishedImmutableNote": (
                "status draft — unpublished. After publish this version is immutable; "
                "feedback creates a new draft versionId."
            ),
        }
        if extra:
            doc_data.update(extra)
        doc = PathVersion.model_validate(doc_data)
        self._conn.execute(
            "INSERT INTO paths (path_id, name, created_at, author_id) VALUES (?, ?, ?, ?)",
            (pid, name, now, actor_id),
        )
        self._write_version(doc, insert=True)
        evt = self._emit(
            event_type="path.create_draft", actor_id=actor_id, agent_id=agent_id,
            correlation_id=correlation_id, path_id=pid, version_id=vid,
            rbac=RbacDecision.allow, payload={"name": name, "goal": goal},
        )
        return OpResponse(
            ok=True, correlationId=correlation_id, pathId=pid, versionId=vid,
            status=PathStatus.draft, auditEventId=evt.eventId,
            data={"document": doc.model_dump(mode="json", by_alias=True)},
        )

    def save_version(
        self, *, actor_id: str, correlation_id: str,
        document: PathVersion | dict[str, Any], agent_id: str | None = None,
    ) -> OpResponse:
        """Save/overwrite a draft (or in_review) version. Published refused."""
        doc = (
            document if isinstance(document, PathVersion)
            else PathVersion.model_validate(document)
        )
        existing = self._conn.execute(
            "SELECT status FROM versions WHERE path_id = ? AND version_id = ?",
            (doc.pathId, doc.versionId),
        ).fetchone()
        if existing is None:
            path_row = self._conn.execute(
                "SELECT 1 FROM paths WHERE path_id = ?", (doc.pathId,)
            ).fetchone()
            if path_row is None:
                self._conn.execute(
                    "INSERT INTO paths (path_id, name, created_at, author_id) "
                    "VALUES (?, ?, ?, ?)",
                    (doc.pathId, doc.name, doc.createdAt or _iso_now(), actor_id),
                )
            if doc.status == PathStatus.published:
                raise ImmutableError("cannot insert a published version via save_version")
            doc.updatedAt = _iso_now()
            self._write_version(doc, insert=True)
            evt = self._emit(
                event_type="path.save_version", actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=doc.pathId, version_id=doc.versionId,
                rbac=RbacDecision.allow,
                payload={"version": doc.version, "status": doc.status.value},
                detail={"insert": True},
            )
            return OpResponse(
                ok=True, correlationId=correlation_id, pathId=doc.pathId,
                versionId=doc.versionId, status=doc.status, auditEventId=evt.eventId,
            )

        if existing["status"] == PathStatus.published.value:
            evt = self._emit(
                event_type="path.save_version", actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=doc.pathId, version_id=doc.versionId,
                rbac=RbacDecision.deny, detail={"reason": "published_immutable"},
            )
            raise ImmutableError(
                f"version {doc.versionId} is published and immutable (audit={evt.eventId})"
            )

        doc.updatedAt = _iso_now()
        if doc.status == PathStatus.published:
            raise StatusError("use publish() to publish; save_version cannot set published")
        self._write_version(doc, insert=False)
        evt = self._emit(
            event_type="path.save_version", actor_id=actor_id, agent_id=agent_id,
            correlation_id=correlation_id, path_id=doc.pathId, version_id=doc.versionId,
            rbac=RbacDecision.allow,
            payload={"version": doc.version, "status": doc.status.value},
            detail={"insert": False},
        )
        return OpResponse(
            ok=True, correlationId=correlation_id, pathId=doc.pathId,
            versionId=doc.versionId, status=doc.status, auditEventId=evt.eventId,
        )
