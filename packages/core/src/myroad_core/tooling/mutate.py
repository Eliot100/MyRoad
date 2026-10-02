"""Block/edge mutation ops for AgentTools."""
from __future__ import annotations

from typing import Any

from myroad_core.errors import StoreError
from myroad_core.models import (
    Block,
    BlockType,
    Edge,
    MasteryRule,
    OpResponse,
    RbacDecision,
    new_id,
)
from myroad_core.store_schema import _iso_now

__all__ = ["ToolsMutateMixin"]


class ToolsMutateMixin:
    def add_block(
        self,
        *,
        actor_id: str,
        correlation_id: str,
        path_id: str,
        version_id: str,
        type: str,
        title: str,
        agent_id: str | None = None,
        learning_objective: str | None = None,
        concept: str | None = None,
        content: dict[str, Any] | None = None,
        mastery_rule: dict[str, Any] | None = None,
        prerequisites: list[str] | None = None,
        source_refs: list[str] | None = None,
        block_id: str | None = None,
    ) -> OpResponse:
        missing = self._require_ids(
            correlation_id=correlation_id, path_id=path_id, version_id=version_id
        )
        if missing:
            return missing
        try:
            doc, err = self._load_mutable(
                path_id, version_id, correlation_id=correlation_id,
                actor_id=actor_id, agent_id=agent_id, event_type="block.add",
            )
            if err:
                return err
            assert doc is not None
            bid = block_id or new_id("blk")
            block = Block(
                blockId=bid,
                type=BlockType(type),
                title=title,
                learningObjective=learning_objective,
                concept=concept,
                content=content or {},
                masteryRule=MasteryRule.model_validate(mastery_rule) if mastery_rule else None,
                prerequisites=prerequisites or [],
                sourceRefs=source_refs or [],
            )
            blocks = list(doc.blocks)
            blocks.append(block)
            doc.blocks = blocks
            doc.updatedAt = _iso_now()
            self.store._write_version(doc, insert=False)
            evt = self.store._emit(
                event_type="block.add", actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                rbac=RbacDecision.allow,
                payload={"blockId": bid, "type": type, "title": title},
            )
            return OpResponse(
                ok=True, correlationId=correlation_id, pathId=path_id,
                versionId=version_id, changedObjectIds=[bid], status=doc.status,
                auditEventId=evt.eventId,
                data={"block": block.model_dump(mode="json", by_alias=True)},
            )
        except StoreError as exc:
            return self._err(
                correlation_id=correlation_id, code=exc.code, message=exc.message,
                path_id=path_id, version_id=version_id,
            )
        except (ValueError, TypeError) as exc:
            return self._err(
                correlation_id=correlation_id, code="INVALID_INPUT",
                message=str(exc), path_id=path_id, version_id=version_id,
            )
    def edit_block(
        self,
        *,
        actor_id: str,
        correlation_id: str,
        path_id: str,
        version_id: str,
        block_id: str,
        patch: dict[str, Any],
        agent_id: str | None = None,
    ) -> OpResponse:
        missing = self._require_ids(
            correlation_id=correlation_id, path_id=path_id, version_id=version_id
        )
        if missing:
            return missing
        try:
            doc, err = self._load_mutable(
                path_id, version_id, correlation_id=correlation_id,
                actor_id=actor_id, agent_id=agent_id, event_type="block.edit",
            )
            if err:
                return err
            assert doc is not None
            idx = next(
                (i for i, b in enumerate(doc.blocks) if b.blockId == block_id), None
            )
            if idx is None:
                evt = self.store._emit(
                    event_type="block.edit", actor_id=actor_id, agent_id=agent_id,
                    correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                    rbac=RbacDecision.deny, detail={"reason": "block_not_found"},
                )
                return self._err(
                    correlation_id=correlation_id, code="NOT_FOUND",
                    message=f"block {block_id} not found",
                    audit_event_id=evt.eventId, path_id=path_id, version_id=version_id,
                )
            # Preserve stable blockId; apply patch to remaining fields.
            safe_patch = {k: v for k, v in patch.items() if k != "blockId"}
            current = doc.blocks[idx].model_dump(mode="json", by_alias=True)
            current.update(safe_patch)
            current["blockId"] = block_id
            updated = Block.model_validate(current)
            blocks = list(doc.blocks)
            blocks[idx] = updated
            doc.blocks = blocks
            doc.updatedAt = _iso_now()
            self.store._write_version(doc, insert=False)
            evt = self.store._emit(
                event_type="block.edit", actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                rbac=RbacDecision.allow,
                payload={"blockId": block_id, "patchKeys": list(safe_patch.keys())},
            )
            return OpResponse(
                ok=True, correlationId=correlation_id, pathId=path_id,
                versionId=version_id, changedObjectIds=[block_id], status=doc.status,
                auditEventId=evt.eventId,
                data={"block": updated.model_dump(mode="json", by_alias=True)},
            )
        except StoreError as exc:
            return self._err(
                correlation_id=correlation_id, code=exc.code, message=exc.message,
                path_id=path_id, version_id=version_id,
            )
    def add_edge(
        self,
        *,
        actor_id: str,
        correlation_id: str,
        path_id: str,
        version_id: str,
        from_: str,
        to: str,
        relationship: str,
        agent_id: str | None = None,
        condition: dict[str, Any] | None = None,
        edge_id: str | None = None,
    ) -> OpResponse:
        missing = self._require_ids(
            correlation_id=correlation_id, path_id=path_id, version_id=version_id
        )
        if missing:
            return missing
        try:
            doc, err = self._load_mutable(
                path_id, version_id, correlation_id=correlation_id,
                actor_id=actor_id, agent_id=agent_id, event_type="edge.add",
            )
            if err:
                return err
            assert doc is not None
            block_ids = {b.blockId for b in doc.blocks}
            if from_ not in block_ids or to not in block_ids:
                evt = self.store._emit(
                    event_type="edge.add", actor_id=actor_id, agent_id=agent_id,
                    correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                    rbac=RbacDecision.deny, detail={"reason": "endpoint_missing"},
                )
                return self._err(
                    correlation_id=correlation_id, code="INVALID_EDGE",
                    message=f"both endpoints must exist (from={from_}, to={to})",
                    audit_event_id=evt.eventId, path_id=path_id, version_id=version_id,
                )
            eid = edge_id or new_id("edge")
            edge = Edge.model_validate({
                "edgeId": eid,
                "from": from_,
                "to": to,
                "relationship": relationship,
                "condition": condition,
            })
            edges = list(doc.edges)
            edges.append(edge)
            doc.edges = edges
            doc.updatedAt = _iso_now()
            self.store._write_version(doc, insert=False)
            evt = self.store._emit(
                event_type="edge.add", actor_id=actor_id, agent_id=agent_id,
                correlation_id=correlation_id, path_id=path_id, version_id=version_id,
                rbac=RbacDecision.allow,
                payload={"edgeId": eid, "from": from_, "to": to, "relationship": relationship},
            )
            return OpResponse(
                ok=True, correlationId=correlation_id, pathId=path_id,
                versionId=version_id, changedObjectIds=[eid], status=doc.status,
                auditEventId=evt.eventId,
                data={"edge": edge.model_dump(mode="json", by_alias=True)},
            )
        except StoreError as exc:
            return self._err(
                correlation_id=correlation_id, code=exc.code, message=exc.message,
                path_id=path_id, version_id=version_id,
            )
        except (ValueError, TypeError) as exc:
            return self._err(
                correlation_id=correlation_id, code="INVALID_INPUT",
                message=str(exc), path_id=path_id, version_id=version_id,
            )
