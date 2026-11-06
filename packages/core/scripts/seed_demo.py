"""Write a demo learner into a new SQLite file.

Separate from real learner data and from content. ``validate_paths`` only reads
``adult/`` and ``grade3/`` JSON, so this script is never loaded as a road.

Refuses the UI database (``packages/core/data/myroad_ui.db`` or ``MYROAD_DB``),
any path inside ``CONTENT_DIR`` or ``MyRoad-content``, and any file that already
exists.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from myroad_core.store import PathStore
from myroad_core.ui.db_path import DEFAULT_UI_DB, resolve_ui_db_path

DEMO_USER = "demo"


def refuse_reason(out: Path) -> str | None:
    if out.suffix.lower() == ".json":
        return "refusing to write a content file"
    resolved = out.expanduser().resolve()
    banned = {DEFAULT_UI_DB.resolve()}
    try:
        banned.add(Path(resolve_ui_db_path()).resolve())
    except OSError:
        pass
    if resolved in banned:
        return "refusing to write the real UI database"
    if "MyRoad-content" in resolved.parts:
        return "refusing to write inside content"
    content = (os.environ.get("CONTENT_DIR") or "").strip()
    if content:
        root = Path(content).expanduser().resolve()
        if resolved == root or root in resolved.parents:
            return "refusing to write inside content"
    return None


def write_demo(out: Path) -> None:
    reason = refuse_reason(out)
    if reason:
        raise SystemExit(reason)
    if out.exists():
        raise SystemExit("refusing to overwrite an existing file")
    out.parent.mkdir(parents=True, exist_ok=True)
    store = PathStore(str(out))
    try:
        store.upsert_learner(DEMO_USER, "הדגמה", locale="he")
        store.set_demo(DEMO_USER)
        store.set_weekly_goal(DEMO_USER, 2)
        store.set_road_plan(DEMO_USER, weekly_tiles=12, weekly_minutes=40)
        store.save_progress(
            DEMO_USER,
            "path_demo_not_content",
            version_id=None,
            node_index=0,
            mastered=set(),
            correct_taps=0,
            incorrect_taps=0,
        )
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write a demo learner into a new SQLite file.")
    ap.add_argument("--out", required=True, help="New .db path. Not the UI database, not content.")
    args = ap.parse_args(argv)
    write_demo(Path(args.out))
    print(f"wrote demo learner to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
