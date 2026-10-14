import type { BlockProgress, EdgeRelationship, PathEdge, ProgressMap } from "./types.ts";

export type EdgeLike = {
  from: string;
  to: string;
  relationship: EdgeRelationship;
  condition?: { mastery?: string } | null;
};

export type NextReason = "branch" | "retry" | "open" | "start" | "done";

export function isBranchEdge(edge: EdgeLike): boolean {
  return edge.relationship === "branch";
}

/** The edge that walks back from a branch onto the block that opened it. */
export function isReturnEdge(edge: EdgeLike, edges: EdgeLike[]): boolean {
  return edges.some((other) => isBranchEdge(other) && other.from === edge.to && other.to === edge.from);
}

/** Pass token this path wrote on a forward edge out of the block. */
export function passSignal(blockId: string, edges: EdgeLike[]): string | null {
  const edge = edges.find(
    (item) =>
      item.from === blockId &&
      item.relationship !== "branch" &&
      item.relationship !== "optional" &&
      item.condition?.mastery,
  );
  return edge?.condition?.mastery ?? null;
}

/** Fail token this path wrote on a branch out of the block. */
export function failSignal(blockId: string, edges: EdgeLike[]): string | null {
  const edge = edges.find((item) => item.from === blockId && isBranchEdge(item) && item.condition?.mastery);
  return edge?.condition?.mastery ?? null;
}

function gateMet(edge: EdgeLike, progress: ProgressMap): boolean {
  const from = progress[edge.from];
  if (!from) return false;
  if (edge.condition?.mastery) return from.signal === edge.condition.mastery;
  return from.masteryResult === "passed";
}

/** Edges that do not point backward into a node already on the stack. */
export function forwardEdges<T extends EdgeLike>(ids: string[], edges: T[]): T[] {
  const adj = new Map<string, T[]>(ids.map((id) => [id, []]));
  for (const edge of edges) adj.get(edge.from)?.push(edge);
  const color = new Map<string, number>(ids.map((id) => [id, 0]));
  const kept: T[] = [];

  function visit(id: string) {
    color.set(id, 1);
    for (const edge of adj.get(id) ?? []) {
      const mark = color.get(edge.to) ?? 0;
      if (mark === 1) continue;
      kept.push(edge);
      if (mark === 0) visit(edge.to);
    }
    color.set(id, 2);
  }

  for (const id of ids) {
    if ((color.get(id) ?? 0) === 0) visit(id);
  }
  return kept;
}

export function topoOrder(ids: string[], edges: EdgeLike[]): string[] {
  const forward = forwardEdges(ids, edges);
  const indeg = new Map<string, number>(ids.map((id) => [id, 0]));
  const adj = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const edge of forward) {
    adj.get(edge.from)?.push(edge.to);
    indeg.set(edge.to, (indeg.get(edge.to) ?? 0) + 1);
  }
  const queue = ids.filter((id) => (indeg.get(id) ?? 0) === 0);
  const order: string[] = [];
  const seen = new Set<string>();
  while (queue.length > 0) {
    const id = queue.shift();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    order.push(id);
    for (const next of adj.get(id) ?? []) {
      indeg.set(next, (indeg.get(next) ?? 1) - 1);
      if ((indeg.get(next) ?? 0) === 0) queue.push(next);
    }
  }
  for (const id of ids) {
    if (!seen.has(id)) order.push(id);
  }
  return order;
}

function branchTargets(edges: EdgeLike[]): Set<string> {
  return new Set(edges.filter(isBranchEdge).map((edge) => edge.to));
}

/** Spine first. A branch target is inserted just after the block that opens it. */
export function readingOrder(ids: string[], edges: EdgeLike[]): string[] {
  const side = branchTargets(edges);
  const mainIds = ids.filter((id) => !side.has(id));
  const mainEdges = edges.filter((edge) => !isBranchEdge(edge) && !side.has(edge.from));
  const main = topoOrder(mainIds, mainEdges);
  const order: string[] = [];
  for (const id of main) {
    order.push(id);
    for (const edge of edges) {
      if (isBranchEdge(edge) && edge.from === id && !order.includes(edge.to)) order.push(edge.to);
    }
  }
  for (const id of ids) {
    if (!order.includes(id)) order.push(id);
  }
  return order;
}

export type TrailStage = {
  stops: string[];
  spurId: string | null;
};

/** Short runs along the spine. A branch target is a spur on the stage that opens it, not its own column. */
export function trailStages(ids: string[], edges: EdgeLike[]): TrailStage[] {
  const order = readingOrder(ids, edges);
  const side = branchTargets(edges);
  const stages: TrailStage[] = [];
  let stops: string[] = [];
  let spurId: string | null = null;

  function flush() {
    if (stops.length === 0 && !spurId) return;
    stages.push({ stops, spurId });
    stops = [];
    spurId = null;
  }

  for (const id of order) {
    if (side.has(id)) {
      spurId = id;
      flush();
      continue;
    }
    if (stops.length >= 3) flush();
    stops.push(id);
  }
  flush();
  return stages;
}

function isOpen(id: string, edges: EdgeLike[], progress: ProgressMap): boolean {
  const incoming = edges.filter((edge) => edge.to === id && edge.relationship !== "optional");
  const gates = incoming.filter((edge) => !isReturnEdge(edge, edges));
  const branches = gates.filter(isBranchEdge);
  const required = gates.filter((edge) => !isBranchEdge(edge));
  if (required.length === 0 && branches.length > 0) return branches.some((edge) => gateMet(edge, progress));
  if (required.length === 0) return true;
  return required.every((edge) => gateMet(edge, progress));
}

/**
 * Next block for this learner on this path.
 * Branch and retry follow the path's own condition tokens.
 * A different path, with different edges, recommends a different step.
 */
export function explainNext(
  ids: string[],
  edges: EdgeLike[],
  progress: ProgressMap,
): { id: string | null; reason: NextReason } {
  const order = readingOrder(ids, edges);
  for (const id of order) {
    const signal = progress[id]?.signal;
    if (!signal) continue;
    const branch = edges.find((edge) => edge.from === id && isBranchEdge(edge) && edge.condition?.mastery === signal);
    if (!branch) continue;
    if (progress[branch.to]?.masteryResult !== "passed") return { id: branch.to, reason: "branch" };
    if (progress[id]?.masteryResult !== "passed") return { id, reason: "retry" };
  }

  const ready = order.filter((id) => progress[id]?.masteryResult !== "passed" && isOpen(id, edges, progress));
  ready.sort((a, b) => {
    const rank = (id: string) => (progress[id]?.masteryResult === "incomplete" ? 0 : 1);
    const byState = rank(a) - rank(b);
    if (byState !== 0) return byState;
    return order.indexOf(a) - order.indexOf(b);
  });
  const id = ready[0] ?? null;
  if (!id) return { id: null, reason: "done" };
  const required = edges.filter((edge) => edge.to === id && edge.relationship !== "optional" && !isReturnEdge(edge, edges) && !isBranchEdge(edge));
  return { id, reason: required.length === 0 ? "start" : "open" };
}

export function nextBlockId(ids: string[], edges: EdgeLike[], progress: ProgressMap): string | null {
  return explainNext(ids, edges, progress).id;
}

export type Point = { x: number; y: number };

const COLUMN = 300;
const ROW = 168;

/** Layered spine. A branch sits under the block that opens it. Narrow screens stack the reading order. */
export function layoutBlocks(ids: string[], edges: EdgeLike[], rtl: boolean, compact = false): Record<string, Point> {
  const side = branchTargets(edges);
  if (compact) {
    const order = readingOrder(ids, edges);
    const positions: Record<string, Point> = {};
    order.forEach((id, index) => {
      const branch = side.has(id);
      const x = rtl ? (branch ? -20 : 24) : branch ? 72 : 24;
      positions[id] = { x, y: 16 + index * 156 };
    });
    return positions;
  }
  const main = ids.filter((id) => !side.has(id));
  const mainEdges = edges.filter((edge) => !isBranchEdge(edge) && !side.has(edge.from) && !side.has(edge.to));
  const forward = forwardEdges(main, mainEdges);
  const layer = new Map<string, number>(main.map((id) => [id, 0]));
  const indeg = new Map<string, number>(main.map((id) => [id, 0]));
  const adj = new Map<string, string[]>(main.map((id) => [id, []]));
  for (const edge of forward) {
    adj.get(edge.from)?.push(edge.to);
    indeg.set(edge.to, (indeg.get(edge.to) ?? 0) + 1);
  }
  const queue = main.filter((id) => (indeg.get(id) ?? 0) === 0);
  const seen = new Set<string>();
  while (queue.length > 0) {
    const id = queue.shift();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    for (const next of adj.get(id) ?? []) {
      layer.set(next, Math.max(layer.get(next) ?? 0, (layer.get(id) ?? 0) + 1));
      indeg.set(next, (indeg.get(next) ?? 1) - 1);
      if ((indeg.get(next) ?? 0) === 0) queue.push(next);
    }
  }

  const positions: Record<string, Point> = {};
  for (const id of main) {
    const column = layer.get(id) ?? 0;
    positions[id] = { x: rtl ? 24 - column * COLUMN : 24 + column * COLUMN, y: 24 };
  }
  const underCount = new Map<string, number>();
  for (const edge of edges) {
    if (!isBranchEdge(edge)) continue;
    const source = positions[edge.from];
    if (!source || positions[edge.to]) continue;
    const slot = underCount.get(edge.from) ?? 0;
    underCount.set(edge.from, slot + 1);
    positions[edge.to] = { x: source.x, y: source.y + ROW * (slot + 1) };
  }
  for (const id of ids) {
    if (!positions[id]) positions[id] = { x: 24, y: 24 };
  }
  return positions;
}

/** Flip the direct edge between a block and its neighbor in reading order. */
export function moveAlongSpine(ids: string[], edges: PathEdge[], id: string, direction: -1 | 1): PathEdge[] | null {
  const order = readingOrder(ids, edges);
  const index = order.indexOf(id);
  const neighbor = index + direction;
  if (index < 0 || neighbor < 0 || neighbor >= order.length) return null;
  const other = order[neighbor];
  const edgeIndex = edges.findIndex((edge) => (edge.from === id && edge.to === other) || (edge.from === other && edge.to === id));
  if (edgeIndex < 0) return null;
  const current = edges[edgeIndex];
  if (!current) return null;
  const flipped: PathEdge = { ...current, from: current.to, to: current.from };
  return edges.map((edge, i) => (i === edgeIndex ? flipped : edge));
}

export function progressFor(result: BlockProgress["masteryResult"], signal: string | null = null): BlockProgress {
  return { masteryResult: result, signal };
}
