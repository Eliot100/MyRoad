# Library login/auth review gap (2026-11-05)

Source: `library-files/48-grok-build-fix-login.md`, evidence screenshot `58-image.png`
(terminal: unknown email still lands on `/login/verify` after
`[MyRoad login] … No account … sent a register notice (no code).`).

**Pass 3 rule: no auth code changes on this branch.** Planning only.

## What the brief asks

1. Unknown email on Sign in must not open the code page; return to register mode with a clear message.
2. Local review: `MYROAD_DEV_MAIL_CONSOLE=1` prints the code to stderr; verify page says to look at the console (not embed the code).
3. Non-localhost http: warn that Secure cookies will not stick; name `MYROAD_DEV_INSECURE_COOKIES=1` or `127.0.0.1`.
4. Keep production fail-closed; no codes in HTML/logs without the dev flag; session stays server-side cookie.
5. Tests for the above behaviours.

## What the branch already has (do not regress)

- `packages/core/tests/test_email_login_code.py` covers mail_failed without SMTP/dev flag, DEV_MAIL_CONSOLE path, cookie secure defaults, and intentional **same response shape** for known vs unknown email (privacy / enumeration).
- Issue #59 code field behaviour is covered in `test_login_code_input.py`.

## Gap / conflict

Brief 48 wants Sign-in of an unknown email to **not** open `/login/verify`. Current product tests assert known and unknown emails get the **same** redirect/body so an attacker cannot tell accounts apart. Changing that is a product + security decision for Eliot/Cyber — not a silent fix on this picks branch.

Also still useful as review UX (without changing auth here): clearer `mail_failed` / host messaging copy when reviewing on a LAN IP (screenshot 58 / 60 context).

## Action taken

This note only. No edits under login routes, cookies, or auth tests.
