"""PathStoreBase = connection + events + version helpers."""
from __future__ import annotations

from myroad_core.errors import StoreError
from myroad_core.store_events import EventMixin
from myroad_core.store_schema import SqliteConnMixin, _digest, _iso_now
from myroad_core.store_versions import VersionMixin

__all__ = ["PathStoreBase", "StoreError", "_iso_now", "_digest"]


class PathStoreBase(SqliteConnMixin, EventMixin, VersionMixin):
    """SQLite connection, schema, events, and version read/write helpers."""
