import assert from "node:assert/strict";
import { act, type ReactNode } from "react";
import { createRoot } from "react-dom/client";

import { BlockNodeView } from "./block-node.tsx";
import { DetailPanel } from "./detail-panel.tsx";
import { PathList } from "./path-list.tsx";
import { PathTrail } from "./path-trail.tsx";
import { PathShell } from "./shell.tsx";
import { RichText } from "./rich-text.tsx";
import { ReactFlowProvider } from "@xyflow/react";
import { LINEAR, QUADRATIC } from "@/lib/path/sample.ts";
import { usePathStore } from "@/lib/path/store.ts";

const emptyMetrics = {
  sessions: 0,
  settingsOpens: 0,
  mapOpens: 0,
  listOpens: 0,
  timeToNextMs: null,
  recoveredChecks: 0,
  returnsAfterBranch: 0,
};

function reset(pathId = QUADRATIC.pathId) {
  usePathStore.getState().openPath(pathId);
  usePathStore.getState().restoreSample();
  usePathStore.getState().setLocale("he");
  usePathStore.setState({
    mode: "view",
    selectedBlockId: null,
    selectedEdgeId: null,
    metrics: { ...emptyMetrics },
  });
}

async function mount(node: ReactNode) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(node);
  });
  return {
    host,
    async unmount() {
      await act(async () => {
        root.unmount();
      });
      host.remove();
    },
    async click(element: Element | null) {
      assert.ok(element, "missing element to click");
      await act(async () => {
        (element as HTMLElement).click();
      });
    },
  };
}

export async function testTrailPutsTheRemediationOnASpur() {
  reset();
  const view = await mount(<PathTrail nextId="blk_qeq_remediation_007" />);
  try {
    const trail = view.host.querySelector("[data-testid=path-trail]");
    assert.ok(trail);
    assert.equal(trail.getAttribute("data-rtl") ?? view.host.querySelector("[data-rtl]")?.getAttribute("data-rtl"), "true");
    const stops = [...view.host.querySelectorAll("[data-testid=trail-stop]")];
    assert.equal(stops.length, 7);
    const spur = view.host.querySelector('[data-block-id="blk_qeq_remediation_007"]');
    assert.equal(spur?.getAttribute("data-spur"), "true");
    assert.equal(spur?.getAttribute("data-next"), "true");
    assert.match(spur?.textContent ?? "", /תרגול תיקון/);
    assert.equal(
      view.host.querySelector('[data-block-id="blk_qeq_experience_006"]')?.getAttribute("data-spur"),
      "false",
    );
    assert.ok(view.host.textContent?.includes("שלב"));
  } finally {
    await view.unmount();
  }
}

export async function testLinearTrailHasNoSpur() {
  reset(LINEAR.pathId);
  const view = await mount(<PathTrail nextId="blk_lin_practice_002" />);
  try {
    assert.equal(view.host.querySelector('[data-spur="true"]'), null);
    const next = view.host.querySelector('[data-next="true"]');
    assert.equal(next?.getAttribute("data-block-id"), "blk_lin_practice_002");
    assert.match(next?.textContent ?? "", /תרגול העברת אגפים/);
  } finally {
    await view.unmount();
  }
}

export async function testShellHidesControlsBehindSettings() {
  reset();
  const view = await mount(<PathShell />);
  try {
    const header = view.host.querySelector("header");
    assert.ok(header);
    assert.equal(header.querySelectorAll(".chip").length, 0);
    assert.equal(view.host.querySelector(".settings-pop"), null);
    assert.equal(view.host.querySelector("[data-testid=settings-button]")?.getAttribute("aria-label"), "הגדרות");
    assert.match(view.host.querySelector(".next-link")?.textContent ?? "", /תרגול תיקון/);
    assert.ok(view.host.querySelector("[data-testid=path-trail]"));
    assert.equal(view.host.querySelector(".react-flow"), null);

    await view.click(view.host.querySelector("[data-testid=settings-button]"));
    const pop = view.host.querySelector(".settings-pop");
    assert.ok(pop);
    assert.match(pop.textContent ?? "", /איכות/);
    assert.match(pop.textContent ?? "", /לא שימור אמיתי/);
    assert.match(pop.textContent ?? "", /משוואות לינאריות/);
    assert.ok(pop.querySelector(".chip"));
    assert.equal(usePathStore.getState().metrics.settingsOpens, 1);
  } finally {
    await view.unmount();
  }
}

export async function testSettingsSwitchesToTheLinearPath() {
  reset();
  const view = await mount(<PathShell />);
  try {
    await view.click(view.host.querySelector("[data-testid=settings-button]"));
    const linear = [...view.host.querySelectorAll("button")].find((button) =>
      button.textContent?.includes("משוואות לינאריות"),
    );
    await view.click(linear ?? null);
    assert.match(view.host.querySelector("[data-testid=path-title]")?.textContent ?? "", /משוואות לינאריות/);
    assert.match(view.host.querySelector(".next-link")?.textContent ?? "", /תרגול העברת אגפים/);
    assert.equal(view.host.querySelector('[data-spur="true"]'), null);
    assert.equal(view.host.querySelector(".settings-pop"), null);
  } finally {
    await view.unmount();
  }
}

export async function testListMarksTheSuggestedBlock() {
  reset();
  const view = await mount(<PathList />);
  try {
    const list = view.host.querySelector("[data-testid=path-list]");
    assert.ok(list);
    const next = view.host.querySelector('[data-next="true"]');
    assert.equal(next?.getAttribute("data-block-id"), "blk_qeq_remediation_007");
    assert.equal(view.host.querySelectorAll("[data-testid=list-block]").length, 7);
  } finally {
    await view.unmount();
  }
}

export async function testDetailCanMarkTheSpurMastered() {
  reset();
  const view = await mount(
    <>
      <PathShell />
      <DetailPanel />
    </>,
  );
  try {
    await view.click(view.host.querySelector(".next-link"));
    assert.match(view.host.querySelector("[data-testid=detail-title]")?.textContent ?? "", /תרגול תיקון/);
    const mastered = [...view.host.querySelectorAll("button")].find((button) => button.textContent === "זה נשלט");
    await view.click(mastered ?? null);
    assert.match(view.host.querySelector(".next-link")?.textContent ?? "", /הערכה קצרה/);
    assert.equal(usePathStore.getState().metrics.returnsAfterBranch, 1);
  } finally {
    await view.unmount();
  }
}

export async function testRichTextRendersEmphasisAndLists() {
  const view = await mount(<RichText text={"A **formula**.\n\n- first\n- second"} />);
  try {
    assert.equal(view.host.querySelector("strong")?.textContent, "formula");
    assert.equal(view.host.querySelectorAll("li").length, 2);
  } finally {
    await view.unmount();
  }
}

export async function testBlockNodeShowsNextAndRtl() {
  const view = await mount(
    <ReactFlowProvider>
      <BlockNodeView
      id="blk_qeq_assess_005"
      type="block"
      selected={false}
      dragging={false}
      zIndex={0}
      selectable
      deletable
      draggable
      isConnectable
      positionAbsoluteX={0}
      positionAbsoluteY={0}
      data={{
        title: "הערכה קצרה",
        typeLabel: "הערכה",
        stateLabel: "צריך חיזוק",
        state: "needs_remediation",
        isNext: true,
        draft: false,
        rtl: true,
        nextLabel: "הבא",
      }}
    />
    </ReactFlowProvider>,
  );
  try {
    const node = view.host.querySelector("[data-testid=block-node]");
    assert.equal(node?.getAttribute("data-rtl"), "true");
    assert.equal(node?.getAttribute("data-next"), "true");
    assert.equal(node?.getAttribute("data-state"), "needs_remediation");
    assert.match(node?.textContent ?? "", /הערכה קצרה/);
    assert.match(node?.textContent ?? "", /הבא/);
  } finally {
    await view.unmount();
  }
}

export async function testDraftModeReplacesTheTrail() {
  reset();
  usePathStore.getState().setMode("draft");
  const view = await mount(<PathShell />);
  try {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 80));
    });
    assert.match(view.host.textContent ?? "", /גוררים מנקודה/);
    assert.equal(view.host.querySelector("[data-testid=path-trail]"), null);
    assert.ok(view.host.querySelector(".react-flow"));
  } finally {
    usePathStore.getState().setMode("view");
    await view.unmount();
  }
}
