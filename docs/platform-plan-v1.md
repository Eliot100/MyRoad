# MyRoad platform plan v1

Status: **v1, ready to merge**. Owner: MyRoad PM. Written 2026-10-21 (Israel time).
Inputs folded in: [`docs/ux-research-2026-10.md`](ux-research-2026-10.md) (UX, Must M1–M8 / Should S1–S5 / Could C1–C4, cited below as **UX M#**) and [`docs/ui-audit-2026-10.md`](ui-audit-2026-10.md) (UI, cited as **UI audit**). Learner we design for (from UX): an adult Hebrew speaker returning to bagrut English or math, on a phone, in short gaps, often anxious about math.

## 1. Goal and v1 definition

**v1** = a learner can sign in by email, finish onboarding, pick a path from the catalog, walk the path map, finish every step in the step player, see progress and review, and get an end-of-path summary. This works in he/en/ar (RTL polished) on phone and desktop, and it looks high-standard by 2026 norms. The bar is reached when Eliot's Grok-built paths, written in the existing path JSON format (schema v2), are merged into `Eliot100/MyRoad-content` and play end to end with no platform code changes.

Baseline on `main` today: FastAPI + Jinja + htmx 2, SQLite `PathStore`, schema v2 (step kind, review, prerequisites, score), data-driven locales (`locales/*.json`), email-code login, screens: login, settings, home/catalog, path map, step player, stats, accessibility statement.

Already shipped by UI on 2026-10-21 (UI audit §1, PRs #89–#116): semantic colour/spacing/type tokens, dark theme following the system, one main landmark + skip link per screen, language switch on login, map Start/Continue in reach on phones, announced pending state when answering, text size 100/125/150% and reduce-motion toggle (client-side only), end-of-path screen led by "what you learned / next up" (UX M5), floating "back to my station" (UX S1), "explanations are in Hebrew" notice for ar/en (UX S3), empty-tab and offline-answer states, localised step-type pill. axe-core reports 0 violations on every screen in he/en/ar, light and dark, at 375 and 1280 px; no sideways scroll at 375 px, also at 150% text.

**Out of scope:** Cloudflare, agent/AI gateway and model-backed builder, security hardening (paused per the 20.10 work plan).
**Publish rule:** an agent may publish. There is no human-only gate (decisions log; `publish_gate.py` checks format only).

## 2. Reuse first

Prefer mature, maintained libraries over custom code. Every capability PR states one line in its body:
`Reuse: <lib>` or `Built: <why no lib fits>`.
Candidates (use one only after a short check: license, size, maintenance):

| Need | Default reuse |
|---|---|
| Design tokens | CSS custom properties; optional build with Style Dictionary |
| CSS base / logical props | Open Props or a modern-normalize, written with logical properties (`margin-inline`, `inset-inline-start`) |
| Fonts | Self-hosted Noto Sans Hebrew, Noto Sans Arabic / Noto Naskh Arabic, Inter (or Noto Sans), via Fontsource files |
| Interactions | htmx 2 (already vendored); Alpine.js only if local state needs it |
| Motion | CSS transitions + View Transitions API (already used in #69); `prefers-reduced-motion` |
| Icons | Lucide (SVG sprite), with mirroring rules for RTL |
| a11y testing | axe-core via Playwright (`@axe-core/playwright` or `axe-playwright-python`) |
| E2E / visual | Playwright (Python) with screenshots per locale and viewport |
| Performance | Lighthouse CI |
| Spaced review | FSRS (`fsrs` Python package) |
| i18n plurals/numbers | Babel (Python) for CLDR plurals, numbers and dates |

## 3. Quality bar (cross-cutting, applies to every milestone)

- **Design system:** a tokens file (color incl. dark mode, spacing 4-pt scale, radius, shadow, z-index, motion durations/easings, typography scale). No raw hex or px in components after M1. A documented component set: button, input, code input, card, chip, progress bar/ring, toast, dialog, tabs, empty state, skeleton.
- **Typography:** fluid type scale (`clamp()`); per-script font stacks via `:lang(he)`, `:lang(ar)`; Arabic gets about 10% more line-height; no letter-spacing on Arabic; numbers and math stay LTR via the existing `bdi` filter.
- **RTL polish:** logical properties only; directional icons mirrored, non-directional icons not; the map, progress bars and transitions follow `dir`; mixed-direction strings tested.
- **Responsive:** mobile-first; breakpoints 360 / 768 / 1200; touch targets ≥ 44×44 px (WCAG 2.2 asks for 24 px minimum; we aim higher); safe-area insets.
- **Motion:** 150–250 ms UI transitions, one easing set; everything respects `prefers-reduced-motion`.
- **Anxiety-safe learning (UX §7):** no timers anywhere in the player; no red/warning colour on mistake counts; wrong answers say "not yet", not "wrong".
- **Accessibility WCAG 2.2 AA:** contrast, visible focus that is not obscured (2.4.11), target size (2.5.8), no drag-only actions (2.5.7), accessible auth with no cognitive test (3.3.8; email code must be pasteable and autofill `one-time-code`), consistent help (3.2.6), redundant entry avoided (3.3.7), htmx swaps announced via `aria-live`.
- **States:** each screen has designed empty, loading (skeleton, shows after 300 ms), error (retry + plain message in the UI locale) and offline states.
- **Performance budgets (mid-range phone, 4G):** LCP ≤ 2.0 s, INP ≤ 200 ms, CLS ≤ 0.05; per page ≤ 100 KB CSS+JS gzipped excluding fonts; fonts subset, ≤ 150 KB per script, `font-display: swap`; server HTML p95 ≤ 200 ms locally.

## 4. Learner UX end to end

Follows the UX first-version journey (UX §b). *(new)* = does not exist yet.

1. **First visit / login:** one-line promise in the learner's language, language switch before sign-up (done, #97). Email → 8-digit code in one pasteable `one-time-code` field (done). Polish: register vs sign-in look different (UI audit, Low). Must stay puzzle-free (UX M8).
2. **Onboarding *(new)*, `/welcome`, first login only, max 3 questions, one per screen, skippable (UX M1):** subject (English / math), starting point (zero / some / exam refresh), optional "math makes me nervous" which turns on calm copy (UX S4). Ends on one "Start here: <path>" card plus "choose another". No goal question here; visual preferences live in settings, not onboarding.
3. **Home / catalog:** "Continue" card first (exists). On phones, filters go behind a "Filter" disclosure so the first card is above the fold (UI audit). Catalog cards show progress for started paths (UI audit, Low).
4. **Path map:** stations, locks, review stations, `#here` and floating back-to-station (exist). Add: text mastery labels started / familiar / mastered next to the bar (UX S5), one-time inline tip under the first station.
5. **Step player:** answer in place (exists). Add: per-distractor explanation for the chosen wrong option (UX M2), optional hint before answering and "Show me how" worked solution after 2 misses (UX M3), offline handling for Continue/Next (UI audit), Next visually secondary until answered, "no voice for this language" note for read-aloud.
6. **Goal and consistency (UX M4, replaces a daily streak):** after the first station is finished, ask for a weekly days-goal (2 / 3 / 5, default 3). Home shows a week strip in locale week order with ✓ + "2 of 3 days". Missing a day never shows a "lost" message.
7. **Review:** review stations stay in the path (exist). *(new)* Return warm-up: after a gap of ≥ 3 days, the continue card offers "Warm-up (about 3 min)" with ≤ 5 questions from finished stations, plus "skip to where I was" (UX M6).
8. **Settings / profile / language:** name, email change, UI language, accessibility link (exist); text size and reduce motion (exist, this browser only). Add: weekly goal, server-stored reading comfort so it follows the learner and works without JS, phone layout in headed sections (UI audit), optional reminder email (UX S2, off by default).
9. **End-of-path:** reframed (done, #108). Add: list only mastered stations, real "Next up" from the onboarding mapping (UI audit). Stored metrics in §6.
10. **Shell:** one shared base template for all learner screens (UI audit; lowers risk for every later change); print stylesheet for the summary.

## 5. Milestones

Dates are relative to start (S = the day this plan merges). Owners among active bots: **PM**, **UI**, **MyRoad Content (Content)**, **Dev**; **UX** for research input only. Server-side items belong to **MyRoad Backend**, which is paused (see open item O1).

| # | Name | Window | Owner(s) |
|---|---|---|---|
| M1 | Foundations finish (base template, fonts, CI gates) | S → S+5 | UI, Dev |
| M2 | Onboarding and first path | S+3 → S+12 | UI, PM (mapping), Backend* |
| M3 | Step player: explanations, hint, show-me-how | S+3 → S+14 | Content, UI, PM (schema), Backend* |
| M4 | Weekly goal, warm-up review, mastery labels | S+10 → S+24 | UI, PM, Backend* |
| M5 | Phone polish, settings, states, login check | S → S+21 (parallel) | UI, Dev |
| M6 | Content plug-in: Eliot's Grok paths | S+7 → S+28 (parallel) | Content, Dev |
| M7 | v1 release check | S+28 → S+31 | PM |

\* blocked while Backend is paused (O1).

### M1 Foundations finish (UI, Dev)
- Tokens and dark theme exist (#91, #93). Remaining: one shared base template for all learner screens (UI audit #4), self-hosted subset fonts for Hebrew/Arabic/Latin, no physical `left/right` in CSS.
- **Accept:** every learner template extends one base `<head>`/shell, with no visual diff in the Playwright screenshots (3 locales × 375/1280 × light/dark); grep finds no raw hex colours outside the tokens file; a CI job runs axe on every screen in he/en/ar with 0 violations and fails the build on any new one.

### M2 Onboarding and first path (UI, PM, Backend*)
- `/welcome` per §4.2; PM writes the answers → path mapping table (O3); Backend stores answers.
- **Accept (from UX M1):** a new learner reaches step 1 of the recommended path in ≤ 4 taps after the code; skip goes to the catalog; each question is a `<fieldset>` with `<legend>`; works without JS; axe clean in he/ar/en; a returning learner never sees `/welcome`; end-of-path "Next up" uses the same mapping.

### M3 Step player: explanations, hint, show-me-how (Content, UI, PM, Backend*)
- PM specs optional fields in the path JSON (O4); Content authors them for the two pilot paths; Backend passes the chosen choice's text in the answer payload; UI renders.
- **Accept (UX M2, M3):** picking distractor B shows B's explanation under the choices; a step without per-choice text still shows `feedback_try`; the screen reader announces verdict + text once; "Show me how" appears only after the 2nd miss, opens with Enter/Space, needs no JS; scoring follows O5; hint appears before answering only when the content has one; no timer, no red "wrong" copy.

### M4 Weekly goal, warm-up review, mastery labels (UI, PM, Backend*)
- Goal prompt after the first finished station; week strip on home; goal in settings; warm-up after a gap; text mastery levels on the map.
- **Accept (UX M4, M6, S5):** missing one day never shows a "lost" message; strip follows locale week order (Sun–Sat he/ar, Mon–Sun en) and direction, done days marked by ✓ + text, not colour alone; active-day rule per O6; after a gap ≥ O7 the card shows "Warm-up" and "skip", warm-up has ≤ 5 steps then lands on the continue step, never shown on a same-day return (time frozen in tests); each station shows a text level + icon.

### M5 Phone polish, settings, states, login check (UI, Dev)
- Home filters behind a disclosure on phones; settings in headed sections, reading comfort near the top; offline handling for step navigation; Next secondary until answered; read-aloud "no voice" note; manual login pass on real phones.
- **Accept:** at 375 px the first path card is above the fold on home; navigating Continue/Next offline shows the app's offline message, never the browser error page; theme / text size / reduce motion persist across sessions (cross-device once Backend stores them, O1); Lighthouse CI budgets in §3 enforced on home, map, play; manual test with 5 bad codes never shows an image or text puzzle, and paste plus iOS/Android autofill work (UX M8).

### M6 Content plug-in (Content, Dev)
- Eliot's Grok-built paths (first: `adult/path_english_zero_to_sentences.json`, `adult/path_math_bagrut_4_units.json`) land in `MyRoad-content` via PR, validated by content CI against schema v2. Content adds per-distractor explanations, hints and worked solutions to these two first (M3).
- **Accept:** content CI green; each path appears in the catalog and plays to the end-of-path screen in a Playwright run, with no change to MyRoad code; missing locale strings fall back to `explain_locale` (#81); ar/en learners see the "explanations are in Hebrew" notice until translations exist.

### M7 v1 release check (PM)
- **Accept:** a single checklist issue with all M1–M6 criteria linked to green CI runs; a scripted E2E "golden learner run" (login → onboarding → first path → show-me-how → end-of-path → return warm-up) passes in he, en, ar on mobile and desktop viewports; STATUS.md and README updated; tag `v1.0.0`.

## 6. End-of-path metrics (stored, learner-visible)
Completion (yes/no, date), total time, steps attempted/correct, unified score, per-station mastery level, hints and "show me how" used, warm-ups taken, active days per week vs goal, days to complete. Shown to the learner as learning first (what you learned, next up); time and mistake counts stay in a collapsed details section (UX M5). Stored in the existing SQLite event log / learner progress tables; no external analytics.

## 7. Optional extras (not required for v1)
- *Optional:* PWA (manifest + service worker) for install and offline replay of the current path.
- *Optional:* audio for language steps (Web Speech API TTS) for the English path.
- *Optional:* certificates (printable/PDF) at end of path.
- *Optional:* reuse the React `packages/path-viewer` trail as an island on the map page if it beats the Jinja map in tests.
- *Optional:* weekly email digest of progress (uses existing mailer).
- *Optional:* teacher/coordinator views (roles are open in vision 02).
- *Optional:* auto-read aloud setting (UX C1); weekly summary email (UX C2); exam-date countdown (UX C4, see O9).
- *Optional:* FSRS spaced review queue (`fsrs` package) once the warm-up rule (M4) is in use.

## 8. Open decisions and open items (PM default in bold)

Design defaults:
1. Font for Latin text: Inter or Noto Sans? **Default: Noto Sans** (same family as Hebrew/Arabic).
2. Dark mode in v1? **Done: follows system (#93); add a settings toggle in M5.**
3. Is onboarding skippable? **Default: yes, skip goes to the catalog** (UX M1).
4. Review in v1: fixed warm-up rule or FSRS? **Default: warm-up rule (UX M6) in v1; FSRS optional later.**
5. Habit mechanic: daily streak or weekly goal? **Default: weekly days-goal with forgiveness, no daily streak, no leaderboards** (UX M4).
6. Styleguide page in production? **Default: dev-only route.**
7. Visual regression in CI blocking or advisory? **Default: advisory in M1–M4, blocking from M5.**
8. Use the React path-viewer in v1? **Default: no; stay Jinja + htmx, keep it optional.**
9. Which Grok paths gate v1? **Default: the two adult pilots (English from zero, Math 4 units).**
10. Who publishes paths? **Any agent or user may publish (no human-only gate), format check only.**

Open items raised by the UX research and UI audit:
- **O1. Backend is paused (2026-10-20).** M2, M3 and M4 need server work: store onboarding answers, pass per-choice explanation, per-day activity record, warm-up picker, mastery level rules, server-stored reading comfort, reminder emails. **Default: file each as a `bot:backend` issue marked blocked; UI builds templates against fixtures meanwhile. Eliot decides when Backend resumes.**
- **O2. Login code length.** 8 digits is harder to retype than 6 (UX M8). **Default: keep 8 until security work resumes; revisit with Backend and Cyber.**
- **O3. Onboarding → path mapping.** **Default: English + any level → `path_english_zero_to_sentences`; math + any level → `path_math_bagrut_4_units`; refine as more paths land.**
- **O4. Path JSON fields for explanations.** **Default: optional `explain` per choice, optional `hint` and `worked_solution` per practice step, added to schema v2 as optional fields (no version bump); old paths stay valid.**
- **O5. Does "Show me how" affect mastery?** **Default: the step counts as practised, not mastered; it never drops the station below "familiar".**
- **O6. What counts as an active day?** **Default: 5 answered steps or one finished station, whichever comes first.**
- **O7. Warm-up gap threshold.** **Default: 3 days.**
- **O8. Translating explanations into ar/en.** **Default: not in v1; the Hebrew-only notice (#112) stays; Content plans translations after the two pilots.**
- **O9. Exam countdown (UX C4).** **Default: not in v1** (may raise anxiety; test with users first).

Missing input (not blocking the merge):
- Manual login test on real phones (iOS/Android autofill, paste, 5 bad codes, Turnstile never a puzzle). No one has run it yet; owner UI with Eliot's phone, part of M5.
- Whether the device has Hebrew/Arabic speech voices cannot yet be detected reliably (UI audit); the "no voice" note needs a detection method.
- The UX doc builds on `/workspace/briefs/ux-ui-research-2026.md`, which is not in the repo; the parts this plan relies on are already in §3.
- No real-user check yet that the floating "back to my station" button is noticed at the top on phones.
