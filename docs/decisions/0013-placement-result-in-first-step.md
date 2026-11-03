# Placement result inside the road's first step (2026-11-03, UI bot)
## Context
#212 (absorbs #200, docs/product/11 items 14, 14b): show each domain's level and score, one summary score, and the gap the weights point at. Lessons and 0002 forbid a separate "done" screen: finishing placement already 303s into the recommended road's first step. Data: #231 (merged) `domains`, `overall`, `weights`, stored per learner. No route, store or path builder change.
DoD: result renders above the first step in he/en/ar; missing or partial fields fall back to the old hint; 0, 1, many domains; no dashes in copy; axe clean at 375/1280 light/dark.
## Options considered
| Option | Pros | Cons | Rubric (flow, calm, honesty, a11y, cost) | Cost to switch later |
|---|---|---|---|---|
| A (chosen) Result card in the first step's head, replacing the placement hint; rows with a 5 segment meter + level word + score; "הפער שלך" list ordered by weight; primary button dismisses into the step | no interstitial, step visible on the same page, works without JS, one template + view helper | the step card starts lower on 375 on the first visit only | 23/25 | - |
| B Result panel on the road map (`view=map`) head | whole road and result together | adds a forced exit to the map, which Eliot said is optional; extra tap to start | 17/25 | low: include the partial in map.html |
| C Radial/radar chart of domains | compact, visual | reads as a score dashboard, hard for screen readers, color heavy, weak in RTL | 14/25 | medium: new SVG component |
## Decision
A: keeps the learner flowing (lesson 2026-10-31), shows real measurement only (no praise, no badges), and the gap is named with the allowed word פער. Gap = domains whose weight is above an even share, highest first, at most 3; one domain or even weights name no gap. No weights: lowest scores first.
Wiring: `ui/placement_result_view.py` (pure), a read only template global `placement_result_for` in platform_routes (reads `get_placement_detail`, no write), `_placement_result.html` included by play.html when `from=placement`.
Events: taps on the two actions carry `data-ev` (`placement_result_start`, `placement_result_map`) through the existing `static/analytics.js` batcher; `screen_view` is already sent. No new pipeline.
## Verified
- pytest `tests/test_placement_result_screen.py` (18) and full suite: 730 passed, with and without vendored content.
- `tests_a11y` new state `placement-result`: 0 violations at 375/1280 x light/dark.
- Screens: docs/ui/screens/212/.
## Known limits
- Guests without a stored detail see the old hint (fallback), as does any learner whose placement predates #231.
- Domain names come from the placement topic titles (content has no `area` tags yet); untitled ids show the raw id.
## How to switch
To B: include `_placement_result.html` in map.html under the path head and point `pr_start` at the first step URL; about 1 hour, tests change the URL only.
