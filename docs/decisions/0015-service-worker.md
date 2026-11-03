# 0015 Service worker: precache shell, offline page, never cache personal data (#234)

## Context
D27 (PWA). FastAPI + htmx, plain `ui/static`, no Node or bundler. Signed-in HTML, `/api`,
`/tools`, `/login*` must never sit in Cache Storage (shared devices, logout, privacy).

## Options
| Option | Pros | Cons | Score | Cost to switch |
|---|---|---|---|---|
| A. Hand-written SW (~60 lines), served by `/sw.js` with a content-hash cache name | No new deps or build step; whole policy readable in one file; only precache writes the cache | We own the code (update/cleanup logic) | 9 | Low |
| B. Workbox (workbox-cli/-build, pinned) | Maintained, well-known strategies | Adds Node + a build step to CI/Docker for 3 rules; runtime-caching config is easy to widen by mistake | 6 | Low: same routes, swap the file |
| C. vite-plugin-pwa | Full PWA tooling | Needs Vite; we have no bundler | 2 | High |

## Decision
A. Built: Workbox would add a Node build for three rules. `ui/pwa.py` renders `static/sw.template.js` with
`CACHE = myroad-shell-<sha256 of shell files + offline page>`. Install precaches `/static`
CSS/JS/woff2 (incl. htmx) + `/offline` (credentials omitted, refuses private/no-store).
Navigations are network-only, with the cached `/offline` as fallback. `/static` assets are
served cache-first. Every other request is untouched, and no runtime response is ever stored.
Activate deletes other `myroad-shell-*` caches. `/offline` holds he/en/ar sections, and `offline.js`
shows the one for the `myroad_locale` cookie and sets lang/dir (rtl for he/ar).

## Verified checks
`tests/test_service_worker.py` (core-tests): SW public, root scope, `no-cache`, versioned;
precache only `/static` + `/offline`; single `cache.put` in install; offline page 3 locales + dir.
`tests_a11y/test_service_worker_offline.py` (Chromium, a11y job): offline navigation -> offline
page in he/en/ar with the right dir; after sign-in + `/`, `/settings`, `/api` the caches hold
only shell URLs and offline `/settings` shows no personal data; an old `myroad-shell-*` cache is
deleted on activate, others stay; plain-http LAN host / blocked SW: no errors; kill switch
leaves 0 registrations and 0 caches.

Kill switch: `MYROAD_SW_KILL=1` makes `/sw.js` a worker that deletes all caches and
unregisters itself on each browser's next visit (ops: packages/core/README.md).

## Known limits
- SW needs HTTPS or localhost; plain-http hosts (today's LAN setup) skip it cleanly.
- No icons/manifest yet (UI issue); offline answers: #235.

## How to switch
To Workbox: generate `sw.js` with workbox-build from the same precache list, keep `/sw.js`,
`/offline` and the tests; delete `sw.template.js`.
