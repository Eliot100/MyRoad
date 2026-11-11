# Arena road UI, candidate 2: journey map

Road screen (`/play/<id>?view=map`) as one winding road with a station per שלב.

- `_journey.html` + `journey_view.py` + `journey.css`: one template for every road shape
  (short, long, linear series, read-only). Replaces the world map canvas (`worldmap.js`),
  the topic diagram, the long station list and the linear rows.
- Mini map at the top (sticky): one segment per שלב, as long as its משבצות, with the
  current שלב outlined, plus "שלב n מתוך m", stages done and משבצות done.
- The current שלב is open with its משבצות; every other שלב stays on screen and opens on tap.
- Review stations are milestones (rounded square marker); the road ends at a flag.
- One named next action: "המשך בנתיב" + the next משבצת title, sticky at the bottom on phones.
- Phones: the road is a narrow strip at the inline start. Wide: the road runs down the middle
  and stations alternate sides.

Shots: `<road>-<375|1280>-<light|dark>-<fold|full>.png`. `before-main-*` are from `main`
(world map) with the same AMIRNET progress (31 of 97 משבצות).
Roads: AMIRNET (15 stations, 97 משבצות, PR #55 content), math 5 algebra (linear series,
4 stations, 54 משבצות), math 3 units (21 stations, not started), math 5 trig (locked,
read-only), English placement (linear).
