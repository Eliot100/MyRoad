# BUILD: placement result screen (issue 151)

Goal: after the last מבדק question the learner sees the detected פער and ONE recommended דרך, with "התחל" and "דרכים אחרות". Non goals: server routes, store, model calls (MyRoad Backend, paused).

## Definition of done
1. Finishing the placement renders the result, not the generic road summary (pytest e2e).
2. "התחל" opens the recommended road's first open step; "דרכים אחרות" links /roads?subject=english (pytest).
3. Sample data (level, minutes) only with MYROAD_UI_PREVIEW=1 and labelled "נתוני דוגמה" (pytest).
4. Screenshots 375 (mobile emulation) and 1280, light and dark, no clipped RTL labels.
5. axe wcag2a/aa/2.1/2.2: zero violations in both themes; full packages/core pytest green.

## Rubric (1 to 5): hierarchy and one primary action; calm, adult, no game feel; RTL and theme correctness; reuse (no new design system parts); honesty of data.
Budget: 3 visual rounds. Stop at all criteria >= 4.

## Options
| Option | Sketch | Hierarchy | Calm | RTL/theme | Reuse | Honest | Total |
|---|---|---|---|---|---|---|---|
| A (chosen) Single column arrival | h1, quiet 8 stop chain line with the פער marked, one road card, 2 buttons | 5 | 5 | 5 | 4 | 5 | 24 |
| B Two column summary | result text one side, road card and stats tiles other side | 3 | 3 | 4 | 5 | 4 | 19 |
| C Full bleed road hero | large drawn road with the road title on it | 4 | 3 | 3 | 2 | 4 | 16 |

A wins: one job per screen, works the same at 375 and 1280, uses existing tokens and the 52px/14 button system. B shows scores (accuracy tiles) which drifts to game feel. C needs new illustration parts (issue says no new design system parts).

## Reflections
- Round 1: kicker "מבדק" repeated the h1; switched to the מקצוע label. Note about review roads was false when the פער is road 1; now hidden then.
- Round 1: the chain line had no visible scale; added "דרך N מתוך 8" caption.
- Tests: "#151" in a CSS comment tripped the raw hex token test; wrote "issue 151".
