import { PATHS, SEED_PROGRESS } from "./sample.ts";
import type { PathVersion, ProgressMap } from "./types.ts";

/**
 * Browser stand-in for PathStore.
 *
 * The real store (packages/core) keeps a PathVersion and one learner_progress
 * row per user and path. These three calls are the ones a FastAPI client
 * would make. Here they read the freeze samples and the record this browser
 * is holding for a single sample learner. Nothing is published.
 */
export const LEARNER_ID = "learner_sample";

const byId = new Map(PATHS.map((path) => [path.pathId, path]));

export function listPaths(): PathVersion[] {
  return PATHS;
}

export function getPathVersion(pathId: string): PathVersion {
  const path = byId.get(pathId);
  if (!path) throw new Error(`Unknown path ${pathId}`);
  return path;
}

export function getProgress(pathId: string): ProgressMap {
  const path = getPathVersion(pathId);
  const seed = SEED_PROGRESS[pathId];
  if (!seed) return {};
  return Object.fromEntries(path.blocks.map((block) => [block.blockId, { ...seed[block.blockId] }]));
}
