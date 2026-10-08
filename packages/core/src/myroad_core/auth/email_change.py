"""Verified email change (Cyber security review of #46/#47).

Changing the sign-in email needs proof of BOTH addresses:
- a fresh code sent to the CURRENT address (so a stolen session alone cannot
  move the account), and
- a code sent to the NEW address (so nobody can point an account at an
  address they do not control).
The old address is told when the change completes. Until both codes check out
the account keeps its email and the new address stays free: it is not
reserved, and anyone may still register it normally. If it gets registered
first, the change fails with ``email_taken``.

The codes use the login-code machinery (same hashing, same atomic per-code
attempt limit, same per email+IP failure backoff) with their own purposes, so
a login code is never accepted here and these codes never sign anyone in.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from myroad_core.auth.login_codes import (
    CODE_TTL_SECONDS,
    PURPOSE_EMAIL_CHANGE_CURRENT,
    PURPOSE_EMAIL_CHANGE_NEW,
    PURPOSE_LOGIN,
    _ip,
    _new_code,
    _now,
    _ts,
    hash_code,
)

__all__ = ["EMAIL_CHANGE_COOKIE", "EmailChangeMixin", "EmailChangeRequest"]

EMAIL_CHANGE_COOKIE = "myroad_email_change"

_EMAIL_CHANGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS email_changes (
  change_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  old_email TEXT NOT NULL,
  new_email TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  completed_at TEXT,
  cancelled_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_email_changes_user ON email_changes(user_id);
"""


@dataclass(frozen=True)
class EmailChangeRequest:
    """Outcome of starting an email change. The HTTP response is the same for every kind.

    kind "codes": send ``current_code`` to ``old_email``; send ``new_code`` to
    ``new_email``, or, when ``new_code`` is None (the new address already has
    an account), a short notice instead. kind "rate_limited": this IP's own send
    bucket is full, send nothing. kind "email_limited": the per-email cap for
    untrusted IPs is full for one of the addresses; the caller asks for a
    CAPTCHA (when configured) or tells the user to wait. Never a silent drop.
    """

    kind: Literal["codes", "rate_limited", "email_limited"]
    change_id: str
    old_email: str
    new_email: str
    current_code: str | None = None
    new_code: str | None = None


class EmailChangeMixin:
    """Mixin expecting LoginCodeMixin, LearnerProgressMixin and SessionMixin."""

    def ensure_email_change_schema(self) -> None:
        self._conn.executescript(_EMAIL_CHANGE_SCHEMA)
        self._conn.commit()

    def start_email_change(
        self,
        user_id: str,
        new_email: str,
        *,
        client_ip: str = "unknown",
        now: datetime | None = None,
        captcha_ok: bool = False,
    ) -> EmailChangeRequest:
        """Issue the two codes. Raises ValueError: email_required, email_invalid, email_same."""
        learner = self.get_learner(user_id)  # type: ignore[attr-defined]
        if not learner or not learner.get("email"):
            raise ValueError("email_required")
        old = self._normalize_email(learner["email"])  # type: ignore[attr-defined]
        new = self._validate_email(new_email)  # type: ignore[attr-defined]
        if new == old:
            raise ValueError("email_same")
        now = now or _now()
        ip = _ip(client_ip)
        # Always two PBKDF2 hashes, whatever happens below (uniform timing).
        current_code, new_code = _new_code(), _new_code()
        current_hash, new_hash = hash_code(current_code), hash_code(new_code)
        with self._lock:
            # Same send limits as sign-in, for both addresses (trusted pairs skip the per-email cap).
            trust = {e: self._is_trusted(e, ip, now) for e in (old, new)}  # type: ignore[attr-defined]
            statuses = {self._send_status(e, ip, now, trusted=trust[e]) for e in (old, new)}  # type: ignore[attr-defined]
            if "rate_limited" in statuses:
                refused: str | None = "rate_limited"
            elif "email_limited" in statuses and not captcha_ok:
                refused = "email_limited"
            else:
                refused = None
            if refused:
                return EmailChangeRequest(
                    kind=refused, change_id=secrets.token_urlsafe(24), old_email=old, new_email=new  # type: ignore[arg-type]
                )
            self._log_send(old, ip, now, trusted=trust[old])  # type: ignore[attr-defined]
            self._log_send(new, ip, now, trusted=trust[new])  # type: ignore[attr-defined]
            taken = self.get_learner_by_email(new) is not None  # type: ignore[attr-defined]
            # One pending change per user: cancel older ones and retire their codes.
            self._conn.execute(
                "UPDATE login_codes SET used_at = ? WHERE used_at IS NULL AND change_id IN "
                "(SELECT change_id FROM email_changes WHERE user_id = ? AND completed_at IS NULL "
                "AND cancelled_at IS NULL)",
                (_ts(now), user_id),
            )
            self._conn.execute(
                "UPDATE email_changes SET cancelled_at = ? WHERE user_id = ? AND completed_at IS NULL "
                "AND cancelled_at IS NULL",
                (_ts(now), user_id),
            )
            change_id = secrets.token_urlsafe(24)
            self._conn.execute(
                "INSERT INTO email_changes (change_id, user_id, old_email, new_email, created_at, expires_at) "
                "VALUES (?,?,?,?,?,?)",
                (change_id, user_id, old, new, _ts(now), _ts(now + timedelta(seconds=CODE_TTL_SECONDS))),
            )
            for email, code_hash, purpose in (
                (old, current_hash, PURPOSE_EMAIL_CHANGE_CURRENT),
                (new, new_hash, PURPOSE_EMAIL_CHANGE_NEW),
            ):
                self._insert_code(  # type: ignore[attr-defined]
                    email=email, code_hash=code_hash, now=now, purpose=purpose, client_ip=ip, change_id=change_id
                )
            self._conn.commit()
        return EmailChangeRequest(
            kind="codes", change_id=change_id, old_email=old, new_email=new,
            current_code=current_code, new_code=None if taken else new_code,
        )

    def pending_email_change(self, user_id: str, change_id: str | None) -> dict[str, Any] | None:
        if not change_id:
            return None
        row = self._conn.execute(
            "SELECT * FROM email_changes WHERE change_id = ? AND user_id = ? AND completed_at IS NULL "
            "AND cancelled_at IS NULL AND expires_at > ?",
            (change_id, user_id, _ts(_now())),
        ).fetchone()
        return dict(row) if row else None

    def email_change_challenges(self, change_id: str | None) -> list[str]:
        if not change_id:
            return []
        rows = self._conn.execute(
            "SELECT challenge_id FROM login_codes WHERE change_id = ? ORDER BY purpose", (change_id,)
        ).fetchall()
        return [r["challenge_id"] for r in rows]

    def confirm_email_change(
        self,
        user_id: str,
        change_id: str | None,
        *,
        current_code: str | None,
        new_code: str | None,
        client_ip: str = "unknown",
        now: datetime | None = None,
        captcha_ok: bool = False,
    ) -> dict[str, Any]:
        """Check both codes and switch the email. Returns {learner, old_email, new_email}.

        All of the user's sessions are revoked (the caller starts a new one).
        Raises ValueError: code_required, code_invalid, code_slow_down,
        account_limited, code_used, code_expired, code_locked, code_wrong,
        email_taken. ``captcha_ok``: the caller verified a CAPTCHA (lifts
        account_limited for untrusted IPs).
        """
        now = now or _now()
        if not change_id:
            raise ValueError("code_invalid")
        if not (current_code or "").strip() or not (new_code or "").strip():
            raise ValueError("code_required")
        with self._lock:
            change = self._conn.execute(
                "SELECT * FROM email_changes WHERE change_id = ? AND user_id = ?", (change_id, user_id)
            ).fetchone()
            if not change:
                raise ValueError("code_invalid")  # unknown, or another user's change
            if change["completed_at"] or change["cancelled_at"]:
                raise ValueError("code_used")
            ids = {
                r["purpose"]: r["challenge_id"]
                for r in self._conn.execute(
                    "SELECT purpose, challenge_id FROM login_codes WHERE change_id = ?", (change_id,)
                ).fetchall()
            }
        cur = self._check_code(  # type: ignore[attr-defined]
            ids.get(PURPOSE_EMAIL_CHANGE_CURRENT), current_code,
            purpose=PURPOSE_EMAIL_CHANGE_CURRENT, client_ip=client_ip, now=now, captcha_ok=captcha_ok,
        )
        new = self._check_code(  # type: ignore[attr-defined]
            ids.get(PURPOSE_EMAIL_CHANGE_NEW), new_code,
            purpose=PURPOSE_EMAIL_CHANGE_NEW, client_ip=client_ip, now=now, captcha_ok=captcha_ok,
        )
        with self._lock:
            learner = self.get_learner(user_id)  # type: ignore[attr-defined]
            if not learner or self._normalize_email(learner.get("email")) != change["old_email"]:  # type: ignore[attr-defined]
                raise ValueError("code_invalid")
            if not (self._mark_code_used(cur["challenge_id"], now) and self._mark_code_used(new["challenge_id"], now)):  # type: ignore[attr-defined]
                self._conn.commit()
                raise ValueError("code_used")
            if self.get_learner_by_email(change["new_email"]) is not None:  # type: ignore[attr-defined]
                # Registered by someone else while the change was pending: they keep it.
                self._conn.execute(
                    "UPDATE email_changes SET cancelled_at = ? WHERE change_id = ?", (_ts(now), change_id)
                )
                self._conn.commit()
                raise ValueError("email_taken")
            self._conn.execute(
                "UPDATE email_changes SET completed_at = ? WHERE change_id = ?", (_ts(now), change_id)
            )
            # Outstanding login codes for either address must not sign anyone in afterwards.
            self._conn.execute(
                "UPDATE login_codes SET used_at = ? WHERE used_at IS NULL AND purpose = ? AND email IN (?, ?)",
                (_ts(now), PURPOSE_LOGIN, change["old_email"], change["new_email"]),
            )
            self._conn.execute(
                "UPDATE learners SET email = ?, updated_at = ? WHERE user_id = ?",
                (change["new_email"], _ts(now), user_id),
            )
            # Proven control of the new address from this IP: trust the pair like a sign-in.
            self._mark_trusted(change["new_email"], _ip(client_ip), now)  # type: ignore[attr-defined]
            self._conn.commit()
            self.revoke_user_sessions(user_id)  # type: ignore[attr-defined]
            updated = self.get_learner(user_id)  # type: ignore[attr-defined]
        return {"learner": updated, "old_email": change["old_email"], "new_email": change["new_email"]}
