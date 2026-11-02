# Path head goal meter, continue card, in flow step done (2026-11-02, UI bot)
## Context
Issues #193 (path head) and #191 (first AC only). Eliot's rules override the proposal: no interstitial done or summary screens, no game mechanics or praise, on screen words only דרך/שרשרת/נתיב/שלב/פער, premium, light/dark, RTL, 375 mobile, no dashes. Session end screen and week strip wait for Eliot's decision. Data from #192 (`ctx['engagement']`, merged as #194).
## Options considered
| Option | Pros | Cons | Score | Cost to switch |
| A (chosen) template partial `_path_head_engagement.html` + pure `engagement_view` (uses ctx engagement, else derives the same shape) | no route or store change, works before and after #192, testable as a function | one more Jinja global | 23/25 | - |
| B compute everything in routes | single source | touches server routes (out of scope for UI) | 18/25 | low: move derive into `_engagement` |
| C client side fetch of /api/path/{id}/engagement | live updates | layout shift, no JS fallback, extra request | 15/25 | medium |
## Decision
A: smallest surface, renders nothing broken when engagement is absent, and the later week strip / set end slot attaches below the continue card in the same partial.
- Goal meter: `stage` from #192 counts finished שלבים; the head names the current one (`min(stage+1, total)`). Segmented track fills from inline start; start point marker from placement. `start_stage` 0 and `stages_total` get their own copy. Target equal to the path title is not repeated.
- Step done: ✓ + `עכשיו אפשר:` line inside the existing `#step-feedback` polite live region, so it is read once; mark animates only without reduced motion. Text from `session.can_do` for that step, else the step title.
## Verified
- pytest packages/core/tests: all pass (see PR). New: tests/test_engagement_head.py (17).
- axe (wcag2a/aa, 21aa, 22aa, best practice) on path head and step done, 375/1280 × light/dark: 0 violations.
- Screenshots docs/ui/screens/193/ (harness forced the placement case: target 800, start stage 2).
## Known limits
- Target copy is `שלב n מתוך N, היעד: X` (no maqaf) so it reads for 800, N יח"ל and a path title.
- Week strip, warm up and set end screen not built (await Eliot).
## How to switch
To B: call `derive_engagement` inside `_engagement` in platform_routes.py and drop the fallback; templates stay the same.
