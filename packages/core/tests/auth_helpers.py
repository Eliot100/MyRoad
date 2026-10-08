"""Test helpers: sign in through the two-step email-code flow (issue #41).

``login()`` is the stable entry point for tests (same signature as on #46,
where it posts the one-step form), so tests that call it work in any merge
order. ``login_with_code`` captures the emailed code with the app's
``login_code_sender`` hook, then posts it to ``/login/verify``. Both mirror
``client.post("/login", ...)`` return values.
"""
from __future__ import annotations

from typing import Any

__all__ = ["login", "login_with_code", "request_login_code"]


def request_login_code(client: Any, data: dict[str, str]) -> tuple[Any, list[tuple[str, str]]]:
    outbox: list[tuple[str, str]] = []
    app = client.app
    previous = getattr(app.state, "login_code_sender", None)
    previous_notice = getattr(app.state, "login_notice_sender", None)
    app.state.login_code_sender = lambda email, code: outbox.append((email, code))
    if previous_notice is None:
        app.state.login_notice_sender = lambda email: None  # "no account" notice: nothing to capture
    try:
        resp = client.post("/login", data=data, follow_redirects=False)
    finally:
        app.state.login_code_sender = previous
        app.state.login_notice_sender = previous_notice
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


def login(
    client: Any,
    email: str = "test@example.com",
    *,
    first_name: str = "Test",
    last_name: str = "User",
    next: str = "/",
    follow_redirects: bool = True,
) -> Any:
    """Sign in (registering on first use) with the email-code flow; return the final response."""
    return login_with_code(
        client,
        {"first_name": first_name, "last_name": last_name, "email": email, "next": next},
        follow_redirects=follow_redirects,
    )
