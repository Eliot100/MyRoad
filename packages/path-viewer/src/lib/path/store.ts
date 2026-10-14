import { create } from "zustand";
import { persist } from "zustand/middleware";

import { failSignal, isBranchEdge, layoutBlocks, moveAlongSpine, passSignal } from "@/lib/path/graph";
import { getPathVersion, getProgress, LEARNER_ID, listPaths } from "@/lib/path/path-store";
import { QUADRATIC } from "@/lib/path/sample";
import type { EdgeRelationship, Locale, MasteryState, PathBlock, PathEdge, PathStatus, ProgressMap } from "@/lib/path/types";

export type LocalMetrics = {
  sessions: number;
  settingsOpens: number;
  mapOpens: number;
  listOpens: number;
  timeToNextMs: number | null;
  recoveredChecks: number;
  returnsAfterBranch: number;
};

const emptyMetrics = (): LocalMetrics => ({
  sessions: 0,
  settingsOpens: 0,
  mapOpens: 0,
  listOpens: 0,
  timeToNextMs: null,
  recoveredChecks: 0,
  returnsAfterBranch: 0,
});

export type EditorMode = "view" | "draft";

const RELATIONSHIPS: EdgeRelationship[] = ["sequence", "prerequisite", "optional", "branch"];

type PathState = {
  learnerId: string;
  locale: Locale;
  mode: EditorMode;
  pathId: string;
  versionId: string;
  version: number;
  status: PathStatus;
  title: PathStateTitle;
  description: PathStateTitle;
  blocks: PathBlock[];
  edges: PathEdge[];
  positions: Record<string, { x: number; y: number }> | null;
  progressByPath: Record<string, ProgressMap>;
  progress: ProgressMap;
  selectedBlockId: string | null;
  selectedEdgeId: string | null;
  metrics: LocalMetrics;
  setLocale: (locale: Locale) => void;
  setMode: (mode: EditorMode) => void;
  openPath: (pathId: string) => void;
  selectBlock: (id: string | null) => void;
  selectEdge: (id: string | null) => void;
  setMastery: (id: string, state: MasteryState) => void;
  restoreSample: () => void;
  startOver: () => void;
  addEdge: (from: string, to: string) => void;
  removeEdge: (id: string) => void;
  cycleRelationship: (id: string) => void;
  moveBlock: (id: string, direction: -1 | 1) => void;
  setPosition: (id: string, point: { x: number; y: number }) => void;
  tidy: () => void;
  resetDraft: () => void;
  noteSession: () => void;
  noteSettings: () => void;
  notePresentation: (presentation: "map" | "list") => void;
  noteTimeToNext: (ms: number) => void;
};

type PathStateTitle = { he: string; en: string; ar: string };

function applyPath(pathId: string, progressByPath: Record<string, ProgressMap>) {
  const path = getPathVersion(pathId);
  const progress = progressByPath[pathId] ?? getProgress(pathId);
  return {
    pathId: path.pathId,
    versionId: path.versionId,
    version: path.version,
    status: path.status,
    title: path.name,
    description: path.description,
    blocks: path.blocks,
    edges: path.edges.map((edge) => ({ ...edge, condition: edge.condition ? { ...edge.condition } : null })),
    progress,
    progressByPath: { ...progressByPath, [pathId]: progress },
    positions: null as Record<string, { x: number; y: number }> | null,
    selectedBlockId: null as string | null,
    selectedEdgeId: null as string | null,
    mode: "view" as EditorMode,
  };
}

function initialProgress(): Record<string, ProgressMap> {
  return Object.fromEntries(listPaths().map((path) => [path.pathId, getProgress(path.pathId)]));
}

const opening = applyPath(QUADRATIC.pathId, initialProgress());

export const usePathStore = create<PathState>()(
  persist(
    (set, get) => ({
      learnerId: LEARNER_ID,
      locale: "he",
      metrics: emptyMetrics(),
      ...opening,
      setLocale: (locale) => set({ locale, positions: null }),
      setMode: (mode) => set({ mode: get().status === "draft" ? mode : "view" }),
      openPath: (pathId) => {
        const current = get();
        const saved = { ...current.progressByPath, [current.pathId]: current.progress };
        set(applyPath(pathId, saved));
      },
      selectBlock: (id) => set({ selectedBlockId: id, selectedEdgeId: null }),
      selectEdge: (id) => set({ selectedEdgeId: id, selectedBlockId: id ? null : get().selectedBlockId }),
      setMastery: (id, state) => {
        const edges = get().edges;
        const previous = get().progress[id];
        const progress = { ...get().progress };
        const metrics = { ...get().metrics };
        if (state === "mastered") progress[id] = { masteryResult: "passed", signal: passSignal(id, edges) };
        else if (state === "needs_remediation") progress[id] = { masteryResult: "failed", signal: failSignal(id, edges) };
        else if (state === "in_progress") progress[id] = { masteryResult: "incomplete", signal: null };
        else progress[id] = { masteryResult: "not_started", signal: null };
        if (state === "mastered" && previous?.masteryResult === "failed" && failSignal(id, edges)) {
          metrics.recoveredChecks += 1;
        }
        if (state === "mastered" && edges.some((edge) => isBranchEdge(edge) && edge.to === id)) {
          metrics.returnsAfterBranch += 1;
        }
        set({
          progress,
          metrics,
          progressByPath: { ...get().progressByPath, [get().pathId]: progress },
        });
      },
      restoreSample: () => {
        const progress = getProgress(get().pathId);
        set({ progress, progressByPath: { ...get().progressByPath, [get().pathId]: progress } });
      },
      startOver: () => {
        const progress = Object.fromEntries(
          get().blocks.map((block) => [block.blockId, { masteryResult: "not_started" as const, signal: null }]),
        );
        set({ progress, progressByPath: { ...get().progressByPath, [get().pathId]: progress } });
      },
      addEdge: (from, to) => {
        if (get().status !== "draft" || get().mode !== "draft") return;
        if (!from || !to || from === to) return;
        if (get().edges.some((edge) => edge.from === from && edge.to === to)) return;
        const edgeId = `e_${from}_${to}_${Math.random().toString(36).slice(2, 7)}`;
        set({
          edges: [...get().edges, { edgeId, from, to, relationship: "sequence", condition: null }],
          selectedEdgeId: edgeId,
          selectedBlockId: null,
          positions: null,
        });
      },
      removeEdge: (id) => {
        if (get().status !== "draft" || get().mode !== "draft") return;
        set({
          edges: get().edges.filter((edge) => edge.edgeId !== id),
          selectedEdgeId: get().selectedEdgeId === id ? null : get().selectedEdgeId,
          positions: null,
        });
      },
      cycleRelationship: (id) => {
        if (get().status !== "draft" || get().mode !== "draft") return;
        set({
          edges: get().edges.map((edge) => {
            if (edge.edgeId !== id) return edge;
            const index = RELATIONSHIPS.indexOf(edge.relationship);
            const relationship = RELATIONSHIPS[(index + 1) % RELATIONSHIPS.length] ?? "sequence";
            return { ...edge, relationship };
          }),
        });
      },
      moveBlock: (id, direction) => {
        if (get().status !== "draft" || get().mode !== "draft") return;
        const next = moveAlongSpine(
          get().blocks.map((block) => block.blockId),
          get().edges,
          id,
          direction,
        );
        if (!next) return;
        set({ edges: next, positions: null });
      },
      setPosition: (id, point) => {
        const state = get();
        const base =
          state.positions ??
          layoutBlocks(
            state.blocks.map((block) => block.blockId),
            state.edges,
            state.locale !== "en",
          );
        set({ positions: { ...base, [id]: point } });
      },
      tidy: () => set({ positions: null }),
      resetDraft: () => {
        const path = getPathVersion(get().pathId);
        set({
          blocks: path.blocks,
          edges: path.edges.map((edge) => ({ ...edge, condition: edge.condition ? { ...edge.condition } : null })),
          positions: null,
          status: path.status,
          mode: "view",
          selectedEdgeId: null,
        });
      },
      noteSession: () => set({ metrics: { ...get().metrics, sessions: get().metrics.sessions + 1 } }),
      noteSettings: () => set({ metrics: { ...get().metrics, settingsOpens: get().metrics.settingsOpens + 1 } }),
      notePresentation: (presentation) =>
        set({
          metrics: {
            ...get().metrics,
            mapOpens: get().metrics.mapOpens + (presentation === "map" ? 1 : 0),
            listOpens: get().metrics.listOpens + (presentation === "list" ? 1 : 0),
          },
        }),
      noteTimeToNext: (ms) => set({ metrics: { ...get().metrics, timeToNextMs: ms } }),
    }),
    {
      name: "myroad-path-store",
      skipHydration: true,
      partialize: (state) => ({
        learnerId: state.learnerId,
        locale: state.locale,
        mode: state.mode,
        pathId: state.pathId,
        edges: state.edges,
        positions: state.positions,
        progressByPath: state.progressByPath,
        progress: state.progress,
        metrics: state.metrics,
      }),
      onRehydrateStorage: () => (state) => {
        if (!state?.pathId) return;
        const saved = { ...state.progressByPath, [state.pathId]: state.progress };
        const applied = applyPath(state.pathId, saved);
        const known = new Set(applied.blocks.map((block) => block.blockId));
        const edgesFit = state.edges.every((edge) => known.has(edge.from) && known.has(edge.to) && edge.relationship);
        usePathStore.setState({
          ...applied,
          locale: state.locale,
          learnerId: state.learnerId || LEARNER_ID,
          mode: applied.status === "draft" ? state.mode : "view",
          edges: edgesFit ? state.edges : applied.edges,
          positions: edgesFit ? state.positions : null,
          progress: saved[state.pathId] ?? applied.progress,
          progressByPath: saved,
          metrics: state.metrics ?? emptyMetrics(),
        });
      },
    },
  ),
);
