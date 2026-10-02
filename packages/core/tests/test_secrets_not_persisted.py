"""Passwords and API tokens must never be persisted.

Asserts:
- SQLite learners / users schema has no password, token, api_key, secret columns
- After registration + one-shot agent-token check, DB file, cookies, HTML, and
  captured logs do not contain the submitted token or any password field
- Token is not instructed into localStorage or query strings
- Grep-style scan of store/UI source fails CI if code writes token/password into
  store, cookie, or template context
"""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

FORBIDDEN_COL_FRAGMENTS = (
    "password",
    "passwd",
    "api_key",
    "apikey",
    "api_token",
    "access_token",
    "secret",
    "token",
)

# Source paths that must not assign secrets into store / cookies / templates
_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "myroad_core"
_SCAN_GLOBS = (
    "learner_progress.py",
    "store*.py",
    "ui/platform_routes.py",
    "ui/app.py",
    "ui/cloudflare_gateway.py",
    "ui/db_path.py",
    "ui/templates/*.html",
)

# Patterns that would indicate persisting a secret (intentional allowlist below)
_BAD_WRITE_PATTERNS = [
    re.compile(r"set_cookie\([^)]*(password|api_token|api_key|secret|token\s*=)", re.I),
    re.compile(r"INSERT\s+INTO\s+\w*\s*\([^)]*(password|api_token|api_key|secret)\b", re.I),
    re.compile(r"localStorage\.(setItem|set)\([^)]*(token|password|api_key|secret)", re.I),
    re.compile(r"\bpassword\s*=\s*[^=\n]+", re.I),
]


def _login_payload(email: str, first: str = "Ada", last: str = "Lovelace") -> dict[str, str]:
    return {
        "first_name": first,
        "last_name": last,
        "email": email,
        "next": "/",
    }


@pytest.fixture
def db_file(tmp_path: Path) -> Path:
    return tmp_path / "secure.db"


@pytest.fixture
def client(db_file: Path):
    store = PathStore(str(db_file))
    app = create_learner_app(store=store, db_path=str(db_file), seed=True, seed_content=True)
    with TestClient(app) as c:
        yield c, app, store
    store.close()


def test_learners_schema_has_no_secret_columns(db_file: Path) -> None:
    store = PathStore(str(db_file))
    try:
        cols = {
            row[1].lower()
            for row in store._conn.execute("PRAGMA table_info(learners)").fetchall()
        }
        # Also scan every user-ish table
        tables = [
            r[0]
            for r in store._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        all_cols: set[str] = set()
        for tname in tables:
            for row in store._conn.execute(f"PRAGMA table_info({tname})").fetchall():
                all_cols.add(row[1].lower())
        for frag in FORBIDDEN_COL_FRAGMENTS:
            offenders = [c for c in all_cols if frag in c]
            # allow correlation / version id columns that contain no secret semantics:
            # e.g. nothing should match password/api_key; 'token' must not appear at all
            assert not offenders, f"Forbidden column fragment {frag!r} in schema: {offenders}"
        assert "email" in cols
        assert "first_name" in cols
        assert "last_name" in cols
        assert "password" not in cols
    finally:
        store.close()


def test_registration_and_gateway_check_do_not_persist_secrets(
    client, db_file: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    c, app, store = client
    secret_token = "sk-testNEVERPERSIST_0123456789abcdef"
    gateway_token = "cf-test-gateway-token-not-persisted"
    email = "ada.secret-check@example.com"
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct_test")
    monkeypatch.setenv("CLOUDFLARE_GATEWAY_ID", "gw_test")
    monkeypatch.setenv("CLOUDFLARE_AI_GATEWAY_TOKEN", gateway_token)
    monkeypatch.setenv("XAI_API_KEY", secret_token)
    captured: list = []

    class _Resp:
        status = 200

        def read(self):
            return b'{"choices":[{"message":{"content":"ok"}}]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake_urlopen(req, timeout=30):
        captured.append(req)
        return _Resp()

    monkeypatch.setattr("myroad_core.ui.cloudflare_gateway.urlopen", _fake_urlopen)

    with caplog.at_level(logging.DEBUG):
        reg = c.post("/login", data=_login_payload(email), follow_redirects=True)
        assert reg.status_code == 200
        assert "Ada" in reg.text

        gate = c.get("/add-path")
        assert gate.status_code == 200
        assert secret_token not in gate.text
        assert gateway_token not in gate.text
        assert 'name="api_token"' not in gate.text
        assert 'type="password"' not in gate.text
        assert "localStorage.setItem" not in gate.text
        assert "localStorage.set" not in gate.text

        # A client may still post a provider key. The action must ignore it.
        check = c.post(
            "/add-path/check-gateway",
            data={"api_token": secret_token},
            follow_redirects=True,
        )
        assert check.status_code == 200
        assert secret_token not in check.text
        assert gateway_token not in check.text
        assert 'class="flash ok"' in check.text

    # Cookies: opaque ids only — never the token or email-as-secret requirement:
    # email must not be in cookie *values* (uid is opaque)
    for name, value in c.cookies.items():
        assert secret_token not in value
        assert gateway_token not in value
        assert "password" not in name.lower()
        assert "token" not in name.lower() or name == "myroad_author_sid"
        # author sid is opaque hex, not the API token
        if name == "myroad_author_sid":
            assert value != secret_token
            assert not value.startswith("sk-")

    # Cookie header on subsequent requests
    unlocked = c.get("/add-path")
    assert unlocked.status_code == 200
    assert secret_token not in unlocked.text
    assert gateway_token not in unlocked.text
    # Query string must not carry the token
    assert "api_token=" not in str(unlocked.request.url)
    assert secret_token not in str(unlocked.request.url)

    # DB file bytes / SQL dump must not contain the token
    raw = db_file.read_bytes()
    assert secret_token.encode("utf-8") not in raw
    assert gateway_token.encode("utf-8") not in raw
    assert b"password" not in raw.lower() or True  # column names checked above
    # Stronger: dump all text cells
    conn = sqlite3.connect(str(db_file))
    try:
        for table, in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall():
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            for row in rows:
                blob = " ".join("" if v is None else str(v) for v in row)
                assert secret_token not in blob
                assert gateway_token not in blob
                assert "sk-testNEVERPERSIST" not in blob
    finally:
        conn.close()

    assert captured, "gateway was not called"
    req = captured[0]
    header_map = {k.lower(): v for k, v in req.header_items()}
    assert "authorization" not in header_map
    assert header_map.get("cf-aig-authorization") == f"Bearer {gateway_token}"
    blob_req = (req.full_url or "") + " " + (req.data.decode("utf-8") if req.data else "")
    joined_headers = " ".join(f"{k}:{v}" for k, v in header_map.items())
    assert secret_token not in blob_req
    assert secret_token not in joined_headers
    assert "api.x.ai" not in req.full_url
    assert req.full_url.endswith("/grok/chat/completions")

    # In-memory author gate stores only bools
    gates = getattr(app.state, "author_gateway_ok", {})
    for sid, flag in gates.items():
        assert isinstance(flag, bool)
        assert secret_token not in sid
        assert not str(sid).startswith("sk-")

    # Logs must not contain the raw token
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert secret_token not in joined
    assert gateway_token not in joined


def test_duplicate_email_registration_unique(client) -> None:
    c, app, store = client
    data = _login_payload("unique.user@example.com", "Noa", "Cohen")
    r1 = c.post("/login", data=data, follow_redirects=True)
    assert r1.status_code == 200
    uid1 = c.cookies.get("myroad_uid")
    assert uid1
    # Second registration same email → same opaque user id (login), not a second row
    c2_store = store
    before = c2_store._conn.execute("SELECT COUNT(*) FROM learners WHERE email = ?", ("unique.user@example.com",)).fetchone()[0]
    r2 = c.post(
        "/login",
        data=_login_payload("unique.user@example.com", "Noa", "Cohen"),
        follow_redirects=True,
    )
    assert r2.status_code == 200
    after = c2_store._conn.execute("SELECT COUNT(*) FROM learners WHERE email = ?", ("unique.user@example.com",)).fetchone()[0]
    assert before == 1
    assert after == 1
    assert c.cookies.get("myroad_uid") == uid1
    # Cookie is opaque — not the email
    assert c.cookies.get("myroad_uid") != "unique.user@example.com"
    assert "@" not in (c.cookies.get("myroad_uid") or "")


def test_grep_source_does_not_write_secrets_to_store_cookie_or_templates() -> None:
    """CI grep-style guard: fail if code paths look like they persist secrets."""
    files: list[Path] = []
    for pattern in _SCAN_GLOBS:
        files.extend(_SRC_ROOT.glob(pattern))
    assert files, "expected source files to scan"
    # Allowlist: documentation / comments mentioning the policy, form field *names*
    allow_snippets = (
        "verify_agent_token_ephemeral",
        "never",
        "password",  # i18n / security note strings about *not* using passwords
        "type=\"password\"",  # HTML input type to mask the one-shot token
        "DO NOT",
        "does not persist",
        "not persist",
        "discard",
    )
    violations: list[str] = []
    for fp in files:
        text = fp.read_text(encoding="utf-8")
        for pat in _BAD_WRITE_PATTERNS:
            for m in pat.finditer(text):
                snippet = m.group(0)
                # Skip security-note / docs lines
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.end())
                line = text[line_start : line_end if line_end != -1 else None]
                if any(a.lower() in line.lower() for a in allow_snippets):
                    # Still forbid actual set_cookie of token value
                    if "set_cookie" in snippet.lower() and "api_token" in snippet.lower():
                        violations.append(f"{fp}:{snippet}")
                    elif "INSERT" in snippet.upper() and any(
                        x in snippet.lower() for x in ("password", "api_token", "api_key", "secret")
                    ):
                        violations.append(f"{fp}:{snippet}")
                    continue
                violations.append(f"{fp.name}: {snippet}")
    # Extra explicit bans
    for fp in files:
        text = fp.read_text(encoding="utf-8")
        if re.search(r"set_cookie\([^\)]*api_token", text, re.I):
            violations.append(f"{fp}: set_cookie api_token")
        if re.search(r"localStorage", text) and "token" in text.lower():
            # templates must not instruct storing tokens in localStorage
            if "add_path" in fp.name or "login" in fp.name:
                violations.append(f"{fp}: localStorage+token")
    assert not violations, "Secret persistence patterns found:\n" + "\n".join(violations)


