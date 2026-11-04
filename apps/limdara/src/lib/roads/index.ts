import type { Stage } from "./types";
import { roadMeta } from "./meta";
import mathA from "./content/math-a.json";
import mathB from "./content/math-b.json";
import englishA from "./content/english-a.json";
import englishB from "./content/english-b.json";
import physicsA from "./content/physics-a.json";
import physicsB from "./content/physics-b.json";
import arabicA from "./content/arabic-a.json";
import arabicB from "./content/arabic-b.json";
import psychometricA from "./content/psychometric-a.json";
import psychometricB from "./content/psychometric-b.json";

const parts: Record<string, { stages: Stage[] }> = {
  "math-a": mathA as unknown as { stages: Stage[] },
  "math-b": mathB as unknown as { stages: Stage[] },
  "english-a": englishA as unknown as { stages: Stage[] },
  "english-b": englishB as unknown as { stages: Stage[] },
  "physics-a": physicsA as unknown as { stages: Stage[] },
  "physics-b": physicsB as unknown as { stages: Stage[] },
  "arabic-a": arabicA as unknown as { stages: Stage[] },
  "arabic-b": arabicB as unknown as { stages: Stage[] },
  "psychometric-a": psychometricA as unknown as { stages: Stage[] },
  "psychometric-b": psychometricB as unknown as { stages: Stage[] },
};

export const roads = roadMeta.map((meta) => {
  const stages = meta.parts
    .flatMap((part) => parts[part]?.stages ?? [])
    .map((stage, index) => ({ ...stage, index: index + 1 }));
  return { ...meta, stages };
});

export function getRoad(id: string) {
  return roads.find((road) => road.id === id);
}
