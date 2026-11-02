# 0004 Session model and weekly active days (#192)

Status: accepted (2026-11-02). Proposal: design/engagement/proposal.md (option A).

## Interface (fixed, the UI builds on it)
`myroad_core.engagement.engagement_for(store, user_id, doc, locale)` returns
`{session, week, goal_meter, gap_days, warmup_suggested}`. It is exposed as template context
`engagement` (path view `map.html` and step player `play.html`), `GET /api/path/{id}/engagement`,
`POST /api/path/{id}/session/next`, and `GET/POST /api/settings/weekly-goal` (`{"goal": 2|3|5}`, else 422).
All JSON endpoints need the session cookie and `X-MyRoad-Request: 1` (403 without, 401 unknown learner,
404 unknown/unpublished path).

## Decisions
- **Session = frozen list.** `learner_sessions(user_id, path_id, session_no, day, step_ids)`. The first
  read on a local day stores the next 6 un-done steps (one per base step, after `select_variants`) from
  `learner_progress.node_index`, then earlier gaps. Reloads that day return the same list. A new local
  day, or `session/next`, stores `session_no + 1` from the current position.
  `done` = in the mastered set, or a correct answer / mastery event. `right_first_time` = the first
  `answer` event for that step was correct. `can_do` = titles of the 2 most recently done steps.
- **Active day** = a local date (Asia/Jerusalem, `ui/dates.LOCAL_TZ` / `local_date`) with at least one
  `answer` event on any path. Week starts Sunday for he/ar, Monday for en. `wd` is 0=Sunday .. 6=Saturday.
  Nothing is stored per week, so missed days reset nothing and a new week simply starts with 0 days.
- **Weekly goal**: `learners.weekly_goal INTEGER NULL` (lightweight ALTER like `audio_on`; no index uses
  it). NULL shows 3 with `goal_set: false`.
- **Goal meter (stages only, no predicted score)**: `stage` = stations (map topics) fully mastered,
  `stages_total` = stations with steps. `start_stage` comes from the path's `placement_route` and the
  learner's placement band (`placement_band` on the placement progress): band inside the route -> 1,
  above it -> `stages_total`, below it -> 0; no route or no finished placement -> null.
  `target_label` from the path id: `psychometric` -> `800`, `bagrut5`/`bagrut_5_units` -> `5 יח"ל`,
  `bagrut_3_units`/`bagrut_4_units` -> `3/4 יח"ל`; otherwise the path title in the locale (he fallback).
- `gap_days` = whole local days since the last active day (null if none); `warmup_suggested` = gap >= 3.
- Clock seam: `engagement._now()` (tests monkeypatch it; no freezegun dependency).

## Options considered
| Option | Pros | Cons |
|---|---|---|
| A. Frozen session rows per day (chosen) | Stable on reload, session numbers, tiny table, cheap | One more table |
| B. Derive session on the fly from position | No table | List shifts as steps are done; no session number |
| C. Session in the play cookie session | No DB | Lost across devices/restarts; not testable from the API |
| D. Store active days / streak counters | Fast reads | Can drift from events; resets tempt shame copy |

A gives the "ending" the proposal needs and stays a view over existing steps. Active days stay derived
(not D) so the event log is the single source of truth.

## How to switch
- Session size: `engagement.SESSION_SIZE` (or `n=`). To derive on the fly (B), ignore `learner_sessions`
  in `session_for`; the table can be dropped with no other reader.
- Week rule: `SUNDAY_FIRST`. Active-day rule: `active_dates` (e.g. count `mastery` too).
- Predicted score: add a field next to `goal_meter` once a calibrated retest exists; do not change `stage`.
- Target labels: `_TARGETS`, or move to a content field (`target_label`) when content adds one.
