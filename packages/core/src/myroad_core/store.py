"""PathStore write operations (create/save/revise/publish) + learner progress."""
from __future__ import annotations

from myroad_core.auth.login_codes import LoginCodeMixin
from myroad_core.auth.sessions import SessionMixin
from myroad_core.errors import StoreError
from myroad_core.learner_progress import LearnerProgressMixin
from myroad_core.store_base import PathStoreBase
from myroad_core.store_draft_ops import DraftOpsMixin
from myroad_core.store_publish_ops import PublishOpsMixin

__all__ = ["PathStore", "StoreError"]


class PathStore(PathStoreBase, DraftOpsMixin, PublishOpsMixin, LearnerProgressMixin, SessionMixin, LoginCodeMixin):
    """Minimal SQLite-backed store implementing phase-1 persistence ops."""

    def __init__(self, db_path: str | object = ":memory:") -> None:
        super().__init__(db_path)  # type: ignore[arg-type]
        self.ensure_learner_schema()
        self.ensure_session_schema()
        self.ensure_login_code_schema()
