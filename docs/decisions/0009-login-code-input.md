# Login code field: one input, paste and autofill (2026-11-02, UI bot)
## Context
Issue #59 (with #41, #62). The verify step needs a code field that takes a pasted or autofilled code, reads digits left to right inside the RTL page, ties errors to the field, and works without JS. Server auth, code generation, verification, rate limits and routes are out of scope.
DoD: one `<input>` with one-time-code autofill, numeric keyboard, digits pattern, label, error via aria-describedby; paste normalized; no-JS submit signs in; axe clean in both themes; 4 screenshots.
## Options considered
| Option | Pros | Cons | Rubric score | Cost to switch later |
|---|---|---|---|---|
| A (chosen) one input + letter-spacing + small JS | native autofill and paste, one tab stop, works without JS, smallest surface | separator paste without JS hits maxlength (server already strips spaces/dashes) | 23/25 | - |
| B 8 separate boxes | strong "code" look | breaks autofill/paste on many devices, 8 tab stops, a11y cost, heavy JS | 14/25 | high |
| C one input, wider maxlength allowing separators | no-JS paste of `1234 5678` works | pattern no longer "digits only", looser browser validation | 20/25 | low: change pattern/maxlength in login.html |
## Decision
A: best autofill/a11y fit, least code. Pattern `[0-9]{8}` matches `CODE_DIGITS = 8` (#62 landed), kept so the existing backend test still pins it.
- Paste/autofill/typing keep ASCII digits only (Arabic-Indic digits mapped), capped at maxlength.
- Auto-submit when the field holds a full valid code, once per page load (guard flag + `data-submitting`), off when a CAPTCHA is shown. bfcache `pageshow` resets the guard.
- WebOTP (`navigator.credentials.get({otp})`) not added: it reads SMS only and our code goes by email, so it would never fire.
## Verified
- `tests/test_login_code_input.py`: attributes in he/en/ar, error tied via aria-describedby + aria-invalid, hint copy has no dashes, headless Chrome paste normalization, full-code paste submits exactly once, no-JS browser submit signs in.
- Full pytest green; axe (wcag2a/aa, 2.1, 2.2, best-practice) 0 violations at 375/1280 light/dark.
- Screens: docs/ui/screens/59/.
## Known limits
- Without JS, pasting a code with separators is truncated by maxlength=8; typing or plain paste works.
- If CODE_DIGITS changes, update pattern/minlength/maxlength and copy (or pass the length from the route: backend change).
## How to switch
To C: in login.html set `pattern="[0-9 \-]{8,11}" maxlength="11"`; server already normalizes. ~5 min, update test_login_limits pin.
