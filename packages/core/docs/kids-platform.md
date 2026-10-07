# MyRoad platform catalog + Grade-3 sample paths (v0.7)

The **platform shell** is age-agnostic: groups, subject categories, content-as-data,
identity POC, locales, topic maps, and a path player with optional speech / piano / rhythm.

The **ten Grade-3 sample paths** (group `דרכים לתלמידי כיתה ג'`) are kid-oriented
in content and tone. Soft styling applies only to that demo group / those players
(`.tone-demo`), not to the whole site.

## Content-as-data

Sample paths live under:

```
MyRoad-content/grade3/*.json (CONTENT_DIR or packages/core/content checkout)
```

Schema: `myroad_core.content.schema.ContentPath`  
Optional `topics[]` (`id`, `title_he`/`title_en`/`title_ar`, `node_ids[]`) group
steps into map stations. If omitted, topics are inferred.
Loader: `seed_content_paths()` → PathStore. These demo samples are pre-published.

Future paths use the same JSON format. An agent may publish a draft;
only these demo seeds are pre-published by design.

## Locale consistency (explanations vs content tokens)

**Rule:** Platform UI language and path *explanations* must match. Learning *content
tokens* (vocabulary/phrases being taught) stay in the path's `content_locale`.

Example: learning English with UI in Hebrew → all chrome + explanations in Hebrew;
only target vocabulary/phrases in English. When the learner switches UI language,
shell + explanation strings switch; content tokens do not.

Content JSON fields:

| Field | Role |
|-------|------|
| `explain_locale` | Language of authored explanations / feedback chrome |
| `content_locale` | Language of tokens being taught (e.g. `en` for English paths) |
| `body_he` / `body_en` / `body_ui` | Explanations (follow UI locale) |
| `body_content` | Target vocab/phrases (stay in content_locale) |
| `speak_text` | TTS for content tokens |
| `speak_ui` | Optional TTS for the explanation |

Validation: `myroad_core.content.locale_rules` + pytest (`tests/test_locale_rules.py`)
fail English-learning paths that mix unexplained English chrome into HE explanations
without `body_content` / `speak_text`.

## Home bookmarks / tabs (v0.7)

Primary home navigation sits in a side column (not a full-width bar). Side follows UI locale `dir` from `locales/manifest.json`: right for RTL (`he`, `ar`), left for LTR (`en`). The catalog (groups, subjects, path cards) fills the other side. Tab order still starts on the inline-start side (RTL right, LTR left):

- **דרכים שעשינו** — started / in progress (persisted in `learner_progress`)
- **דרכים שסיימנו** — completed
- **דרכים לתרגול** — needs practice (weak mastery / marked for review)
- **כל הדרכים** — full catalog (filters still apply)

Toggle **לפי זמן**: group paths by recently touched vs older vs never, within subject categories.

## v0.6 platform polish

- **Identity (POC):** first/last name + unique email; opaque `myroad_uid` cookie (`/login`). No passwords / no OAuth.
- **Per-user data:** progress, completed paths, and attempt metrics in SQLite
  (`learners`, `learner_progress`, `learner_attempts`), keyed by user id.
- **Locales:** `he` / `en` / `ar` shell chrome (RTL for he/ar). Language is chosen on `/settings`.
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
Add a path (token-gated): http://127.0.0.1:8765/add-path  
Register / sign in: http://127.0.0.1:8765/login

UI SQLite file: `packages/core/data/myroad_ui.db` (or `MYROAD_DB`). Content: set `CONTENT_DIR` to a MyRoad-content clone.

## Player notes

- Mouse-first: big choice tiles, next/back, piano keys, rhythm beats.
- 🔊 Web Speech API TTS (הקראה) when supported.
- 🎤 Optional MediaRecorder (הקלטה) on speak nodes — graceful fallback.
- Resume: same user cookie restores path progress; catalog shows in-progress / completed.
