# Read aloud voice detection and fallback (2026-11-01, UI bot)
## Context
Issue #181: on the Arabic placement שלב, הקראה played nothing. platform.js set he-IL for Arabic text, and Eliot's Windows has only en-US voices, so speechSynthesis was silent with no feedback.
## Options considered
| Option | Pros | Cons | Cost to switch later |
| A (chosen) Web Speech API with script detection, voice match by prefix, content audio first, calm aria-live note | No new deps, works offline, honest feedback | Quality depends on installed voices | - |
| B Server TTS (cloud) | Same voice everywhere | Cost, latency, privacy, new service | medium: add endpoint, set data-speak-audio |
| C Hide the button when no voice | Simple | Learner does not know why | low |
## Decision
A: smallest surface, and B plugs in later through the data-speak-audio attribute the card already reads.
## Verified
- pytest full suite; tests/test_speak_fallback.py runs a browser with en-US only voices.
- Playwright on the Arabic placement: lang ar, note shown, axe 0 violations at 375/1280 light/dark.
## Known limits
No content currently ships audio_url; the wiring is ready for it.
