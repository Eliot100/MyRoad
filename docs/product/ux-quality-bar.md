# UX quality bar: learner flow

Issue: #238. Flow: placement → path → practice → session end. Related: #233 (mobile), #235 (PWA/offline), #247 (seen the solution, continue), #215 (full solution), #219 (worked examples), Eliot100/MyRoad-content#43. All checks run at 360px and 412px in he/en/ar (RTL for he/ar).

Owner: bot:ui (copy items tagged `supergrok`). Sources: docs/ui/lessons.md, docs/product/10-step-variants.md, docs/product/11-final-poc-decisions.md (items 1-19, D23-D27), docs/platform-plan-v1.md, docs/vision/05-decisions-log.md (D7, D25, D27), acceptance on #210 #211 #212 #218 #219 #233 #235.
Every check has to pass by looking at a screenshot or by running a test. If a check can't be shown that way, it doesn't count as passed.

## North-star moments (these rank first)
1. **First 60 seconds:** a new learner on a phone at 360px gets one question right before any sign-up, with nothing confusing. (D25 / item 19, #210)
2. **Wrong answer:** the full solution reads as kind and clear, never as punishment, and offers a "seen the solution, continue" path (#247). (item 9, #215)
3. **End of a session or stage:** the screen shows real progress toward the goal and one obvious next step. The primary button is "Continue learning"; ending is secondary. (items 6-8, 17, #191, #216, #206)
A failure in one of these moments blocks the release, even if every other screen is polished.

## Shared rules (apply to every screen below)
- **Copy:** plain Hebrew. For product words use only דרך / שרשרת / נתיב / שלב / פער (per UI rules). No points, streak loss, leagues, badges or praise words (item 7, item 23). No English IDs or raw keys on screen. Test: a string lint over he/en/ar.json finds no banned terms and no untranslated keys.
- **Layout & spacing:** every margin, padding and gap is on the 8px scale (4 is allowed for hairlines). Each screen has exactly one `.primary` action in view. Test: CSS token lint, plus DOM count of `.primary:visible` == 1.
- **States:** empty, loading (htmx-request indicator ≤ 300ms), error (plain sentence + retry), offline (he/en/ar message, the answer is not lost) (#235).
- **RTL/LTR:** `dir` comes from the locale. Mixed content uses `<bdi>`/`dir=auto`. Arabic text carries `lang="ar"`, and harakat render without clipping (line-height ≥ 1.8 on Arabic content).
- **Mobile 360/412 (#233, D27):** `scrollWidth <= innerWidth`. Tap targets ≥ 44×44 CSS px. The focused input stays visible when the soft keyboard opens (visualViewport test). Audio controls are play, slow and repeat (item 12), each ≥ 44px.
- **A11y WCAG 2.2 AA (#218):** axe reports 0 serious/critical. Text contrast ≥ 4.5:1 and UI contrast ≥ 3:1 in light and dark. Focus is visible and not hidden behind sticky bars (2.4.11). Every input has a label. Answer feedback sits in `aria-live="polite"`. Target size meets 2.5.8.
- **Evidence UI attaches to the PR:** screenshots at 360 he + 360 en (plus 412 he, and ar for Arabic screens), light + dark, axe JSON, and a Playwright run of the checks marked [test].

---

## 1. Login / first entry
- Copy: [ ] A first visit to `/` lands on practice with no `/login` redirect (#210) [test]. [ ] There is one sentence asking for the audio/writing preference with one tap (item 5). [ ] The sign-up offer appears only after the first passed step and can be dismissed. [ ] The login lede is ≤ 1 short sentence. `supergrok`: rewrite the login, register and verify microcopy.
- Layout: [ ] On the login card the only primary is submit. The language switcher is secondary. [ ] After the first login, no auth UI appears on home/play. Profile and language live in `/settings` only (D7) [test].
- States: [ ] error on wrong/expired code (role=alert); [ ] resend/restart link; [ ] offline message; [ ] loading on submit (button disabled, no double post).
- RTL: [ ] the code input stays `dir=ltr` inside an RTL page; [ ] the email field is LTR.
- Mobile: [ ] the code field shows the numeric keyboard and stays visible above it; [ ] links ≥ 44px tall (today they are 24px).
- A11y: [ ] labels on every field; [ ] the Turnstile widget has an accessible fallback; [ ] focus moves to the error.
- Evidence: shots of guest landing, preference tap, sign-up offer, and verify error.

## 2. Settings
- Copy: [ ] Section titles are plain (פרופיל, שפה, שמע וכתיבה, תצוגה). `supergrok`: full settings microcopy list.
- Layout: [ ] one Save per form; [ ] audio_on/writing_on toggles are present (item 5).
- States: [ ] saved confirmation in aria-live; [ ] the email-change error; [ ] the reading/theme prefs show without JS or are hidden cleanly.
- RTL/Mobile/A11y: [ ] the locale select is labelled; [ ] toggles ≥ 44px; [ ] dark-mode contrast passes.

## 3. Home
- Copy: [ ] one line "continue where you stopped" naming the דרך and שלב; [ ] no gamification.
- Layout: [ ] one primary (continue); [ ] the week strip uses real days only (#191).
- States: [ ] empty (no road yet → the placement CTA); [ ] loading tabs; [ ] offline.
- Mobile: [ ] the `.qtabs`/shelves scroll inside their box only, the page never scrolls horizontally [test].

## 4. Placement (adaptive test) (#211)
- Copy: [ ] a short intro: how many questions at most (≤ 15) and that a wrong answer is fine. [ ] No "test score" anxiety words. `supergrok`.
- Layout: [ ] progress shows "question n of ≤15" without an exact countdown that jumps; [ ] one primary.
- States: [ ] the loading of the next item ≤ 300ms with an indicator; [ ] offline keeps the answer and retries; [ ] resume after reload.
- RTL: [ ] English items `lang=en dir=ltr` inside the Hebrew UI.
- Mobile/A11y: [ ] choices ≥ 44px, full width at 360; [ ] the new item's focus moves to its heading.

## 5. Placement result (#212, item 14/14b)
- Copy: [ ] per-domain level in words, plus a number; [ ] the פער is named as "here we'll practice more", not as failure. `supergrok`: level names 1-5.
- Layout: [ ] one primary "start the first step" plus the text-link to the map; [ ] the domain meters fit at 360 without wrapping digits.
- States: [ ] missing API fields → the plain hint (exists); [ ] a domain without score is hidden, not shown as 0.
- A11y: [ ] each meter has role=img and a full label (exists); [ ] meter segments ≥ 3:1 contrast in dark.

## 6. First step / step player
- Copy: [ ] the type pill is in plain words; [ ] title + body ≤ 3 lines at 360 before the choices.
- Layout: [ ] before an answer the choices are the focus. Prev/next sit below and are visually tertiary. [ ] After an answer, exactly one primary (next step).
- States: [ ] offline answer message (exists), with the tapped choice kept; [ ] loading during the htmx swap (hx-sync drop); [ ] an error swap that isn't a blank card.
- RTL/Arabic: [ ] choice labels `dir=auto` + lang; [ ] harakat not clipped in the choice tiles.
- Mobile: [ ] the speak button and audio controls (play/slow/repeat) ≥ 44px; [ ] the scratchpad canvas doesn't cause horizontal scroll.
- A11y: [ ] focus goes to the feedback after the answer (exists) and is visible.

## 7. Worked example (#219: ≥ 3 per English stage, item 10)
- Copy: [ ] labelled as an example, with numbered steps; [ ] "איך פותרים" is opened before the question, never after it as a penalty. `supergrok`: worked-example template copy.
- Layout: [ ] the steps line up as a list; [ ] math/English is LTR inside an RTL card.
- Test: [ ] the content lint finds ≥ 3 learn/example steps before the first practice in each English stage.

## 8. Practice
- Copy: [ ] the warmup (2-3 old questions, item 4) is labelled as חזרה; [ ] extra engine questions until the threshold (item 3) explain why, in one line.
- Layout/States: [ ] same as the step player; [ ] the a1w0/a0w0/a1w1/a0w1 variants each render with no audio/typing that the learner turned off [test, 10-step-variants].
- Mobile: [ ] the fill_in input stays visible above the keyboard; [ ] Arabic input normalisation hint.

## 9. Wrong answer → full solution (item 9, moment 2)
- Copy: [ ] no ✗ in red as the dominant element. The first line is calm ("כמעט. ככה פותרים:"), then the full solution with steps. No "wrong/failed". `supergrok`: tone guide plus all feedback strings.
- Layout: [ ] the solution appears under the choices without a page jump; [ ] one primary ("seen the solution, continue", #247), never two competing.
- States: [ ] content without a solution falls back to the choice feedback plus "איך פותרים", never just "עוד לא."
- A11y: [ ] the solution is in aria-live polite (not assertive); [ ] colour is not the only signal; [ ] the wrong-tile contrast passes in dark.
- Evidence: 360 he/en shots light/dark of a wrong answer with the solution.

## 10. Session end (moment 3, items 6/9/17)
- Copy: [ ] real numbers only (done n/total, right first time, day counted). [ ] The word "סשן" is replaced or approved as a product word. `supergrok`.
- Layout: [ ] progress toward the goal is shown (stages + mastered skills vs the target, #206); [ ] exactly one primary. The primary is "Continue learning" (המשך ללמוד); "done for today" is secondary.
- States: [ ] stats missing → hide the row, never show 0/0.
- A11y: [ ] the dl is readable by a screen reader; [ ] the heading gets focus on swap.

## 11. Stage end (moment 3, item 8, #216)
- Copy: [ ] "stage n of total done" + "now you can …"; [ ] no praise words; [ ] the 2-week-goal case asks keep practising vs leave the נתיב (item 8). `supergrok`.
- Layout: [ ] a short animation that respects `prefers-reduced-motion` [test]; [ ] one primary (next stage) + a secondary (choose); [ ] a progress meter toward the goal.
- A11y: [ ] the SVG art is aria-hidden (exists); [ ] the stage-end title is announced once.

## Done when
All boxes are checked with evidence attached. axe shows 0 serious at 360 he/en/ar, light+dark. The Playwright suite has the [test] items green. The three north-star moments are recorded as one 360px he video each.

## Candidate gaps (from templates, to be confirmed with 360px screenshots)
1. [moment 2] `_step_card.html` + he.json: wrong answer shows only "✗ עוד לא. בחרו תשובה אחרת.", no full solution (item 9 / #215).
2. [moment 2] `_step_card.html`: red ✗ / is-wrong is the dominant signal; verdict text is visually-hidden; feels punitive.
3. [moment 2] `_step_card.html`: "איך פותרים" is a closed details before answering, not surfaced after a miss.
4. [moment 1] `platform_routes.py`: `/login` redirect still present, #210 open; guest likely hits auth wall before first right answer.
5. [moment 1] `_step_card.html`: at 360 choices compete with ~8 elements; prev/next lets a new learner skip the question.
6. [moment 1] he.json `login_lede`: 3 sentences on the first screen (`supergrok`).
7. [moment 3] `_session_end.html`: no progress toward goal (stages + mastered skills vs target, item 17 / #206).
8. [moment 3] `_session_end.html`: two big buttons; the primary ("סיימתי להיום") ends learning; next step ambiguous.
9. [moment 3] `_session_end.html`: stage end lacks animation and 2-week "continue or leave the נתיב" question (item 8); "סשן" is not a product word.
10. [other] `_base.html` no manifest/SW (#235); `platform.css:1193` auth links 24px (<44px); settings has no audio/writing toggles.
