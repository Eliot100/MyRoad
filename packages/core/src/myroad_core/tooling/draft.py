"""Draft create/revise ops for AgentTools."""
from __future__ import annotations

from typing import Any

from myroad_core.errors import StoreError
from myroad_core.models import OpResponse

__all__ = ["ToolsDraftMixin"]


class ToolsDraftMixin:
    def create_draft(
        self,
        *,
        actor_id: str,
        correlation_id: str,
        name: str,
        goal: str | None = None,
        audience: dict[str, Any] | None = None,
        prerequisites: list[dict[str, Any]] | None = None,
        content_language: str = "he",
        ui_locale: str = "he-IL",
        description: str | None = None,
        agent_id: str | None = None,
        topic_hint: str | None = None,
    ) -> OpResponse:
        extra = {"topicHint": topic_hint} if topic_hint else None
        try:
            return self.store.create_draft(
                actor_id=actor_id, correlation_id=correlation_id, name=name,
                goal=goal, audience=audience, prerequisites=prerequisites,
                content_language=content_language, ui_locale=ui_locale,
                description=description, agent_id=agent_id, extra=extra,
            )
        except StoreError as exc:
            return self._err(
                correlation_id=correlation_id, code=exc.code, message=exc.message,
            )
    def revise_draft(
        self,
        *,
        actor_id: str,
        correlation_id: str,
        path_id: str,
        base_version_id: str,
        agent_id: str | None = None,
        change_set: dict[str, Any] | None = None,
        feedback_ids: list[str] | None = None,
    ) -> OpResponse:
        try:
            return self.store.revise_draft(
                actor_id=actor_id, correlation_id=correlation_id, path_id=path_id,
                base_version_id=base_version_id, agent_id=agent_id,
                change_set=change_set, feedback_ids=feedback_ids,
            )
        except StoreError as exc:
            return self._err(
                correlation_id=correlation_id, code=exc.code, message=exc.message,
                path_id=path_id, version_id=base_version_id,
            )
