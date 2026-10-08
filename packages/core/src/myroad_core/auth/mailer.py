"""Send login mail: the one-time code, or a "no account" notice.

With SMTP configured (server env only, never in git):
  MYROAD_SMTP_HOST      required to enable mail
  MYROAD_SMTP_PORT      default 587
  MYROAD_SMTP_USER      optional (login)
  MYROAD_SMTP_PASSWORD  optional (login)
  MYROAD_SMTP_STARTTLS  default "1" (STARTTLS with certificate verification;
                        "0" only for a trusted local relay)
  MYROAD_MAIL_FROM      sender address (default: MYROAD_SMTP_USER)

Local / demo only: with MYROAD_DEV_MAIL_CONSOLE=1 and no MYROAD_SMTP_HOST the
message is printed to the server console (stderr). Without SMTP and without
that flag, sending fails closed (MailNotConfigured), so production never leaks
codes into logs. Codes are never written to the database, a cookie, or a page.
"""
from __future__ import annotations

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

from myroad_core.auth.login_codes import CODE_TTL_SECONDS

__all__ = [
    "DEV_MAIL_CONSOLE_ENV",
    "MailNotConfigured",
    "dev_console_enabled",
    "mail_configured",
    "send_login_code",
    "send_no_account_notice",
]

DEV_MAIL_CONSOLE_ENV = "MYROAD_DEV_MAIL_CONSOLE"


class MailNotConfigured(RuntimeError):
    """No SMTP and no explicit dev console flag: refuse to 'send'."""


def mail_configured() -> bool:
    return bool((os.environ.get("MYROAD_SMTP_HOST") or "").strip())


def dev_console_enabled() -> bool:
    return (os.environ.get(DEV_MAIL_CONSOLE_ENV) or "").strip() == "1"


def _deliver(to: str, subject: str, body: str, console_line: str) -> None:
    if not mail_configured():
        if not dev_console_enabled():
            raise MailNotConfigured(
                f"set MYROAD_SMTP_HOST (or {DEV_MAIL_CONSOLE_ENV}=1 for local/demo only)"
            )
        print(f"[MyRoad login] dev mail console ({DEV_MAIL_CONSOLE_ENV}=1). {console_line}",
              file=sys.stderr, flush=True)
        return
    host = os.environ["MYROAD_SMTP_HOST"].strip()
    port = int((os.environ.get("MYROAD_SMTP_PORT") or "587").strip())
    user = (os.environ.get("MYROAD_SMTP_USER") or "").strip()
    secret = os.environ.get("MYROAD_SMTP_PASSWORD") or ""
    starttls = (os.environ.get("MYROAD_SMTP_STARTTLS") or "1").strip() not in ("0", "false", "no")
    sender = (os.environ.get("MYROAD_MAIL_FROM") or user or "no-reply@localhost").strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if starttls:
            smtp.starttls(context=ssl.create_default_context())
        if user:
            smtp.login(user, secret)
        smtp.send_message(msg)


def send_login_code(email: str, code: str) -> None:
    minutes = CODE_TTL_SECONDS // 60
    _deliver(
        email,
        f"MyRoad sign-in code: {code}",
        f"Your MyRoad sign-in code is {code}.\n\n"
        f"It works once and expires in {minutes} minutes.\n"
        "If you did not try to sign in, ignore this email.\n",
        f"Code for {email}: {code} (valid {minutes} min, single use)",
    )


def send_no_account_notice(email: str) -> None:
    _deliver(
        email,
        "MyRoad sign-in",
        "Someone tried to sign in to MyRoad with this email, but there is no account for it.\n"
        "To create one, open the sign-in page and choose \"Register\".\n"
        "If this was not you, ignore this email.\n",
        f"No account for {email}; sent a register notice (no code).",
    )
