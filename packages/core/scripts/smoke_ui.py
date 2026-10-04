#!/usr/bin/env python3
"""Smoke: health is public, catalog requires a session, publish has no human checkbox."""
from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app


def main() -> int:
    store = PathStore(":memory:")
    app = create_learner_app(store=store, seed=True, seed_content=False)
    client = TestClient(app)
    h = client.get("/health").json()
    assert h["status"] == "ok", h
    gated = client.get("/", follow_redirects=False)
    assert gated.status_code == 303
    assert "/login" in gated.headers["location"]
    client.post(
        "/login",
        data={
            "first_name": "Smoke",
            "last_name": "User",
            "email": "smoke@example.com",
            "next": "/",
        },
        follow_redirects=True,
    )
    home = client.get("/")
    assert home.status_code == 200
    assert "MyRoad" in home.text
    author = client.get("/author")
    assert author.status_code == 200
    assert "human_confirm" not in author.text
    published = client.post("/author/publish", data={})
    assert "נדרש אישור אנושי" not in published.text
    print("smoke_ui OK", h["pathId"], h["versionIds"])
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
