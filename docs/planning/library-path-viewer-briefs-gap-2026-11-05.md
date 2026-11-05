# Library path-viewer briefs gap (2026-11-05)

Sources:
- `49-Pasted_Text-….txt`, `50-Pasted_Text-….txt`, `108-Pasted_Text-….txt` —
  React Flow path graph viewer + draft editor briefs (paper/ink/pine/stone).
- `51-grok-build-path-viewer-tests.md` — missing component tests brief.

## What landed on this branch (pass 3)

- `packages/path-viewer` already held trail/shell/graph sources.
- Added `i18n.test.ts`, `store.test.ts`, `view.test.tsx`,
  `scripts/run-path-tests.mjs`, local `package.json` / lockfile, and
  `npm test` scripts. Graph + path suites green.
- Fixed `noteSettings()` so it is not called inside a `setState` updater
  (brief 51).

## Still open / not done here

- Full “preview app” wiring (index.html host) stays on `feat/path-viewer-trail`
  / local trail worktree; this picks branch only makes the package testable.
- Briefs 49/50 ask for FastAPI progress endpoints and richer draft editing —
  path-viewer README still says it is not wired to FastAPI. No new backend
  on this pass.
- Palette in path-viewer (paper/pine) differs from the Jinja adult learner
  dark/teal road. Both exist on purpose for now; unifying is a product call.

## Images linked to this thread

- `59`, `60`: local WSL setup pain (python/uvicorn/venv) while on
  `feat/path-viewer-trail` — env notes only.
- `62`: early Grok Build focus list (thin learner UI, golden loop; no video/3D).
- `63`: early light paper/pine step player mock — historical; do not regress
  current Jinja dark road to this.
