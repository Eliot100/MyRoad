# MyRoad UI lessons (read before every UI task)

Generalized, testable lessons from Eliot's feedback. Add new entries dated, with a short Why quoting Eliot.

## Top rules

1. Every surface follows the active theme (light in light, dark in dark).
2. The road screen shows the whole road on one screen, never filtered by stage.
3. Premium, Apple level quality; never childish.
4. No game mechanics (points, stars, streaks, badges) until Eliot decides otherwise.

## Rules (always / never)

- [2026-10-29] Always: every new surface follows the active theme, light in light mode and dark in dark mode. Never ship a fixed dark surface. Test: screenshot in both themes; no surface keeps a dark background in light mode. Why: "ציפיתי שתוסיף את זה כהה בעיצוב DARK ובהיר כשאנחנו בעיצוב בהיר".
- [2026-10-29] Always: the road screen shows the whole road on one screen, with no filter by stage. Test: all stages are visible on the road screen without choosing a stage. Why: "שכל הדרך תהיה במסך ללא סינון לשלב ספציפי".
- [2026-10-29] Never: childish visuals. Always: premium quality at Apple level. Test: no cartoon styling, toy colors or clip art; spacing, type and motion feel polished. Why: "זה עיצוב כאילו ילד עיצב".
- [2026-10-29] Never: game mechanics (points, stars, streaks, badges) until Eliot decides otherwise. Eliot asked for more gamification of the road, but the decision on mechanics is still open, and doc 01 says no gamification. Test: no scores, stars, streak counters or badges in the UI. Why: "אני מעוניין ביותר gamification של הדרך", plus doc 01.
- [2026-10-29] Never: labels clipped at the frame edge in RTL. Test: at 375 and 1280 widths, every label is fully visible inside the frame.
- [2026-10-31] Rule: bot PRs merge with gh pr merge --auto --squash once checks are green, without per-PR approval. Technical choices, such as sample data until an API lands, are mine to make. Only product decisions go to Eliot, through frank. Why: standing rule since 2026-10-21, relayed by frank.
- [2026-10-31] Rule: no interstitial done/result screens; keep the learner flowing into the next משבצת with visible progress; return to the road is optional. Test: finishing placement or a משבצת opens the next משבצת, the player shows a road rail with the current שלב, and the map link stays one tap away. Why: "אני לא רואה צורך במסך בו כתוב שהבדיקה הסתיימה, עם הUI/UX ברור אפשר פשוט לעבור חזרה לדרך ושהוא יבחר מה ללמוד ואיך" and "לא חובה לחזור לדרך, אם הלומד מבין מהר שווה שהוא ימשיך ללמוד מכמה משבצות ברצף ללא 'הוצאה יזומה' אלא עם המחשה וויזואלית של התקדמות".

## Preferences (taste)

- [2026-10-29] Experiential, not template like. Use the road metaphor (a path, a winding mountain road). Test: the screen reads as a journey, not a generic list or card grid. Why: "פחות תבניתי ומשעמם אלא חוויתי".
- [2026-10-29] Raise the quality bar on every round. Test: each new round is visibly more refined than the previous one. Why: "להבא תעשה באיכות גבוהה יותר".

## Keep doing (things Eliot liked)

- [2026-10-29] One whole road view on a single screen.
- [2026-10-29] Worlds map (option B) is the chosen direction for the road screen.

## Pre-PR checklist additions

- [2026-10-29] Attach 4 screenshots: 375 and 1280 widths, each in light and dark. Why: "ציפיתי שתוסיף את זה כהה בעיצוב DARK ובהיר כשאנחנו בעיצוב בהיר".
- [2026-10-29] Check RTL labels do not clip at the frame edge at 375 and 1280.

## Change log

Mockup rounds for the road screen:

- v1: rejected. Templated and boring, filtered by stage.
- v2 (garden path, mountain road, map trail): rejected. Childish.
- v3 (elevation profile, map route, spine): Eliot asked for higher quality and more gamification.
- v4 (path, worlds map, medals): Eliot did not love any; chose B, worlds map. Shipped in PR #144. PR #146 made it follow light/dark.
- [2026-10-31] Added the merge and decision rule to Rules.
- 2026-10-31: placement result screen (#156) removed; placement and each משבצת flow into the next משבצת, with a road rail in the player.
