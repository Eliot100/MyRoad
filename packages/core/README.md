# myroad-core (persistence + agent tools)

SQLite-backed path/version/status storage, audit event log, and a thin
`AgentTools` facade aligned with `freeze/v0/03-agent-tool-contract.md`.

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
