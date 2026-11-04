export type RoadMeta = {
  id: string;
  title: string;
  he: string;
  kicker: string;
  summary: string;
  exam: string;
  parts: string[];
};

export const roadMeta: RoadMeta[] = [
  {
    id: "math-5",
    title: "Mathematics",
    he: "מתמטיקה",
    kicker: "5 units · Bagrut",
    summary: "Functions through proof: the full 5-unit mathematics syllabus as one road.",
    exam: "Israeli 5-unit mathematics bagrut. Questionnaire numbers change by year. The topics do not: functions, polynomials, exponents and logs, sequences and induction, trigonometry, analytic geometry, vectors, calculus, probability, and Euclidean geometry.",
    parts: ["math-a", "math-b"],
  },
  {
    id: "english-5",
    title: "English",
    he: "אנגלית",
    kicker: "5 units · Bagrut",
    summary: "Grammar, unseen reading, listening, writing, literature, and the oral for 5-unit English.",
    exam: "Israeli 5-unit English at the higher band. Literature craft is taught on public-domain texts, so it still applies when a school changes its list. Listening is trained from transcripts: this reader has no audio player.",
    parts: ["english-a", "english-b"],
  },
  {
    id: "physics-5",
    title: "Physics",
    he: "פיזיקה",
    kicker: "5 units · Bagrut",
    summary: "Mechanics, electromagnetism, waves, light, modern physics, and the lab judgment a 5-unit paper expects.",
    exam: "Israeli 5-unit physics. Take g as 10 m/s² everywhere on this road. The internal lab is practiced as judgment on paper: uncertainty, graphs, and what a conclusion is allowed to say.",
    parts: ["physics-a", "physics-b"],
  },
  {
    id: "arabic-5",
    title: "Arabic",
    he: "ערבית",
    kicker: "5 units · MSA",
    summary: "Modern Standard Arabic for the 5-unit exam taken by Hebrew-speaking students.",
    exam: "5-unit Arabic for students whose school language is Hebrew (ערבית לדוברי עברית). The exam language is fusḥā, not a spoken dialect. Explanations are in English. Examples are in Arabic.",
    parts: ["arabic-a", "arabic-b"],
  },
  {
    id: "psychometric",
    title: "Psychometric",
    he: "פסיכומטרי",
    kicker: "Start to finish",
    summary: "From the shape of the test to a full simulation: quantitative, verbal, and English.",
    exam: "The Israeli Psychometric Entrance Test, written by NITE (מרכז ארצי לבחינות ולהערכה). The scaled score runs from 200 to 800. Three domains are scored — verbal, quantitative, and English — and unscored pilot sections are mixed in. No calculator. On the live paper the verbal domain is in Hebrew; this road trains the logic in English and puts Hebrew into the analogy stage so the transfer is explicit.",
    parts: ["psychometric-a", "psychometric-b"],
  },
];
