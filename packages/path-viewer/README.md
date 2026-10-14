# path-viewer

Learner view of a MyRoad path. This is the lift of the preview trail into the monorepo. It is not wired to FastAPI.

It reads the same PathStore shapes as `packages/core`. Do not rename those fields.

- Block types: `explanation`, `practice`, `assessment`, `experience`.
- Edges: `{ edgeId, from, to, relationship, condition }`.
- `relationship`: `sequence`, `prerequisite`, `optional`, or `branch`.

Next-best (`explainNext` in `src/lib/path/graph.ts`) walks this path's edges and this learner's progress. The quadratic sample and the linear sample do not share one rule.

## Layout

- `src/components/path` — quiet header, settings, vertical trail, list, detail, draft canvas.
- `src/lib/path` — types, the two sample paths, on-device progress, next-best.
- `src/styles/path.css` — paper, ink, pine, and stone classes the trail uses.
- `docs/path-viewer.md` — the contract the preview follows.

The default view is the trail. The React Flow canvas loads only after settings, then editing. Locale, path, view or editing, and map or list stay in that popover. Quality counts there are local numbers for this learner, not retention.

Imports use the `@/` alias aimed at `src/`. Peer pieces the preview already has: React, Zustand, and `@xyflow/react` (draft editing only).

## Tests

- `src/lib/path/graph.test.ts` — next-best and trail grouping (node:test).
- `src/lib/path/store.test.ts` — mastery, recovered checks, path switch, local quality counts.
- `src/lib/path/i18n.test.ts` — he / en / ar copy and direction.
- `src/components/path/view.test.tsx` — trail, settings, list, detail, draft canvas, block node.
- `scripts/run-path-tests.mjs` — runner used by the preview app (`node scripts/run-path-tests.mjs`).

These are the viewer checks. They do not call FastAPI.
