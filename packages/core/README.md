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

In-process callers (`AgentTools`, the path builder, the golden loop) do not go
over HTTP and are unchanged.

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
