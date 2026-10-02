# MyRoad / מיי-רואד

**MyRoad** is an adaptive learning platform POC: turn a learner goal into a measurable path (blocks, edges, mastery)—not another unstructured tutoring chat.

**MyRoad** היא POC לפלטפורמת למידה אדפטיבית: המרת מטרת לומד למסלול מדיד (בלוקים, קשתות, שליטה) — לא עוד צ'אט חופשי.

**Product ID:** `MyRoad` · **Never auto-publish** — human approval is required to publish any learning path.

## v0 freeze contents / תוכן הקפאת v0

| Path | Description |
|------|-------------|
| `freeze/v0/01-path-before-feedback.json` | Golden scenario draft (quadratic equations / משוואות ריבועיות) before feedback |
| `freeze/v0/02-path-after-feedback.json` | Same path after feedback + remediation + `_diff` |
| `freeze/v0/03-agent-tool-contract.md` | Agent/tool ops, RBAC, audit — agent may draft/revise; **never auto-publish** |
| `freeze/v0/04-comparison.md` | Comparison vs first generic scaffold / השוואה לפיגום הגנרי |
| `docs/design-extraction.md` | Requirements extraction from design docs |

## Phase-1 persistence (`packages/core`)

Python + Pydantic + SQLite store for path/version/status + audit event log.

| Capability | Notes |
|------------|-------|
| `create_draft` / `save_version` | Draft path documents |
| `get_version` / `list_versions` | Read path versions |
| `revise_draft` | Always creates a **new** `versionId` |
| `request_publish` | `draft` → `in_review` (does not publish) |
| `publish` | Human-only; **refuses when `agentId` is set** |
| `append_event` / `query_events` | Audit by `pathId` or `correlationId` |
| `seed_golden_quadratic` | Loads freeze/v0 JSON as draft versions |

### Run persistence tests

```bash
cd packages/core
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
```

With uv:

```bash
cd packages/core
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q
```

## Next build steps / שלבי בנייה הבאים

1. ~~**Persistence** — versions, statuses, event log~~ (this package)
2. **Agent API** — tool contract + RBAC + audit (HTTP/tool surface)
3. **Thin UI** — learner path + minimal author/editor
4. **Golden loop** — topic → draft → learn → feedback → revise → human publish

## CI

On push/PR to `main`:

1. Validate both freeze path JSON files with `python -m json.tool`
2. Install `packages/core` and run `pytest`

## License / note

Freeze artifacts + phase-1 persistence library. No HTTP API or UI yet. No published learning paths in the golden freeze (both are `draft`).
