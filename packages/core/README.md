# myroad-core (phase-1 persistence)

SQLite-backed path/version/status storage and audit event log for the MyRoad POC.

Aligned with `freeze/v0/03-agent-tool-contract.md`.

## Setup

```bash
cd packages/core
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Run tests

From repo root:

```bash
cd packages/core
pip install -e ".[dev]"
pytest -q
```

Or with uv:

```bash
cd packages/core
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q
```

## What this package does

- Pydantic types for PathVersion, Block, Edge, Source, Attempt, Feedback, Event
- SQLite store: create draft, save version, get path/version, list versions
- Event append + query by `pathId` or `correlationId`
- Status transitions: `draft` → `in_review` (`request_publish`) → `published` (`publish`)
- **Never auto-publish**: `publish` refuses when `agentId` is set
- Published versions are immutable; revise always creates a new `versionId`
- Seed loader for golden quadratic path JSON under `freeze/v0/`
