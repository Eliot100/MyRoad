"""One-time email login codes (issue #41, hardened after Cyber security review).

Sign-in emails a 6-digit code. Per code:
- expires after 15 minutes and works once;
- at most 5 checks (one atomic conditional UPDATE claims a check BEFORE any
  hashing, so parallel guesses can never exceed the limit);
- stored only as a salted PBKDF2-SHA256 hash (never in plain text).

Per email address:
- up to 3 codes can be active at once (a new request no longer cancels the
  code the real user is typing; only the oldest beyond 3 is retired);
- at most 15 wrong guesses per 24 hours across all codes, then every code for
  that email is locked until the window passes.

Sends (codes and "no account" notices) are limited per email+IP, per email
and per IP. A limited request gets the same response as a sent one.

A new user's account is created only after the code is verified, and the login
session starts only then. No passwords anywhere.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

__all__ = [
    "CODE_DIGITS",
    "CODE_TTL_SECONDS",
    "LoginCodeMixin",
    "LoginRequest",
    "MAX_ACTIVE_CODES",
    "MAX_FAILURES_PER_EMAIL",
    "MAX_VERIFY_ATTEMPTS",
    "SEND_LIMITS",
    "hash_code",
    "verify_code_hash",
]

CODE_DIGITS = 6
CODE_TTL_SECONDS = 15 * 60
MAX_VERIFY_ATTEMPTS = 5
MAX_ACTIVE_CODES = 3
MAX_FAILURES_PER_EMAIL = 15
FAILURE_WINDOW_SECONDS = 24 * 3600
SEND_WINDOW_SECONDS = 15 * 60
# Sends allowed per SEND_WINDOW_SECONDS.
SEND_LIMITS = {"email_ip": 5, "email": 10, "ip": 30}
_PBKDF2_ITERATIONS = 120_000

_LOGIN_CODE_SCHEMA = """
CREATE TABLE IF NOT EXISTS login_codes (
  challenge_id TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  first_name TEXT,
  last_name TEXT,
  locale TEXT NOT NULL DEFAULT 'he',
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  used_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_login_codes_email ON login_codes(email);
CREATE TABLE IF NOT EXISTS login_send_log (
  email TEXT NOT NULL,
  client_ip TEXT NOT NULL,
  sent_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_send_email ON login_send_log(email, sent_at);
CREATE INDEX IF NOT EXISTS idx_login_send_ip ON login_send_log(client_ip, sent_at);
"""

_LOGIN_CODE_EXTRA_COLUMNS = (
    ("failures", "INTEGER NOT NULL DEFAULT 0"),
    ("client_ip", "TEXT"),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(dt: datetime) -> str:
    """Fixed-width UTC timestamp so SQL string comparison orders correctly."""
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def hash_code(code: str, *, salt: bytes | None = None, iterations: int = _PBKDF2_ITERATIONS) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_code_hash(code: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        expected = bytes.fromhex(digest_hex)
        got = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, expected)


def _normalize_code(raw: str | None) -> str:
    return "".join(ch for ch in (raw or "") if not ch.isspace() and ch != "-")


@dataclass(frozen=True)
class LoginRequest:
    """Outcome of a sign-in request. The HTTP response is the same for every kind.

    kind: "code" (send ``code``), "no_account" (send a notice, no code),
    "rate_limited" (send nothing). ``challenge_id`` is always set; for the last
    two it is a random value that matches no stored challenge.
    """

    kind: Literal["code", "no_account", "rate_limited"]
    email: str
    challenge_id: str
    code: str | None = None


class LoginCodeMixin:
    """Mixin expecting self._conn / self._lock plus LearnerProgressMixin helpers."""

    def ensure_login_code_schema(self) -> None:
        self._conn.executescript(_LOGIN_CODE_SCHEMA)
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(login_codes)").fetchall()}
        for col, decl in _LOGIN_CODE_EXTRA_COLUMNS:
            if col not in cols:
                self._conn.execute(f"ALTER TABLE login_codes ADD COLUMN {col} {decl}")
        self._conn.commit()

    # ----- sending -----

    def _send_allowed(self, email: str, client_ip: str, now: datetime) -> bool:
        since = _ts(now - timedelta(seconds=SEND_WINDOW_SECONDS))
        q = "SELECT COUNT(*) FROM login_send_log WHERE sent_at > ? AND "
        by_email_ip = self._conn.execute(q + "email = ? AND client_ip = ?", (since, email, client_ip)).fetchone()[0]
        by_email = self._conn.execute(q + "email = ?", (since, email)).fetchone()[0]
        by_ip = self._conn.execute(q + "client_ip = ?", (since, client_ip)).fetchone()[0]
        return (
            by_email_ip < SEND_LIMITS["email_ip"]
            and by_email < SEND_LIMITS["email"]
            and by_ip < SEND_LIMITS["ip"]
        )

    def request_login(
        self,
        *,
        email: str,
        first_name: str = "",
        last_name: str = "",
        locale: str = "he",
        client_ip: str = "unknown",
        now: datetime | None = None,
    ) -> LoginRequest:
        """Neutral sign-in request: known and unknown emails look the same to the caller.

        - known email: a code for that account (names ignored);
        - unknown email with first+last name: a code that registers on verify;
        - unknown email without names: "no_account" (a notice email, no code);
        - over a send limit: "rate_limited" (nothing sent).
        Raises ValueError only for malformed input (email_required, email_invalid).
        """
        email_n = self._validate_email(email)  # type: ignore[attr-defined]
        now = now or _now()
        ip = (client_ip or "unknown")[:64]
        decoy = secrets.token_urlsafe(24)
        with self._lock:
            if not self._send_allowed(email_n, ip, now):
                return LoginRequest(kind="rate_limited", email=email_n, challenge_id=decoy)
            self._conn.execute(
                "INSERT INTO login_send_log (email, client_ip, sent_at) VALUES (?,?,?)",
                (email_n, ip, _ts(now)),
            )
            self._conn.commit()
            first = (first_name or "").strip()
            last = (last_name or "").strip()
            if not self.get_learner_by_email(email_n) and (not first or not last):  # type: ignore[attr-defined]
                return LoginRequest(kind="no_account", email=email_n, challenge_id=decoy)
            cid, code = self.start_login_challenge(
                email=email_n, first_name=first, last_name=last, locale=locale, client_ip=ip, now=now
            )
        return LoginRequest(kind="code", email=email_n, challenge_id=cid, code=code)

    def start_login_challenge(
        self,
        *,
        email: str,
        first_name: str = "",
        last_name: str = "",
        locale: str = "he",
        client_ip: str | None = None,
        now: datetime | None = None,
    ) -> tuple[str, str]:
        """Create a code challenge (no send limits; use request_login for HTTP).

        Returns (challenge_id, code); the DB keeps only the code's hash.
        Raises ValueError: email_required, email_invalid, name_required.
        """
        email_n = self._validate_email(email)  # type: ignore[attr-defined]
        first = (first_name or "").strip()
        last = (last_name or "").strip()
        now = now or _now()
        code = f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"
        code_hash = hash_code(code)
        challenge_id = secrets.token_urlsafe(24)
        with self._lock:
            if not self.get_learner_by_email(email_n) and (not first or not last):  # type: ignore[attr-defined]
                raise ValueError("name_required")
            self._conn.execute(
                "INSERT INTO login_codes (challenge_id, email, code_hash, first_name, last_name, locale, "
                "created_at, expires_at, client_ip) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    challenge_id, email_n, code_hash, first or None, last or None, locale or "he",
                    _ts(now), _ts(now + timedelta(seconds=CODE_TTL_SECONDS)), client_ip,
                ),
            )
            # Keep at most MAX_ACTIVE_CODES usable codes per email: retire the oldest.
            self._conn.execute(
                "UPDATE login_codes SET used_at = ? WHERE email = ? AND used_at IS NULL AND expires_at > ? "
                "AND challenge_id NOT IN (SELECT challenge_id FROM login_codes WHERE email = ? "
                "AND used_at IS NULL AND expires_at > ? ORDER BY created_at DESC, rowid DESC LIMIT ?)",
                (_ts(now), email_n, _ts(now), email_n, _ts(now), MAX_ACTIVE_CODES),
            )
            self._conn.commit()
        return challenge_id, code

    def get_login_challenge_email(self, challenge_id: str | None) -> str | None:
        if not challenge_id:
            return None
        row = self._conn.execute(
            "SELECT email FROM login_codes WHERE challenge_id = ?", (challenge_id,)
        ).fetchone()
        return row["email"] if row else None

    # ----- verifying -----

    def _failures_since(self, email: str, now: datetime) -> int:
        return self._conn.execute(
            "SELECT COALESCE(SUM(failures), 0) FROM login_codes WHERE email = ? AND created_at > ?",
            (email, _ts(now - timedelta(seconds=FAILURE_WINDOW_SECONDS))),
        ).fetchone()[0]

    def verify_login_challenge(
        self, challenge_id: str | None, code: str | None, *, now: datetime | None = None
    ) -> dict[str, Any]:
        """Check the code and return the (possibly new) learner.

        Raises ValueError: code_required, code_invalid (unknown challenge),
        code_used, code_expired, code_locked, code_wrong.
        """
        entered = _normalize_code(code)
        if not entered:
            raise ValueError("code_required")
        if not challenge_id:
            raise ValueError("code_invalid")
        now = now or _now()
        window = _ts(now - timedelta(seconds=FAILURE_WINDOW_SECONDS))
        with self._lock:
            # Claim one check atomically BEFORE hashing: unused, unexpired, under
            # the per-code limit and under the per-email failure cap.
            claimed = self._conn.execute(
                "UPDATE login_codes SET attempts = attempts + 1 "
                "WHERE challenge_id = ? AND used_at IS NULL AND expires_at > ? AND attempts < ? "
                "AND (SELECT COALESCE(SUM(f.failures), 0) FROM login_codes f "
                "     WHERE f.email = login_codes.email AND f.created_at > ?) < ?",
                (challenge_id, _ts(now), MAX_VERIFY_ATTEMPTS, window, MAX_FAILURES_PER_EMAIL),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM login_codes WHERE challenge_id = ?", (challenge_id,)
            ).fetchone()
            if claimed.rowcount != 1:
                if not row:
                    raise ValueError("code_invalid")
                if row["used_at"]:
                    raise ValueError("code_used")
                if row["expires_at"] <= _ts(now):
                    raise ValueError("code_expired")
                raise ValueError("code_locked")
        ok = (
            len(entered) == CODE_DIGITS
            and entered.isdigit()
            and verify_code_hash(entered, row["code_hash"])
        )
        if not ok:
            with self._lock:
                self._conn.execute(
                    "UPDATE login_codes SET failures = failures + 1 WHERE challenge_id = ?", (challenge_id,)
                )
                self._conn.commit()
                locked = (
                    int(row["attempts"]) >= MAX_VERIFY_ATTEMPTS
                    or self._failures_since(row["email"], now) >= MAX_FAILURES_PER_EMAIL
                )
            raise ValueError("code_locked" if locked else "code_wrong")
        with self._lock:
            # Single use: only one caller can flip used_at.
            done = self._conn.execute(
                "UPDATE login_codes SET used_at = ? WHERE challenge_id = ? AND used_at IS NULL",
                (_ts(now), challenge_id),
            )
            self._conn.commit()
            if done.rowcount != 1:
                raise ValueError("code_used")
            return self.register_or_login(  # type: ignore[attr-defined]
                email=row["email"],
                first_name=row["first_name"] or "",
                last_name=row["last_name"] or "",
                locale=row["locale"] or "he",
            )
