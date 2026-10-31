# Placement result screen (2026-10-31, UI bot)
## Context
Issue 151: after the last מבדק question show the detected פער and one recommended דרך, with "התחל" and "דרכים אחרות". UI only; MyRoad Backend is paused, so no route, store or model changes.
## Options considered
| Option | Pros | Cons | Rubric score | Cost to switch later |
|---|---|---|---|---|
| A single column arrival (chosen) | one primary action, same at 375 and 1280, calm chain line | chain line has no road names | 24/25 | - |
| B two column summary | reuses stats tiles | scores on screen feel like a game, weaker hierarchy | 19/25 | low: swap the partial |
| C full bleed road hero | strong mood | needs new illustration parts, harder in RTL and dark | 16/25 | medium: new CSS and art |
## Decision
A. The partial `_placement_result.html` is included from `stats.html` only when the finished road is `path_english_bagrut5_00_placement`. The recommended road is `unlocked_next[0]`, already computed by the server from the placement band. The chain position is read from the road id (01 to 08).
## Verified
- pytest packages/core: 514 passed, 19 skipped (incl. 2 new e2e tests in test_english_bagrut_flow.py).
- axe (wcag2a, 2aa, 21aa, 22aa) at 375 and 1280, light and dark: 0 violations.
- Screenshots: /workspace/ui-review/placement-result/{live,preview}-{375,1280}-{light,dark}.png.
## Known limits
- Level and minutes are not in this view context; shown only under MYROAD_UI_PREVIEW=1 as "נתוני דוגמה".
- "התחל" opens `/play/<road>?view=learn`, which starts at the session index (first step for a fresh road), not a server computed first open step.
- If the band road is not in the catalog, unlocked_next is empty and the screen shows the no road message with only "דרכים אחרות".
## How to switch
To B: replace the include in stats.html with a two column partial reusing `.stats-grid`; ~1 hour, no data changes. To real data: once the backend adds `placement` (band, level, minutes, first step id) to the stats context, read it in the partial and drop the preview branch.
