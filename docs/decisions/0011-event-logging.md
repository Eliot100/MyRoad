# 0011 Event logging: own SQLite table and endpoint (issue #208)

Status: accepted (Bot: Dev, 2026-11-03). Schema: [docs/analytics-events.md](../analytics-events.md).

## Need

Log answer submits, taps, screen transitions with time, and answer latency, pseudonymously,
with no PII, batched to a backend table, with an off switch for tests.

## Options

| option | pros | cons |
|---|---|---|
| A. PostHog JS + self-hosted PostHog | mature SDK, autocapture, dashboards | a second service (ClickHouse, Kafka, Postgres) to run; we stay SQLite-only; autocapture records element text, which can hold names; default sends IP / user agent |
| B. PostHog JS pointed at our own endpoint | reuse SDK | its wire format is large and versioned; we would reimplement its ingest; still autocapture/PII risk |
| C. Extend `learner_events` | one table | it is keyed by real `user_id` and drives learning logic (#25, #199 first-try); mixing pseudonymous, free-form client events there risks both privacy and scoring |
| D. New `analytics_events` table + thin `POST /api/events` + 60-line vanilla batcher (chosen) | SQLite only, schema-validated, unknown types rejected, PII scan on write, random pseudonym with no secret | we build the small batcher and a rate limit ourselves; no dashboard (none wanted: "do not build a custom analytics UI") |

Pseudonym: a random `analytics_id` per learner in `analytics_ids`, rather than an HMAC of the
user id. No secret to manage or leak, and deleting the mapping row unlinks the events.

## Why D

The product rule is SQLite only, no external analytics service, and no PII. A and B add a
service and default to capturing PII. C would put pseudonymous data next to identified
learning data. D is the smallest thing that meets every acceptance item.

Built: no library fits a SQLite-only, header-guarded, schema-validated endpoint; the client
batcher is ~60 lines of vanilla JS (sendBeacon cannot send our CSRF header, so it uses fetch
keepalive).

## How to switch

To PostHog later: keep the event names and props in docs/analytics-events.md, load
posthog-js with `autocapture: false`, `ip: false`, `persistence: "memory"`, call
`posthog.identify(analytics_id)`, map our three client types to `posthog.capture`, and move
`emit_server_event` to posthog-python. A one-off export of `analytics_events` can be replayed.
To turn analytics off: `MYROAD_ANALYTICS=0`.
