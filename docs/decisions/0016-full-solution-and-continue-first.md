# Full solution after a mistake, continue first at the session end (2026-11-03, UI · UI UX dev)

## Context
Issue #215 (items 9, 10) and UX quality bar #238 moments 2 and 3. A wrong answer showed a red ✗ and "נסו שוב", with "איך פותרים" closed above the choices. The session end had "סיימתי להיום" as the filled button and "עכשיו אפשר" as plain bullets. Stay in the UI layer: no route, store or content change.
DoD: the right answer and the worked method show under the choices after any miss; the right tile is the one next tap; the session end shows finished שלבים of all and continue is the only filled button; axe 0 new violations at 375/1280 light/dark; core and a11y suites green.

## Options considered
| Option | Pros | Cons | Score | Cost to switch later |
| A (chosen) solution inside the feedback live region, right tile marked as the next tap | One place to read, no page jump, uses existing `correct` + `worked_method` + choice feedback, no new route | The learner still taps the right tile to move on (route needs a right answer) | 22/25 | - |
| B open the existing closed "איך פותרים" disclosure after a miss | Smallest diff | Sits above the choices, far from the feedback; not in the live region; no right answer named | 15/25 | low: template only |
| C a "show solution, then continue" button that skips the step | One tap forward | Needs a server route that marks a step done without a right answer (Backend, out of scope) | 18/25 | medium: new route + store event |

## Decision
A. It reads calmly ("כמעט. ככה פותרים:"), names the right answer, shows the method as numbered lines, and keeps one obvious next step without changing route semantics. Session end: continue ("עוד אחד קצר") is primary, "סיימתי להיום" secondary, a calm road line shows finished שלבים, and each "עכשיו אפשר" line is a button that reopens that step through the existing `/play/<id>/start` form.

## Verified
- pytest packages/core/tests: 737 passed. tests_a11y: 14 passed (new state session-end-continue; wrong answer asserts the open solution).
- Screens: docs/ui/screens/215/ (375/1280 light/dark, 360 he/en), crops in before-after/.

## Known limits
- Fallback when a step has no `worked_method`: the right choice's own feedback, else only the right answer.
- `session.can_do` is text only; the step is found by matching text to block can_do/title.

## How to switch
To C: add a Backend route that records "seen solution" and advances, then swap the hint line for a primary button in `_step_card.html`.
