# Analytics events (issue #208)

Pseudonymous product analytics, stored in our own SQLite DB. No external analytics service.
Decision: [0011-event-logging](decisions/0011-event-logging.md).

## Identity

Events never carry a user id, email, name, IP or user agent. Each learner gets a random
`analytics_id` (`a_` + 24 hex chars) on first event, kept in table `analytics_ids
(user_id, analytics_id, created_at)`. No server secret is involved. Deleting a learner's
`analytics_ids` row unlinks their events for good. `move_analytics_id(old, new)` keeps one
pseudonym if a session's learner id changes (for guest -> registered, #210).

## Switch

`MYROAD_ANALYTICS`: on unless set to `0`/`false`/`no`/`off`. The app runs with it on. The
test suite sets `MYROAD_ANALYTICS=0` (tests/conftest.py); tests that check analytics turn
it on. Off: `/static/analytics.js` is not served in pages, `POST /api/events` answers 204
and stores nothing, and server-side events are skipped.

## Table `analytics_events` (append-only)

| column | meaning |
|---|---|
| event_id | autoincrement |
| analytics_id | pseudonym (see above) |
| source | `client` (POST /api/events) or `server` |
| event_type | one of the types below |
| screen | URL path of the page (client events), else null |
| props_json | type-specific props (below), JSON |
| client_ts | client clock, ms since epoch (client events), else null |
| created_at | server clock, ISO 8601 UTC |

## Event types

Client (sent by `static/analytics.js`):

| type | props |
|---|---|
| `tap` | `target`: element `data-ev`, else `id`, else `name`, else tag name. Never its text. |
| `screen_view` | `from_screen`: previous URL path; `ms`: time on the previous screen (both absent on the first screen of a tab session) |
| `answer_submit` | `path_id`; `latency_ms`: time from the step being shown (page load or htmx swap) to submit |

Server (emitted by the app, never accepted from the client):

| type | where | props |
|---|---|---|
| `answer` | `POST /play/{path}/answer` (non-placement paths) | `path_id`, `block_id`, `ok`, `latency_ms` (server clock, since the previous event on that step, as in #25) |
| `placement_answer` | same, on a placement path; and per question in `POST /api/placement/result` | same as `answer` (`latency_ms` absent from the API) |
| `placement_result` | `POST /api/placement/result` | `path_id`, `band`, `correct`, `incorrect` |
| `solution_seen_continue` | `POST /play/{path}/seen_solution` (#247), only after a wrong answer on the current step; not on placement paths. Not an answer: mastery, right first time and the #213 KPI ignore it | `path_id`, `block_id` |

## `POST /api/events`

Headers: session cookie and `X-MyRoad-Request: 1`. Body
`{"events": [{"type", "screen"?, "ts"?, "props"?}]}`, 1 to 50 events, at most 16 KB.
String fields must match `^[A-Za-z0-9_./:\-]{1,160}$` (no spaces, no `@`). Unknown event
types, unknown fields, and any PII key or value are rejected.

| status | meaning |
|---|---|
| 204 | stored (or analytics off) |
| 401 `unknown_learner` | no signed-in session |
| 403 `csrf_header_missing` | header missing |
| 413 `payload_too_large` | body over 16 KB |
| 422 `invalid_events` / `pii_rejected` | schema, unknown type, or PII |
| 429 `rate_limited` | over 30 batches per learner per minute (in-process) |

## PII guard

`myroad_core.analytics.assert_no_pii` runs on every event before it is written. It rejects
keys such as `email`, `name`, `first_name`, `last_name`, `ip`, `user_agent`, `user_id` at any
depth, and string values that look like an email, an IPv4/IPv6 address or a browser user
agent. `tests/test_analytics_events.py` scans every stored row after a real flow.

## Client batcher

`static/analytics.js` (vanilla, no dependency) queues events and flushes at 20 events,
every 10 s, and on `pagehide` / tab hidden. `navigator.sendBeacon` cannot set the
`X-MyRoad-Request` header, so the unload flush uses `fetch(..., {keepalive: true})`, which
is delivered after unload in the same way.
