#!/usr/bin/env python3
"""Smoke: health is public, catalog requires a session, publish has no human checkbox."""
from __future__ import annotations

import os
import sys

from fastapi.testclient import TestClient

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app


def main() -> int:
    # The in-process test client is plain http, which drops Secure cookies.
    os.environ.setdefault("MYROAD_DEV_INSECURE_COOKIES", "1")
    store = PathStore(":memory:")
    app = create_learner_app(store=store, seed=True, seed_content=False)
    client = TestClient(app)
    h = client.get("/health").json()
    assert h["status"] == "ok", h
    gated = client.get("/", follow_redirects=False)
    assert gated.status_code == 303
    assert "/login" in gated.headers["location"]
    # Two-step email login: capture the code instead of mailing / printing it.
    outbox: list[str] = []
    app.state.login_code_sender = lambda email, code: outbox.append(code)
    step1 = client.post(
        "/login",
        data={
            "first_name": "Smoke",
            "last_name": "User",
            "email": "smoke@example.com",
            "next": "/",
        },
        follow_redirects=False,
    )
    assert step1.headers["location"].startswith("/login/verify"), step1.headers
    assert client.get("/", follow_redirects=False).status_code == 303  # no session before the code
    client.post("/login/verify", data={"code": outbox[-1], "next": "/"}, follow_redirects=True)
    home = client.get("/", follow_redirects=False)
    assert home.status_code == 200, "not signed in"
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
