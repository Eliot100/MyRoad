# Path graph viewer

The preview opens a PathStore `PathVersion`, not a private viewer schema.

- Block types are `explanation`, `practice`, `assessment`, and `experience`.
- Edges are `{ edgeId, from, to, relationship, condition }`.
- `relationship` is `sequence`, `prerequisite`, `optional`, or `branch`.
- `condition.mastery` is a token written on that path. The quadratic check uses `assessment_failed` and `assessment_passed`. The linear path has neither.

## Two paths, one learner

The sample learner failed the quadratic check, so the next step is the remediation branch that path authored. The same learner, on the linear path, is mid-practice. That path has no fail branch, so the next step is the open practice block.

The learner view is a vertical trail. Blocks are grouped into short stages. A branch, such as the quadratic remediation, is a spur off the check rather than a second column. The node graph is only for draft editing.

Locale, path, view or editing, and map or list sit behind the settings icon. Quality counts in that menu are local to this device and this learner.


## What is stored

Progress is kept per path for `learner_sample`, in the shape PathStore already uses: a mastery result and the condition token that result satisfies. Draft edge edits stay on this device. A later slice can post the same `getPathVersion` / `getProgress` calls to FastAPI.

## Tests

Graph rules stay in `src/lib/path/graph.test.ts` (node:test). Component and store checks are in `src/components/path/view.test.tsx`, `src/lib/path/store.test.ts`, and `src/lib/path/i18n.test.ts`. Run them with `node scripts/run-path-tests.mjs` from the preview app. They cover the trail, the quiet settings menu, list, detail, the draft canvas, and the local quality counts.
