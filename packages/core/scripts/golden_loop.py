#!/usr/bin/env python3
"""CLI entry for MyRoad golden loop E2E demo. See myroad_core.golden_loop."""
from __future__ import annotations

import sys

from myroad_core.golden_loop import main

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"golden_loop FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
