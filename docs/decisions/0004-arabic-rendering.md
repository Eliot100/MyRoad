# Arabic script rendering (2026-11-01, UI bot)
## Context
Issue 170, for the Arabic 5-unit path (content PRs 16/18, subject from 173). Arabic must render RTL in a quality font, letters joined, harakat not clipped, mixed Arabic/Hebrew isolated, and alphabet steps must show each letter's four positional forms. Readable at 375px, axe clean, light+dark, he and ar UI.
## Options considered
| Option | Pros | Cons | Rubric | Cost to switch |
| A (chosen) Self-hosted Noto Naskh Arabic variable woff2 (fontsource 5.3.0), unicode-range | No CDN (matches htmx vendoring), 94 KB only when Arabic appears, Naskh is the school/textbook style learners meet in bagrut texts | Naskh small sizes look lighter in UI chrome | 22/25 | low: swap the woff2 + family |
| B Google Fonts CSS link | Zero repo bytes | Third-party request on every page, privacy, offline breaks | 17/25 | low |
| C Noto Sans Arabic | Better for small UI labels | Less like printed learning material; harakat sit tighter | 19/25 | low |
Letter forms: ZWJ (U+200D) on the joining sides, shaped by the font itself, vs. Unicode presentation-form code points (FE70-FEFF). ZWJ chosen: works with any OpenType Arabic font and keeps text searchable/speakable.
## Decision
A + ZWJ. The step card's content line no longer forces `dir="ltr"` (it scrambled "ب + ا + ب = بَاب"); it uses the content locale direction plus `<bdi>`. A content line that is only single Arabic letters renders the letter-forms table (`ui/arabic.py`, filter `letter_forms`). `:lang(ar)` resets letter-spacing/text-transform (the content label had uppercase + tracking that broke joins in the ar UI) and raises line-height (1.8 body, 2 for the content word) so harakat are not clipped.
## Verified
- pytest packages/core: 551 passed, 20 skipped (new tests/test_arabic_script.py).
- axe (wcag2a/aa, 21aa, 22aa) on 16 pages: he/ar UI x word/letters step x 375/1280 x light/dark -> 0 violations (docs/ui/screens/170/axe.json). Font "MyRoad Naskh" loaded on all.
## Known limits
- Content has no dedicated letter-forms step yet; the table appears on any step whose content line is a run of single letters (e.g. "ا ب ت ن م ل").
- Arabic UI chrome also uses Naskh; if small labels feel light, add Noto Sans Arabic for chrome only.
- Practice choices in Arabic get the font and line-height, but no larger size beyond 1.2rem.
## How to switch
To C: replace `static/fonts/noto-naskh-arabic-wght.woff2` with the Noto Sans Arabic arabic-subset woff2 from fontsource, keep the family name or rename it in platform.css; update VENDOR.md. ~15 min, nothing else breaks.
