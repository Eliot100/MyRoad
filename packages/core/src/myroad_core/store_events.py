"""Event log helpers for PathStore."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from myroad_core.errors import StoreError
from myroad_core.models import Event, RbacDecision
from myroad_core.store_schema import _digest

__all__ = ["EventMixin"]


class EventMixin:
    def append_event(self, event: Event) -> Event:
        self._conn.execute(
            """INSERT INTO events (
              event_id, event_type, actor_id, agent_id, correlation_id,
              path_id, version_id, payload_digest, timestamp, rbac_decision, detail_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.eventId, event.eventType, event.actorId, event.agentId,
                event.correlationId, event.pathId, event.versionId, event.payloadDigest,
                event.timestamp, event.rbacDecision.value,
                json.dumps(event.detail, ensure_ascii=False) if event.detail else None,
            ),
        )
        self._conn.commit()
        return event

    def query_events(
        self, *, path_id: str | None = None, correlation_id: str | None = None
    ) -> list[Event]:
        if path_id is None and correlation_id is None:
            raise StoreError("INVALID_QUERY", "path_id or correlation_id required")
        clauses: list[str] = []
        params: list[str] = []
        if path_id is not None:
            clauses.append("path_id = ?")
            params.append(path_id)
        if correlation_id is not None:
            clauses.append("correlation_id = ?")
            params.append(correlation_id)
        rows = self._conn.execute(
            f"SELECT * FROM events WHERE {' AND '.join(clauses)} "
            "ORDER BY timestamp ASC, event_id ASC",
            params,
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def _row_to_event(self, row: sqlite3.Row) -> Event:
        detail = json.loads(row["detail_json"]) if row["detail_json"] else None
        return Event(
            eventId=row["event_id"], eventType=row["event_type"],
            actorId=row["actor_id"], agentId=row["agent_id"],
            correlationId=row["correlation_id"], pathId=row["path_id"],
            versionId=row["version_id"], payloadDigest=row["payload_digest"],
            timestamp=row["timestamp"],
            rbacDecision=RbacDecision(row["rbac_decision"]), detail=detail,
        )

    def _emit(
        self, *, event_type: str, actor_id: str, agent_id: str | None,
        correlation_id: str, path_id: str | None, version_id: str | None,
        rbac: RbacDecision, payload: Any = None, detail: dict[str, Any] | None = None,
    ) -> Event:
        return self.append_event(Event(
            eventType=event_type, actorId=actor_id, agentId=agent_id,
            correlationId=correlation_id, pathId=path_id, versionId=version_id,
            payloadDigest=_digest(payload) if payload is not None else None,
            rbacDecision=rbac, detail=detail,
        ))
