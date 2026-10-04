"""Cloudflare AI Gateway BYOK: no provider key leaves MyRoad."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app
from myroad_core.ui.cloudflare_gateway import (
    GatewayNotConfigured,
    GatewayRequestError,
    call_grok_chat,
    gateway_headers,
    gateway_is_configured,
    grok_base_url,
)

_SRC = Path(__file__).resolve().parents[1] / "src" / "myroad_core"
_PROVIDER_KEY = "sk-provider-key-must-not-be-sent"


def _clear_gateway_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_GATEWAY_ID",
        "CLOUDFLARE_AI_GATEWAY_TOKEN",
        "CLOUDFLARE_AI_GATEWAY_BASE_URL",
        "XAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


class _Resp:
    def __init__(self, status: int = 200, body: bytes = b'{"choices":[{"message":{"content":"ok"}}]}'):
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _header_map(req) -> dict[str, str]:
    return {k.lower(): v for k, v in req.header_items()}


def test_missing_gateway_config_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_gateway_env(monkeypatch)
    monkeypatch.setenv("XAI_API_KEY", _PROVIDER_KEY)
    assert gateway_is_configured() is False
    with pytest.raises(GatewayNotConfigured) as exc:
        grok_base_url()
    message = str(exc.value)
    assert "not configured" in message
    assert "CLOUDFLARE_ACCOUNT_ID" in message
    assert _PROVIDER_KEY not in message
    assert "XAI_API_KEY" not in message


def test_add_path_missing_config_does_not_ask_for_provider_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_gateway_env(monkeypatch)
    called = {"n": 0}

    def _boom(req, timeout=30):
        called["n"] += 1
        raise AssertionError("gateway must not be called when unconfigured")

    monkeypatch.setattr("myroad_core.ui.cloudflare_gateway.urlopen", _boom)
    store = PathStore(str(tmp_path / "gw.db"))
    app = create_learner_app(store=store, db_path=str(tmp_path / "gw.db"), seed=True, seed_content=False)
    try:
        with TestClient(app) as client:
            client.cookies.set("myroad_locale", "en")
            client.post(
                "/login",
                data={
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "email": "ada.gateway@example.com",
                    "next": "/add-path",
                },
                follow_redirects=True,
            )
            page = client.get("/add-path")
            assert page.status_code == 200
            assert "Cloudflare AI Gateway is not configured" in page.text
            assert "Do not paste an xAI API key into MyRoad" in page.text
            assert "name=\"api_token\"" not in page.text
            assert "type=\"password\"" not in page.text
            assert _PROVIDER_KEY not in page.text
            failed = client.post("/add-path/check-gateway", data={"api_token": _PROVIDER_KEY})
            assert failed.status_code == 200
            assert "Cloudflare AI Gateway is not configured" in failed.text
            assert _PROVIDER_KEY not in failed.text
            assert called["n"] == 0
    finally:
        store.close()


def test_chat_request_omits_provider_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_gateway_env(monkeypatch)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct_test")
    monkeypatch.setenv("CLOUDFLARE_GATEWAY_ID", "gw_test")
    monkeypatch.setenv("CLOUDFLARE_AI_GATEWAY_TOKEN", "cf-token-for-gateway-only")
    monkeypatch.setenv("CLOUDFLARE_AI_GATEWAY_BASE_URL", "http://gateway.test/v1/acct_test/gw_test/grok")
    monkeypatch.setenv("XAI_API_KEY", _PROVIDER_KEY)
    seen = []

    def _fake(req, timeout=30):
        seen.append(req)
        return _Resp()

    result = call_grok_chat([{"role": "user", "content": "ping"}], urlopen_fn=_fake)
    assert result["ok"] is True
    assert _PROVIDER_KEY not in str(result)
    assert "cf-token-for-gateway-only" not in str(result)
    req = seen[0]
    headers = _header_map(req)
    assert "authorization" not in headers
    assert headers["cf-aig-authorization"] == "Bearer cf-token-for-gateway-only"
    assert "cf-aig-byok-alias" not in headers
    assert req.full_url == "http://gateway.test/v1/acct_test/gw_test/grok/v1/chat/completions"
    raw = req.data.decode("utf-8")
    assert _PROVIDER_KEY not in raw
    assert json.loads(raw)["model"] == "grok-4"
    built = gateway_headers()
    assert "Authorization" not in built
    assert all(k.lower() != "authorization" for k in built)


def test_unauthenticated_gateway_omits_cf_header(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_gateway_env(monkeypatch)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_GATEWAY_ID", "my gateway")
    assert grok_base_url() == "https://gateway.ai.cloudflare.com/v1/acct/my%20gateway/grok"
    headers = gateway_headers()
    assert "cf-aig-authorization" not in headers
    assert all(k.lower() != "authorization" for k in headers)


def test_gateway_http_error_hides_body(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_gateway_env(monkeypatch)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_GATEWAY_ID", "gw")

    def _fake(req, timeout=30):
        raise HTTPError(req.full_url, 401, "nope", hdrs=None, fp=None)

    with pytest.raises(GatewayRequestError) as exc:
        call_grok_chat([{"role": "user", "content": "ping"}], urlopen_fn=_fake)
    assert exc.value.status == 401
    assert _PROVIDER_KEY not in str(exc.value)
    assert "Bearer" not in str(exc.value)


def test_source_never_reads_provider_key() -> None:
    offenders = []
    for path in _SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "XAI_API_KEY" in text or "token_check" in text:
            offenders.append(str(path))
        if "api_token" in text:
            offenders.append(str(path) + ":api_token")
    assert not offenders
    gateway = (_SRC / "ui" / "cloudflare_gateway.py").read_text(encoding="utf-8")
    assert '["Authorization"]' not in gateway
    assert "headers['Authorization']" not in gateway
    template = (_SRC / "ui" / "templates" / "add_path.html").read_text(encoding="utf-8")
    assert "api_token" not in template
    assert "password" not in template
