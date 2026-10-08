"""Test helper: sign in through the two-step email-code flow (issue #41).

Captures the emailed code with the app's ``login_code_sender`` hook, then posts
it to ``/login/verify``. Mirrors ``client.post("/login", ...)`` return values.
"""
from __future__ import annotations

from typing import Any


def request_login_code(client: Any, data: dict[str, str]) -> tuple[Any, list[tuple[str, str]]]:
    outbox: list[tuple[str, str]] = []
    app = client.app
    previous = getattr(app.state, "login_code_sender", None)
    app.state.login_code_sender = lambda email, code: outbox.append((email, code))
    try:
        resp = client.post("/login", data=data, follow_redirects=False)
    finally:
        app.state.login_code_sender = previous
    return resp, outbox


def login_with_code(client: Any, data: dict[str, str], *, follow_redirects: bool = True) -> Any:
    resp, outbox = request_login_code(client, data)
    location = resp.headers.get("location", "")
    if resp.status_code != 303 or not location.startswith("/login/verify") or not outbox:
        # Step-1 error (e.g. name_required): same as the old single POST.
        return client.get(location) if follow_redirects and location else resp
    return client.post(
        "/login/verify",
        data={"code": outbox[-1][1], "next": data.get("next", "/")},
        follow_redirects=follow_redirects,
    )
