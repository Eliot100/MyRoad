"""PathStore write operations (create/save/revise/publish)."""
from __future__ import annotations

from myroad_core.errors import StoreError
from myroad_core.store_base import PathStoreBase
from myroad_core.store_draft_ops import DraftOpsMixin
from myroad_core.store_publish_ops import PublishOpsMixin

__all__ = ["PathStore", "StoreError"]


class PathStore(PathStoreBase, DraftOpsMixin, PublishOpsMixin):
    """Minimal SQLite-backed store implementing phase-1 persistence ops."""
