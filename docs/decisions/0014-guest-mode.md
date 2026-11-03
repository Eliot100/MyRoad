# 0014 Guest mode: practise before sign-up (#210, #241)

## Context
D25 / item 19: a new learner answers a question before any sign-up. Placement, progress,
settings and events are keyed by `user_id`; `adopt_learner_data` moves them to a new id.
Security review (#240): page views must not write, guest creation must be rate-limited,
guest data must expire, offer flags must live in the DB.

## Options
| Option | Pros | Cons | Score | Cost to switch |
|---|---|---|---|---|
| A. Lazy guest learner row (`gst_` + random, no name/email) + existing server-side session | All routes/APIs unchanged; merge = `adopt_learner_data`; one column added | Rows per active guest; needs purge + limit | 9 | Low |
| B. Separate guest cookie + guest tables | Clear split | Duplicates storage and every read path | 4 | High |
| C. Client-only state, upload at sign-up | No server rows | Trusts client progress; no-JS breaks | 3 | High |

## Decision
A. Cookieless GETs of `/` and `/play/*` render anonymously and write no learner/session
rows. The first `POST /play/*` (or `POST /api/settings/steps` with the CSRF header) creates
the guest + session; per-IP limit 20/hour (`MYROAD_GUEST_MAX_PER_HOUR`), else 429. Built:
in-process sliding window (`ui/guest_limit.py`); slowapi/limits are route decorators plus two
deps. `/author`, `/settings`, `/add-path`, the tools API need an account. `/login/verify` →
`merge_guest` (data + prefs, then guest rows deleted). Offer state is `learners.guest_offer`
(offered/dismissed), header `X-Offer-Registration: true` once, `GET /api/guest`,
`POST /api/guest/offer/dismiss`. Cleanup (#241): `purge_stale_guests` deletes `gst_` learners
idle 30+ days with all their rows, at every app start and via
`python -m myroad_core.guest_cleanup [--db PATH]` (cron-safe, idempotent).

## Verified checks
`tests/test_guest_mode.py`: 100 cookieless GETs → 0 new rows; lazy creation; 429 after limit;
offer once/dismiss persisted across a second store; sign-up merge, no duplicate; guests isolated;
guests blocked from author/settings/tools; cleanup deletes only idle guests, idempotent, CLI.

## Known limits
- Rate limit is per worker; a multi-worker deploy gets N× the limit (fine on one LAN box).
- `events` (tool audit trail) still logs one anonymous `path.get_version` per play view.

## How to switch
To B/C: replace `create_guest`/`merge_guest`/`purge_stale_guests` and the gate branch.
