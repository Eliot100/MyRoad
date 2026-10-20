# MyRoad platform plan v1

Status: **draft**. Owner: MyRoad PM. Written 2026-10-21 (Israel time).
A later pass will fold in `docs/ux-research-2026-10.md` and `docs/ui-audit-2026-10.md`. Neither doc existed on `main` or in an open PR when this draft was written.

## 1. Goal and v1 definition

**v1** = a learner can sign in by email, finish onboarding, pick a path from the catalog, walk the path map, finish every step in the step player, see progress and review, and get an end-of-path summary. This works in he/en/ar (RTL polished) on phone and desktop, and it looks high-standard by 2026 norms. The bar is reached when Eliot's Grok-built paths, written in the existing path JSON format (schema v2), are merged into `Eliot100/MyRoad-content` and play end to end with no platform code changes.

Baseline on `main` today: FastAPI + Jinja + htmx 2, SQLite `PathStore`, schema v2 (step kind, review, prerequisites, score), data-driven locales (`locales/*.json`), email-code login, screens: login, settings, home/catalog, path map, step player, stats, accessibility statement. CSS is hand-written (`platform.css`, about 34 KB, few custom properties).

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
- **Accessibility WCAG 2.2 AA:** contrast, visible focus that is not obscured (2.4.11), target size (2.5.8), no drag-only actions (2.5.7), accessible auth with no cognitive test (3.3.8; email code must be pasteable and autofill `one-time-code`), consistent help (3.2.6), redundant entry avoided (3.3.7), htmx swaps announced via `aria-live`.
- **States:** each screen has designed empty, loading (skeleton, shows after 300 ms), error (retry + plain message in the UI locale) and offline states.
- **Performance budgets (mid-range phone, 4G):** LCP ≤ 2.0 s, INP ≤ 200 ms, CLS ≤ 0.05; per page ≤ 100 KB CSS+JS gzipped excluding fonts; fonts subset, ≤ 150 KB per script, `font-display: swap`; server HTML p95 ≤ 200 ms locally.

## 4. Learner UX end to end

1. **Login:** email → 8-digit code (exists). Polish: autofill, paste, resend timer, clear error copy.
2. **Onboarding (new, first login only, ≤ 3 screens, skippable):** UI language (prefilled from `Accept-Language`), display name, goal/interest (subjects), daily minutes target. Ends on a suggested first path.
3. **Home / catalog:** "Continue" card first (last path + next step); catalog grouped by subject and audience (adult/kids), search and filters (language, subject, length); path cards with title, blurb, estimated time, progress.
4. **Path map:** stations from `topics[]`, steps from `nodes[]`; locked prerequisites, review stations, current station in view (exists, #68). Add: per-station progress, a "start here" cue, a path overview header (goal, time, steps).
5. **Step player:** answer in place (exists, #65); add keyboard support, clear correct/incorrect feedback with explanation, hint, "skip / come back", progress within station, celebration at end of station (reduced-motion safe).
6. **Progress:** per path and overall: steps done, score (schema v2 unified score), time, streak.
7. **Review:** schema v2 `review` steps in the path, plus a "Review today" queue from missed items (FSRS scheduling, local only).
8. **Gamification (light):** daily streak, daily goal ring, station badges. No leaderboards or points shop.
9. **Personalization (light):** pick up where you left off, suggested next path by subject/goal, adaptive review queue.
10. **Settings / profile / language:** name, email (change flow exists), UI language, content-language preference, daily goal, reduced motion, text size, theme (system/light/dark), accessibility statement link (exists).
11. **End-of-path:** summary screen: completion, score, time spent, topics mastered vs weak, review suggestion, next path; stored as metrics (see 6).

## 5. Milestones

Dates are relative to start (S = the day this plan merges). Owners only among active bots: **PM**, **UI**, **MyRoad Content (Content)**, **Dev**; **UX** for research only.

| # | Name | Window | Owner(s) |
|---|---|---|---|
| M1 | Design foundations | S → S+7 | UI (UX research input) |
| M2 | Onboarding, home and catalog | S+7 → S+14 | UI, PM |
| M3 | Path map and step player polish | S+12 → S+21 | UI |
| M4 | Progress, review, light gamification, end-of-path | S+19 → S+28 | UI, PM |
| M5 | Settings/profile, states, a11y and performance gates | S+24 → S+33 | UI, Dev |
| M6 | Content plug-in: Eliot's Grok paths | S+14 → S+35 (parallel) | Content, Dev |
| M7 | v1 release check | S+35 → S+38 | PM |

### M1 Design foundations (UI)
- Tokens file (`static/tokens.css`), light + dark; components listed in §3 exist on a `/_styleguide` page (dev only) in he, en, ar.
- Fonts self-hosted and subset for Hebrew, Arabic, Latin.
- **Accept:** grep finds no raw hex colors outside `tokens.css`; no physical `left/right` margins/paddings in CSS (lint rule); Playwright screenshots of the styleguide in 3 locales × 2 viewports are committed and reviewed; axe has 0 serious/critical issues on the styleguide.

### M2 Onboarding, home and catalog (UI, PM)
- Onboarding flow after first login; home "Continue" card; catalog filters and search.
- **Accept:** E2E test: new email → code → onboarding (3 screens) → suggested path opens; a returning user skips onboarding; "Continue" opens the exact next step; filtering by language/subject returns the expected fixture paths; empty catalog and empty search show their designed state.

### M3 Path map and step player polish (UI)
- Station progress, overview header, keyboard support, hint/skip, station celebration.
- **Accept:** a full fixture path is completed with keyboard only (Playwright); in `ar` and `he` the map runs right to left and math stays LTR; each htmx answer swap is announced (aria-live checked in test); INP ≤ 200 ms in the Lighthouse run of `/play`.

### M4 Progress, review, gamification, end-of-path (UI, PM)
- Progress page, "Review today" queue (FSRS), streak + daily goal, end-of-path summary.
- **Accept:** tests: finishing a path shows the summary with correct counts/score from fixture answers; a wrong answer appears in the review queue on the due date (time frozen in test); streak increments once per day and resets after a missed day; metrics rows stored for each finished path.

### M5 Settings, states, a11y and performance gates (UI, Dev)
- Settings additions (§4.10); every screen has empty/loading/error/offline states; CI gates.
- **Accept:** CI job runs axe on every screen in 3 locales (0 serious/critical); Lighthouse CI budgets in §3 enforced on home, map, play; theme/text size/reduced-motion persist across sessions; forced server error on each screen shows the error state in the UI locale.

### M6 Content plug-in (Content, Dev)
- Eliot's Grok-built paths (first: `adult/path_english_zero_to_sentences.json`, `adult/path_math_bagrut_4_units.json`) land in `MyRoad-content` via PR, validated by existing content CI against schema v2.
- **Accept:** content CI green; each path appears in the catalog, plays to the end-of-path screen in a Playwright run, with no change to MyRoad code; missing locale strings fall back to `explain_locale` (exists, #81).

### M7 v1 release check (PM)
- **Accept:** a single checklist issue with all M1–M6 criteria linked to green CI runs; a scripted E2E "golden learner run" (login → onboarding → path → end-of-path) passes in he, en, ar on mobile and desktop viewports; STATUS.md and README updated; tag `v1.0.0`.

## 6. End-of-path metrics (stored, learner-visible)
Completion (yes/no, date), total time, steps attempted/correct, unified score, per-topic accuracy, hints used, review items created, days to complete. Stored in the existing SQLite event log / learner progress tables; no external analytics.

## 7. Optional extras (not required for v1)
- *Optional:* PWA (manifest + service worker) for install and offline replay of the current path.
- *Optional:* audio for language steps (Web Speech API TTS) for the English path.
- *Optional:* certificates (printable/PDF) at end of path.
- *Optional:* reuse the React `packages/path-viewer` trail as an island on the map page if it beats the Jinja map in tests.
- *Optional:* weekly email digest of progress (uses existing mailer).
- *Optional:* teacher/coordinator views (roles are open in vision 02).

## 8. Open decisions (PM default in bold)

1. Font for Latin text: Inter or Noto Sans? **Default: Noto Sans** (same family as Hebrew/Arabic).
2. Dark mode in v1? **Default: yes, follows system, toggle in settings.**
3. Is onboarding skippable? **Default: yes, skip uses defaults from the browser locale.**
4. Review scheduling: FSRS or a fixed 1/3/7-day schedule? **Default: FSRS (`fsrs` package).**
5. Gamification scope: streak + daily goal + badges only? **Default: yes; no leaderboards in v1.**
6. Styleguide page in production? **Default: dev-only route.**
7. Visual regression in CI blocking or advisory? **Default: advisory in M1–M4, blocking from M5.**
8. Use the React path-viewer in v1? **Default: no; stay Jinja + htmx, keep it optional.**
9. Which Grok paths gate v1? **Default: the two adult pilots (English from zero, Math 4 units).**
10. Who publishes paths? **Default: any agent or user may publish (no human-only gate), format check only.**
