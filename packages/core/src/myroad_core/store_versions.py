"""Version read/write helpers for PathStore."""
from __future__ import annotations

import json
from typing import Any

from myroad_core.errors import ImmutableError, NotFoundError
from myroad_core.models import PathStatus, PathVersion
from myroad_core.store_schema import _iso_now

__all__ = ["VersionMixin"]


class VersionMixin:
    def get_version(self, path_id: str, version_id: str) -> PathVersion:
        row = self._conn.execute(
            "SELECT document_json FROM versions WHERE path_id = ? AND version_id = ?",
            (path_id, version_id),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"version {version_id} not found for path {path_id}")
        return PathVersion.model_validate_json(row["document_json"])

    def get_path_latest(self, path_id: str) -> PathVersion:
        row = self._conn.execute(
            "SELECT document_json FROM versions WHERE path_id = ? "
            "ORDER BY version_num DESC LIMIT 1",
            (path_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"path {path_id} not found")
        return PathVersion.model_validate_json(row["document_json"])

    def list_versions(self, path_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT version_id, version_num, status, created_at, updated_at "
            "FROM versions WHERE path_id = ? ORDER BY version_num ASC",
            (path_id,),
        ).fetchall()
        if not rows:
            exists = self._conn.execute(
                "SELECT 1 FROM paths WHERE path_id = ?", (path_id,)
            ).fetchone()
            if exists is None:
                raise NotFoundError(f"path {path_id} not found")
        return [
            {
                "versionId": r["version_id"], "version": r["version_num"],
                "status": r["status"], "createdAt": r["created_at"],
                "updatedAt": r["updated_at"],
            }
            for r in rows
        ]

    def _require_mutable(self, doc: PathVersion) -> None:
        if doc.status == PathStatus.published:
            raise ImmutableError(f"version {doc.versionId} is published and immutable")
        if doc.status == PathStatus.archived:
            raise ImmutableError(f"version {doc.versionId} is archived")

    def _write_version(self, doc: PathVersion, *, insert: bool) -> None:
        payload = doc.model_dump(mode="json", by_alias=True)
        raw = json.dumps(payload, ensure_ascii=False)
        if insert:
            self._conn.execute(
                "INSERT INTO versions (version_id, path_id, version_num, status, "
                "document_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    doc.versionId, doc.pathId, doc.version, doc.status.value, raw,
                    doc.createdAt or _iso_now(), doc.updatedAt or _iso_now(),
                ),
            )
        else:
            self._conn.execute(
                "UPDATE versions SET status = ?, document_json = ?, updated_at = ?, "
                "version_num = ? WHERE version_id = ? AND path_id = ?",
                (
                    doc.status.value, raw, doc.updatedAt or _iso_now(), doc.version,
                    doc.versionId, doc.pathId,
                ),
            )
        self._conn.commit()
