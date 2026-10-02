"""Thin agent-tool facade over PathStore (freeze/v0/03-agent-tool-contract.md).

Callable without HTTP. Every op emits an audit event via PathStore and returns
the shared OpResponse envelope. Never auto-publishes: publish denies when
agentId is present unless human_publisher=True.
"""
from __future__ import annotations

from myroad_core.store import PathStore
from myroad_core.tooling.draft import ToolsDraftMixin
from myroad_core.tooling.helpers import ToolsHelpersMixin
from myroad_core.tooling.mutate import ToolsMutateMixin
from myroad_core.tooling.publish import ToolsPublishMixin
from myroad_core.tooling.reads import ToolsReadMixin
from myroad_core.tooling.validate import ToolsValidateMixin


class AgentTools(
    ToolsHelpersMixin,
    ToolsReadMixin,
    ToolsMutateMixin,
    ToolsDraftMixin,
    ToolsValidateMixin,
    ToolsPublishMixin,
):
    """Contract-aligned tool surface over PathStore."""

    def __init__(self, store: PathStore) -> None:
        self.store = store


__all__ = ["AgentTools"]
