#!/usr/bin/env python3
"""Smoke: seed golden path, open learner UI routes, refuse publish without confirm."""
from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app


def main() -> int:
    store = PathStore(":memory:")
    app = create_learner_app(store=store, seed=True)
    client = TestClient(app)
    h = client.get("/health").json()
    assert h["status"] == "ok", h
    home = client.get("/")
    assert home.status_code == 200
    assert "MyRoad" in home.text
    denied = client.post("/publish", data={})
    assert "נדרש אישור אנושי" in denied.text
    print("smoke_ui OK", h["pathId"], h["versionIds"])
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
