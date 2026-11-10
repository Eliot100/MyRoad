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
