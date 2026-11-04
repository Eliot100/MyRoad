import { readFileSync } from "node:fs";

const expected = {
  "math-a": ["math-fn", "math-poly", "math-explog", "math-seq", "math-trig", "math-ag"],
  "math-b": ["math-vec", "math-diff", "math-integ", "math-prob", "math-geom", "math-syn"],
  "english-a": ["eng-verb", "eng-clause", "eng-vocab", "eng-read", "eng-listen"],
  "english-b": ["eng-para", "eng-write", "eng-story", "eng-poem", "eng-oral"],
  "physics-a": ["phys-meas", "phys-kin", "phys-force", "phys-energy", "phys-mom", "phys-circ"],
  "physics-b": ["phys-wave", "phys-elec", "phys-circuit", "phys-mag", "phys-light", "phys-mod"],
  "arabic-a": ["ar-script", "ar-noun", "ar-past", "ar-present", "ar-particle"],
  "arabic-b": ["ar-sentence", "ar-read", "ar-vocab", "ar-write", "ar-exam"],
  "psychometric-a": ["psy-test", "psy-arith", "psy-alg", "psy-word", "psy-geom", "psy-data"],
  "psychometric-b": ["psy-ana", "psy-logic", "psy-vread", "psy-ecomp", "psy-eread", "psy-sim"],
};

const LEVELS = ["Foundations", "Technique", "Mastery"];
const KINDS = ["concept", "practice", "worked", "practice", "concept", "checkpoint"];
const findings = [];

for (const [file, ids] of Object.entries(expected)) {
  const path = `src/lib/roads/content/${file}.json`;
  let data;
  try {
    data = JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    findings.push(`${file}: ${error instanceof Error ? error.message : "unreadable"}`);
    continue;
  }
  const stages = data.stages;
  if (!Array.isArray(stages)) {
    findings.push(`${file}: missing stages array`);
    continue;
  }
  const got = stages.map((stage) => stage.id);
  if (got.join() !== ids.join()) {
    findings.push(`${file}: ids ${got.join(",")} expected ${ids.join(",")}`);
  }
  for (const stage of stages) {
    if (!Array.isArray(stage.syllabus) || stage.syllabus.length !== 6) {
      findings.push(`${stage.id}: syllabus must have 6 lines`);
    }
    if (!Array.isArray(stage.levels) || stage.levels.length !== 3) {
      findings.push(`${stage.id}: expected 3 levels`);
      continue;
    }
    const covers = [];
    stage.levels.forEach((level, levelIndex) => {
      if (level.title !== LEVELS[levelIndex]) findings.push(`${stage.id}: level title ${level.title}`);
      if (!Array.isArray(level.nodes) || level.nodes.length !== 2) {
        findings.push(`${stage.id}: level ${level.title} node count`);
        return;
      }
      level.nodes.forEach((node, nodeIndex) => {
        const kind = KINDS[levelIndex * 2 + nodeIndex];
        if (node.kind !== kind) findings.push(`${node.id}: kind ${node.kind} expected ${kind}`);
        if (!node.teach || node.teach.trim().length < 160) findings.push(`${node.id}: thin teach`);
        if (!node.he || node.he === node.title) findings.push(`${node.id}: missing Hebrew`);
        const need = node.kind === "checkpoint" ? 4 : 2;
        if (!Array.isArray(node.practice) || node.practice.length !== need) {
          findings.push(`${node.id}: practice ${node.practice?.length} expected ${need}`);
        }
        for (const item of node.practice ?? []) {
          if (!item?.q || !item?.answer || !item?.why) findings.push(`${node.id}: empty check`);
        }
        if (!node.example?.answer || (node.example.steps ?? []).length < 3) {
          findings.push(`${node.id}: weak example`);
        }
        for (const bullet of node.covers ?? []) covers.push(bullet);
      });
    });
    const syllabus = new Set(stage.syllabus ?? []);
    const owned = new Set(covers);
    for (const bullet of syllabus) {
      if (!owned.has(bullet)) findings.push(`${stage.id}: missing cover ${bullet}`);
    }
    for (const bullet of owned) {
      if (!syllabus.has(bullet)) findings.push(`${stage.id}: extra cover ${bullet}`);
    }
  }
}

if (findings.length) {
  console.log(findings.slice(0, 80).join("\n"));
  console.log(`\n${findings.length} findings`);
  process.exit(1);
}
console.log("roads ok");
