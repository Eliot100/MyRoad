# Step hint and per choice feedback in the player (2026-11-01, UI bot)
## Context
#185 added optional `hint` (step) and `feedback` (choice). `media_hint` existed and was never rendered. Keys are absent when unset.
## Options considered
| Option | Pros | Cons |
| A (chosen) closed `<details>` hint before choices; note under the picked choice | no JS, matches scratchpad disclosure, calm | one more row on the card |
| B hint as a button that reveals inline text via JS | compact | needs JS, custom a11y |
| C merge choice feedback into the existing feedback box | one box | loses the link to the picked choice |
## Decision
A. Native disclosure, works without JS, same look as the scratchpad rows. Choice note spans the grid row under the picked choice (dense flow keeps siblings on that row), aria-live polite, neutral colours.
## media_hint
History shows English asset slugs only ("bird", "clap_pattern", "free_play", "thank you"); no current content sets it. Not learner facing, so it is not rendered.
## Verified
- pytest (tests/test_step_hint_feedback_ui.py + full suite); axe 0 violations at 375/1280 × light/dark.
## How to switch
To B: replace the `<details class="step-hint">` block in `_step_card.html` with a button + hidden paragraph and toggle in platform.js.
