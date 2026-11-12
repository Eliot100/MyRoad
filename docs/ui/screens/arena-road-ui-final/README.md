# Arena road UI: final synthesis (for Eliot's review, not merged)

Branch `arena/road-ui-final`, off `main` 28f3797. Base: candidate 1 (vertical timeline), with
grafts from candidate 2 (journey map) and candidate 3 (dashboard). This replaces the world map
chosen in round v4 (PR #144); that call is Eliot's.

- Head: the next משבצת is named and the continue card comes first, so it sits on a phone's first
  screen even under AMIRNET's long blurb. The button opens exactly the named משבצת. A finished
  road shows one message and a secondary "פתיחת המשבצת הראשונה"; a locked road shows the lock
  note and one action (read-only peek) in the head.
- Road: every שלב on one line, closed שלבים keep a dot per משבצת. Sticky overview: "שלב n מתוך m",
  משבצות and שלבים done, one bar segment per שלב sized by its משבצות, the current one outlined.
  The line is solid behind the learner and dashed ahead. Wide screens put the line in the middle
  with שלבים on alternating sides.
- One next action: the sticky continue bar shows only while the head button is off screen.

Shots: `after/<road>-<375|1280>-<light|dark>-<top|landing>.png`. `top` is the first screen,
`landing` is where the page lands (it scrolls to the current שלב on load). `before/` is main with
the same seeded progress. `compare-375.png` and `compare-1280.png`: AMIRNET, main vs final.
Roads: AMIRNET (PR #55 content, 15 שלבים, 97 משבצות, 23 done), math 5 algebra (linear, 20 done),
math from zero (19 שלבים, 9 done), math 5 placement finished (13 of 13), math 5 trig locked.
