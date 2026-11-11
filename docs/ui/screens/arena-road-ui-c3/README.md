# Arena road UI, candidate 3: road dashboard

Branch `arena/road-ui-c3`, off `main` at 28f3797. Not a PR. Screens are from real MyRoad-content
(`feat/amirnet-road`, which includes main) on a fresh guest database, Hebrew, 375 (mobile emulation)
and 1280, light and dark.

| Road | Shape | State shown |
|---|---|---|
| `amirnet` (path_english_amirnet_01) | 15 שלבים, 97 משבצות | 23 tiles done, on שלב 4 |
| `math-zero` (path_math_zero_to_equation) | 19 שלבים, 75 משבצות, review stages | 9 tiles done, on שלב 3 |
| `math5-algebra` (path_math_bagrut5_01_algebra) | 4 שלבים, 54 משבצות, linear, locked | read-only peek |
| `math5-placement` (path_math_bagrut5_00_placement) | 1 שלב, 13 משבצות | finished |

`before/` is `main` (world map) for amirnet and math5-algebra, the fold only. `after/` has full page and
fold (`-fold`) shots, plus `axe-after.json`: axe-core 4.12 with every tile list open, 0 violations of
any impact in all 16 runs, and no horizontal overflow.

## Shape

1. Head card: subject, road title, blurb, then the **hero**: the next tile by name, its שלב, "משבצת n
   מתוך N", the dots of the current short נתיב, and the one primary button. The button posts the exact
   tile it names. Finished road: "כל N המשבצות בדרך הושלמו" and a secondary button. Locked road: the
   lock note and the read-only link live in the hero, so there is one message and one action.
2. Progress: the existing goal meter (#193, stage track, start point, mastered skills) plus the real
   tile count, next to the week strip on desktop. No percent anywhere.
3. Every שלב on one screen (lessons rule): a card per שלב with its number, title, state word, a
   tile line, and a closed tile list. Only the שלב the learner is on is open. Grid on desktop, one
   column with a quiet spine joining the numbers on phones.

## Code

- `ui/road_view.py`: `road_dashboard(topics, mastered, current_block, linear, read_only)`, pure,
  never raises. All state rules (here, done, started, ahead past the gap, finished, read-only) are
  here and unit tested (`tests/test_road_dashboard.py`).
- `templates/_road_dashboard.html`: macros `road_hero`, `stage_grid`, `stage_card`, `tile_row`. They
  take their data as arguments, so another road page can reuse them.
- `map.html` composes them; the three old layouts (world map, station list, topic diagram, linear rows)
  are one template now.
