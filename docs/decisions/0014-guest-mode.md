# 0014 Guest mode: practise before sign-up (#210)

## Context
D25 / item 19: a new learner answers a question before any sign-up. The auth gate sent `/` and
`/play` to `/login`. Placement, progress, step settings and events are all keyed by `user_id`,
and `adopt_learner_data` already moves those rows to a new id.

## Options
| Option | Pros | Cons | Score | Cost to switch |
|---|---|---|---|---|
| A. Guest learner row (`gst_` + random id, no name/email) + the existing server-side session cookie | Every route, API and store call works unchanged; merge = `adopt_learner_data`; no schema change | Guest rows accumulate until purged | 9 | Low: one gate branch + `merge_guest` |
| B. Separate guest cookie + guest tables | Clear split from accounts | Duplicates progress/placement storage and every read path | 4 | High |
| C. Client-only state (localStorage), upload at sign-up | No server rows for guests | Placement/progress are server-side today; trusting client progress; no-JS flow breaks | 3 | High |

## Decision
A. The gate mints a guest learner + session on a cookie-less GET of `/` or `/play/*` (never on a
POST). `/author`, `/settings`, `/add-path` and the tools API need a non-guest account. On
`/login/verify`, `merge_guest` moves progress, attempts, sessions, events, placement detail and
`audio_on/writing_on` to the account, then deletes the guest's rows (no duplicate learner).
The first passed scored step returns `X-Offer-Registration: true` once; `GET /api/guest`
reports it for the UI (#227), `POST /api/guest/offer/dismiss` hides it. Built: no library
fits; it reuses sessions and `adopt_learner_data`.

## Verified checks
`tests/test_guest_mode.py`: GET `/` -> 200 as guest, no PII; preference stored; offer once and
dismiss; sign-up keeps progress + preference, guest row gone; returning login merges without
overwriting; two guests never see each other's data; guests get 303 on `/author`,
`/settings`, `/add-path` and no tools principal. Full core suite green.

## Known limits
- Offer/dismiss state is in memory (lost on restart -> may be offered again once).
- No purge job yet for never-registered guests; retention must follow the #209 notice.
- Guest locale comes from the locale cookie at creation; UI half (prompt, settings) is #227.

## How to switch
To B/C: replace `create_guest`/`merge_guest` and the guest branch in `_auth_gate`; routes keep
reading `_learner()`.
