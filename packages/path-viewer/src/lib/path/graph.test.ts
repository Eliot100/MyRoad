import assert from "node:assert/strict";
import test from "node:test";

import { explainNext, layoutBlocks, nextBlockId, readingOrder, trailStages } from "./graph.ts";
import { blankProgress, LINEAR, LINEAR_PROGRESS, QUADRATIC, QUADRATIC_PROGRESS } from "./sample.ts";
import { progressFor } from "./graph.ts";

const ids = QUADRATIC.blocks.map((block) => block.blockId);
const intro = "blk_qeq_intro_001";
const disc = "blk_qeq_disc_002";
const assess = "blk_qeq_assess_005";
const experience = "blk_qeq_experience_006";
const remediation = "blk_qeq_remediation_007";

test("the quadratic path sends a failed check down its own branch", () => {
  const next = explainNext(ids, QUADRATIC.edges, QUADRATIC_PROGRESS);
  assert.equal(next.id, remediation);
  assert.equal(next.reason, "branch");
});

test("mastering the branch returns to the check, not the word problem", () => {
  const progress = {
    ...QUADRATIC_PROGRESS,
    [remediation]: progressFor("passed", "remediation_practice_met"),
  };
  const next = explainNext(ids, QUADRATIC.edges, progress);
  assert.equal(next.id, assess);
  assert.equal(next.reason, "retry");
});

test("passing the check opens the word problem", () => {
  const progress = {
    ...QUADRATIC_PROGRESS,
    [assess]: progressFor("passed", "assessment_passed"),
    [remediation]: progressFor("passed", "remediation_practice_met"),
  };
  assert.equal(nextBlockId(ids, QUADRATIC.edges, progress), experience);
});

test("a fresh path starts at the first block, not the branch", () => {
  const next = explainNext(ids, QUADRATIC.edges, blankProgress(ids));
  assert.equal(next.id, intro);
  assert.equal(next.reason, "start");
});

test("the optional edge does not skip the discriminant", () => {
  const progress = blankProgress(ids);
  progress[intro] = progressFor("passed");
  assert.equal(nextBlockId(ids, QUADRATIC.edges, progress), disc);
});

test("a path with no fail branch recommends its own open block", () => {
  const linearIds = LINEAR.blocks.map((block) => block.blockId);
  const next = explainNext(linearIds, LINEAR.edges, LINEAR_PROGRESS);
  assert.equal(next.id, "blk_lin_practice_002");
  assert.equal(next.reason, "open");
});

test("the quadratic remediation is a spur beside the check, not its own stage", () => {
  const stages = trailStages(ids, QUADRATIC.edges);
  const spur = stages.find((stage) => stage.spurId === remediation);
  assert.ok(spur);
  assert.ok(spur.stops.includes(assess));
  assert.equal(
    stages.some((stage) => stage.stops.includes(experience) && stage.spurId),
    false,
  );
});

test("a path with no branch has no spur", () => {
  const linearIds = LINEAR.blocks.map((block) => block.blockId);
  const stages = trailStages(linearIds, LINEAR.edges);
  assert.equal(stages.every((stage) => stage.spurId === null), true);
  assert.equal(stages.flatMap((stage) => stage.stops).length, linearIds.length);
});

test("reading order keeps the branch beside the check", () => {
  assert.deepEqual(readingOrder(ids, QUADRATIC.edges), [
    intro,
    disc,
    "blk_qeq_formula_003",
    "blk_qeq_practice_004",
    assess,
    remediation,
    experience,
  ]);
});

test("the branch sits under the check", () => {
  const points = layoutBlocks(ids, QUADRATIC.edges, false);
  const check = points[assess];
  const extra = points[remediation];
  assert.ok(check && extra);
  assert.equal(extra.x, check.x);
  assert.ok(extra.y > check.y);
  assert.ok((points[experience]?.x ?? 0) > check.x);
});
