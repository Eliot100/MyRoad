# MyRoad UI lessons (read before every UI task)

Generalized, testable lessons from Eliot's feedback. Add new entries dated, with a short Why quoting Eliot.

## Top rules

1. Every surface follows the active theme (light in light, dark in dark).
2. The road screen shows the whole road on one screen, never filtered by stage.
3. Premium, Apple level quality; never childish.
4. Progress feedback grounded in real learning (session summary, weekly days goal) is core. Still no points for clicks, no loss messages, no empty praise.

## Rules (always / never)

- [2026-10-29] Always: every new surface follows the active theme, light in light mode and dark in dark mode. Never ship a fixed dark surface. Test: screenshot in both themes; no surface keeps a dark background in light mode. Why: "ציפיתי שתוסיף את זה כהה בעיצוב DARK ובהיר כשאנחנו בעיצוב בהיר".
- [2026-10-29] Always: the road screen shows the whole road on one screen, with no filter by stage. Test: all stages are visible on the road screen without choosing a stage. Why: "שכל הדרך תהיה במסך ללא סינון לשלב ספציפי".
- [2026-10-29] Never: childish visuals. Always: premium quality at Apple level. Test: no cartoon styling, toy colors or clip art; spacing, type and motion feel polished. Why: "זה עיצוב כאילו ילד עיצב".
- [2026-11-02] Rule: progress feedback grounded in real learning (session summary, weekly days goal) is core. Still no points for clicks, no loss messages, no empty praise. Test: the session end shows only real numbers from engagement; the week strip says "x מתוך y ימים" with no loss copy; no scores, points or praise words. Why: "לולאת סשן 10 דקות: סשן + יעד ימים שבועי סלחני מלא" and "רק התקדמות אמיתית". Replaces [2026-10-29] game mechanics rule.
- [2026-10-29] Never: labels clipped at the frame edge in RTL. Test: at 375 and 1280 widths, every label is fully visible inside the frame.
- [2026-10-31] Rule: bot PRs merge with gh pr merge --auto --squash once checks are green, without per-PR approval. Technical choices, such as sample data until an API lands, are mine to make. Only product decisions go to Eliot, through frank. Why: standing rule since 2026-10-21, relayed by frank.
- [2026-10-31] Rule: no interstitial done/result screens; keep the learner flowing into the next משבצת with visible progress; return to the road is optional. Test: finishing placement or a משבצת opens the next משבצת, the player shows a road rail with the current שלב, and the map link stays one tap away. Why: "אני לא רואה צורך במסך בו כתוב שהבדיקה הסתיימה, עם הUI/UX ברור אפשר פשוט לעבור חזרה לדרך ושהוא יבחר מה ללמוד ואיך" and "לא חובה לחזור לדרך, אם הלומד מבין מהר שווה שהוא ימשיך ללמוד מכמה משבצות ברצף ללא 'הוצאה יזומה' אלא עם המחשה וויזואלית של התקדמות".
- [2026-11-02] Rule: allowed on screen product words are דרך, שרשרת, נתיב, שלב, פער and now סשן. Why: Eliot approved "סשן" (item 6, 2.11).
- [2026-11-02] Rule: the end of a שלב gets a short premium animation (line and check, under 1s, off with reduced motion), then the learner chooses what to continue with. The session end sits in the same step card with "סיימתי להיום" and "עוד אחד קצר", so the learner can pass straight through. Why: Eliot items 8 and 9, 2.11.
- [2026-11-02] Rule: every UI PR to main shows before/after screenshots of each changed component (375/1280, light/dark) in a לפני / אחרי section. Why: "על כל PR של הUI למיין אני אראה את הלפני ואחרי בקומפוננטות שהשתנו".
- [2026-11-03] Rule: a wrong answer is kind and complete: calm lead, the right answer named, the full worked method open right under the choices (numbered lines), the right tile marked as the next tap, no red ✗. Session end: continue is the filled button, ending for today is secondary, and "עכשיו אפשר" lines are real actions. Test: test_full_solution_session_end.py. Why: Eliot, #215 / #238 moments 2 and 3.
- [2026-11-03] Rule: no dashes (— or –) in UI copy in any locale; an inline-flex link with an arrow needs a CSS gap (whitespace collapses). Why: Eliot on the 360px shots ("Got it — continue", "→הנתיב").
- [2026-11-01] Always: practice and check steps offer an optional place to work out the answer (scratchpad, closed by default, device only, never graded). Test: a practice step with choices has a closed scratchpad under the question. Why: on math step 2 (487 + 256) there was "no place to write out working" (relayed by frank).

## Preferences (taste)

- [2026-10-29] Experiential, not template like. Use the road metaphor (a path, a winding mountain road). Test: the screen reads as a journey, not a generic list or card grid. Why: "פחות תבניתי ומשעמם אלא חוויתי".
- [2026-10-29] Raise the quality bar on every round. Test: each new round is visibly more refined than the previous one. Why: "להבא תעשה באיכות גבוהה יותר".

## Keep doing (things Eliot liked)

- [2026-10-29] One whole road view on a single screen.
- [2026-10-29] Worlds map (option B) is the chosen direction for the road screen.

## Pre-PR checklist additions

- [2026-10-29] Attach 4 screenshots: 375 and 1280 widths, each in light and dark. Why: "ציפיתי שתוסיף את זה כהה בעיצוב DARK ובהיר כשאנחנו בעיצוב בהיר".
- [2026-10-29] Check RTL labels do not clip at the frame edge at 375 and 1280.

- [2026-11-02] Before/after crops (locator.screenshot) of each changed component at 375/1280, light/dark, BEFORE from origin/main with the same seed and state, under docs/ui/screens/<issue>/before-after/, shown in a לפני / אחרי section of the PR body.

## Change log

Mockup rounds for the road screen:

- v1: rejected. Templated and boring, filtered by stage.
- v2 (garden path, mountain road, map trail): rejected. Childish.
- v3 (elevation profile, map route, spine): Eliot asked for higher quality and more gamification.
- v4 (path, worlds map, medals): Eliot did not love any; chose B, worlds map. Shipped in PR #144. PR #146 made it follow light/dark.
- [2026-10-31] Added the merge and decision rule to Rules.
- 2026-10-31: placement result screen (#156) removed; placement and each משבצת flow into the next משבצת, with a road rail in the player.
- 2026-11-01: Arabic script (#170): self-hosted Noto Naskh, no letter-spacing/uppercase where Arabic shows, letter-forms table for alphabet steps.
- 2026-11-01: optional scratchpad on practice steps (#183), decision 0005.
- 2026-11-01: read aloud (#181): Arabic text speaks as ar with a matching voice; with no voice or audio a calm aria-live note shows instead of silence.
- 2026-11-01: step hint and per choice feedback (#187): hint is a closed 'רמז' disclosure before answering; choice feedback sits under the picked choice, calm neutral note. media_hint is an internal asset slug, never shown as text.
- 2026-11-02: path head goal meter + continue card (#193) and in flow step done line (#191 first AC), decision 0007. Progress copy uses only שלב/נתיב; no end screen, the learner stays on the step card with Next.
- 2026-11-02: login code field (#59), decision 0009: one input with one-time-code autofill, LTR digits in RTL, paste normalized by JS, error tied via aria-describedby; auth surface PRs wait for Cyber security, no auto-merge.
- 2026-11-02: session end + stage end in the step card (#191), forgiving weekly days goal strip and mastered skills on the goal meter (#193, #206), decision 0010. סשן added to the allowed words.
- 2026-11-03: placement result (#212, #200), decision 0013: per domain level and score sit in the first step of the recommended road (no separate screen), five segment meter + level word + score, gap named as פער by weight; fallback to the hint when the API fields are missing.
- 2026-11-03: full solution after a mistake + continue first at the session end (#215), decision 0016.
- 2026-11-04: mobile pass at 360 and 412 px (#233), decision 0017: 44px tap areas on header links, chips, subject tabs and map tiles with the text size unchanged; focused field kept above the soft keyboard; CI test tests_a11y/test_mobile_360_412.py in he, ar and en.
