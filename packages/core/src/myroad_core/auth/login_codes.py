"""One-time email codes for sign-in and email change (issue #41, hardened).

Sign-in emails a 6-digit code. Per code:
- expires after 15 minutes and works once;
- at most 5 checks (one atomic conditional UPDATE claims a check BEFORE any
  hashing, so parallel guesses can never exceed the limit);
- stored only as a salted PBKDF2-SHA256 hash (never in plain text);
- bound to a purpose ("login", or one side of an email change), so a code
  issued for one purpose is refused for any other.

Per email address, up to 3 login codes can be active at once (a new request
no longer cancels the code the real user is typing).

Wrong guesses are counted per email + client IP, never as one global counter
per email, so a stranger cannot lock the real user out:
- after 5 failures in 24 hours from one IP for one email, that IP must wait
  before each further check (exponential backoff, 2 s doubling, max 15 min);
- after 3 failures from one IP, or 15 failures for the email from all IPs,
  a CAPTCHA is required when a CAPTCHA provider is configured (see
  ``auth/captcha.py``; off by default). Without one, only the backoff applies.

Sends (codes and notices) are limited per email+IP, per email and per IP. A
limited request gets the same response as a sent one, and every request path
runs one PBKDF2 hash so known and unknown emails take the same time.

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
    "BACKOFF_AFTER_FAILURES",
    "CAPTCHA_AFTER_EMAIL_FAILURES",
    "CAPTCHA_AFTER_FAILURES",
    "CODE_DIGITS",
    "CODE_TTL_SECONDS",
    "LoginCodeMixin",
    "LoginRequest",
    "MAX_ACTIVE_CODES",
    "MAX_VERIFY_ATTEMPTS",
    "PURPOSE_EMAIL_CHANGE_CURRENT",
    "PURPOSE_EMAIL_CHANGE_NEW",
    "PURPOSE_LOGIN",
    "SEND_LIMITS",
    "backoff_seconds",
    "hash_code",
    "verify_code_hash",
]

CODE_DIGITS = 6
CODE_TTL_SECONDS = 15 * 60
MAX_VERIFY_ATTEMPTS = 5
MAX_ACTIVE_CODES = 3
FAILURE_WINDOW_SECONDS = 24 * 3600
# Per email + client IP, within FAILURE_WINDOW_SECONDS:
BACKOFF_AFTER_FAILURES = 5
BACKOFF_BASE_SECONDS = 2
BACKOFF_MAX_SECONDS = 15 * 60
CAPTCHA_AFTER_FAILURES = 3
# Per email, all IPs (distributed guessing): CAPTCHA for everyone, never a lock.
CAPTCHA_AFTER_EMAIL_FAILURES = 15
SEND_WINDOW_SECONDS = 15 * 60
# Sends allowed per SEND_WINDOW_SECONDS.
SEND_LIMITS = {"email_ip": 5, "email": 10, "ip": 30}
_PBKDF2_ITERATIONS = 120_000

PURPOSE_LOGIN = "login"
PURPOSE_EMAIL_CHANGE_CURRENT = "email_change_current"
PURPOSE_EMAIL_CHANGE_NEW = "email_change_new"

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
CREATE TABLE IF NOT EXISTS login_failures (
  email TEXT NOT NULL,
  client_ip TEXT NOT NULL,
  failed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_failures ON login_failures(email, client_ip, failed_at);
"""

_LOGIN_CODE_EXTRA_COLUMNS = (
    ("failures", "INTEGER NOT NULL DEFAULT 0"),
    ("client_ip", "TEXT"),
    ("purpose", "TEXT NOT NULL DEFAULT 'login'"),
    ("change_id", "TEXT"),
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


def _new_code() -> str:
    return f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"


def _dummy_hash() -> None:
    """Same PBKDF2 cost as issuing a code, for paths that issue none (timing)."""
    hash_code(_new_code())


def _normalize_code(raw: str | None) -> str:
    return "".join(ch for ch in (raw or "") if not ch.isspace() and ch != "-")


def _ip(client_ip: str | None) -> str:
    return (client_ip or "unknown")[:64]


def backoff_seconds(failures: int) -> int:
    """Wait required after the last failure, given failures for one email+IP."""
    if failures < BACKOFF_AFTER_FAILURES:
        return 0
    return min(BACKOFF_BASE_SECONDS * 2 ** (failures - BACKOFF_AFTER_FAILURES), BACKOFF_MAX_SECONDS)


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

    def _log_send(self, email: str, client_ip: str, now: datetime) -> None:
        self._conn.execute(
            "INSERT INTO login_send_log (email, client_ip, sent_at) VALUES (?,?,?)", (email, client_ip, _ts(now))
        )

    def _insert_code(
        self,
        *,
        email: str,
        code_hash: str,
        now: datetime,
        purpose: str,
        client_ip: str | None,
        first_name: str | None = None,
        last_name: str | None = None,
        locale: str = "he",
        change_id: str | None = None,
    ) -> str:
        challenge_id = secrets.token_urlsafe(24)
        self._conn.execute(
            "INSERT INTO login_codes (challenge_id, email, code_hash, first_name, last_name, locale, "
            "created_at, expires_at, client_ip, purpose, change_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                challenge_id, email, code_hash, first_name or None, last_name or None, locale or "he",
                _ts(now), _ts(now + timedelta(seconds=CODE_TTL_SECONDS)), client_ip, purpose, change_id,
            ),
        )
        return challenge_id

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
        Every path runs exactly one PBKDF2 hash, so they take the same time.
        Raises ValueError only for malformed input (email_required, email_invalid).
        """
        email_n = self._validate_email(email)  # type: ignore[attr-defined]
        now = now or _now()
        ip = _ip(client_ip)
        decoy = secrets.token_urlsafe(24)
        with self._lock:
            if not self._send_allowed(email_n, ip, now):
                kind: str = "rate_limited"
            else:
                self._log_send(email_n, ip, now)
                self._conn.commit()
                first = (first_name or "").strip()
                last = (last_name or "").strip()
                known = self.get_learner_by_email(email_n)  # type: ignore[attr-defined]
                kind = "code" if known or (first and last) else "no_account"
        if kind != "code":
            _dummy_hash()
            return LoginRequest(kind=kind, email=email_n, challenge_id=decoy)  # type: ignore[arg-type]
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
        """Create a login code challenge (no send limits; use request_login for HTTP).

        Returns (challenge_id, code); the DB keeps only the code's hash.
        Raises ValueError: email_required, email_invalid, name_required.
        """
        email_n = self._validate_email(email)  # type: ignore[attr-defined]
        first = (first_name or "").strip()
        last = (last_name or "").strip()
        now = now or _now()
        code = _new_code()
        code_hash = hash_code(code)
        with self._lock:
            if not self.get_learner_by_email(email_n) and (not first or not last):  # type: ignore[attr-defined]
                raise ValueError("name_required")
            challenge_id = self._insert_code(
                email=email_n, code_hash=code_hash, now=now, purpose=PURPOSE_LOGIN, client_ip=client_ip,
                first_name=first, last_name=last, locale=locale,
            )
            # Keep at most MAX_ACTIVE_CODES usable login codes per email: retire the oldest.
            self._conn.execute(
                "UPDATE login_codes SET used_at = ? WHERE email = ? AND purpose = ? AND used_at IS NULL "
                "AND expires_at > ? AND challenge_id NOT IN (SELECT challenge_id FROM login_codes "
                "WHERE email = ? AND purpose = ? AND used_at IS NULL AND expires_at > ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?)",
                (_ts(now), email_n, PURPOSE_LOGIN, _ts(now), email_n, PURPOSE_LOGIN, _ts(now), MAX_ACTIVE_CODES),
            )
            self._conn.commit()
        return challenge_id, code

    def get_login_challenge_email(self, challenge_id: str | None) -> str | None:
        if not challenge_id:
            return None
        row = self._conn.execute(
            "SELECT email FROM login_codes WHERE challenge_id = ? AND purpose = ?", (challenge_id, PURPOSE_LOGIN)
        ).fetchone()
        return row["email"] if row else None

    # ----- failures, backoff, CAPTCHA -----

    def _failure_stats(self, email: str, client_ip: str, now: datetime) -> tuple[int, str | None]:
        row = self._conn.execute(
            "SELECT COUNT(*), MAX(failed_at) FROM login_failures WHERE email = ? AND client_ip = ? AND failed_at > ?",
            (email, client_ip, _ts(now - timedelta(seconds=FAILURE_WINDOW_SECONDS))),
        ).fetchone()
        return int(row[0]), row[1]

    def _email_failures(self, email: str, now: datetime) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM login_failures WHERE email = ? AND failed_at > ?",
            (email, _ts(now - timedelta(seconds=FAILURE_WINDOW_SECONDS))),
        ).fetchone()[0]

    def login_backoff_remaining(self, email: str, client_ip: str, now: datetime | None = None) -> float:
        """Seconds this email+IP must still wait before the next check (0 = none)."""
        now = now or _now()
        with self._lock:
            count, last = self._failure_stats(email, _ip(client_ip), now)
        wait = backoff_seconds(count)
        if not wait or not last:
            return 0.0
        remaining = (datetime.fromisoformat(last) + timedelta(seconds=wait) - now).total_seconds()
        return max(0.0, remaining)

    def captcha_required_for(
        self, challenge_ids: str | list[str | None] | None, client_ip: str, now: datetime | None = None
    ) -> bool:
        """True when a check on these challenges should first pass a CAPTCHA.

        After CAPTCHA_AFTER_FAILURES from this IP for the email, or
        CAPTCHA_AFTER_EMAIL_FAILURES for the email from all IPs. Only enforced
        when a CAPTCHA provider is configured (the HTTP layer decides).
        """
        ids = [challenge_ids] if isinstance(challenge_ids, str) or challenge_ids is None else challenge_ids
        now = now or _now()
        ip = _ip(client_ip)
        with self._lock:
            for cid in ids:
                if not cid:
                    continue
                row = self._conn.execute("SELECT email FROM login_codes WHERE challenge_id = ?", (cid,)).fetchone()
                if not row:
                    continue
                if self._failure_stats(row["email"], ip, now)[0] >= CAPTCHA_AFTER_FAILURES:
                    return True
                if self._email_failures(row["email"], now) >= CAPTCHA_AFTER_EMAIL_FAILURES:
                    return True
        return False

    # ----- verifying -----

    def _check_code(
        self,
        challenge_id: str | None,
        code: str | None,
        *,
        purpose: str,
        client_ip: str | None,
        now: datetime,
    ) -> dict[str, Any]:
        """Claim one check, then compare the code. Returns the row; does NOT mark it used.

        Raises ValueError: code_required, code_invalid, code_slow_down,
        code_used, code_expired, code_locked, code_wrong.
        """
        entered = _normalize_code(code)
        if not entered:
            raise ValueError("code_required")
        if not challenge_id:
            raise ValueError("code_invalid")
        ip = _ip(client_ip)
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM login_codes WHERE challenge_id = ? AND purpose = ?", (challenge_id, purpose)
            ).fetchone()
            if not row:
                raise ValueError("code_invalid")
            if self.login_backoff_remaining(row["email"], ip, now) > 0:
                raise ValueError("code_slow_down")  # refused before any attempt or hashing
            # Claim one check atomically BEFORE hashing: unused, unexpired, under the per-code limit.
            claimed = self._conn.execute(
                "UPDATE login_codes SET attempts = attempts + 1 "
                "WHERE challenge_id = ? AND purpose = ? AND used_at IS NULL AND expires_at > ? AND attempts < ?",
                (challenge_id, purpose, _ts(now), MAX_VERIFY_ATTEMPTS),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM login_codes WHERE challenge_id = ?", (challenge_id,)).fetchone()
            if claimed.rowcount != 1:
                if row["used_at"]:
                    raise ValueError("code_used")
                if row["expires_at"] <= _ts(now):
                    raise ValueError("code_expired")
                raise ValueError("code_locked")
        ok = len(entered) == CODE_DIGITS and entered.isdigit() and verify_code_hash(entered, row["code_hash"])
        if not ok:
            with self._lock:
                self._conn.execute(
                    "UPDATE login_codes SET failures = failures + 1 WHERE challenge_id = ?", (challenge_id,)
                )
                self._conn.execute(
                    "INSERT INTO login_failures (email, client_ip, failed_at) VALUES (?,?,?)",
                    (row["email"], ip, _ts(now)),
                )
                self._conn.commit()
            raise ValueError("code_locked" if int(row["attempts"]) >= MAX_VERIFY_ATTEMPTS else "code_wrong")
        return dict(row)

    def _mark_code_used(self, challenge_id: str, now: datetime) -> bool:
        done = self._conn.execute(
            "UPDATE login_codes SET used_at = ? WHERE challenge_id = ? AND used_at IS NULL", (_ts(now), challenge_id)
        )
        return done.rowcount == 1

    def verify_login_challenge(
        self,
        challenge_id: str | None,
        code: str | None,
        *,
        client_ip: str = "unknown",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Check a login code and return the (possibly new) learner.

        Raises ValueError: code_required, code_invalid (unknown challenge or a
        code issued for another purpose), code_slow_down, code_used,
        code_expired, code_locked, code_wrong.
        """
        now = now or _now()
        row = self._check_code(challenge_id, code, purpose=PURPOSE_LOGIN, client_ip=client_ip, now=now)
        with self._lock:
            # Single use: only one caller can flip used_at.
            if not self._mark_code_used(row["challenge_id"], now):
                self._conn.commit()
                raise ValueError("code_used")
            self._conn.commit()
            return self.register_or_login(  # type: ignore[attr-defined]
                email=row["email"],
                first_name=row["first_name"] or "",
                last_name=row["last_name"] or "",
                locale=row["locale"] or "he",
            )
