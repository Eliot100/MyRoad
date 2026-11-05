import assert from "node:assert/strict";

import { explainNext } from "./graph.ts";
import { LINEAR, QUADRATIC } from "./sample.ts";
import { usePathStore } from "./store.ts";

const emptyMetrics = {
  sessions: 0,
  settingsOpens: 0,
  mapOpens: 0,
  listOpens: 0,
  timeToNextMs: null,
  recoveredChecks: 0,
  returnsAfterBranch: 0,
};

function reset() {
  usePathStore.getState().openPath(QUADRATIC.pathId);
  usePathStore.getState().restoreSample();
  usePathStore.getState().setLocale("he");
  usePathStore.setState({
    mode: "view",
    selectedBlockId: null,
    selectedEdgeId: null,
    metrics: { ...emptyMetrics },
  });
}

export function testMasteringTheSpurReturnsToTheCheck() {
  reset();
  usePathStore.getState().setMastery("blk_qeq_remediation_007", "mastered");
  const state = usePathStore.getState();
  assert.equal(state.metrics.returnsAfterBranch, 1);
  assert.equal(state.metrics.recoveredChecks, 0);
  const next = explainNext(
    state.blocks.map((block) => block.blockId),
    state.edges,
    state.progress,
  );
  assert.equal(next.id, "blk_qeq_assess_005");
  assert.equal(next.reason, "retry");
}

export function testMasteringAFailedCheckCountsAsRecovered() {
  reset();
  usePathStore.getState().setMastery("blk_qeq_assess_005", "mastered");
  assert.equal(usePathStore.getState().metrics.recoveredChecks, 1);
}

export function testSwitchingPathsKeepsEachLearnersRecord() {
  reset();
  usePathStore.getState().setMastery("blk_qeq_remediation_007", "mastered");
  usePathStore.getState().openPath(LINEAR.pathId);
  const state = usePathStore.getState();
  assert.equal(state.pathId, LINEAR.pathId);
  assert.equal(state.mode, "view");
  assert.equal(state.progress.blk_lin_practice_002.masteryResult, "incomplete");
  assert.equal(
    state.progressByPath[QUADRATIC.pathId].blk_qeq_remediation_007.masteryResult,
    "passed",
  );
  const next = explainNext(
    state.blocks.map((block) => block.blockId),
    state.edges,
    state.progress,
  );
  assert.equal(next.id, "blk_lin_practice_002");
  assert.equal(next.reason, "open");
}

export function testQualityCountsStayLocal() {
  reset();
  usePathStore.getState().noteSession();
  usePathStore.getState().noteSettings();
  usePathStore.getState().notePresentation("list");
  usePathStore.getState().noteTimeToNext(180);
  const metrics = usePathStore.getState().metrics;
  assert.equal(metrics.sessions, 1);
  assert.equal(metrics.settingsOpens, 1);
  assert.equal(metrics.listOpens, 1);
  assert.equal(metrics.mapOpens, 0);
  assert.equal(metrics.timeToNextMs, 180);
}
