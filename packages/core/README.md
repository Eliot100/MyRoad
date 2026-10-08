# myroad-core (persistence + agent tools + thin UI)

SQLite-backed path/version/status storage, audit event log, a thin
`AgentTools` facade aligned with `freeze/v0/03-agent-tool-contract.md`,
and a minimal learner UI (`myroad_core.ui`).

An agent may publish. A published version stays immutable.

## Setup

```bash
cd packages/core
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
# optional HTTP layer:
# pip install -e ".[api,dev]"
```

## Run tests

```bash
cd packages/core
pip install -e ".[dev]"
pytest -q
```

## AgentTools (no HTTP required)

```python
from myroad_core import PathStore, AgentTools

store = PathStore(":memory:")  # or a file path
tools = AgentTools(store)

resp = tools.create_draft(
    actor_id="user_author",
    agent_id="agent_1",
    correlation_id="corr_1",
    name="My path",
    goal="Learn X",
)
# resp.ok, resp.pathId, resp.versionId, resp.auditEventId
```

Ops: `create_draft`, `get_path`, `get_version`, `add_block`, `edit_block`,
`add_edge`, `revise_draft`, `validate_path`, `record_feedback`,
`request_publish`, `publish`.

## Optional FastAPI wrapper

```bash
pip install -e ".[api]"
uvicorn myroad_core.api:app --reload
```

POST endpoints under `/tools/<op>` (e.g. `/tools/createDraft`) accept the
shared request envelope (`correlationId`, `pathId?`, `versionId?`, …).

**Auth (required on every `/tools/*` route).** A call without one of these
gets `401`:

- **Logged-in user:** the `myroad_session` cookie from the UI login. The
  session id is random; SQLite keeps only its SHA-256 digest. To accept UI
  sessions, run both apps on the same SQLite file (`MYROAD_DB=...`) or pass the
  same `PathStore` to `create_app`.
- **Agent:** `Authorization: Bearer <credential>`, compared in constant time
  with the server env var `MYROAD_AGENT_TOKEN` (min 16 chars). Unset or empty =
  agent access disabled. The agent acts as `MYROAD_AGENT_ID` (default
  `agent_service`). Set these in the server environment only, never in git.

The actor comes from the session or the credential. `actorId`, `agentId` and
`publisherId` in the body are not trusted: if sent and they differ from the
authenticated principal the call gets `403 ACTOR_MISMATCH`.

- **CSRF:** cookie (session) calls must send the header `X-MyRoad-Request: 1`,
  otherwise `403 CSRF_HEADER_REQUIRED`. Bearer (agent) calls do not need it.
- **Ownership:** every op except `createDraft` needs a `pathId` the caller may
  act on, otherwise `404` (same as a missing path). A user may act only on
  paths they authored (`paths.author_id`, fixed at creation). The agent may act
  only on paths it authored (`MYROAD_AGENT_ID`) or on path ids listed in
  `MYROAD_AGENT_ALLOWED_PATHS` (comma-separated, server env).
- **Session cookie:** `myroad_session` is `HttpOnly; SameSite=Lax; Secure`.
  Browsers accept Secure cookies on `http://localhost`; for other plain-http
  dev hosts set `MYROAD_DEV_INSECURE_COOKIES=1` (never in production).
  `POST /logout` revokes the session.
- **Email change:** only through the verified flow (see "Email change" below);
  editing the email in the profile form is refused (`email_change_disabled`).
- **Browser forms (UI app):** every POST/PUT/PATCH/DELETE needs an `Origin`
  (or, failing that, `Referer`) from this site, on top of `SameSite=Lax`.
  Cross-site, `Origin: null` or header-less requests get `403`. "This site" is
  `<scheme>://<Host>` as the app sees it; add the public origin to
  `MYROAD_ALLOWED_ORIGINS` (comma-separated, e.g. `https://myroad.example`)
  when a proxy changes the scheme or host.

In-process callers (`AgentTools`, the path builder, the golden loop) do not go
over HTTP and are unchanged.

## Email sign-in (one-time code)

`/login` asks for an email (plus first and last name for a new account) and
emails a 6-digit code. The user enters it at `/login/verify`. The session
(`myroad_session` cookie) starts only after the code checks out, and a new
account is created only then.

- A code expires after 15 minutes and works once. Up to 3 codes per email stay
  active, so a stranger asking for codes cannot cancel the one you are typing
  (a 4th retires the oldest).
- Guessing: each code allows 5 tries. The try is claimed with one conditional
  `UPDATE` (tries < 5, unused, unexpired) before the code is hashed, and store
  access is serialized by a lock, so parallel guesses cannot pass the limit.
- Wrong codes are counted per email + client IP (24 hours), never as one
  global lock per email, so a stranger cannot lock the real user out. After 5
  failures that IP waits before each further check (2 s, doubling, max
  15 min; `code_slow_down`, no attempt used). After 3 failures from that IP,
  or 15 for the email from all IPs, a CAPTCHA is required if one is
  configured.
- CAPTCHA hook (off by default, so dev and tests need nothing):
  `MYROAD_CAPTCHA_PROVIDER=turnstile` with `MYROAD_CAPTCHA_SITE_KEY` and
  `MYROAD_CAPTCHA_SECRET` (server env only) enables Cloudflare Turnstile.
  Any other check can be plugged in as `app.state.captcha_verifier =
  callable(token, client_ip) -> bool`. Without a CAPTCHA only the backoff
  applies, so a public server should enable one.
- Timing: every request path (known, unknown, rate-limited) runs one PBKDF2
  hash, so known and unknown emails take the same time. Mail is still sent
  inline so a mail failure can be reported (`mail_failed`).
- Sending: at most 5 codes per email+IP, 10 per email and 30 per IP every
  15 minutes. Over the limit, no mail is sent but the answer looks the same.
- Same answer for every email: known, unknown and rate-limited requests all go
  to the code page with the same cookie. A known email gets a code; an unknown
  email gets a short "no account, register here" note. Register mode (with
  names) creates the account after the code checks out.
- SQLite (`login_codes`, `login_send_log`) keeps only a salted PBKDF2-SHA256
  hash of the code. There are no passwords.
- Mail settings (server env only, never in git): `MYROAD_SMTP_HOST` (enables
  mail), `MYROAD_SMTP_PORT` (587), `MYROAD_SMTP_USER`, `MYROAD_SMTP_PASSWORD`,
  `MYROAD_SMTP_STARTTLS` (`1`, uses a verified TLS context), `MYROAD_MAIL_FROM`.
- Without `MYROAD_SMTP_HOST` sign-in **fails closed** (`mail_failed`), unless
  `MYROAD_DEV_MAIL_CONSOLE=1` is set for local dev. Then the code is printed to
  stderr: `[MyRoad login] dev mail console ... Code for you@example.com: 123456`.
  Never set it on a shared or public server.
- Client IP is the direct peer address. Behind a proxy, run uvicorn with
  `--proxy-headers --forwarded-allow-ips=<proxy address>`. That value must be
  the proxy's own address, **never `*`**: with `*` any client can send
  `X-Forwarded-For` and pick its own IP, which defeats the per-IP limits.

## Email change (verified)

Settings → "Change email" sends a code to the **current** address and a code
to the **new** address (`POST /settings/email`). Both must be entered
(`POST /settings/email/verify`) before anything changes. Then the email
switches, every session of the user is revoked (this browser gets a fresh
one), pending login codes for both addresses are retired, and the old address
gets a "your email was changed" notice.

- A stolen session alone cannot move the account: the current-address code
  goes to the real owner.
- Nobody can point an account at an address they do not control. The new
  address is not reserved or claimed while the change is pending; if someone
  registers it first, the change fails with `email_taken`.
- If the new address already has an account, it gets a notice instead of a
  code, and the response looks the same.
- The codes use the login-code rules (hash, 15 minutes, single use, 5 tries,
  per email+IP backoff, CAPTCHA hook) but are bound to their purpose: a login
  code is never accepted for an email change, and these codes never sign in.
- Send limits are shared with sign-in. A new change request cancels the
  previous pending one.

## What this package does

- Pydantic types for PathVersion, Block, Edge, Source, Attempt, Feedback, Event
- SQLite store: create draft, save version, get path/version, list versions
- Event append + query by `pathId` or `correlationId`
- Status transitions: `draft` → `in_review` → `published`
- Published versions immutable; revise always creates a new `versionId`
- Seed loader for golden quadratic path JSON under `freeze/v0/`


## Thin learner UI

```bash
pip install -e ".[api]"
uvicorn myroad_core.ui.app:app --reload --port 8765
```

- Seeds the golden quadratic path from `freeze/v0`
- Hebrew labels; product id **MyRoad**
- One block at a time; mastery gate for practice/assessment/experience
- Feedback → `record_feedback` (+ optional `reviseDraft`)
- Publish is available to the signed-in user (no human-only checkbox)

```bash
python scripts/smoke_ui.py
```

## Golden loop (E2E demo)

```bash
pip install -e ".[dev,api]"
python scripts/golden_loop.py
python scripts/golden_loop.py --create-draft
python scripts/golden_loop.py --json
```

End-to-end: topic → draft/seed → simulate learn → `record_feedback` →
`revise_draft` → `request_publish` → agent `publish` succeeds.

Thin UI: primary button "שמור משוב ועדכן טיוטה" is one-click feedback→revise;
version diff banner appears briefly after revise.



## Content samples

See `content/grade3/` and `docs/kids-platform.md`.

**v0.7:** learner identity POC, per-user progress/attempts, he/en/ar shell i18n,
topic map before play, completion stats, expanded English demo paths.

**Internationalization (i18n) is part of the platform implementation:** shell strings
and path titles/blurbs are data-driven locale content (`he`, `en`, and `ar` today),
with RTL for Hebrew and Arabic, fallback locales for missing translations, and a
split between the language used to explain a path and the language of its learning
content (`explain_locale` vs `content_locale`). See
[`docs/how-to-add-locale.md`](docs/how-to-add-locale.md) for how to add another
locale.

## Locale split (v0.7)

English Grade-3 paths use `explain_locale=he` + `content_locale=en` with `body_content`
for target words. See `docs/kids-platform.md` and `myroad_core.content.locale_rules`.
