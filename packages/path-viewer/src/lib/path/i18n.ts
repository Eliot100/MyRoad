import type { BlockType, Locale, MasteryState, PathEdge } from "@/lib/path/types";
import type { NextReason } from "@/lib/path/graph";

export const LOCALES: { id: Locale; label: string }[] = [
  { id: "he", label: "עברית" },
  { id: "en", label: "English" },
  { id: "ar", label: "العربية" },
];

export function direction(locale: Locale): "rtl" | "ltr" {
  return locale === "en" ? "ltr" : "rtl";
}

type Copy = {
  view: string;
  editing: string;
  draft: string;
  published: string;
  publishedLock: string;
  notStarted: string;
  inProgress: string;
  mastered: string;
  needsRemediation: string;
  next: string;
  wholePath: string;
  map: string;
  list: string;
  explanation: string;
  practice: string;
  assessment: string;
  experience: string;
  suggestedNow: string;
  fromHere: string;
  nothingLeft: string;
  selectPrompt: string;
  passMark: string;
  currentScore: string;
  resources: string;
  masteredCount: (done: number, total: number) => string;
  onThis: string;
  markMastered: string;
  markRemediation: string;
  restoreSample: string;
  startOver: string;
  blocking: string;
  notBlocking: string;
  removeEdge: string;
  earlier: string;
  later: string;
  tidy: string;
  resetDraft: string;
  edgeTitle: string;
  optional: string;
  prerequisite: string;
  failedRoute: string;
  retryRoute: string;
  sequence: string;
  branchReason: string;
  retryReason: string;
  openReason: string;
  startReason: string;
  editHint: string;
  overviewHint: string;
  localNote: string;
  settings: string;
  quality: string;
  qualityNote: string;
  uiGroup: string;
  learnGroup: string;
  keepGroup: string;
  timeToNext: string;
  mapToggles: string;
  listToggles: string;
  settingsOpens: string;
  masteredBlocks: string;
  recovered: string;
  returns: string;
  sessions: string;
  pathsOpen: string;
  pathsDone: string;
  stage: (n: number) => string;
  milliseconds: (n: number | null) => string;
  version: (n: number) => string;
};

const copy: Record<Locale, Copy> = {
  he: {
    view: "צפייה",
    editing: "עריכה",
    draft: "טיוטה",
    published: "מפורסם",
    publishedLock: "גרסה מפורסמת נשארת קבועה. עורכים רק טיוטה.",
    notStarted: "טרם התחיל",
    inProgress: "בתהליך",
    mastered: "נשלט",
    needsRemediation: "צריך חיזוק",
    next: "הבא",
    wholePath: "כל הדרך",
    map: "מפה",
    list: "רשימה",
    explanation: "הסבר",
    practice: "תרגול",
    assessment: "הערכה",
    experience: "יישום",
    suggestedNow: "מומלץ עכשיו",
    fromHere: "מכאן",
    nothingLeft: "אין בלוק פתוח. הדרך הזו מאחוריך.",
    selectPrompt: "בוחרים בלוק כדי לקרוא אותו ולעדכן שליטה.",
    passMark: "רף שליטה",
    currentScore: "ציון נוכחי",
    resources: "מקור",
    masteredCount: (done, total) => `${done} מתוך ${total} נשלטו`,
    onThis: "אני כאן",
    markMastered: "זה נשלט",
    markRemediation: "צריך עוד סבב",
    restoreSample: "שחזור התקדמות לדוגמה",
    startOver: "התחלה מהבלוק הראשון",
    blocking: "קשת חוסמת",
    notBlocking: "קשת לא חוסמת",
    removeEdge: "הסרת קשת",
    earlier: "הזזה אחורה",
    later: "הזזה קדימה",
    tidy: "סידור מחדש",
    resetDraft: "ביטול שינויי הטיוטה",
    edgeTitle: "קשת",
    optional: "אופציונלי",
    prerequisite: "קדם",
    failedRoute: "אם ההערכה נכשלת",
    retryRoute: "חזרה אחרי חיזוק",
    sequence: "המשך",
    branchReason: "בדרך הזו, כישלון בבלוק פותח את הענף שכתוב עליו.",
    retryReason: "הענף בדרך הזו הושלם, אז חוזרים אל הבלוק שפתח אותו.",
    openReason: "הקשתות שחוסמות את זה בדרך הזו כבר מתקיימות אצל הלומד.",
    startReason: "זו נקודת הפתיחה של הדרך הזו, אצל הלומד הזה.",
    editHint: "גוררים מנקודה ירוקה אל בלוק אחר כדי לחבר. סוג הקשת (המשך, קדם, אופציונלי, ענף) נערך בטיוטה.",
    overviewHint: "ההמלצה נקראת מהקשתות של הדרך הזו ומהמצב של הלומד, לא מכלל קבוע.",
    localNote: "הרשומה כאן היא בצורת PathStore: דרך אחת, לומד אחד. היא נשמרת במכשיר הזה עד חיבור לשרת.",
    settings: "הגדרות",
    quality: "איכות",
    qualityNote: "ספירות על המכשיר הזה, עבור הלומד הזה. לא שימור אמיתי.",
    uiGroup: "ממשק",
    learnGroup: "למידה וזיכרון",
    keepGroup: "הנאה, שימור וצמיחה",
    timeToNext: "זמן עד שהצעד הבא נראה",
    mapToggles: "מעבר למפת הדרך",
    listToggles: "מעבר לרשימה",
    settingsOpens: "פתיחות הגדרות",
    masteredBlocks: "בלוקים שנשלטו",
    recovered: "הערכות שנכשלו וחזרו דרך ענף",
    returns: "חזרה להערכה אחרי חיזוק",
    sessions: "מפגשים שהתחילו",
    pathsOpen: "דרכים עם צעד שעוד פתוח",
    pathsDone: "דרכים שהושלמו",
    stage: (n) => `שלב ${n}`,
    milliseconds: (n) => (n == null ? "—" : `${n} ms`),
    version: (n) => `גרסה ${n}`,
  },
  en: {
    view: "View",
    editing: "Editing",
    draft: "Draft",
    published: "Published",
    publishedLock: "A published version stays fixed. Edits belong on a draft.",
    notStarted: "Not started",
    inProgress: "In progress",
    mastered: "Mastered",
    needsRemediation: "Needs another pass",
    next: "Next",
    wholePath: "Whole path",
    map: "Map",
    list: "List",
    explanation: "Explanation",
    practice: "Practice",
    assessment: "Check",
    experience: "Experience",
    suggestedNow: "Suggested now",
    fromHere: "From here",
    nothingLeft: "Nothing left open. This path is behind you.",
    selectPrompt: "Choose a block to read it and update mastery.",
    passMark: "Pass mark",
    currentScore: "Current score",
    resources: "Source",
    masteredCount: (done, total) => `${done} of ${total} mastered`,
    onThis: "I am on this",
    markMastered: "Mastered",
    markRemediation: "Needs another pass",
    restoreSample: "Restore sample progress",
    startOver: "Start from the first block",
    blocking: "Blocking edge",
    notBlocking: "Non-blocking edge",
    removeEdge: "Remove edge",
    earlier: "Move earlier",
    later: "Move later",
    tidy: "Tidy layout",
    resetDraft: "Discard draft edits",
    edgeTitle: "Edge",
    optional: "Optional",
    prerequisite: "Prerequisite",
    failedRoute: "If the check fails",
    retryRoute: "Return after another pass",
    sequence: "Continues",
    branchReason: "On this path, a failed block opens the branch written on it.",
    retryReason: "This path's branch is done, so the learner returns to the block that opened it.",
    openReason: "The edges that gate this block are already met for this learner.",
    startReason: "This is where this path starts for this learner.",
    editHint: "Drag from a pine dot to another block to connect them. The relationship (sequence, prerequisite, optional, branch) is edited on the draft.",
    overviewHint: "The suggestion is read from this path's edges and this learner's record, not from one fixed rule.",
    localNote: "This record matches PathStore: one path, one learner. It stays on this device until a server is connected.",
    settings: "Settings",
    quality: "Quality",
    qualityNote: "Counts on this device, for this learner. Not real retention.",
    uiGroup: "Interface",
    learnGroup: "Learning and memory",
    keepGroup: "Enjoyment, retention, growth",
    timeToNext: "Time until the next step is in view",
    mapToggles: "Switches to the path",
    listToggles: "Switches to the list",
    settingsOpens: "Settings opened",
    masteredBlocks: "Blocks mastered",
    recovered: "Checks failed, then recovered on a branch",
    returns: "Returns to a check after another pass",
    sessions: "Sessions started",
    pathsOpen: "Paths with a step still open",
    pathsDone: "Paths completed",
    stage: (n) => `Stage ${n}`,
    milliseconds: (n) => (n == null ? "—" : `${n} ms`),
    version: (n) => `Version ${n}`,
  },
  ar: {
    view: "عرض",
    editing: "تحرير",
    draft: "مسودة",
    published: "منشور",
    publishedLock: "النسخة المنشورة تبقى ثابتة. التحرير للمسودة فقط.",
    notStarted: "لم يبدأ",
    inProgress: "قيد التعلّم",
    mastered: "مُتقن",
    needsRemediation: "يحتاج جولة أخرى",
    next: "التالي",
    wholePath: "المسار كله",
    map: "خريطة",
    list: "قائمة",
    explanation: "شرح",
    practice: "تدريب",
    assessment: "فحص",
    experience: "تطبيق",
    suggestedNow: "المقترح الآن",
    fromHere: "من هنا",
    nothingLeft: "لا خطوة مفتوحة. هذا المسار خلفك.",
    selectPrompt: "اختر خطوة لقراءتها وتحديث الإتقان.",
    passMark: "حد الإتقان",
    currentScore: "النتيجة الحالية",
    resources: "مصدر",
    masteredCount: (done, total) => `${done} من ${total} مُتقنة`,
    onThis: "أنا هنا",
    markMastered: "أُتقنت",
    markRemediation: "تحتاج جولة أخرى",
    restoreSample: "استعادة تقدّم العيّنة",
    startOver: "البدء من الخطوة الأولى",
    blocking: "رابط حاجز",
    notBlocking: "رابط غير حاجز",
    removeEdge: "حذف الرابط",
    earlier: "تحريك للخلف",
    later: "تحريك للأمام",
    tidy: "ترتيب تلقائي",
    resetDraft: "التراجع عن تعديلات المسودة",
    edgeTitle: "رابط",
    optional: "اختياري",
    prerequisite: "متطلب",
    failedRoute: "إذا رسب الفحص",
    retryRoute: "عودة بعد التقوية",
    sequence: "متابعة",
    branchReason: "على هذا المسار، الرسوب في خطوة يفتح الفرع المكتوب عليها.",
    retryReason: "فرع هذا المسار اكتمل، فيعود المتعلّم إلى الخطوة التي فتحته.",
    openReason: "الروابط التي تغلق هذه الخطوة تحقّقت لهذا المتعلّم.",
    startReason: "هذه بداية هذا المسار لهذا المتعلّم.",
    editHint: "اسحب من النقطة الخضراء إلى خطوة أخرى للربط. نوع الرابط (متابعة، متطلب، اختياري، فرع) يُحرَّر في المسودة.",
    overviewHint: "الاقتراح يُقرأ من روابط هذا المسار ومن سجل هذا المتعلّم، لا من قاعدة ثابتة.",
    localNote: "السجل هنا بشكل PathStore: مسار واحد ومتعلّم واحد. يبقى على هذا الجهاز حتى يتصل بخادم.",
    settings: "إعدادات",
    quality: "جودة",
    qualityNote: "أعداد على هذا الجهاز لهذا المتعلّم. ليست استمراراً حقيقياً.",
    uiGroup: "الواجهة",
    learnGroup: "التعلّم والذاكرة",
    keepGroup: "المتعة والاستمرار والنمو",
    timeToNext: "الوقت حتى تظهر الخطوة التالية",
    mapToggles: "الانتقال إلى المسار",
    listToggles: "الانتقال إلى القائمة",
    settingsOpens: "فتح الإعدادات",
    masteredBlocks: "خطوات أُتقنت",
    recovered: "فحوص رسبت ثم عادت عبر فرع",
    returns: "عودة إلى الفحص بعد التقوية",
    sessions: "جلسات بدأت",
    pathsOpen: "مسارات فيها خطوة مفتوحة",
    pathsDone: "مسارات اكتملت",
    stage: (n) => `مرحلة ${n}`,
    milliseconds: (n) => (n == null ? "—" : `${n} ms`),
    version: (n) => `الإصدار ${n}`,
  },
};

export function copyFor(locale: Locale): Copy {
  return copy[locale];
}

export function stateLabel(locale: Locale, state: MasteryState): string {
  const c = copy[locale];
  if (state === "mastered") return c.mastered;
  if (state === "in_progress") return c.inProgress;
  if (state === "needs_remediation") return c.needsRemediation;
  return c.notStarted;
}

export function typeLabel(locale: Locale, type: BlockType): string {
  const c = copy[locale];
  if (type === "explanation") return c.explanation;
  if (type === "practice") return c.practice;
  if (type === "assessment") return c.assessment;
  return c.experience;
}

export function edgeLabel(locale: Locale, edge: Pick<PathEdge, "relationship" | "condition">): string | null {
  const c = copy[locale];
  if (edge.relationship === "optional") return c.optional;
  if (edge.relationship === "branch") return c.failedRoute;
  if (edge.relationship === "prerequisite") return c.prerequisite;
  if (edge.condition?.mastery) return c.retryRoute;
  return null;
}

export function reasonLabel(locale: Locale, reason: NextReason): string | null {
  const c = copy[locale];
  if (reason === "branch") return c.branchReason;
  if (reason === "retry") return c.retryReason;
  if (reason === "open") return c.openReason;
  if (reason === "start") return c.startReason;
  return null;
}

export function relationshipLabel(locale: Locale, relationship: PathEdge["relationship"]): string {
  const c = copy[locale];
  if (relationship === "optional") return c.optional;
  if (relationship === "branch") return c.failedRoute;
  if (relationship === "prerequisite") return c.prerequisite;
  return c.sequence;
}
