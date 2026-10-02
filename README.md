# MyRoad

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

## Phase-1+ (`packages/core`)

Python + Pydantic + SQLite store, **AgentTools** facade (callable without HTTP), optional FastAPI tool API, and a **thin learner UI** (FastAPI + Jinja).

| Capability | Notes |
|------------|-------|
| `PathStore` | create/save/get/revise/requestPublish/publish + events |
| `AgentTools` | Contract ops: createDraft, getPath/getVersion, addBlock, editBlock, addEdge, reviseDraft, validatePath, recordFeedback, requestPublish, publish |
| `publish` | Human-only; **refuses when `agentId` is set** unless `human_publisher=True` |
| Learner UI | Seeds golden quadratic path; one block at a time; practice/assessment forms; **one-click** feedback→`reviseDraft` + brief version diff; publish button **disabled until human checkbox** |
| Golden loop | `scripts/golden_loop.py` — seed/createDraft → learn → feedback → revise → requestPublish → human publish only |
| Audit | Every tool call emits an event via PathStore |
| FastAPI tools API (optional) | `uvicorn myroad_core.api:app` |

### Run tests

```bash
cd packages/core
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev,api]"
pytest -q
```

With uv:

```bash
cd packages/core
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,api]"
pytest -q
```

### Thin learner UI

```bash
cd packages/core
pip install -e ".[api]"
uvicorn myroad_core.ui.app:app --reload --port 8765
# open http://127.0.0.1:8765/
```

Hebrew UI labels; product id stays **MyRoad**. Flow:

1. Loads golden quadratic path from `freeze/v0` via PathStore seed
2. Shows path name/goal and one block at a time
3. Next/prev; practice/assessment/experience advance on mastery
4. Feedback form calls `AgentTools.record_feedback` (optional `reviseDraft` — new draft only)
5. **Publish** stays disabled until the human confirmation checkbox is checked — never auto-publish

Smoke without a browser:

```bash
cd packages/core
python scripts/smoke_ui.py
```

### Optional HTTP AgentTools API

```bash
cd packages/core
pip install -e ".[api]"
uvicorn myroad_core.api:app --reload
# POST /tools/createDraft, /tools/addBlock, … /tools/publish
```

## Next build steps / שלבי בנייה הבאים

1. ~~**Persistence** — versions, statuses, event log~~
2. ~~**Agent API** — tool contract facade + optional HTTP~~
3. ~~**Thin UI** — learner path + feedback / gated publish~~
4. ~~**Golden loop** — topic → draft → learn → feedback → revise → human publish~~ (demo script + UI one-click revise + version diff)
5. **Author/editor polish** — richer diff UX, source approval flows, multi-path catalog

### Golden loop (end-to-end demo)

```bash
cd packages/core
pip install -e ".[dev,api]"
python scripts/golden_loop.py
# or: python scripts/golden_loop.py --create-draft
# or: python scripts/golden_loop.py --json
```

Flow: seed quadratic path (or `createDraft`) → simulate learn/attempts →
`recordFeedback` → `reviseDraft` → `requestPublish` → **publish only with
`human_publisher=True`** (asserts `agentId` alone is `RBAC_DENY`).

**Never auto-publish.**

Thin UI polish: primary feedback button is one-click feedback→revise; a brief
version-diff banner shows `from → to` after revise.

## CI

On push/PR to `main`:

1. Validate both freeze path JSON files with `python -m json.tool`
2. Install `packages/core` with `[dev,api]` and run `pytest` (persistence + tools + learner UI)

## License / note

Freeze artifacts + persistence + agent-tool facade + thin learner UI + golden loop demo. No auto-publish; golden freeze paths remain `draft` until a human publishes.
