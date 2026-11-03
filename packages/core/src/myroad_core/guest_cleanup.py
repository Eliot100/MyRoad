"""Delete guest learners idle for 30+ days and all their rows (#241, decision 0014).

Run: ``python -m myroad_core.guest_cleanup [--db PATH] [--days 30]`` (default DB: MYROAD_DB,
as the app). Idempotent; safe from cron. The app also runs it once at every start.
"""
from __future__ import annotations

import argparse

from myroad_core.learner_progress import GUEST_RETENTION_DAYS
from myroad_core.store import PathStore
from myroad_core.ui.db_path import resolve_ui_db_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=None)
    ap.add_argument("--days", type=int, default=GUEST_RETENTION_DAYS)
    args = ap.parse_args(argv)
    store = PathStore(args.db or resolve_ui_db_path())
    try:
        print(f"deleted {store.purge_stale_guests(args.days)} stale guest learner(s)")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
