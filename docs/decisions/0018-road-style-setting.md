# 0018. Road style setting (timeline and winding road)

Date: 2026-11-11
Status: accepted (pending Eliot's review of PR #259)
Source: Eliot, after reviewing the arena timeline: "I want you to build in the settings an option to switch to other style to be like my first idea."

## Decision

The road page (`/play/<id>?view=map`) offers two visual styles, chosen in Settings:

- **ציר זמן** (`timeline`): the vertical timeline from the 11-11 arena (PR #259 as first opened).
- **דרך מפותלת** (`journey`): a winding asphalt road with stage cards, built from Eliot's original vision (SuperGrok mockup 12 look, his words in `docs/ui/lessons.md`, brief at `/workspace/arena-road-ui/vision-brief.md`).

The choice is stored in `localStorage` as `myroad.roadStyle`, the same way the theme (`myroad.theme`) and reading prefs are stored: on this device only, no server-side preference. Default is `timeline`, so the page he already reviewed does not change until he switches.

This overrides the earlier "not now" in `docs/product/05-מבנה-המוצר.md` and `docs/product/07-מפת-שלבים.md` ("אין מעבר בין סגנונות מפה" / "לא עכשיו: סגנון מפה נוסף"), because he asked for the selection himself.

## Consequences

- Both styles use the same `road_timeline()` view model and the same real progress data.
- Level "I of X" is shown only when real level data exists; it is not invented.
- Main is not touched. No auto-merge.
