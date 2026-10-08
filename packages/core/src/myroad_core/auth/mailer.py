"""Send the one-time login code.

With SMTP configured (server env only, never in git):
  MYROAD_SMTP_HOST      required to enable mail
  MYROAD_SMTP_PORT      default 587
  MYROAD_SMTP_USER      optional (login)
  MYROAD_SMTP_PASSWORD  optional (login)
  MYROAD_SMTP_STARTTLS  default "1" (set "0" to disable, e.g. a local relay)
  MYROAD_MAIL_FROM      sender address (default: MYROAD_SMTP_USER)

Without MYROAD_SMTP_HOST (local / demo) the code is printed to the server
console (stderr) so sign-in can still be tested. The code is never written to
the database, a cookie, or a page.
"""
from __future__ import annotations

import os
import smtplib
import sys
from email.message import EmailMessage

from myroad_core.auth.login_codes import CODE_TTL_SECONDS

__all__ = ["mail_configured", "send_login_code"]


def mail_configured() -> bool:
    return bool((os.environ.get("MYROAD_SMTP_HOST") or "").strip())


def _console(email: str, code: str) -> None:
    minutes = CODE_TTL_SECONDS // 60
    print(
        f"[MyRoad login] mail not configured (MYROAD_SMTP_HOST unset). "
        f"Code for {email}: {code} (valid {minutes} min, single use)",
        file=sys.stderr,
        flush=True,
    )


def send_login_code(email: str, code: str) -> None:
    if not mail_configured():
        _console(email, code)
        return
    host = os.environ["MYROAD_SMTP_HOST"].strip()
    port = int((os.environ.get("MYROAD_SMTP_PORT") or "587").strip())
    user = (os.environ.get("MYROAD_SMTP_USER") or "").strip()
    secret = os.environ.get("MYROAD_SMTP_PASSWORD") or ""
    starttls = (os.environ.get("MYROAD_SMTP_STARTTLS") or "1").strip() not in ("0", "false", "no")
    sender = (os.environ.get("MYROAD_MAIL_FROM") or user or "no-reply@localhost").strip()

    msg = EmailMessage()
    msg["Subject"] = f"MyRoad sign-in code: {code}"
    msg["From"] = sender
    msg["To"] = email
    minutes = CODE_TTL_SECONDS // 60
    msg.set_content(
        f"Your MyRoad sign-in code is {code}.\n\n"
        f"It works once and expires in {minutes} minutes.\n"
        "If you did not try to sign in, ignore this email.\n"
    )
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if starttls:
            smtp.starttls()
        if user:
            smtp.login(user, secret)
        smtp.send_message(msg)
