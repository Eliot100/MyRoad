"""One-time email codes for sign-in and email change (issues #41, #49, #50).

Sign-in emails an 8-digit code (10^8 possible values). Per code:
- expires after 15 minutes and works once;
- at most 5 checks (one atomic conditional UPDATE claims a check BEFORE any
  hashing, so parallel guesses can never exceed the limit);
- stored only as a salted PBKDF2-SHA256 hash (never in plain text);
- bound to a purpose ("login", or one side of an email change), so a code
  issued for one purpose is refused for any other.

Per email + IP, up to 3 login codes can be active at once; a 4th from the
same IP retires that IP's oldest. Requests from other IPs never cancel the
code the real user is typing (#50).

Trusted pairs: an email + client IP that signed in successfully in the last
90 days. Per-email limits never apply to a trusted pair, so an attacker on
other IPs cannot stop a returning user's codes or lock their correct code.

Verify limits (wrong codes, rolling 24 hours):
- per email + IP: after 5 failures that IP waits before each further check
  (2 s doubling, max 15 min; ``code_slow_down``, no attempt used);
- per IP, across all emails: at most 50 failures, then ``code_slow_down``;
- per email, from untrusted IPs (all of them together): at most 30 checks
  that were wrong (``EMAIL_FAILURE_BUDGET``). Over it, an untrusted check is
  refused with ``account_limited`` unless a CAPTCHA was solved. Each check is
  reserved before hashing, so parallel requests cannot pass the budget.
  Worst case without a CAPTCHA: 30 guesses per email per day from rotating
  IPs (was ~4,800 with 6-digit codes), i.e. a 3 in 10 million daily chance.
- a CAPTCHA (when configured; see ``auth/captcha.py``, off by default) is
  asked after 3 failures from one IP, 15 for the email, or once the budget is
  used up, and a solved CAPTCHA lets the real user through.

Send limits (codes and notices, rolling 15 minutes):
- per email + IP: 5 (each IP has its own bucket; others cannot use it up);
- per IP, across all emails: 30;
- per email, from untrusted IPs: 20 (mail-bomb guard). Over it the request
  is not silently dropped: with a CAPTCHA configured the user is asked to
  solve it and the code is sent; without one the user is told to wait or use
  a device they signed in from before. Trusted pairs are exempt.
Own-bucket limits (email+IP, IP) answer like a sent request.

Every request path runs one PBKDF2 hash so known and unknown emails take the
same time. A new user's account is created only after the code is verified,
and the login session starts only then. No passwords anywhere.
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
    "EMAIL_FAILURE_BUDGET",
    "IP_FAILURE_BUDGET",
    "TRUST_DAYS",
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

CODE_DIGITS = 8
CODE_TTL_SECONDS = 15 * 60
MAX_VERIFY_ATTEMPTS = 5
MAX_ACTIVE_CODES = 3
FAILURE_WINDOW_SECONDS = 24 * 3600
# Per email + client IP, within FAILURE_WINDOW_SECONDS:
BACKOFF_AFTER_FAILURES = 5
BACKOFF_BASE_SECONDS = 2
BACKOFF_MAX_SECONDS = 15 * 60
CAPTCHA_AFTER_FAILURES = 3
# Per email, all IPs (distributed guessing): ask for a CAPTCHA (when configured).
CAPTCHA_AFTER_EMAIL_FAILURES = 15
# Per email, untrusted IPs together: wrong checks allowed per FAILURE_WINDOW_SECONDS
# without a solved CAPTCHA. This is the worst-case daily guess budget per email.
EMAIL_FAILURE_BUDGET = 30
# Per IP, across all emails, per FAILURE_WINDOW_SECONDS.
IP_FAILURE_BUDGET = 50
# An email + IP that signed in successfully stays trusted this long.
TRUST_DAYS = 90
SEND_WINDOW_SECONDS = 15 * 60
# Sends allowed per SEND_WINDOW_SECONDS. "email" counts untrusted IPs only.
SEND_LIMITS = {"email_ip": 5, "email": 20, "ip": 30}
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
CREATE TABLE IF NOT EXISTS login_trusted (
  email TEXT NOT NULL,
  client_ip TEXT NOT NULL,
  trusted_at TEXT NOT NULL,
  PRIMARY KEY (email, client_ip)
);
"""

_EXTRA_COLUMNS = {
    "login_send_log": (("trusted", "INTEGER NOT NULL DEFAULT 0"),),
    "login_failures": (("trusted", "INTEGER NOT NULL DEFAULT 0"),),
}

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
    "rate_limited" (this IP's own bucket is full; send nothing, answer as if
    sent), "email_limited" (the per-email cap for untrusted IPs is full; the
    caller asks for a CAPTCHA or tells the user to wait, never drops silently). ``challenge_id`` is always set; for the last
    two it is a random value that matches no stored challenge.
    """

    kind: Literal["code", "no_account", "rate_limited", "email_limited"]
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
        for table, extra in _EXTRA_COLUMNS.items():
            have = {row[1] for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for col, decl in extra:
                if col not in have:
                    self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        self._conn.commit()

    # ----- trusted email + IP pairs -----

    def _is_trusted(self, email: str, client_ip: str, now: datetime) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM login_trusted WHERE email = ? AND client_ip = ? AND trusted_at > ?",
            (email, client_ip, _ts(now - timedelta(days=TRUST_DAYS))),
        ).fetchone()
        return row is not None

    def _mark_trusted(self, email: str, client_ip: str, now: datetime) -> None:
        if client_ip in ("", "unknown"):
            return  # never trust an unknown address
        self._conn.execute(
            "INSERT INTO login_trusted (email, client_ip, trusted_at) VALUES (?,?,?) "
            "ON CONFLICT(email, client_ip) DO UPDATE SET trusted_at = excluded.trusted_at",
            (email, client_ip, _ts(now)),
        )

    # ----- sending -----

    def _send_status(self, email: str, client_ip: str, now: datetime, *, trusted: bool) -> str:
        """"ok", "rate_limited" (this IP's own bucket) or "email_limited" (per-email cap, untrusted)."""
        since = _ts(now - timedelta(seconds=SEND_WINDOW_SECONDS))
        q = "SELECT COUNT(*) FROM login_send_log WHERE sent_at > ? AND "
        by_email_ip = self._conn.execute(q + "email = ? AND client_ip = ?", (since, email, client_ip)).fetchone()[0]
        by_ip = self._conn.execute(q + "client_ip = ?", (since, client_ip)).fetchone()[0]
        if by_email_ip >= SEND_LIMITS["email_ip"] or by_ip >= SEND_LIMITS["ip"]:
            return "rate_limited"
        if not trusted:
            by_email = self._conn.execute(q + "email = ? AND trusted = 0", (since, email)).fetchone()[0]
            if by_email >= SEND_LIMITS["email"]:
                return "email_limited"
        return "ok"

    def _log_send(self, email: str, client_ip: str, now: datetime, *, trusted: bool = False) -> None:
        self._conn.execute(
            "INSERT INTO login_send_log (email, client_ip, sent_at, trusted) VALUES (?,?,?,?)",
            (email, client_ip, _ts(now), 1 if trusted else 0),
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
        captcha_ok: bool = False,
    ) -> LoginRequest:
        """Neutral sign-in request: known and unknown emails look the same to the caller.

        - known email: a code for that account (names ignored);
        - unknown email with first+last name: a code that registers on verify;
        - unknown email without names: "no_account" (a notice email, no code);
        - over this IP's own send bucket: "rate_limited" (nothing sent);
        - over the per-email cap for untrusted IPs: "email_limited", unless
          ``captcha_ok`` (the caller verified a CAPTCHA). Trusted pairs are exempt.
        Every path runs exactly one PBKDF2 hash, so they take the same time.
        Raises ValueError only for malformed input (email_required, email_invalid).
        """
        email_n = self._validate_email(email)  # type: ignore[attr-defined]
        now = now or _now()
        ip = _ip(client_ip)
        decoy = secrets.token_urlsafe(24)
        with self._lock:
            trusted = self._is_trusted(email_n, ip, now)
            status = self._send_status(email_n, ip, now, trusted=trusted)
            if status == "email_limited" and captcha_ok:
                status = "ok"
            if status != "ok":
                kind: str = status
            else:
                self._log_send(email_n, ip, now, trusted=trusted)
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
            # Keep at most MAX_ACTIVE_CODES usable login codes per email + IP: retire the oldest
            # from the SAME IP only, so requests from other IPs never cancel the real user's code
            # (#50). Guessing stays capped by the per-email failure budget, not by this count.
            ip_key = client_ip or ""
            self._conn.execute(
                "UPDATE login_codes SET used_at = ? WHERE email = ? AND purpose = ? AND used_at IS NULL "
                "AND expires_at > ? AND IFNULL(client_ip, '') = ? AND challenge_id NOT IN "
                "(SELECT challenge_id FROM login_codes WHERE email = ? AND purpose = ? AND used_at IS NULL "
                "AND expires_at > ? AND IFNULL(client_ip, '') = ? ORDER BY created_at DESC, rowid DESC LIMIT ?)",
                (_ts(now), email_n, PURPOSE_LOGIN, _ts(now), ip_key,
                 email_n, PURPOSE_LOGIN, _ts(now), ip_key, MAX_ACTIVE_CODES),
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

    def _email_failures(self, email: str, now: datetime, *, untrusted_only: bool = False) -> int:
        q = "SELECT COUNT(*) FROM login_failures WHERE email = ? AND failed_at > ?"
        if untrusted_only:
            q += " AND trusted = 0"
        return self._conn.execute(q, (email, _ts(now - timedelta(seconds=FAILURE_WINDOW_SECONDS)))).fetchone()[0]

    def _ip_failures(self, client_ip: str, now: datetime) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM login_failures WHERE client_ip = ? AND failed_at > ?",
            (client_ip, _ts(now - timedelta(seconds=FAILURE_WINDOW_SECONDS))),
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

    def email_budget_exhausted(self, email: str, client_ip: str, now: datetime | None = None) -> bool:
        """True when an untrusted check on this email needs a CAPTCHA (or must wait)."""
        now = now or _now()
        ip = _ip(client_ip)
        with self._lock:
            if self._is_trusted(email, ip, now):
                return False
            return self._email_failures(email, now, untrusted_only=True) >= EMAIL_FAILURE_BUDGET

    def captcha_required_for(
        self, challenge_ids: str | list[str | None] | None, client_ip: str, now: datetime | None = None
    ) -> bool:
        """True when a check on these challenges should first pass a CAPTCHA.

        After CAPTCHA_AFTER_FAILURES from this IP for the email,
        CAPTCHA_AFTER_EMAIL_FAILURES for the email from all IPs, or once the
        email's untrusted budget is used up (the email-wide triggers skip
        trusted pairs). Only enforced
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
                if self._is_trusted(row["email"], ip, now):
                    continue  # email-wide triggers never apply to a trusted pair
                if self._email_failures(row["email"], now) >= CAPTCHA_AFTER_EMAIL_FAILURES:
                    return True
                if self._email_failures(row["email"], now, untrusted_only=True) >= EMAIL_FAILURE_BUDGET:
                    return True
        return False

    def send_captcha_required(self, email: str, client_ip: str, now: datetime | None = None) -> bool:
        """True when a send for this email from this IP is over the untrusted per-email cap."""
        now = now or _now()
        ip = _ip(client_ip)
        try:
            email_n = self._validate_email(email)  # type: ignore[attr-defined]
        except ValueError:
            return False
        with self._lock:
            trusted = self._is_trusted(email_n, ip, now)
            return self._send_status(email_n, ip, now, trusted=trusted) == "email_limited"

    # ----- verifying -----

    def _check_code(
        self,
        challenge_id: str | None,
        code: str | None,
        *,
        purpose: str,
        client_ip: str | None,
        now: datetime,
        captcha_ok: bool = False,
    ) -> dict[str, Any]:
        """Claim one check, then compare the code. Returns the row; does NOT mark it used.

        Raises ValueError: code_required, code_invalid, code_slow_down,
        account_limited, code_used, code_expired, code_locked, code_wrong.
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
            email = row["email"]
            # All refusals below happen before any attempt is used or any hashing.
            if self.login_backoff_remaining(email, ip, now) > 0:
                raise ValueError("code_slow_down")
            if self._ip_failures(ip, now) >= IP_FAILURE_BUDGET:
                raise ValueError("code_slow_down")
            trusted = self._is_trusted(email, ip, now)
            if (
                not trusted
                and not captcha_ok
                and self._email_failures(email, now, untrusted_only=True) >= EMAIL_FAILURE_BUDGET
            ):
                raise ValueError("account_limited")
            # Claim one check atomically BEFORE hashing: unused, unexpired, under the per-code limit.
            claimed = self._conn.execute(
                "UPDATE login_codes SET attempts = attempts + 1 "
                "WHERE challenge_id = ? AND purpose = ? AND used_at IS NULL AND expires_at > ? AND attempts < ?",
                (challenge_id, purpose, _ts(now), MAX_VERIFY_ATTEMPTS),
            )
            reservation = None
            if claimed.rowcount == 1:
                # Reserve the check as a failure now (removed again if the code is right), so
                # parallel requests cannot get past the per-email / per-IP budgets.
                reservation = self._conn.execute(
                    "INSERT INTO login_failures (email, client_ip, failed_at, trusted) VALUES (?,?,?,?)",
                    (email, ip, _ts(now), 1 if trusted else 0),
                ).lastrowid
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM login_codes WHERE challenge_id = ?", (challenge_id,)).fetchone()
            if claimed.rowcount != 1:
                if row["used_at"]:
                    raise ValueError("code_used")
                if row["expires_at"] <= _ts(now):
                    raise ValueError("code_expired")
                raise ValueError("code_locked")
        ok = len(entered) == CODE_DIGITS and entered.isdigit() and verify_code_hash(entered, row["code_hash"])
        with self._lock:
            if ok:
                self._conn.execute("DELETE FROM login_failures WHERE rowid = ?", (reservation,))
            else:
                self._conn.execute(
                    "UPDATE login_codes SET failures = failures + 1 WHERE challenge_id = ?", (challenge_id,)
                )
            self._conn.commit()
        if not ok:
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
        captcha_ok: bool = False,
    ) -> dict[str, Any]:
        """Check a login code and return the (possibly new) learner.

        Raises ValueError: code_required, code_invalid (unknown challenge or a
        code issued for another purpose), code_slow_down, account_limited, code_used,
        code_expired, code_locked, code_wrong.
        """
        now = now or _now()
        row = self._check_code(
            challenge_id, code, purpose=PURPOSE_LOGIN, client_ip=client_ip, now=now, captcha_ok=captcha_ok
        )
        with self._lock:
            # Single use: only one caller can flip used_at.
            if not self._mark_code_used(row["challenge_id"], now):
                self._conn.commit()
                raise ValueError("code_used")
            self._mark_trusted(row["email"], _ip(client_ip), now)
            self._conn.commit()
            return self.register_or_login(  # type: ignore[attr-defined]
                email=row["email"],
                first_name=row["first_name"] or "",
                last_name=row["last_name"] or "",
                locale=row["locale"] or "he",
            )
