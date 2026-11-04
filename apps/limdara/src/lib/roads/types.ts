export type NodeKind = "concept" | "worked" | "practice" | "checkpoint";

export type PracticeItem = {
  q: string;
  answer: string;
  why: string;
};

export type LessonNode = {
  id: string;
  title: string;
  he: string;
  minutes: number;
  kind: NodeKind;
  covers: string[];
  objectives: string[];
  teach: string;
  rules: string[];
  example: {
    prompt: string;
    steps: string[];
    answer: string;
  };
  practice: PracticeItem[];
};

export type Level = {
  id: string;
  title: string;
  he: string;
  intent: string;
  nodes: LessonNode[];
};

export type Stage = {
  id: string;
  index: number;
  title: string;
  he: string;
  topic: string;
  thesis: string;
  syllabus: string[];
  levels: Level[];
};

export type Road = {
  id: string;
  title: string;
  he: string;
  kicker: string;
  summary: string;
  exam: string;
  stages: Stage[];
};

export type FlatNode = {
  road: Road;
  stage: Stage;
  level: Level;
  node: LessonNode;
};
