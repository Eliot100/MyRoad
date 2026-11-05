# Library mockups pass 2 (2026-11-05)

Source folder: `/workspace/supergrok/imagine/library-files/` (Eliot grok.com Library export).
Branch work only. No product decision changes.

## Implemented on this branch

| Mockups | What landed | Commits |
|---|---|---|
| 06, 07, 08, 10, 11, 16, 17 | Dashed two-lane road rail behind linear tiles; stage progress meter under level chip; path metaphor for adult learner | `ui: dashed road rail…` |
| 14, 15, 25 | SVG track marks (done / here / open / lock) and soft current-tile glow | same + assets commit |
| 06, 17, 18 | Calm end-of-road mark after last stage | same |
| 06, 16 | Perspective road brand mark on home/map/series; series open/gap card icon | `ui: brand road mark…` |
| assets | `/static/icons/{road-mark,mark-*,end-tile}.svg` | `ui: add road and track-mark SVG assets…` |

## Skipped (and why)

| Files | Why |
|---|---|
| 01–05 (math KPI / progress dashboards) | Ties to math 5-unit / metrics product work left as an open decision; not general English adult road UI. |
| 03 list-of-stages with locks | Overlaps current series/chain; no clearer adult premium win than existing series screen. |
| 09, 12 staggered card grids | Close to current linear tiles; staggered left/right risks density/RTL clipping without a clear win. |
| 13 hopscotch photo | Childish playground metaphor; violates lessons.md premium/adult rule. |
| 18 earthy multi-color tile blocks | Reads playful / craft; weaker Apple-level restraint than ink+teal. |
| 19 stage grid with flame footer | Grid + flame lean gamified; worlds-map direction already chosen (lessons Keep doing). |
| 20 suggested-path timeline | Useful reference; largely covered by series + linear track already shipped. |
| 21 worlds map option B | Already the chosen road direction (PR #144 / lessons.md); no change. |
| 22 (if present) | Review if new files arrive; none required beyond above at pass time. |
| 23 Avatar/Torrentio screenshot | Unrelated media player UI. |
| 43, 44 Duolingo path | Explicitly childish / mascot / gems / hearts; never. |
| Praise / streak / flame copy in 05 | Conflicts with real-progress-only rule. |

## Note

Worlds map stays the non-linear road. Linear English roads keep the track list (pass 1) with the path-rail polish above. Glossary UI terms unchanged: מקצוע > סדרה > דרך > שלב > משבצת.
