"""Pluggable CAPTCHA check, asked for after repeated wrong codes.

Off by default (dev, tests, demo). Enable on a public server with:
  MYROAD_CAPTCHA_PROVIDER   "turnstile" (Cloudflare Turnstile); empty/"off" = disabled
  MYROAD_CAPTCHA_SITE_KEY   public site key (rendered in the form)
  MYROAD_CAPTCHA_SECRET     server-side secret (server env only, never in git)

When enabled, a code check needs a solved CAPTCHA once the email has
``CAPTCHA_AFTER_FAILURES`` failures from the caller's IP, or
``CAPTCHA_AFTER_EMAIL_FAILURES`` from all IPs (see ``login_codes.py``).
Apps and tests can plug in any verifier by setting
``app.state.captcha_verifier`` to ``callable(token, client_ip) -> bool``
(and optionally ``app.state.captcha_site_key``).
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

__all__ = [
    "CAPTCHA_PROVIDER_ENV",
    "CAPTCHA_SITE_KEY_ENV",
    "CaptchaVerifier",
    "TurnstileVerifier",
    "captcha_site_key",
    "captcha_verifier_from_env",
]

CAPTCHA_PROVIDER_ENV = "MYROAD_CAPTCHA_PROVIDER"
CAPTCHA_SITE_KEY_ENV = "MYROAD_CAPTCHA_SITE_KEY"
_CAPTCHA_SERVER_KEY_ENV = "MYROAD_CAPTCHA_SECRET"
_TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

CaptchaVerifier = Callable[[str, str], bool]


class TurnstileVerifier:
    """Cloudflare Turnstile server-side check. Any error counts as a failed check."""

    def __init__(self, server_key: str, *, timeout: float = 5.0) -> None:
        if not server_key:
            raise ValueError(f"{_CAPTCHA_SERVER_KEY_ENV} is required for {CAPTCHA_PROVIDER_ENV}=turnstile")
        self._server_key = server_key
        self._timeout = timeout

    def __call__(self, token: str, client_ip: str) -> bool:
        if not token:
            return False
        data = urlencode({"secret": self._server_key, "response": token, "remoteip": client_ip}).encode()
        try:
            with urlopen(Request(_TURNSTILE_VERIFY_URL, data=data), timeout=self._timeout) as resp:  # noqa: S310
                return bool(json.loads(resp.read().decode("utf-8")).get("success"))
        except Exception:  # noqa: BLE001 - network/parse error: fail closed
            return False


def captcha_verifier_from_env() -> CaptchaVerifier | None:
    provider = (os.environ.get(CAPTCHA_PROVIDER_ENV) or "").strip().lower()
    if provider in ("", "off", "0", "none"):
        return None
    if provider == "turnstile":
        return TurnstileVerifier((os.environ.get(_CAPTCHA_SERVER_KEY_ENV) or "").strip())
    raise ValueError(f"unknown {CAPTCHA_PROVIDER_ENV}: {provider!r}")


def captcha_site_key() -> str:
    return (os.environ.get(CAPTCHA_SITE_KEY_ENV) or "").strip()
