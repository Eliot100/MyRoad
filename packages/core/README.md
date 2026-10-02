# myroad-core (persistence + agent tools + thin UI)

SQLite-backed path/version/status storage, audit event log, a thin
`AgentTools` facade aligned with `freeze/v0/03-agent-tool-contract.md`,
and a minimal learner UI (`myroad_core.ui`).

**Never auto-publish** — `publish` refuses when `agentId` is set unless
`human_publisher=True`.

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
shared request envelope (`actorId`, `agentId?`, `correlationId`, …).

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
- Publish button disabled until human confirmation — **never auto-publish**

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
`revise_draft` → `request_publish` → `publish(human_publisher=True)`.

Asserts agent-only publish is denied (`RBAC_DENY`). **Never auto-publish.**

Thin UI: primary button "שמור משוב ועדכן טיוטה" is one-click feedback→revise;
version diff banner appears briefly after revise.



## Content samples

See `content/grade3/` and `docs/kids-platform.md`.

**v0.6:** learner identity POC, per-user progress/attempts, he/en/ar shell i18n,
topic map before play, completion stats, expanded English demo paths.
