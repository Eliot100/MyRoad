# Session end, stage end, weekly days goal, mastered skills (2026-11-02, UI · UI UX dev)
## Context
Issues #191, #193, #206 on top of the engagement API (#192, PR #194) and the path head (PR #195, decision 0007).
Eliot 2.11: full forgiving weekly days goal, real progress only (stages, mastered skills, daily/weekly),
a short premium animation at the end of a שלב then a choice, real session stats, "סשן" approved.
No interstitial screen; no points, loss copy or empty praise. DoD: tests, a11y CI state, 375/1280 light/dark shots.
## Options considered
| Option | Pros | Cons | Score | Cost to switch |
|---|---|---|---|---|
| A (chosen) session end and stage end inside the answered step card; week strip as a third head card | no forced exit, "עוד אחד קצר" continues in place via htmx, reuses step-card + eng-head | the card gets long at 375 | 23/25 | - |
| B separate /play/{id}/session-end page | room for richer stats | an interstitial, breaks the 2026-10-31 flow rule | 15/25 | low: move `_session_end.html` into its own route |
| C modal/sheet over the card | feels like a moment | traps focus, extra JS, worse no-JS | 17/25 | medium |
Week strip: 7 day circles with ✓ and hidden full day text (not colour alone) vs a single "x of y" bar; chose circles + text count (both).
## Decision
A: keeps the learner flowing, smallest surface, works without JS (links). Goal change (2, 3, 5 days, the API's set) is a closed
disclosure shown only with JS, since the API is JSON. Stage end animation: SVG road line + check, 1s total, transform/stroke only,
none under reduced motion. Session end shows only when the server dict says complete (never from the derived fallback).
## Verified
- `pytest tests` -> all pass; new `tests/test_session_end_week.py` covers server dict, missing engagement, locales, copy.
- `pytest tests_a11y` (new state week-strip) -> 10 passed locally with content checkout.
- Screens: docs/ui/screens/191/ (+ before-after/).
## Known limits
- Mastered skills list is derived from the page (mastered steps' can_do or title, later road steps first) until the API sends `goal_meter.mastered_can_do` (newest first). The view already prefers that field.
- The a11y fixture path is one שלב with a celebrate step, so session end and stage end are covered by pytest, not axe.
## How to switch
To B: render `_session_end.html` from a new GET route and point the last answer's continue link at it (Dev route; ~1h).
