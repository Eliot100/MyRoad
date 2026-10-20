# UI audit, October 2026

Owner: UI bot. Written 21 Oct 2026 after the overnight visual-quality pass.
Scope: login, settings, home, path map, step player, end-of-path summary and the shared shell
(templates, `ui/static/`, `packages/core/locales/*.json`, UI tests). Server, schema, content and
model work is out of scope here and is listed under handoffs.

How this was checked: full test suite with `CONTENT_DIR` pointing at a MyRoad-content clone,
`scripts/smoke_ui.py`, and headless Chrome at 375 px and 1280 px in Hebrew, English and Arabic,
light and dark. axe-core (WCAG 2.0/2.1/2.2 A and AA plus best-practice) reports **0 violations**
on every screen in every combination after tonight's changes, and no screen scrolls sideways at
375 px (also checked at 150% text size).

Severity: **High** = blocks or misleads a learner; **Medium** = noticeable friction or a WCAG
risk that axe cannot catch; **Low** = polish.

## 1. What shipped tonight

| Issue | PR | Change |
|---|---|---|
| #88 | #89 | Map connector line sits behind the station cards; demo accent passes AA |
| #90 | #91 | Semantic colour, spacing and type tokens |
| #92 | #93 | Dark theme that follows the system setting |
| #94 | #95 | One main landmark and a skip link on every screen |
| #96 | #97 | Language switch on login, stacked footer, accent-coloured links |
| #98 | #99 | Map Start/Continue button stays in reach on phones |
| #100 | #101 | Type scale on headings, accent colour on plain links |
| #102 | #103 | Visible and announced pending state when answering a step |
| #104 | #105 | Settings: text size 100/125/150% and a reduce-motion toggle (UX M7, client-side) |
| #107 | #108 | End-of-path screen leads with what you learned and what's next (UX M5) |
| #109 | #110 | Map: floating "back to my station" button (UX S1) |
| #111 | #112 | Player: notice that explanations are only in Hebrew for ar/en learners (UX S3) |
| #113 | #114 | Home: empty tabs link to the catalog; player: offline answer message |
| #115 | #116 | Player: localised step-type pill (was a raw English id like "PRACTICE") |

## 2. Current gaps by screen

### Login
- **Medium** - The 8-digit code field and any Turnstile fallback have not been tested by hand
  with 5 bad codes, iOS/Android autofill or paste (UX M8). Needs a manual pass on real phones.
- **Low** - The register and sign-in modes look almost the same; the heading is the only cue.

### Settings
- **Medium** - Text size and reduce motion are saved in this browser only (localStorage). They do
  not follow the learner to another device. Server-side storage is a Backend handoff.
- **Medium** - Without JavaScript the reading-comfort controls are hidden (they only change
  client-side state). A server-stored preference would let them work without JS too.
- **Low** - The page is long on phones: profile, email change, language and accessibility are one
  column of forms. Grouping into headed sections (or moving reading comfort higher) would help.

### Home
- **Medium** - At 375 px the group, subject and tab filters push the first path card well below
  the fold. A collapsed "Filter" disclosure on phones would put content first.
- **Low** - Path cards show time and step count but no progress for paths already started in
  the catalog view (the status view has it).
- Done tonight: empty tabs now offer "Browse all paths".

### Path map
- **Low** - Stations show a percentage bar; the research suggests text levels (started /
  familiar / mastered, UX S5). Needs Backend level rules first.
- **Low** - The floating "back to my station" button sits at the top on phones to keep clear of
  the sticky Start bar; worth checking with real users that it is noticed there.
- Checked: tabbing through the map at 375 px never leaves a focused element fully covered by the
  sticky Start/Continue bar (WCAG 2.4.11).

### Step player
- **High (content/backend)** - A wrong answer only says "try again"; there is no explanation of
  why the chosen option is wrong (UX M2) and no "show me how" after two misses (UX M3). The UI can
  render these once the data exists.
- **Medium** - The read-aloud button depends on the device's voices; Hebrew or Arabic voices may
  be missing and nothing tells the learner. A small "no voice for this language" message is UI
  work once we can detect it reliably.
- **Medium** - The offline message only covers answering. Moving between steps while offline
  still falls back to a full navigation and the browser's error page.
- **Low** - Choice tiles are large and clear, but the "previous / next" buttons look equal in
  weight to answering; next could be visually secondary until the step is answered.

### End-of-path summary
- **Low** - "What you learned" lists every non-review station of the path. If a learner skipped
  ahead, it could list stations they did not master. Showing only mastered stations needs
  per-station mastery passed to the template (small view-glue or Backend change).
- **Low** - When nothing new unlocks, "Next up" only suggests the catalog. A real
  recommendation needs the onboarding/path mapping (UX M1).

### Shell (all screens)
- **Low** - Each template repeats its own `<head>`; adding a shared script or stylesheet means
  touching 8 files. A base template would make future shell changes safer.
- **Low** - No print stylesheet (the summary screen is the one people may want to print).

## 3. Handoffs (not UI work)

**Backend**
- UX M7: store text size and reduce motion on the learner so they follow them across devices
  (the UI already reads `data-text-size` / `data-motion` on `<html>`; the server could set them).
- UX M2: pass the per-choice explanation for the picked distractor in the answer payload.
- UX M4: per-day activity record for a weekly goal and the home week strip.
- UX M6: pick up to 5 warm-up questions after a gap of 3+ days.
- UX M1: store onboarding answers and map them to a first path.
- UX S5: mastery level rules (started / familiar / mastered) per station.
- UX S2/C2: opt-in reminder and weekly summary emails.
- Summary screen: per-station mastery for the "What you learned" list.

**Content**
- UX M2: an `explain` text per distractor.
- UX M3: optional hint and worked-solution fields per practice step.
- UX S3/S4: Arabic and English explanations (today the player shows a notice instead), and
  calm-mode feedback copy in he/ar/en.

**PM**
- UX M1: mapping from onboarding answers to paths.
- UX M3: whether using "show me how" affects mastery.
- UX M4: what counts as an active day; UX M6: the gap threshold.
- UX M8: whether the 8-digit login code can become 6 digits; confirm Turnstile never shows a puzzle.
- UX C4: exam countdown (risk of raising anxiety; test first).

## 4. Prioritised next list (UI)

1. **Wrong-answer explanation and "show me how" UI (M2, M3)** - biggest learning impact; build the
   templates as soon as Backend/Content provide the fields. Size: M.
2. **Phone home: filters behind a disclosure** - first path card above the fold at 375 px. Size: S.
3. **Offline handling for step navigation** - extend tonight's offline message to Continue/Next so
   learners never hit the browser error page. Size: S.
4. **Shared base template** - one `<head>` and shell for all learner screens; lowers risk for every
   later change. Size: M (touches every template, no visual change).
5. **Settings layout on phones** - headed sections, reading comfort near the top. Size: S.
6. **Weekly goal strip on home (M4)** once Backend has the activity record; must not rely on
   colour alone and must follow locale week order. Size: M.
7. **Text mastery levels on the map (S5)** once Backend has the rules. Size: S.
8. **Manual login pass on real phones (M8)** - autofill, paste, 5 bad codes. Size: S (testing).
9. **Print stylesheet for the summary.** Size: S.
