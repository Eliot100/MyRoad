# Arena road UI, candidate 1: vertical timeline

Branch `arena/road-ui-c1`, off `main` at 28f3797. Not a PR. For the arena picker.

## What changed
The road page (`/play/{path_id}`, map view) draws every road with one template:
one vertical line of שלבים (topics), each שלב a node on the line with its משבצות (steps).

- `ui/road_timeline.py`: one pure view model. Stage and tile states (done, here, open,
  ahead for a linear chain past the פער, view for a locked road), totals, and the one next משבצת.
- `ui/templates/_road_timeline.html`: the timeline. A closed שלב still shows one dot per
  משבצת, so the shape of the whole road is always on screen (lesson 2026-10-29: whole road, no
  stage filter). The current שלב is open; a road of 12 משבצות or fewer opens every שלב.
- `ui/static/road-timeline.css`: theme tokens only, logical properties only, 44px targets,
  shape carries state (filled check, ring, outline, dashed with a lock, rounded square for חזרה).
- Head: the continue card names the next משבצת (`_road_next.html`) and says "המשך בנתיב"
  whenever the road has progress.
- Sticky continue bar: next משבצת + "המשך", shown by JS only while the head button is off
  screen, so one next action is always in view and never twice.
- Removed: world map (`worldmap.js`, `--world-*` tokens), the three list modes
  (station list, topic diagram, linear rows) and the floating "back to my station" button,
  with their CSS (about 560 lines) and tests. New `tests/test_road_timeline.py` covers the same
  behavior (current marker, read-only, linear lock, review by shape, jump script, CSS rules).

## Screens
`after/` and `before/`: AMIRNET (15 שלבים, 97 משבצות, 23 done), math 5 algebra (linear
chain, 54 משבצות, 20 done), math from zero (19 שלבים) and the math placement (1 שלב, finished),
at 375 and 1280, light and dark. `-first-screen` is the first viewport, `-at-here` is scrolled to
the current שלב with the sticky bar, `-full` is the whole page.
