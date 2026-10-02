# MyRoad platform catalog + Grade-3 sample paths

The **platform shell** is age-agnostic: groups, subject categories, content-as-data,
and a path player with optional speech / piano / rhythm controls.

The **ten Grade-3 sample paths** (group `דרכים לתלמידי כיתה ג׳`) are kid-oriented
in content and tone. Soft styling applies only to that demo group / those players
(`.tone-demo`), not to the whole site.

## Content-as-data

Sample paths live under:

```
packages/core/content/grade3/*.json
```

Schema: `myroad_core.content.schema.ContentPath`  
Loader: `seed_content_paths()` → PathStore (human publish gate for these demos only).

Future paths use the same JSON format. Do **not** auto-publish arbitrary drafts;
only these demo seeds are pre-published by design.

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

## Player notes

- Mouse-first: big choice tiles, next/back, piano keys, rhythm beats.
- Web Speech API TTS when supported.
- Optional MediaRecorder on speak nodes — graceful fallback.
