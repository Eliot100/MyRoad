# 0012 Adaptive English placement on catsim (issue #211)

Status: accepted (Bot: Dev, 2026-11-03). Code: `packages/core/src/myroad_core/placement_cat.py`.

## Need

A short adaptive placement (harder after a first-try correct, easier after a miss), first-try
scoring (#199), at most 15 items, every domain at least twice, a level and a 0-100 score per
domain, an overall score, and practice weights (lower score = higher weight).

## Options

| option | pros | cons |
|---|---|---|
| A. catsim 0.21.0 (Python, BSD-3-Clause, release 2026-04-08, active) (chosen) | maintained IRT library: ability estimation (numerical search, Dodd's heuristic for all-right / all-wrong), item information, standard error; same language as the server | pulls numpy, scipy, scikit-learn, matplotlib (~200 MB in the image); unidimensional, so one estimate per domain |
| B. jsCAT (JS) | small, browser-side | scoring must stay on the server (first-try events live in SQLite); a second runtime for the same logic |
| C. Hand-written Elo / 1PL | tiny, no dependency | home-made psychometrics, which #211 rules out when a library fits |

## Why A

catsim fits: 1PL items (a=1, c=0, d=1), estimation and information from the library. Our code
only does what is product-specific: which domain to test next (coverage, then unstable
domains), the harder/easier direction rule, the stop rule, and the 0-100 mapping.

Reuse: catsim==0.21.0 (pinned in `packages/core/pyproject.toml`, `api` extra).

## Model

- Item = scored placement step (practice/check with choices). Domain = node `area`; difficulty
  = node `difficulty` (1PL b, -4..4). Content has neither yet: domain falls back to the topic
  id and b is spread evenly from -2.5 to 2.5 in content order (the placement is ordered easy to
  hard). Partial `area` tagging is a schema error; no tagging is reported by a test.
- Next item: domains with fewer than 2 items first; then domains whose standard error > 1.5.
  Within them, an item harder (after a first-try correct) or easier (after a miss) than the
  last one, most informative at the current estimate; if none is left, the hardest (easiest).
  Stop at 15 items, or when every domain has >= 2 items and SE <= 1.5.
- Scores: 1PL maximum likelihood per domain, clamped to [-4, 4], mapped to 0-100; level 1-5 =
  score // 20 + 1; overall from all answers. Weights = (101 - score) normalised to sum 1.
- Audio off: `select_variants` serves the text variant; it inherits the base step's area and
  difficulty and keeps its block id, so it is scored as the same item.
- `band` / `recommended_road_id` are unchanged (first-try wrong count, #199).
- The result is stored per learner in `placement_details` at the end of the test; the API
  recomputes from first-try events if it is missing.
- Guests (#210) do not exist yet. Everything keys on the session's learner id;
  `adopt_learner_data(old, new)` moves placement progress, answers, result and analytics id
  for the guest -> registered step.

## How to switch

To Elo / own 1PL: replace `_estimate` and `_se` in `placement_cat.py` (two functions); the
selection, stop rule, API and tests stay. To jsCAT: move `next_item` to the client and keep
`summarize` on the server. To 2PL/3PL: add `discrimination` / `guessing` to content and pass
them as catsim item columns. To turn adaptivity off: make `_adaptive_advance` return False.
