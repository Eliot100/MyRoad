"""One-time email login codes (issue #41).

Sign-in emails a 6-digit code. The code:
- expires after 15 minutes,
- works once,
- allows at most 5 wrong tries, then the challenge is locked,
- is stored only as a salted PBKDF2-SHA256 hash (never in plain text).

A new user's account is created only after the code is verified, and the login
session starts only then. No passwords anywhere.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

__all__ = [
    "CODE_DIGITS",
    "CODE_TTL_SECONDS",
    "LoginCodeMixin",
    "MAX_CODES_PER_WINDOW",
    "MAX_VERIFY_ATTEMPTS",
    "hash_code",
    "verify_code_hash",
]

CODE_DIGITS = 6
CODE_TTL_SECONDS = 15 * 60
MAX_VERIFY_ATTEMPTS = 5
# Send limit per email (stops mail-bombing and code farming).
MAX_CODES_PER_WINDOW = 5
CODE_WINDOW_SECONDS = 15 * 60
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
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


class LoginCodeMixin:
    """Mixin expecting self._conn plus LearnerProgressMixin helpers."""

    def ensure_login_code_schema(self) -> None:
        self._conn.executescript(_LOGIN_CODE_SCHEMA)
        self._conn.commit()

    def start_login_challenge(
        self,
        *,
        email: str,
        first_name: str = "",
        last_name: str = "",
        locale: str = "he",
        now: datetime | None = None,
    ) -> tuple[str, str]:
        """Create a challenge for ``email``. Returns (challenge_id, code).

        The code goes to the mailer only; the DB keeps its hash. Raises
        ValueError with a stable code: email_required, email_invalid,
        name_required (new email without names), too_many_codes.
        """
        email_n = self._validate_email(email)  # type: ignore[attr-defined]
        first = (first_name or "").strip()
        last = (last_name or "").strip()
        if not self.get_learner_by_email(email_n) and (not first or not last):  # type: ignore[attr-defined]
            raise ValueError("name_required")
        now = now or _now()
        window_start = (now - timedelta(seconds=CODE_WINDOW_SECONDS)).isoformat()
        recent = self._conn.execute(
            "SELECT COUNT(*) FROM login_codes WHERE email = ? AND created_at > ?",
            (email_n, window_start),
        ).fetchone()[0]
        if recent >= MAX_CODES_PER_WINDOW:
            raise ValueError("too_many_codes")
        # Only the newest code for an email is usable.
        self._conn.execute(
            "UPDATE login_codes SET used_at = ? WHERE email = ? AND used_at IS NULL",
            (now.isoformat(), email_n),
        )
        code = f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"
        challenge_id = secrets.token_urlsafe(24)
        self._conn.execute(
            "INSERT INTO login_codes (challenge_id, email, code_hash, first_name, last_name, locale, "
            "created_at, expires_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                challenge_id,
                email_n,
                hash_code(code),
                first or None,
                last or None,
                locale or "he",
                now.isoformat(),
                (now + timedelta(seconds=CODE_TTL_SECONDS)).isoformat(),
            ),
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
        row = self._conn.execute(
            "SELECT * FROM login_codes WHERE challenge_id = ?", (challenge_id,)
        ).fetchone()
        if not row:
            raise ValueError("code_invalid")
        if row["used_at"]:
            raise ValueError("code_used")
        if datetime.fromisoformat(row["expires_at"]) <= now:
            raise ValueError("code_expired")
        if int(row["attempts"]) >= MAX_VERIFY_ATTEMPTS:
            raise ValueError("code_locked")
        ok = (
            len(entered) == CODE_DIGITS
            and entered.isdigit()
            and verify_code_hash(entered, row["code_hash"])
        )
        if not ok:
            self._conn.execute(
                "UPDATE login_codes SET attempts = attempts + 1 WHERE challenge_id = ?",
                (challenge_id,),
            )
            self._conn.commit()
            if int(row["attempts"]) + 1 >= MAX_VERIFY_ATTEMPTS:
                raise ValueError("code_locked")
            raise ValueError("code_wrong")
        # Single use: only one caller can flip used_at.
        cur = self._conn.execute(
            "UPDATE login_codes SET used_at = ? WHERE challenge_id = ? AND used_at IS NULL",
            (now.isoformat(), challenge_id),
        )
        self._conn.commit()
        if cur.rowcount != 1:
            raise ValueError("code_used")
        return self.register_or_login(  # type: ignore[attr-defined]
            email=row["email"],
            first_name=row["first_name"] or "",
            last_name=row["last_name"] or "",
            locale=row["locale"] or "he",
        )
