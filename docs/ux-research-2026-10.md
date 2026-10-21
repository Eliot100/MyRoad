# UX research, October 2026: benchmark, first-version journey, prioritized features

Owner: UX bot. Audience: UI team, MyRoad PM, Backend, Content.
Builds on `/workspace/briefs/ux-ui-research-2026.md` (tech stack, RTL, platform features) and `ux-specs-quick-wins.md` (quick wins, mostly shipped in #65, #68, #69, #73, #76). Those are not repeated here. This doc covers the *learning-product* layer: onboarding, goals, habit, review, motivation and the end-to-end journey.

Checked against `main` on Oct 21, 2026. Templates live in `packages/core/src/myroad_core/ui/templates/`.

Learner we design for: an adult Hebrew speaker going back to bagrut English or math. They study on a phone, in short gaps, often after a bad experience with school math.

---

## (a) Key findings by area

### 1. Onboarding
- **What leaders do:** NN/g says to skip onboarding when possible. When an app does onboard, it should only ask for content customization the app actually needs (for example, the subject and current level), keep it short with a skip option and a progress indicator, and explain why it asks ([NN/g](https://www.nngroup.com/articles/mobile-app-onboarding/)). Brilliant lets new users sign up and "begin learning right away," then offers recommendations ([Brilliant help](https://brilliant.org/help/using-brilliant/how-do-i-get-started-on-brilliant/)).
- **MyRoad today:** `login.html` register mode asks for first name, last name and email. The learner then lands on `home.html`, which shows a hero, tabs (in progress / completed / practice / catalog) and a time/status toggle. Nothing asks what they want to study or where they are starting from.
- **Gap:** A new adult has to choose a path from a catalog on their own. Nobody asks "English or math? Starting from zero or refreshing?", so the first visit can end in the wrong path.

### 2. Goal setting
- **What leaders do:** Brilliant asks for a streak goal *after the first lesson is done*, not before ([Brilliant flow, Flownato](https://www.flownato.com/flows/brilliant/setting-a-streak-goal); [Brilliant help](https://brilliant.org/help/using-brilliant/how-do-i-get-started-on-brilliant/)). A day counts as done after a small, clear amount: 3 problems or one concept ([Brilliant streak](https://brilliant.org/help/features/what-is-a-streak/)).
- **MyRoad today:** There is no daily or weekly goal anywhere (no goal or streak in the templates or settings).
- **Gap:** Learners have no sense of "enough for today." Adults with limited time need a small, achievable target they choose themselves.

### 3. Progress and streaks
- **What leaders do:** Duolingo found that streaks build habit, and that *flexibility* (Streak Freeze, up to two) increased daily active learners. Losing a streak demotivates people, and fear of losing one can stop them from starting at all ([Duolingo](https://blog.duolingo.com/how-duolingo-streak-builds-habit/)). Brilliant uses Streak Charges that apply automatically and never expire ([Brilliant streak](https://brilliant.org/help/features/what-is-a-streak/)). Khan Academy shows progress as mastery levels (Attempted → Familiar → Proficient → Mastered), and mixed-skill checks can move a skill up or down ([Khan Academy](https://support.khanacademy.org/hc/en-us/articles/5548760867853)).
- **MyRoad today:** Progress bars exist on the home continue card (`home.html`), the map (`map.html`: % and mastered/total), the player (`_play_status.html`) and the end of a path (`stats.html`: time, stations, correct, incorrect, mastery %). There is no streak and no day-level progress.
- **Gap:** Progress is measured per path, not per day or week, so a returning learner sees nothing about their own consistency. If we add a streak, it needs built-in forgiveness from day one.

### 4. Path map navigation
- **What leaders do:** Duolingo uses a single guided path with review built in, a floating "jump back to my spot" button on long scrolls, and a tap on a node to see what it teaches ([Duolingo path](https://blog.duolingo.com/new-duolingo-home-screen-design/)).
- **MyRoad today:** This is strong. `map.html` uses `<details>` stations, `aria-current="step"`, a "#here" jump pill, distinct review stations (🔁 badge + class) and lock banners that name the prerequisite (#44, #68).
- **Gap:** The "jump here" pill sits only at the top of the list. Nothing floats when the learner scrolls far away. Small gap.

### 5. Step player feedback
- **What leaders do:** Synthesis's pitch is "mistakes are expected" with immediate, patient guidance. It targets kids aged 5 to 11, so we take only the tone from it ([Synthesis](https://www.synthesis.com/tutor)). A meta-analysis found that cognitive support and emotion regulation reduce math anxiety and improve performance ([Sammallahti et al., cited via search, see sources note](https://doi.org/10.5964/jnc.8401)).
- **MyRoad today:** `_step_card.html` answers in place with htmx, puts feedback under the choices in `role="status"`, and marks choices ✓/✗. Content feedback is `feedback_ok` / `feedback_try`: one "try" message per step, not one per wrong choice. A wrong answer adds "pick again." There is no hint before answering and no "show me how."
- **Gap:** A wrong pick doesn't explain *that specific* mistake, and a stuck learner can only guess again. With 3–4 choices, guessing turns learning into trial and error.

### 6. Review and spaced repetition
- **What leaders do:** Duolingo orders the path by spaced repetition: revisit a concept soon, then at growing gaps. Practice is also available outside the path for busy days ([Duolingo path](https://blog.duolingo.com/new-duolingo-home-screen-design/)). Khan's mixed-skill checks can lower a level, so decay shows ([Khan Academy](https://support.khanacademy.org/hc/en-us/articles/5548760867853)).
- **MyRoad today:** Review stations are fixed positions in the path (`kids.kind == 'review'`, `review_topic_ids` chips in `_step_card.html`). The home "practice" tab exists. Nothing is scheduled by *time since learning*.
- **Gap:** A learner who comes back after 10 days gets the same next step as one who studied yesterday. Nobody offers "a quick 3-minute review of what you learned last week."

### 7. Motivation and anxiety
- **What leaders do:** In adults, an imposed time limit raised errors for high-math-anxiety people, and a visible clock hurt performance ([Hunt & Sandhu, via search](https://derby-repository.worktribe.com/output/785926)). A literature review finds *some* evidence that timed or high-stakes conditions add to the performance drop for anxious learners, though the evidence is thin ([Caviola et al., PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5585192/)). Mature students show higher anxiety in evaluation situations ([Ryan et al. 2025, via search](https://www.ingentaconnect.com/content/tandf/tmes/2025/00000056/00000001/art00003)).
- **MyRoad today:** The player has no timers (good). `stats.html`, though, leads with "time" and shows an "incorrect" count in warning colour. That turns a learning summary into a test score.
- **Gap:** The end-of-path screen frames the session as an evaluation. Reframe it around what was learned and what comes next.

### 8. Settings
- **What leaders do:** Brilliant's settings cover notifications (streak reminder emails can be turned off), dark theme and narration ([Flownato](https://www.flownato.com/flows/brilliant/onboarding)). NN/g says visual customization belongs in settings, not onboarding ([NN/g](https://www.nngroup.com/articles/mobile-app-onboarding/)).
- **MyRoad today:** `settings.html` has name/email change, language select and a text section linking to `/accessibility`. There are no learning preferences, reminders, text size or motion controls.
- **Gap:** There's nowhere to set a goal, a reminder, or reading comfort (text size, reduced motion, auto-read aloud).

### 9. Accessibility (WCAG 2.2 AA, IS 5568)
- **What leaders and standards require:** 2.5.8 sets a 24×24 CSS px target minimum ([W3C](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)). 2.4.11 says sticky headers and footers must not hide focus, and suggests `scroll-padding` ([W3C](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html)). 3.3.8 says codes must be pasteable and autofillable, and math or puzzle CAPTCHAs fail ([W3C](https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html)). The IS 5568 legal basis is in the prior brief.
- **MyRoad today:** `login.html` verify uses a single field, `inputmode="numeric"`, `autocomplete="one-time-code"`, 8 digits: good. Cloudflare Turnstile can appear after repeated attempts (`captcha_needed`). An accessibility statement exists (#76). The settings a11y section is text only.
- **Gap:** (1) Make sure the Turnstile fallback never becomes an interactive puzzle. If it does, it needs a non-puzzle alternative (3.3.8 counts tests that appear only after failures). (2) An 8-digit code is longer than the usual 6, so retyping it is harder when autofill fails. **PM/Backend decision.** (3) Any new sticky "continue" bar must use `scroll-padding` (2.4.11).

### 10. RTL
- **MyRoad today:** This is mostly solved: `dir`/`lang` on `<html>`, `dir="auto"` on content, `|bdi` filter, `content_lang` attributes, mirrored back arrow. Explanations only exist in Hebrew, so ar/en learners get Hebrew feedback marked with `lang` (`fb_lang` in `_step_card.html`).
- **Gap:** An Arabic or English learner gets Hebrew feedback with no warning. Tell them up front, and offer read-aloud. Translating the content is a **Content/PM decision**.

---

## (b) First-version end-to-end journey

Each stage lists what happens, the screen, and RTL/accessibility notes. Items marked *(new)* do not exist yet.

1. **First visit:** `/login` (default mode). A one-line promise in the learner's language ("Bagrut English or math, 10 minutes a day, at your pace"), with language switch visible *before* sign-up. RTL: page `dir` follows the chosen locale. A11y: the language switch has a visible label and the targets are ≥24 px.
2. **Sign-in / register:** `login.html`, register then verify. Email → code by email → one pasteable field (already done). A11y: errors appear as text next to the field, not colour alone. No puzzle CAPTCHA on the happy path. The "resend code" link already exists (`login_code_restart`).
3. **Onboarding (new, max 3 questions, skippable):** `/welcome` *(new)*. Q1 subject (English / math). Q2 starting point ("starting from zero / I remember some / refreshing for the exam"). Q3 is optional: "what feels true about math?" with a calm option such as "math makes me nervous", which switches on gentler copy. Shows a progress dots indicator and "skip". RTL: the step indicator runs right-to-left in he/ar. A11y: radio groups in `<fieldset>`/`<legend>`, one question per screen, focus moves to the new heading.
4. **First path:** the onboarding answers pick a recommended path. The learner sees one card: "Start here: <path>", plus "choose another" linking to the catalog (`home.html`). No catalog decision on day one.
5. **Map (first time):** `map.html`. The current station is open (exists). A one-time inline tip under the first station explains: "Stations unlock in order. 🔁 stations mix earlier topics." A11y: the tip is plain text in the flow, not a coach-mark overlay.
6. **Step:** `play.html` + `_step_card.html`. Learn → practice → check. No timer, ever. A *(new)* "Hint" button is available before answering. Speak button exists. RTL: math inside `<bdi>` (done in #73).
7. **Feedback:** `_step_card.html`. Correct: ✓ plus a short "why" and Continue. Wrong: ✗ on that choice plus *that choice's* explanation *(Content)*, and after 2 misses a "show me how" worked example *(new)*. Copy never says "wrong" in red caps. Use "not yet." A11y: `role="status"` and focus move (done). Feedback language is labelled if it isn't the UI language.
8. **First session end / goal:** after the first station is finished (not before), a "You learned X" screen *(new framing of `stats.html`)* asks for a weekly goal: "How many days a week can you study? 2 / 3 / 5", default 3. RTL: day chips ordered by locale. A11y: native radio inputs.
9. **Review:** review stations stay in the path (exists). *(New, Backend)*: when the learner returns after ≥3 days, home offers "Warm-up: 5 quick questions from what you learned" before continuing.
10. **Return next day:** `home.html`. The continue card (exists) gains a week strip (Sun–Sat in he/ar, Mon–Sun in en) with done days filled, and "2 of 3 days this week". A missed day isn't punished. With a weekly goal, nothing breaks after a single missed day. An optional email reminder at the chosen time *(Backend)*.
11. **Settings:** `settings.html`. Adds: weekly goal, reminder on/off and time, text size (100/125/150%), reduce motion (overrides OS), auto-read aloud, interface language (exists), link to the accessibility statement (exists).

---

## (c) Prioritized features

### Must (first version)

**M1. Short, skippable onboarding that picks the first path**
- Screen: new `/welcome` after first verify, then `home.html`.
- Problem: a new adult faces a catalog and may start the wrong path.
- Change: up to 3 one-per-screen questions (subject, starting point, optional "math makes me nervous"), a skip link, then a single "Start here" card. **Backend**: store answers on the learner and map them to a path. **PM**: the mapping table.
- Acceptance: a new learner reaches step 1 of a recommended path in ≤4 taps after the code. Skip goes to the catalog. Every question is a `<fieldset>` with a `<legend>`. Works without JS. Passes axe in he/ar/en.

**M2. Wrong-answer explanation for the chosen distractor**
- Screen: `_step_card.html` feedback.
- Problem: "pick again" invites guessing. The learner doesn't learn why their choice was wrong.
- Change: show the per-choice explanation when it exists, falling back to `feedback_try`. **Content**: author `explain` per distractor. **Backend**: pass it in `answer.text`.
- Acceptance: picking distractor B shows B's text under the choices. A step without per-choice text still shows `feedback_try`. A screen reader announces the verdict and the text once.

**M3. "Show me how" after two misses (plus an optional hint before answering)**
- Screen: `_step_card.html`.
- Problem: stuck learners with math anxiety get no way forward except guessing.
- Change: after 2 wrong picks, a "Show me how" button reveals a worked solution (native `<details>`). An optional "Hint" `<details>` before answering, if the content has one. **Content**: hint and worked-solution fields.
- Acceptance: the button appears only after the 2nd miss. It opens with keyboard (Enter/Space). Using it doesn't lower mastery below "Familiar" (**PM decision** on scoring). No JS needed.

**M4. Weekly goal with forgiving consistency (not a daily streak)**
- Screens: goal prompt after the first station is done; `home.html` week strip; `settings.html`.
- Problem: adults with jobs and kids miss days. Duolingo and Brilliant both added forgiveness because broken streaks demotivate.
- Change: weekly days-goal (2/3/5, default 3). A day counts after 1 station step set or about 5 answered steps (**PM** sets the threshold). Week strip on home. **Backend**: per-day activity record.
- Acceptance: missing one day never shows a "lost" message. The strip respects locale week order and direction. Done days aren't shown by colour alone (✓ glyph + text "2 of 3 days"). The goal can be changed in settings.

**M5. Reframe the end-of-path/session screen around learning, not scoring**
- Screen: `stats.html`.
- Problem: leading with time spent and an "incorrect" count in warning colour frames the session as a test, which raises anxiety.
- Change: lead with "What you learned" (station titles) and "Next up". Move time and incorrect count into a collapsed "details" section. Drop the warning colour for mistakes. Keep mastery %.
- Acceptance: the first heading under the title lists learned stations. No red/warn colour on any count. The time tile isn't visible without expanding.

**M6. Return warm-up review after a gap**
- Screen: `home.html` continue card, then the player.
- Problem: after days away, the learner jumps into new material having forgotten the last station.
- Change: if the last activity was ≥3 days ago (**PM** sets the threshold), the continue card offers "Warm-up (about 3 min)" with 5 questions from completed stations, plus "skip to where I was". **Backend**: pick questions.
- Acceptance: after the gap the card shows both buttons. The warm-up has ≤5 steps, then lands on the continue step. Skip works. The feature never shows on a same-day return.

**M7. Reading comfort settings: text size and reduce motion**
- Screen: `settings.html` (section already exists as text only), applied in `platform.css`.
- Problem: phone users and older learners need bigger text. Some need motion off regardless of OS setting (view transitions, #69).
- Change: text size 100/125/150% (root font-size class) and a "reduce motion" toggle that disables view transitions and smooth scroll. **Backend**: store the preference.
- Acceptance: at 150% no horizontal scroll at 360 px on map and player. With reduce motion on, there's no view transition between map and player. The settings persist across sessions.

**M8. Sign-in stays puzzle-free (verification task)**
- Screen: `login.html`.
- Problem: WCAG 3.3.8 fails if a fallback CAPTCHA requires solving a puzzle, even one that appears only after failures.
- Change: confirm Turnstile runs in non-interactive mode only. If an interactive challenge can appear, provide a non-puzzle alternative (for example, rate-limit and wait). **Backend/PM**: whether 8 digits can become 6.
- Acceptance: a manual test with 5 bad codes never shows an image or text puzzle. Pasting the code and iOS/Android autofill both work.

### Should

**S1. Floating "back to my station" button on long maps**
- Screen: `map.html`.
- Change: show a small sticky link to `#here` when the current station is off-screen. Use `scroll-padding` so it never covers focus (2.4.11).
- Acceptance: 44 px target. Hidden when `#here` is visible. Tab focus is never fully covered.

**S2. Optional email reminder** (**Backend**)
- Screen: `settings.html`.
- Change: reminder off by default, opt-in with a time. One email per day at most, with unsubscribe in the email.
- Acceptance: never sent on a day the goal was already met. Can be turned off in one tap from settings or the email.

**S3. Labelled-language notice for Hebrew-only explanations**
- Screen: `_step_card.html` in ar/en.
- Change: a one-line notice, "Explanations are in Hebrew," with the speak button offered. **Content/PM**: translation roadmap.
- Acceptance: the notice shows only when `fb_lang` differs from the locale. The text carries `lang="he"`.

**S4. Calm-mode copy** (from onboarding Q3)
- Screen: the player.
- Change: softer feedback strings, no counts mid-session.
- Acceptance: with calm mode, the player never shows a correct/incorrect count. **Content** writes the copy in he/ar/en.

**S5. Per-station mastery labels** (Khan-style: started / familiar / mastered) instead of only %
- Screen: `map.html`.
- **Backend** for the level rules.
- Acceptance: each station shows a text label plus an icon, not colour alone.

### Could

- **C1. Auto-read aloud** setting: steps are read on load using the existing speak button. Acceptance: toggling it in settings auto-plays once per step, and it stops when the learner leaves the step.
- **C2. Weekly summary email** of stations learned (**Backend**). Acceptance: opt-in only, and the content matches the home strip.
- **C3. Dark theme** via tokens. Acceptance: all text passes 4.5:1 contrast in both themes.
- **C4. "Exam date" countdown** for bagrut learners (**PM decision**: may raise anxiety, so test with users first).

---

## (d) Sources

Opened and read for this doc:
- Duolingo, The habit-building research behind your streak: https://blog.duolingo.com/how-duolingo-streak-builds-habit/
- Duolingo, Introducing the new learning path: https://blog.duolingo.com/new-duolingo-home-screen-design/
- Brilliant, What is a streak?: https://brilliant.org/help/features/what-is-a-streak/
- Khan Academy, How mastery levels work: https://support.khanacademy.org/hc/en-us/articles/5548760867853
- Synthesis Tutor: https://www.synthesis.com/tutor
- NN/g, Mobile-app onboarding: https://www.nngroup.com/articles/mobile-app-onboarding/
- W3C, Understanding 3.3.8 Accessible Authentication (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html
- W3C, Understanding 2.5.8 Target Size (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- W3C, Understanding 2.4.11 Focus Not Obscured (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html
- Caviola et al., Stress, time pressure, strategy selection and math anxiety (review): https://pmc.ncbi.nlm.nih.gov/articles/PMC5585192/

Seen through search results and abstracts only (the full pages timed out or are paywalled). Treat these as weaker evidence:
- Brilliant help, Getting started: https://brilliant.org/help/using-brilliant/how-do-i-get-started-on-brilliant/
- Brilliant flows (Flownato): https://www.flownato.com/flows/brilliant/setting-a-streak-goal , https://www.flownato.com/flows/brilliant/onboarding
- Hunt & Sandhu, time pressure and math anxiety in adults: https://derby-repository.worktribe.com/output/785926
- Sammallahti et al., meta-analysis of math anxiety interventions: https://doi.org/10.5964/jnc.8401
- Ryan et al. 2025, math anxiety among mature students: https://www.ingentaconnect.com/content/tandf/tmes/2025/00000056/00000001/art00003

IS 5568 and the accessibility statement guide: see the prior brief, `/workspace/briefs/ux-ui-research-2026.md` §6.
