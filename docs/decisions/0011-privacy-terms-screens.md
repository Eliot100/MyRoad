# Privacy notice and terms screens (2026-11-03, UI bot)
## Context
Issue #209, decisions 20 and 22 in docs/product/11-final-poc-decisions.md. Two short pages in he/en/ar that say we keep a pseudonymous log of taps, answers and screen timings (#208) and why. Reachable signed in and signed out, linked from the footer, settings and the signup step. Scope: screens and links only.
DoD: GET /privacy and /terms 200 signed out and in; links in footer, settings, signup; copy mentions the log; no dashes; axe clean 375/1280 x light/dark.
## Options considered
| Option | Pros | Cons | Rubric score | Cost to switch later |
| A (chosen) one `legal.html` template, copy as locale keys, sections listed in the route | one layout, he/en/ar through the existing `t()`, copy editable without touching HTML | copy split over keys | 22/25 | - |
| B two hand written templates per page | free form copy | 2 templates x 3 locales to keep in sync | 17/25 | low: move keys into HTML |
| C Markdown files per locale rendered at request time | lawyers can edit prose | new dependency and renderer, harder to test copy rules | 16/25 | medium: add renderer |
## Decision
A: smallest surface, reuses the shell (`_base.html`, `card`, tokens) and i18n, and the tests can check every key for dashes. The footer became one partial (`_footer.html`) so the two links live in one place; the platform line text is unchanged.
## Verified
- `pytest tests` -> 678 passed (new tests/test_legal_pages.py).
- `pytest tests_a11y` (axe, 375/1280 x light/dark, incl. /privacy, /terms signed out and in, signup, settings) -> 18 passed, 0 violations.
- Screenshots: docs/ui/screens/209/.
## Known limits
- Copy is a DRAFT for Eliot with `[להשלים: ...]` placeholders (controller, contact, retention, storage and analytics processor, operator, governing law, date).
- The log itself (#208) is not live yet; the notice describes what #208 specifies.
- #139 had made the footer link free; #209 asks for footer links, so test_footer now allows exactly /privacy and /terms.
- Signup links sit on today's register form (/login?mode=register); #210 owns the future signup flow.
## How to switch
To B: copy each section into `privacy.html` / `terms.html`, drop `_LEGAL_SECTIONS` and the `privacy_*`/`terms_*` keys. About 1 hour; tests keep working on rendered text.
