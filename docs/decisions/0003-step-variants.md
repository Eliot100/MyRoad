# 0003 Step variants (`variant_of`), Arabic subject, placement routing

Date: 2026-10-31. Context: MyRoad-content PR #16 lists each tile up to 4 times
(`<base>__a1w0|a0w0|a1w1|a0w1`), so a learner saw duplicate tiles.

## Options
1. **Variant steps in the path JSON, picked at runtime** (chosen). Optional `variant_of`
   + `variant_when {audio, writing}` on a step. + Additive, old content unchanged, settings can
   change any time without losing progress. - Every doc read in the learner UI must go through
   `select_variants`.
2. **One step with per-setting sub-fields** (`body_by_setting`). + One node. - Big schema change,
   content scripts rewritten, every renderer changes.
3. **Separate paths per setting.** + No code. - 4x paths, progress split, catalog clutter.

## Choice
Option 1. Fields on a content step (`packages/core/src/myroad_core/content/schema.py`):
- `variant_of: str | null`: id of the base step in the same path. The base must exist and must not
  itself be a variant (no chains, no cycles). Requires `variant_when`.
- `variant_when: {audio: bool|null, writing: bool|null}`: null = any.
`content/variants.py::select_variants` keeps one block per base: the most specific matching
variant, else the base. The chosen variant takes the base blockId, so mastery, step events and
progress count toward the base.

Learner settings: new `learners.audio_on` (default 1) and `learners.writing_on` (default 0);
`GET/POST /api/settings/steps` (`X-MyRoad-Request: 1`). Defaults = PR #16's base `__a1w0`.

Subject: `arabic` added to `SubjectId` and `SUBJECTS` (labels he/en/ar).

Placement routing: optional path field `placement_route {from_placement, band_min, band_max}`
(stored as `placementRoute` on the version). `POST /api/placement/result` accepts an optional
`placementId`; for a non-English placement, `recommended_road_id` is the first published path whose
route covers the band (band from the #152 `placement_band`: 1, 3 or 5). English is unchanged.
The freeze/v0 JSON and the `validate-freeze-json` job hold no step schema (blocks allow extra
keys), so they were not changed.

## How to switch
To drop variants: remove `variant_of`/`variant_when` from content; `select_variants` is a no-op for
docs without them. To move to option 2: generate the per-setting fields from the variant nodes
(same grouping key `variant_of`) and delete `content/variants.py`.
