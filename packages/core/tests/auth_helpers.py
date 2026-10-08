"""Test helper: sign a test client in.

``login()`` is the stable entry point for tests. On this branch (#46) it posts
the one-step ``/login`` form, which starts a server-side session. The
email-code branch (#47) keeps the same signature and runs the two-step code
flow instead, so tests that call ``login()`` work in any merge order.
"""
from __future__ import annotations

from typing import Any

__all__ = ["login"]


def login(
    client: Any,
    email: str = "test@example.com",
    *,
    first_name: str = "Test",
    last_name: str = "User",
    next: str = "/",
    follow_redirects: bool = True,
) -> Any:
    """Sign in (registering on first use) and return the final response."""
    return client.post(
        "/login",
        data={"first_name": first_name, "last_name": last_name, "email": email, "next": next},
        follow_redirects=follow_redirects,
    )
