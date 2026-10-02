"""Validate ops for AgentTools."""
from __future__ import annotations

from typing import Any

from myroad_core.errors import StoreError
from myroad_core.models import BlockType, OpResponse, RbacDecision

__all__ = ["ToolsValidateMixin"]


class ToolsValidateMixin:
    def validate_path(
        self,
        *,
        actor_id: str,
        correlation_id: str,
        path_id: str,
        version_id: str,
        agent_id: str | None = None,
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
                event_type="path.validate", actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                rbac=RbacDecision.deny, detail={"reason": exc.code},
            )
            return self._err(
                correlation_id=correlation_id, code=exc.code, message=exc.message,
                audit_event_id=evt.eventId, path_id=path_id, version_id=version_id,
            )
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        if not doc.name:
            errors.append({"code": "MISSING_NAME", "message": "path name is required"})
        if not doc.goal:
            warnings.append({"code": "MISSING_GOAL", "message": "goal is empty"})
        if not doc.blocks:
            errors.append({"code": "NO_BLOCKS", "message": "path has no blocks"})
        block_ids = {b.blockId for b in doc.blocks}
        referenced: set[str] = set()
        for edge in doc.edges:
            referenced.add(edge.from_)
            referenced.add(edge.to)
            if edge.from_ not in block_ids or edge.to not in block_ids:
                errors.append({
                    "code": "DANGLING_EDGE",
                    "message": f"edge {edge.edgeId} references missing block",
                    "edgeId": edge.edgeId,
                })
        orphans = block_ids - referenced
        if len(doc.blocks) > 1 and orphans:
            warnings.append({
                "code": "ORPHAN_BLOCKS",
                "message": "blocks not linked by any edge",
                "blockIds": sorted(orphans),
            })
        for b in doc.blocks:
            if b.type in (BlockType.practice, BlockType.assessment) and b.masteryRule is None:
                warnings.append({
                    "code": "MISSING_MASTERY_RULE",
                    "message": f"block {b.blockId} ({b.type.value}) has no masteryRule",
                    "blockId": b.blockId,
                })
            for ref in b.sourceRefs:
                src = next((s for s in doc.sources if s.sourceId == ref), None)
                if src is None:
                    warnings.append({
                        "code": "UNKNOWN_SOURCE_REF",
                        "message": f"block {b.blockId} refs unknown source {ref}",
                        "blockId": b.blockId, "sourceId": ref,
                    })
                elif not src.retrievalState.approved:
                    warnings.append({
                        "code": "UNAPPROVED_SOURCE",
                        "message": f"source {ref} is not approved",
                        "sourceId": ref, "blockId": b.blockId,
                    })
        if doc.contentLanguage and doc.uiLocale:
            # soft check: contentLanguage is usually a short code (he) vs locale (he-IL)
            if not doc.uiLocale.startswith(doc.contentLanguage.split("-")[0]):
                warnings.append({
                    "code": "LOCALE_MISMATCH",
                    "message": (
                        f"contentLanguage={doc.contentLanguage} may not match "
                        f"uiLocale={doc.uiLocale}"
                    ),
                })
        valid = len(errors) == 0
        evt = self.store._emit(
            event_type="path.validate", actor_id=actor_id, agent_id=agent_id,
            correlation_id=correlation_id, path_id=path_id, version_id=version_id,
            rbac=RbacDecision.allow,
            detail={"valid": valid, "errorCount": len(errors), "warningCount": len(warnings)},
        )
        return OpResponse(
            ok=valid, correlationId=correlation_id, pathId=path_id,
            versionId=version_id, status=doc.status, errors=errors,
            validationWarnings=warnings, auditEventId=evt.eventId,
            data={"valid": valid},
        )
