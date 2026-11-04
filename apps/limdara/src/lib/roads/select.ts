import type { FlatNode, Road } from "./types";

export function flatten(road: Road): FlatNode[] {
  const out: FlatNode[] = [];
  for (const stage of road.stages) {
    for (const level of stage.levels) {
      for (const node of level.nodes) out.push({ road, stage, level, node });
    }
  }
  return out;
}

export function allNodes(roads: Road[]): FlatNode[] {
  return roads.flatMap((road) => flatten(road));
}

export function locate(roads: Road[], nodeId: string) {
  for (const road of roads) {
    const items = flatten(road);
    const index = items.findIndex((item) => item.node.id === nodeId);
    if (index >= 0) {
      return {
        ...items[index],
        prev: items[index - 1],
        next: items[index + 1],
      };
    }
  }
  return null;
}

export function roadTotals(road: Road) {
  const items = flatten(road);
  const minutes = items.reduce((sum, item) => sum + item.node.minutes, 0);
  const bullets = road.stages.reduce((sum, stage) => sum + stage.syllabus.length, 0);
  return { nodes: items.length, minutes, bullets, stages: road.stages.length };
}

export function formatSpan(minutes: number) {
  if (minutes < 90) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}

export function dirFor(text: string): "rtl" | "ltr" {
  const rtl = (text.match(/[\u0590-\u08FF]/g) ?? []).length;
  const latin = (text.match(/[A-Za-z]/g) ?? []).length;
  return rtl > latin ? "rtl" : "ltr";
}

export function kindLabel(kind: string) {
  if (kind === "concept") return "Read";
  if (kind === "worked") return "Worked";
  if (kind === "practice") return "Drill";
  return "Check";
}
