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

### Platform catalog + path player (v0.8)

Age-agnostic home (groups + subject chips + path cards), **email registration**
(first/last name + unique email, no passwords), he/en/ar UI locale (RTL for he/ar),
topic map before play, completion stats, and per-user progress in **file SQLite**
(`packages/core/data/myroad_ui.db` by default; override with `MYROAD_DB`).

**Path content** lives in the separate public repo
[`Eliot100/MyRoad-content`](https://github.com/Eliot100/MyRoad-content).
The platform loads it via `CONTENT_DIR`, a checkout/submodule at
`packages/core/content`, or a sibling `../MyRoad-content` clone.

**Add a path** (`/add-path`) calls Grok through Cloudflare AI Gateway BYOK.
The xAI key stays in Cloudflare Secrets Store. MyRoad does not accept or send a
provider API key. Server environment names: `CLOUDFLARE_ACCOUNT_ID`,
`CLOUDFLARE_GATEWAY_ID`, and optionally `CLOUDFLARE_AI_GATEWAY_TOKEN` when the
gateway has authenticated gateway enabled. If the account id or gateway id is
missing, the page says the Cloudflare gateway is not configured. See
`packages/core/docs/cloudflare-ai-gateway.md`. The old `/author` golden-loop POC
remains unlinked from the main nav.

```bash
# clone platform + content (sibling layout)
git clone https://github.com/Eliot100/MyRoad.git
git clone https://github.com/Eliot100/MyRoad-content.git
cd MyRoad/packages/core
export CONTENT_DIR="$(cd ../../MyRoad-content && pwd)"   # or copy grade3 into content/
pip install -e ".[api]"
uvicorn myroad_core.ui.app:app --reload --port 8765
# http://127.0.0.1:8765/          catalog
# http://127.0.0.1:8765/login     register / sign in (email)
# http://127.0.0.1:8765/add-path  gated add-a-path flow
```

Windows PowerShell:

```powershell
cd path\to\projects
git clone https://github.com/Eliot100/MyRoad.git
git clone https://github.com/Eliot100/MyRoad-content.git
cd MyRoad\packages\core
$env:CONTENT_DIR = (Resolve-Path ..\..\MyRoad-content).Path
# If Resolve-Path fails, use the full path to the MyRoad-content folder.
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[api,dev]"
$env:CLOUDFLARE_ACCOUNT_ID = ""
$env:CLOUDFLARE_GATEWAY_ID = ""
# Optional, only if the gateway has authenticated gateway enabled:
$env:CLOUDFLARE_AI_GATEWAY_TOKEN = ""
uvicorn myroad_core.ui.app:app --reload --port 8765
```

SQLite UI DB (survives restart): `packages/core/data/myroad_ui.db` (gitignored `*.db`).
Override: `$env:MYROAD_DB = "C:\path\to\myroad.db"`.

Home tabs (in progress / completed / needs practice) + time view by subject;
locale split (`explain_locale` vs `content_locale`) for English paths.

**Internationalization (i18n) is part of the platform implementation:** shell strings
and path titles/blurbs are data-driven locale content (`he`, `en`, and `ar` today),
with RTL for Hebrew and Arabic, fallback locales for missing translations, and a
split between the language used to explain a path and the language of its learning
content (`explain_locale` vs `content_locale`). See
`packages/core/docs/how-to-add-locale.md` for how to add another locale.

See `packages/core/docs/kids-platform.md` and `packages/core/content/README.md`.

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
2. ~~**Agent API** — tool contract facade~~
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
