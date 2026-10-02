"""Resolve the SQLite file used by the platform UI.

Default (survives process restart):
  packages/core/data/myroad_ui.db

Override with env ``MYROAD_DB`` (absolute or relative path).
``:memory:`` is allowed for tests only — never the default uvicorn entrypoint.
"""
from __future__ import annotations

import os
from pathlib import Path

_PKG_CORE = Path(__file__).resolve().parents[3]
DEFAULT_UI_DB = _PKG_CORE / "data" / "myroad_ui.db"


def resolve_ui_db_path() -> str:
    raw = (os.environ.get("MYROAD_DB") or "").strip()
    if raw:
        if raw == ":memory:":
            return ":memory:"
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path.resolve())
    DEFAULT_UI_DB.parent.mkdir(parents=True, exist_ok=True)
    return str(DEFAULT_UI_DB)
