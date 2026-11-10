# Overnight platform QA, 2026-11-11

Branch `supergrok-picks-2026-11-05` at `1533b90` (app) with MyRoad-content `supergrok-picks-2026-11-05` at `7cec9c4`.
Run 2026-11-10, 22:26 to 23:00 Israel time (UTC+2), by Grok Bot (queue items B1 and B2).

## How it was run

- Fresh clones under `/workspace/overnight/qa-b1/` (box). Content is wired through `CONTENT_DIR` (README sibling layout).
- `uvicorn myroad_core.ui.app:app --port 8765` with `MYROAD_DEV_MAIL_CONSOLE=1` (login code printed to the console) and `MYROAD_DEV_INSECURE_COOKIES=1`.
- Playwright (Python, Chromium headless) at desktop 1280x800 and mobile 390x844 (touch), Hebrew UI, light theme.
  Script: [`overnight-2026-11-11/tools/qa.py`](overnight-2026-11-11/tools/qa.py). Raw log: [`overnight-2026-11-11/qa-log.json`](overnight-2026-11-11/qa-log.json).
- Each viewport registered its own learner (email code flow), then visited the screens below and played the math placement end to end.
- Placement sweep: one fresh learner per placement and score (0%, 30%, 50%, 70%, 100% first-try right), playing through the real UI and reading `GET /api/placement/result`.

## Placement bands: the "only 1/3/5" gap is REFUTED

All four placements return every starting level 1 to 5 through the real UI on this branch:

| Placement | 0% | 30% | 50% | 70% | 100% |
|---|---|---|---|---|---|
| math | 1 → 01_analysis | 2 → 02_geometry | 3 → 03_trigonometry | 4 → 04_calculus | 5 → 05_probability |
| physics | 1 → 01_mechanics | 2 → 02_electricity | 3 → 03_waves | 4 → 04_modern | 5 → 04_modern |
| english | 1 → 01_zero | 2 → 02_present | 3 → 03_time | 4 → 04_accuracy | 5 → 05_module_e |
| arabic | 1 → 01_script | 2 → 02_words | 3 → 02_words | 4 → 03_verbs | 5 → 04_reading |

Second check without a browser: [`tools/band_sim.py`](overnight-2026-11-11/tools/band_sim.py) walks every possible first-try answer pattern of the adaptive test (`placement_cat.next_item`) on the real content and scores it with `level_from_counts` + tie-break:

| Placement | items | patterns | level 1 | 2 | 3 | 4 | 5 | test length |
|---|---|---|---|---|---|---|---|---|
| english | 17 | 1006 | 50 | 244 | 396 | 260 | 56 | 8-11 |
| math | 10 | 801 | 27 | 194 | 348 | 203 | 29 | 8-10 |
| physics | 10 | 768 | 33 | 183 | 336 | 183 | 33 | 9-10 |
| arabic | 11 | 576 | 10 | 123 | 255 | 156 | 32 | 8-10 |

Routing notes (content, not a code bug): physics band 5 and band 4 both open 04_modern (05_magnetism is band 6-8); arabic bands 2 and 3 both open 02_words; no placement can reach the band 6-8 roads (math 06-09, physics 05, arabic 05, english 06-08). That matches the `placementRoute` ranges in the content, so it is a content decision.

## What works

- Home (guest and signed in), subject filter, `/roads`, English series page, road screen, world map, placement, lesson tile, metrics, settings, add-path (demo-mode notice), physics lab empty state: all render with status 200 on both viewports.
- Email registration and sign-in with the one-time code.
- Placement plays to the end and lands in the first step of the recommended road (no result screen, as decided).
- No JavaScript page errors, no failed network requests on any screen. The only console errors are the 404s below.
- Tests: `pytest` in `packages/core` 793 passed; `tests_a11y` 25 passed (axe + mobile 360/412 + offline SW).

## Broken flows and problems

1. **Privacy and terms are missing on this branch** (`/privacy`, `/terms` → 404, console "Failed to load resource: 404"; no footer links). They exist on `main` (`e325552`, #257) but the branch was cut before that and never merged `main` back (branch is 5 commits behind `main`: #255, #230, #256, #248, #257). Needs Grok Build or Eliot to decide on merging `main` into the branch; not done here (conflict risk with #248 math chain).
2. **Filler text in teaching stages (content repo, high visibility).** 300 `body_he` fields on the content branch end with generated arithmetic padding like "בדיקה 1: 39 ועוד 1 שווה 40, לא 41. בדיקה 2: …" up to ~900 characters. It comes from `pad()` in `MyRoad-content/scripts/build_bagrut5_roads.py` ("long enough for the span generator"). It shows to learners as the first lesson tile of math 01 (see `mobile-13-lesson-tile.png`), and in math 02-09, physics 01-05 and arabic 02-05 roads. Fixing it needs real stage text or a change in the span generator's length need, so it is left for Grok Build (content + generator), not patched here.
3. **Empty typed or spoken answer counted as a wrong first try** (fixed in B2, see below). On the Arabic placement teaching stages with a voice panel, tapping "בדיקה" with an empty transcript showed "עוד לא… בחרו תשובה אחרת" and recorded an `answer` event with `ok=0`; on a scored item that is a first-try miss and lowers the placement band.
4. Copy (not changed, design call): after an empty voice check the feedback says "בחרו תשובה אחרת" although the step has no choices.
5. README run block did not mention `MYROAD_DEV_MAIL_CONSOLE=1`; without it (and without SMTP) the login code is never sent, so a fresh local run cannot sign in (fixed in B2, doc only).
6. `tests/test_physics_lab.py` read the lab JSON from a fixed sibling `../MyRoad-content` path and ignored `CONTENT_DIR`, so the suite failed with any other documented layout (fixed in B2).

## Fixed in B2 (this branch)

- Empty `type`/`voice` submit is not scored and leaves no `answer` event (`platform_routes.py`), with a regression test in `tests/test_practice_modes.py` (fails before the fix).
- `test_physics_lab.py` uses `default_content_dir()` (same lookup as the app).
- README: local sign-in env vars in the bash and PowerShell run blocks.

## Screenshots

All under [`overnight-2026-11-11/`](overnight-2026-11-11/), `desktop-*` at 1280x800 and `mobile-*` at 390x844 (full page):

| Screen | Desktop | Mobile |
|---|---|---|
| Home, guest | `desktop-01-home-guest.png` | `mobile-01-home-guest.png` |
| Login | `desktop-02-login.png` | `mobile-02-login.png` |
| Privacy (404) | `desktop-03-privacy.png` | `mobile-03-privacy.png` |
| Terms (404) | `desktop-03-terms.png` | `mobile-03-terms.png` |
| Home, signed in | `desktop-04-home-signed-in.png` | `mobile-04-home-signed-in.png` |
| Home, math subject | `desktop-05-home-subject-math.png` | `mobile-05-home-subject-math.png` |
| Roads search | `desktop-06-roads.png` | `mobile-06-roads.png` |
| English series | `desktop-07-series-english.png` | `mobile-07-series-english.png` |
| Road screen (math 01) | `desktop-08-road-math-analysis.png` | `mobile-08-road-math-analysis.png` |
| World map (math 01) | `desktop-09-road-map-math-analysis.png` | `mobile-09-road-map-math-analysis.png` |
| Placement question (math) | `desktop-10-placement-question-math.png` | `mobile-10-placement-question-math.png` |
| After placement (first step of recommended road) | `desktop-11-after-placement.png` | `mobile-11-after-placement.png` |
| Home after placement | `desktop-12-home-after-placement.png` | `mobile-12-home-after-placement.png` |
| Lesson tile (math 01, shows the filler) | `desktop-13-lesson-tile.png` | `mobile-13-lesson-tile.png` |
| Metrics, math placement | `desktop-15-metrics-math-placement.png` | `mobile-15-metrics-math-placement.png` |
| Metrics, math 01 | `desktop-16-metrics-math-analysis.png` | `mobile-16-metrics-math-analysis.png` |
| Settings | `desktop-17-settings.png` | `mobile-17-settings.png` |
| Add path | `desktop-18-add-path.png` | `mobile-18-add-path.png` |
| Physics lab (empty state) | `desktop-19-physics-lab-road.png` | `mobile-19-physics-lab-road.png` |

Not covered: dark theme, en/ar UI locales, add-path with a live gateway.

## Console errors and failed requests

| View | Screen | Error |
|---|---|---|
| desktop, mobile | `/privacy` | 404 Not Found (console "Failed to load resource") |
| desktop, mobile | `/terms` | 404 Not Found (console "Failed to load resource") |

No `pageerror`, no `requestfailed`. (Harness-only 404s from `GET /api/placement/result` before a placement was finished are not app bugs and are not listed.)

---

## B5 re-run after the filler removal and the AMIRNET road (2026-11-11, 00:33 to 00:55 Israel time, UTC+2)

App `supergrok-picks-2026-11-05` at `247c01b` with MyRoad-content `fix/remove-pad-filler` at `4ca3c10` ([MyRoad-content #56](https://github.com/Eliot100/MyRoad-content/pull/56)).
Separate smoke test: app `feat/amirnet-road` at `0dff158` ([MyRoad #258](https://github.com/Eliot100/MyRoad/pull/258)) with content `feat/amirnet-road` at `5454504` ([MyRoad-content #55](https://github.com/Eliot100/MyRoad-content/pull/55)).

### How it was run

- Fresh clones under `/workspace/overnight/qa-b5/` (box), same env as B1 (`MYROAD_DEV_MAIL_CONSOLE=1`, `MYROAD_DEV_INSECURE_COOKIES=1`), branch app on port 8771, AMIRNET app on 8772, fresh SQLite each.
- Playwright (Chromium headless), desktop 1280x800 and mobile 390x844 (touch). Each viewport registered a learner, took the math placement at 0% (lands in math 01 at band 1), read the first teaching tiles, answered the first practice.
- Sweep (mobile): for all 28 bagrut5 roads, the first tile of every topic (140 tiles, `?view=learn&topic=…`) checked for the filler pattern `בדיקה N: X ועוד 1` and for any element of the step card wider than the viewport.
- Scripts: [`tools/qa_b5.py`](overnight-2026-11-11/tools/qa_b5.py), [`tools/amirnet_smoke_b5.py`](overnight-2026-11-11/tools/amirnet_smoke_b5.py). Logs: [`qa-log-b5.json`](overnight-2026-11-11/qa-log-b5.json), [`qa-log-b5-amirnet.json`](overnight-2026-11-11/qa-log-b5-amirnet.json).

### Results

- **Filler is gone.** 0 of 140 swept tiles contain it (`rg` on the content agrees). The math 01 teaching tiles now show one or two short sentences.
- **Short texts look OK.** No horizontal overflow on any of the 139 tiles that have text (the physics lab road is the expected empty state). The shortest card (math 09 "המספר i", 134 characters including the chrome) and the math 01 tiles look normal on both viewports. Math stays in LTR order inside the RTL text.
- Placement at 0% still gives band 1 → `path_math_bagrut5_01_analysis` and lands on its first tile.
- A wrong practice answer shows the calm lead, the right answer and "בחרו את התשובה המסומנת כדי להמשיך" (no change from B1).
- Console errors: only the known `/privacy` and `/terms` 404s. No `pageerror`, no failed requests.
- **AMIRNET pair works.** The road appears on the home page (sidebar group filter "אמירנט: אנגלית לפטור והשמה" and a "להתחיל באנגלית" recommended card), `/roads?group=amirnet` lists 1 road, and `/road/path_english_amirnet_01` returns 200. The first learn tile ("אמירנט ולא פסיכומטרי") continues, and the first check accepts an answer with feedback and the "עכשיו אפשר" line. `/roads?group=psychometric` lists 0 roads, so no English appears there. No console errors on this pair (it has privacy and terms from `main`).
- Tests on the branch with `CONTENT_DIR` = filler-free content: `pytest` 795 passed (793 + 2 new); `tests_a11y` 25 passed.

### Findings

1. Known: `/privacy` and `/terms` still 404 on this branch (5 commits behind `main`). Merging `main` is Eliot's decision, so it was not done here.
2. Content, needs Grok Build or an author: after the filler removal the teaching texts are thin. 60 of 168 "explanation" tiles have exactly the same text as their guided-practice question. Many learn tiles end in an open question with no answer and only a "הבנתי, ממשיכים" button. Example: math 01 "קצב שינוי": "…מה השיפוע בין (1, 2) ל־(3, 8)?". This is not a layout bug.
3. Content typo, small: in `path_arabic_bagrut5_03_verbs` the word "יكتب" (5 places) starts with a Hebrew yod (U+05D9) instead of the Arabic ya, so it should read "يكتب". It comes from `scripts/build_bagrut5_roads.py` line 759 in MyRoad-content. It was not fixed here because this run commits only to the app branch.
4. Fixed in B5 (a11y): on a right answer whose authored `feedback_ok` already opens with the verdict word ("נכון. …", which covers most bagrut5 content), the visually hidden verdict "נכון." was also rendered, so screen readers said "נכון. נכון.". `_step_card.html` now skips the hidden verdict when the feedback's first word is the verdict word. Two tests were added in `tests/test_step_player.py`: one failed before the fix, and the other keeps the hidden verdict for feedback like "מצוין! …". One existing assertion now accepts the visible "נכון!" as the verdict.
5. Note: the psychometric group currently has no roads at all on the AMIRNET pair, so its filter shows "לא נמצאה דרך". The verbal and quantitative roads are still to come (content plan).

### Screenshots

Under [`screens/overnight-2026-11-11-b5/`](screens/overnight-2026-11-11-b5/), viewport-only, 128-colour PNG:

| Screen | Desktop | Mobile |
|---|---|---|
| Home, signed in | `desktop-01-home.png` | `mobile-01-home.png` |
| Road screen, math 01 | `desktop-02-road-math-analysis.png` | `mobile-02-road-math-analysis.png` |
| Teaching stage, math 01 (no filler) | `desktop-03-teaching-stage.png` | `mobile-03-teaching-stage.png` |
| Practice after a wrong answer | `desktop-04-practice-after-answer.png` | `mobile-04-practice-after-answer.png` |
| Placement question, math | `desktop-05-placement-question.png` | `mobile-05-placement-question.png` |
| AMIRNET (feat/amirnet-road): home / first check answered | `desktop-06-amirnet-home.png` | `mobile-06-amirnet-step.png` |
