# 0001 — Per-step learner measurement (#25)

## Context
We need, per learner and per step: time spent, number of attempts, final result / mastery,
as a basis for efficiency work. `learner_attempts` holds one row per *road run*
(path-level totals), not per step. A/B experiments on minors are out of scope.

## Options
| | A: extend `learner_attempts` | B: new append-only `learner_events` |
|---|---|---|
| Granularity | path run; per-step needs a row per step, changing table meaning | one row per step event (view / answer / mastery) |
| Migration | `ALTER TABLE ADD COLUMN` x4 on a live table | `CREATE TABLE IF NOT EXISTS` only |
| Risk to existing reads (stats, `latest_attempt`) | high: rows mix two meanings | none: old table untouched |
| Write pattern | update in place | insert only |

## Decision
**B.** Table `learner_events(user_id, path_id, block_id, event_type, ok, duration_ms, created_at)`.
`record_step_event()` is called from the step player (`step_view` on render, `answer` on
POST /answer, `mastery` the first time a step is mastered, incl. /ack). Duration is
server clock only: time since the learner's previous event on that step, clamped to
[0, 30 min]; no client duration is accepted. `step_aggregates(user_id, path_id=None)` returns
views, attempts, totalMs, lastResult, mastered per step. Only existing ids are stored.

## Verified
- Old-schema DB (no `email`/`needs_practice`, no events table) migrates; old rows kept;
  re-running the migration and reopening are no-ops (tests/test_step_measurement.py).
- Fixed along the way: the email index was created before its column was added on old DBs.
- Player records view/answer/mastery; aggregates and clamping tested. 535 tests pass.

## Known limits
- `step_view` is written on GET (telemetry only; no learner state changes).
- Reloads add views; time between steps on other pages counts until the 30 min cap.
- Stats page not changed yet; no retention policy for events.

## How to switch
Events are a superset: option A columns can be back-filled from `learner_events` with one
GROUP BY; drop the `_step_event` calls in `ui/platform_routes.py` to stop recording.
