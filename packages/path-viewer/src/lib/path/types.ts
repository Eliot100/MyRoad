export type Locale = "he" | "en" | "ar";

export type Localized = Record<Locale, string>;

/** PathStore block types. Content nodes such as `learn` map onto `explanation`. */
export type BlockType = "explanation" | "practice" | "assessment" | "experience";

export type EdgeRelationship = "prerequisite" | "sequence" | "optional" | "branch";

/** PathStore edge condition. The mastery token is authored on that path, not a global rule. */
export type EdgeCondition = {
  mastery?: string;
  note?: string;
} | null;

export type PathStatus = "draft" | "published";

export type MasteryResult = "not_started" | "incomplete" | "passed" | "failed";

/** What the learner has actually done on one block of one path. */
export type BlockProgress = {
  masteryResult: MasteryResult;
  /** Condition token currently true for this learner, taken from this path's edges. */
  signal: string | null;
};

export type ProgressMap = Record<string, BlockProgress>;

export type MasteryState = "not_started" | "in_progress" | "mastered" | "needs_remediation";

export type MasteryRule = {
  type: string;
  passingCriterion: Localized;
  minCorrect?: number;
  total?: number;
};

/** One PathStore block, with UI copy for he / en / ar. Canonical content language is Hebrew. */
export type PathBlock = {
  blockId: string;
  type: BlockType;
  title: Localized;
  learningObjective: Localized;
  concept: string;
  body: Localized;
  masteryRule: MasteryRule;
};

/** One PathStore edge: `from` / `to`, relationship, optional condition. */
export type PathEdge = {
  edgeId: string;
  from: string;
  to: string;
  relationship: EdgeRelationship;
  condition: EdgeCondition;
};

/** Subset of a PathStore PathVersion that the viewer reads. */
export type PathVersion = {
  schemaVersion: "0.1.0";
  pathId: string;
  versionId: string;
  version: number;
  status: PathStatus;
  contentLanguage: string;
  name: Localized;
  description: Localized;
  goal: Localized;
  blocks: PathBlock[];
  edges: PathEdge[];
};

export function uiState(progress: BlockProgress | undefined): MasteryState {
  if (progress?.masteryResult === "passed") return "mastered";
  if (progress?.masteryResult === "failed") return "needs_remediation";
  if (progress?.masteryResult === "incomplete") return "in_progress";
  return "not_started";
}
