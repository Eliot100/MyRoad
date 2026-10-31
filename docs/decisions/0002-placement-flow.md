# Placement flows into the next משבצת (2026-10-31, UI bot)
## Context
Eliot rejected the placement result screen (#156): no "done" screen; keep the learner learning with visible progress, the road is optional. UI only: no route or store changes.
## Options considered
| Option | Pros | Cons |
|---|---|---|
| A meta refresh from the finished placement view into `unlocked_next[0]` learn view (chosen) | template only, no route change, no-JS fallback link | brief blank page before the refresh |
| B HX-Redirect | no flash | the finishing POST lives in a route; needs a route change |
| C redirect to the road map | road is clear | forced exit, Eliot said return to road is optional |
## Decision
A. `stats.html` emits `<meta http-equiv="refresh">` to `/play/<rec>?view=learn&from=placement`; the player shows a dismissible hint and a road rail (one segment per שלב, current marked, `aria-current`). Supersedes 0001-placement-result.
## Known limits / Backend gap
- The next fitting משבצת is the first step of the recommended road (session index), not a server computed first open step within it.
- A cleaner hop needs the answer/ack POST to redirect to the next road directly when placement finishes (route change, Backend).
