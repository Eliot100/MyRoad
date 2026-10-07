"""Grok chat via Cloudflare AI Gateway (BYOK).

The xAI provider key stays in Cloudflare Secrets Store. This module does not
accept a provider API key, does not read a provider key from the environment,
and does not send a provider Authorization header. AI Gateway inserts the
stored key only when that header is absent. Any dummy value would be forwarded
and the provider call would fail.

Native base URL replaces https://api.x.ai/v1; chat uses /v1/chat/completions:
https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/grok

Authenticated gateways additionally send cf-aig-authorization. The default
BYOK alias is "default", so cf-aig-byok-alias is not sent.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request
from urllib.request import urlopen as _urlopen

ENV_ACCOUNT_ID = "CLOUDFLARE_ACCOUNT_ID"
ENV_GATEWAY_ID = "CLOUDFLARE_GATEWAY_ID"
ENV_GATEWAY_TOKEN = "CLOUDFLARE_AI_GATEWAY_TOKEN"
# Optional full grok base, for tests. Not a secret.
ENV_BASE_URL = "CLOUDFLARE_AI_GATEWAY_BASE_URL"

DEFAULT_MODEL = "grok-4"

_NOT_CONFIGURED = (
    "Cloudflare AI Gateway is not configured. "
    "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_GATEWAY_ID on the server. "
    "Do not paste an xAI API key into MyRoad."
)

# Tests may monkeypatch this name.
urlopen = _urlopen


class GatewayNotConfigured(RuntimeError):
    """Account id or gateway id is missing. No provider key is requested."""


class GatewayRequestError(RuntimeError):
    """Gateway HTTP call failed. The message never includes secrets or bodies."""

    def __init__(self, status: int) -> None:
        self.status = int(status)
        super().__init__(
            f"Cloudflare AI Gateway request failed (HTTP {self.status})"
        )


def _clean(name: str) -> str:
    return os.environ.get(name, "").strip()


def missing_gateway_env() -> list[str]:
    """Names of required gateway variables that are unset (values are never returned)."""
    return [name for name in (ENV_ACCOUNT_ID, ENV_GATEWAY_ID) if not _clean(name)]


def gateway_is_configured() -> bool:
    return not missing_gateway_env()


def grok_base_url() -> str:
    if not gateway_is_configured():
        raise GatewayNotConfigured(_NOT_CONFIGURED)
    override = _clean(ENV_BASE_URL)
    if override:
        return override.rstrip("/")
    account = quote(_clean(ENV_ACCOUNT_ID), safe="")
    gateway = quote(_clean(ENV_GATEWAY_ID), safe="")
    return f"https://gateway.ai.cloudflare.com/v1/{account}/{gateway}/grok"


def gateway_headers() -> dict[str, str]:
    """BYOK request headers. Never includes a provider Authorization header."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    token = _clean(ENV_GATEWAY_TOKEN)
    if token:
        headers["cf-aig-authorization"] = f"Bearer {token}"
    if any(name.lower() == "authorization" for name in headers):
        raise RuntimeError("refusing to send a provider authorization header")
    return headers


def call_grok_chat(
    messages: list[dict[str, str]],
    *,
    model: str = DEFAULT_MODEL,
    timeout: float = 30.0,
    urlopen_fn: Callable[..., Any] | None = None,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """POST {grok_base}/v1/chat/completions. Summary never includes request headers.

    ``response_format`` (e.g. ``{"type": "json_object"}``) asks Grok for strict JSON.
    """
    base = grok_base_url()
    url = f"{base}/v1/chat/completions"
    payload: dict[str, Any] = {"model": model, "messages": messages}
    if response_format:
        payload["response_format"] = response_format
    body = json.dumps(payload).encode("utf-8")
    headers = gateway_headers()
    req = Request(url, data=body, headers=headers, method="POST")
    opener = urlopen_fn or urlopen
    try:
        with opener(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200) or 200)
            raw = resp.read()
    except HTTPError as exc:
        raise GatewayRequestError(int(exc.code)) from None
    except URLError:
        raise GatewayRequestError(0) from None
    if status >= 400:
        raise GatewayRequestError(status)
    content = ""
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        choices = parsed.get("choices") or []
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
            if isinstance(message, dict):
                content = str(message.get("content") or "")
    return {"ok": True, "status": status, "model": model, "content": content}