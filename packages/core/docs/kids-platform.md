# MyRoad platform catalog + Grade-3 sample paths (v0.6)

The **platform shell** is age-agnostic: groups, subject categories, content-as-data,
identity POC, locales, topic maps, and a path player with optional speech / piano / rhythm.

The **ten Grade-3 sample paths** (group `דרכים לתלמידי כיתה ג'`) are kid-oriented
in content and tone. Soft styling applies only to that demo group / those players
(`.tone-demo`), not to the whole site.

## Content-as-data

Sample paths live under:

```
packages/core/content/grade3/*.json
```

Schema: `myroad_core.content.schema.ContentPath`  
Optional `topics[]` (`id`, `title_he`/`title_en`/`title_ar`, `node_ids[]`) group
steps into map stations. If omitted, topics are inferred.
Loader: `seed_content_paths()` → PathStore (human publish gate for these demos only).

Future paths use the same JSON format. Do **not** auto-publish arbitrary drafts;
only these demo seeds are pre-published by design.

## v0.6 platform polish

- **Identity (POC):** display name + stable `myroad_uid` cookie (`/login`). No OAuth.
- **Per-user data:** progress, completed paths, and attempt metrics in SQLite
  (`learners`, `learner_progress`, `learner_attempts`), keyed by user id.
- **Locales:** `he` / `en` / `ar` shell chrome (RTL for he/ar). Header language switcher.
- **Topic map first:** `/play/{path}` opens a visual topic diagram; then Start / Enter topic.
- **Completion stats:** time (approx), nodes completed, correct/incorrect taps, mastery %, message; attempt stored.
- **English paths:** colors / animals / hello expanded (~10 steps) with richer EN+HE and speak_text.

## Run (Windows PowerShell)

```powershell
cd path\to\MyRoad\packages\core
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[api,dev]"
uvicorn myroad_core.ui.app:app --reload --port 8765
```

Open http://127.0.0.1:8765/ for the catalog.  
Author / golden-loop POC: http://127.0.0.1:8765/author  
Identity: http://127.0.0.1:8765/login

## Player notes

- Mouse-first: big choice tiles, next/back, piano keys, rhythm beats.
- 🔊 Web Speech API TTS (הקראה) when supported.
- 🎤 Optional MediaRecorder (הקלטה) on speak nodes — graceful fallback.
- Resume: same user cookie restores path progress; catalog shows in-progress / completed.
