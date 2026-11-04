import { useEffect, useState } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type NodeState = {
  correct: number;
  missed: number;
  masteredAt?: number;
  reviewAt?: number;
};

export type ForgeEntry = {
  at: number;
  findings: number;
  pulled: number;
  summary: string;
};

type ProgressState = {
  nodes: Record<string, NodeState>;
  lastId: string | null;
  forge: ForgeEntry[];
  setLast: (id: string) => void;
  record: (id: string, ok: boolean) => void;
  master: (id: string) => void;
  pullDue: () => number;
  logForge: (entry: ForgeEntry) => void;
  reset: () => void;
};

const blank = (): NodeState => ({ correct: 0, missed: 0 });
const DAY = 86_400_000;

export const useProgress = create<ProgressState>()(
  persist(
    (set, get) => ({
      nodes: {},
      lastId: null,
      forge: [],
      setLast: (id) => set({ lastId: id }),
      record: (id, ok) => {
        const prev = get().nodes[id] ?? blank();
        set({
          nodes: {
            ...get().nodes,
            [id]: {
              ...prev,
              correct: prev.correct + (ok ? 1 : 0),
              missed: prev.missed + (ok ? 0 : 1),
            },
          },
        });
      },
      master: (id) => {
        const prev = get().nodes[id] ?? blank();
        const now = Date.now();
        const soon = prev.missed > prev.correct;
        set({
          lastId: id,
          nodes: {
            ...get().nodes,
            [id]: {
              ...prev,
              masteredAt: now,
              reviewAt: now + (soon ? DAY : 3 * DAY),
            },
          },
        });
      },
      pullDue: () => {
        const now = Date.now();
        const nodes = { ...get().nodes };
        let pulled = 0;
        for (const [id, node] of Object.entries(nodes)) {
          if (node.masteredAt && node.missed > node.correct && (node.reviewAt ?? 0) > now) {
            nodes[id] = { ...node, reviewAt: now };
            pulled += 1;
          }
        }
        if (pulled) set({ nodes });
        return pulled;
      },
      logForge: (entry) => set({ forge: [entry, ...get().forge].slice(0, 12) }),
      reset: () => set({ nodes: {}, lastId: null, forge: [] }),
    }),
    { name: "myroad.v1", skipHydration: true },
  ),
);

export function useHydrated() {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const unsub = useProgress.persist.onFinishHydration(() => setReady(true));
    if (useProgress.persist.hasHydrated()) setReady(true);
    else void useProgress.persist.rehydrate();
    return unsub;
  }, []);
  return ready;
}
