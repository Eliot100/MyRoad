import type { Road } from "@/lib/roads/types";

export type Finding = {
  roadId: string;
  stageId?: string;
  nodeId?: string;
  code: string;
  detail: string;
};

export type RoadAudit = {
  id: string;
  stages: number;
  nodes: number;
  bullets: number;
  covered: number;
  minutes: number;
};

export type AuditReport = {
  findings: Finding[];
  roads: RoadAudit[];
};

const LEVELS = ["Foundations", "Technique", "Mastery"] as const;
const KINDS = ["concept", "practice", "worked", "practice", "concept", "checkpoint"] as const;

export function audit(roads: Road[]): AuditReport {
  const findings: Finding[] = [];
  const summaries: RoadAudit[] = [];
  const seen = new Set<string>();

  for (const road of roads) {
    const topics = new Set<string>();
    let bullets = 0;
    let covered = 0;
    let nodes = 0;
    let minutes = 0;

    for (const stage of road.stages) {
      if (!stage.thesis || stage.thesis.trim().length < 20) {
        findings.push({
          roadId: road.id,
          stageId: stage.id,
          code: "partition-thesis",
          detail: `${stage.title} has no thesis.`,
        });
      }
      if (!stage.he || stage.he.trim() === stage.title.trim()) {
        findings.push({
          roadId: road.id,
          stageId: stage.id,
          code: "partition-he",
          detail: `${stage.title} is missing a Hebrew name.`,
        });
      }
      if (topics.has(stage.topic) || stage.topic !== stage.title) {
        findings.push({
          roadId: road.id,
          stageId: stage.id,
          code: "partition-topic",
          detail: `${stage.title} is not a single distinct topic.`,
        });
      }
      topics.add(stage.topic);

      if (stage.levels.length !== 3) {
        findings.push({
          roadId: road.id,
          stageId: stage.id,
          code: "levels-shape",
          detail: `${stage.title} should have three levels.`,
        });
      }

      stage.levels.forEach((level, levelIndex) => {
        if (level.title !== LEVELS[levelIndex]) {
          findings.push({
            roadId: road.id,
            stageId: stage.id,
            code: "levels-shape",
            detail: `${stage.title} level ${levelIndex + 1} should be ${LEVELS[levelIndex] ?? "a level"}.`,
          });
        }
        if (level.nodes.length !== 2) {
          findings.push({
            roadId: road.id,
            stageId: stage.id,
            code: "levels-shape",
            detail: `${stage.title} / ${level.title} should hold two nodes.`,
          });
        }
        level.nodes.forEach((node, nodeIndex) => {
          nodes += 1;
          minutes += node.minutes || 0;
          if (seen.has(node.id)) {
            findings.push({
              roadId: road.id,
              stageId: stage.id,
              nodeId: node.id,
              code: "partition-id",
              detail: `Duplicate node id ${node.id}.`,
            });
          }
          seen.add(node.id);
          const expected = KINDS[levelIndex * 2 + nodeIndex];
          if (expected && node.kind !== expected) {
            findings.push({
              roadId: road.id,
              stageId: stage.id,
              nodeId: node.id,
              code: "levels-kind",
              detail: `${node.title} should be a ${expected} node.`,
            });
          }
          if (!node.he || node.he.trim() === node.title.trim()) {
            findings.push({
              roadId: road.id,
              nodeId: node.id,
              code: "partition-he",
              detail: `${node.title} is missing a Hebrew name.`,
            });
          }
          if ((node.teach ?? "").trim().length < 160) {
            findings.push({
              roadId: road.id,
              nodeId: node.id,
              code: "teach-thin",
              detail: `${node.title} is too thin to teach the line it owns.`,
            });
          }
          if ((node.rules ?? []).length < 3 || (node.objectives ?? []).length < 2) {
            findings.push({
              roadId: road.id,
              nodeId: node.id,
              code: "practice-shape",
              detail: `${node.title} needs two objectives and at least three rules.`,
            });
          }
          if ((node.example?.steps ?? []).length < 3 || !node.example?.answer?.trim()) {
            findings.push({
              roadId: road.id,
              nodeId: node.id,
              code: "practice-shape",
              detail: `${node.title} needs a worked example with steps and an answer.`,
            });
          }
          const needed = node.kind === "checkpoint" ? 4 : 2;
          if ((node.practice ?? []).length !== needed) {
            findings.push({
              roadId: road.id,
              nodeId: node.id,
              code: "practice-shape",
              detail: `${node.title} should have ${needed} checks.`,
            });
          }
          for (const item of node.practice ?? []) {
            if (!item.answer?.trim() || !item.q?.trim() || !item.why?.trim()) {
              findings.push({
                roadId: road.id,
                nodeId: node.id,
                code: "practice-answer",
                detail: `${node.title} has a check with an empty prompt, answer, or reason.`,
              });
            }
          }
        });
      });

      const owned = new Set(stage.levels.flatMap((level) => level.nodes.flatMap((node) => node.covers)));
      for (const bullet of stage.syllabus) {
        bullets += 1;
        if (owned.has(bullet)) covered += 1;
        else {
          findings.push({
            roadId: road.id,
            stageId: stage.id,
            code: "cover-missing",
            detail: `Nothing owns “${bullet}”.`,
          });
        }
      }
      for (const bullet of owned) {
        if (!stage.syllabus.includes(bullet)) {
          findings.push({
            roadId: road.id,
            stageId: stage.id,
            code: "cover-extra",
            detail: `“${bullet}” is not on the ${stage.title} syllabus.`,
          });
        }
      }
    }

    summaries.push({
      id: road.id,
      stages: road.stages.length,
      nodes,
      bullets,
      covered,
      minutes,
    });
  }

  return { findings, roads: summaries };
}
