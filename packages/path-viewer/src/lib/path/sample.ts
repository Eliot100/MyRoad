import { progressFor } from "./graph.ts";
import type { Localized, PathVersion, ProgressMap } from "./types.ts";

function text(he: string, en: string, ar: string): Localized {
  return { he, en, ar };
}

/**
 * Freeze v0 path `path_quadratic_he_hs_001`, version `ver_qeq_draft_002`.
 * Block types and edges match PathStore: explanation, from/to, relationship, condition.mastery.
 * Titles and bodies are filled for en and ar so the shell can switch language.
 * The math and the edge tokens are the ones the path already authored.
 */
export const QUADRATIC: PathVersion = {
  schemaVersion: "0.1.0",
  pathId: "path_quadratic_he_hs_001",
  versionId: "ver_qeq_draft_002",
  version: 2,
  status: "draft",
  contentLanguage: "he",
  name: text("משוואות ריבועיות", "Quadratic equations", "المعادلات التربيعية"),
  description: text(
    "מסלול קצר לתיכון. כישלון בהערכה יורד לענף חיזוק שכתוב על הדרך עצמה, ואז חוזר לאותה הערכה.",
    "A short high-school path. A failed check follows the branch this path wrote, then returns to the same check.",
    "مسار قصير للثانوية. الرسوب في الفحص يتبع الفرع المكتوب على هذا المسار، ثم يعود إلى الفحص نفسه.",
  ),
  goal: text(
    "לזהות משוואה ריבועית, לחשב דיסקרימיננטה, ולפתור בנוסחת השורשים.",
    "Identify a quadratic, compute the discriminant, and solve with the quadratic formula.",
    "تمييز المعادلة التربيعية وحساب المميز والحل بقانون الجذور.",
  ),
  blocks: [
    {
      blockId: "blk_qeq_intro_001",
      type: "explanation",
      concept: "quadratic_equation_definition",
      title: text("מהי משוואה ריבועית", "What is a quadratic equation", "ما هي المعادلة التربيعية"),
      learningObjective: text(
        "הלומד יגדיר משוואה ריבועית ויזהה את a, b, c.",
        "Define a quadratic and name a, b, and c.",
        "تعريف المعادلة التربيعية وتمييز a و b و c.",
      ),
      body: text(
        "משוואה ריבועית היא מהצורה ax² + bx + c = 0 כאשר a ≠ 0.\n\nב־2x² − 5x + 3 = 0 המקדמים הם a = 2, b = −5, c = 3. המשוואה 3x + 1 = 0 אינה ריבועית.",
        "A quadratic equation has the form ax² + bx + c = 0 where a ≠ 0.\n\nIn 2x² − 5x + 3 = 0 the coefficients are a = 2, b = −5, c = 3. The equation 3x + 1 = 0 is not quadratic.",
        "المعادلة التربيعية من الصورة ax² + bx + c = 0 حيث a ≠ 0.\n\nفي 2x² − 5x + 3 = 0 المعاملات a = 2 و b = −5 و c = 3. المعادلة 3x + 1 = 0 ليست تربيعية.",
      ),
      masteryRule: {
        type: "view_and_confirm",
        passingCriterion: text("אישור שההגדרה ברורה", "Confirm the definition is clear", "تأكيد أن التعريف واضح"),
      },
    },
    {
      blockId: "blk_qeq_disc_002",
      type: "explanation",
      concept: "discriminant",
      title: text("הדיסקרימיננטה", "The discriminant", "المميز"),
      learningObjective: text(
        "לחשב D = b² − 4ac ולפרש כמה פתרונות ממשיים יש.",
        "Compute D = b² − 4ac and say how many real solutions there are.",
        "حساب D = b² − 4ac وتفسير عدد الحلول الحقيقية.",
      ),
      body: text(
        "D = b² − 4ac.\n\n- D > 0: שני פתרונות ממשיים שונים\n- D = 0: פתרון ממשי אחד (כפול)\n- D < 0: אין פתרון ממשי",
        "D = b² − 4ac.\n\n- D > 0: two different real solutions\n- D = 0: one real solution (a double root)\n- D < 0: no real solution",
        "D = b² − 4ac.\n\n- D > 0: حلان حقيقيان مختلفان\n- D = 0: حل حقيقي واحد\n- D < 0: لا حل حقيقي",
      ),
      masteryRule: {
        type: "view_and_confirm",
        passingCriterion: text("אישור של שלושת המקרים", "Confirm the three cases", "تأكيد الحالات الثلاث"),
      },
    },
    {
      blockId: "blk_qeq_formula_003",
      type: "explanation",
      concept: "quadratic_formula",
      title: text("נוסחת השורשים", "The quadratic formula", "قانون الجذور"),
      learningObjective: text(
        "ליישם x = (−b ± √D) / (2a).",
        "Apply x = (−b ± √D) / (2a).",
        "تطبيق x = (−b ± √D) / (2a).",
      ),
      body: text(
        "קודם D, אחר כך השורש, ורק אז החילוק ב־2a.\n\nx = (−b ± √(b² − 4ac)) / (2a)",
        "First D, then the square root, then the division by 2a.\n\nx = (−b ± √(b² − 4ac)) / (2a)",
        "أولاً D، ثم الجذر، ثم القسمة على 2a.\n\nx = (−b ± √(b² − 4ac)) / (2a)",
      ),
      masteryRule: {
        type: "view_and_confirm",
        passingCriterion: text("אישור הנוסחה ושלושת השלבים", "Confirm the formula and the three steps", "تأكيد القانون والخطوات الثلاث"),
      },
    },
    {
      blockId: "blk_qeq_practice_004",
      type: "practice",
      concept: "quadratic_practice",
      title: text("תרגול מודרך", "Guided practice", "تدريب موجّه"),
      learningObjective: text(
        "לחשב D ושורשים לשתי משוואות.",
        "Compute D and the roots for two equations.",
        "حساب D والجذور لمعادلتين.",
      ),
      body: text(
        "ל־x² − 5x + 6 = 0 מתקבל D = 1 והשורשים 2 ו־3.\n\nל־x² + 4x + 4 = 0 מתקבל D = 0 ושורש כפול x = −2.",
        "For x² − 5x + 6 = 0, D = 1 and the roots are 2 and 3.\n\nFor x² + 4x + 4 = 0, D = 0 and the double root is x = −2.",
        "في x² − 5x + 6 = 0 يكون D = 1 والجذران 2 و 3.\n\nفي x² + 4x + 4 = 0 يكون D = 0 والجذر المضاعف x = −2.",
      ),
      masteryRule: {
        type: "practice_threshold",
        minCorrect: 3,
        total: 4,
        passingCriterion: text("לפחות 3 מתוך 4", "At least 3 of 4", "3 من 4 على الأقل"),
      },
    },
    {
      blockId: "blk_qeq_assess_005",
      type: "assessment",
      concept: "quadratic_mastery_check",
      title: text("הערכה קצרה", "Short check", "فحص قصير"),
      learningObjective: text(
        "שליטה עצמאית בזיהוי, ב־D ובפתרון.",
        "Independent mastery of recognition, D, and solving.",
        "إتقان مستقل للتمييز و D والحل.",
      ),
      body: text(
        "בלי רמזים. התוצאה קובעת אם ממשיכים ליישום או יורדים לענף החיזוק שעל הדרך הזו.",
        "No hints. The result decides whether this path continues to the word problem or takes its remediation branch.",
        "بلا تلميحات. النتيجة تقرر إن كان هذا المسار يكمل إلى المسألة أو يأخذ فرع التقوية.",
      ),
      masteryRule: {
        type: "assessment_pass",
        minCorrect: 2,
        total: 3,
        passingCriterion: text("לפחות 2 מתוך 3", "At least 2 of 3", "2 من 3 على الأقل"),
      },
    },
    {
      blockId: "blk_qeq_experience_006",
      type: "experience",
      concept: "quadratic_word_problem",
      title: text("בעיה מהחיים", "A word problem", "مسألة من الحياة"),
      learningObjective: text(
        "לנסח משוואה ריבועית מסיטואציה ולפתור.",
        "Write a quadratic from a situation and solve it.",
        "صياغة معادلة تربيعية من موقف وحلها.",
      ),
      body: text(
        "שטח מלבן הוא 48. האורך גדול ב־2 מהרוחב.\n\nx(x + 2) = 48, כלומר x² + 2x − 48 = 0. הרוחב 6 והאורך 8.",
        "A rectangle has area 48. The length is 2 more than the width.\n\nx(x + 2) = 48, so x² + 2x − 48 = 0. The width is 6 and the length is 8.",
        "مساحة مستطيل 48. الطول يزيد عن العرض بـ 2.\n\nx(x + 2) = 48 أي x² + 2x − 48 = 0. العرض 6 والطول 8.",
      ),
      masteryRule: {
        type: "experience_complete",
        passingCriterion: text("רוחב 6 ואורך 8", "Width 6 and length 8", "العرض 6 والطول 8"),
      },
    },
    {
      blockId: "blk_qeq_remediation_007",
      type: "practice",
      concept: "quadratic_remediation",
      title: text("תרגול תיקון", "Another pass", "جولة تقوية"),
      learningObjective: text(
        "לחזק חישוב D ונוסחה לפני חזרה להערכה.",
        "Rebuild D and the formula before the check opens again.",
        "تقوية حساب D والقانون قبل العودة إلى الفحص.",
      ),
      body: text(
        "ל־x² − 6x + 9 = 0 מתקבל D = 0 ושורש כפול x = 3.\n\nל־x² − x − 6 = 0 השורשים הם 3 ו־−2.\n\nאחרי הרף שעל הקשת — חוזרים להערכה, לא קופצים ליישום.",
        "For x² − 6x + 9 = 0, D = 0 and the double root is x = 3.\n\nFor x² − x − 6 = 0 the roots are 3 and −2.\n\nOnce this path's return edge is met, the check opens again. The word problem does not.",
        "في x² − 6x + 9 = 0 يكون D = 0 والجذر المضاعف x = 3.\n\nفي x² − x − 6 = 0 الجذران 3 و −2.\n\nبعد شرط العودة على هذا المسار يُفتح الفحص من جديد، لا المسألة.",
      ),
      masteryRule: {
        type: "practice_threshold",
        minCorrect: 2,
        total: 3,
        passingCriterion: text("לפחות 2 מתוך 3", "At least 2 of 3", "2 من 3 على الأقل"),
      },
    },
  ],
  edges: [
    { edgeId: "e_001", from: "blk_qeq_intro_001", to: "blk_qeq_disc_002", relationship: "sequence", condition: null },
    { edgeId: "e_002", from: "blk_qeq_disc_002", to: "blk_qeq_formula_003", relationship: "sequence", condition: null },
    { edgeId: "e_003", from: "blk_qeq_formula_003", to: "blk_qeq_practice_004", relationship: "prerequisite", condition: null },
    {
      edgeId: "e_004",
      from: "blk_qeq_practice_004",
      to: "blk_qeq_assess_005",
      relationship: "prerequisite",
      condition: { mastery: "practice_threshold_met" },
    },
    {
      edgeId: "e_005",
      from: "blk_qeq_assess_005",
      to: "blk_qeq_experience_006",
      relationship: "sequence",
      condition: { mastery: "assessment_passed" },
    },
    {
      edgeId: "e_006",
      from: "blk_qeq_intro_001",
      to: "blk_qeq_formula_003",
      relationship: "optional",
      condition: { note: "skip the discriminant only if it is already mastered" },
    },
    {
      edgeId: "e_007",
      from: "blk_qeq_assess_005",
      to: "blk_qeq_remediation_007",
      relationship: "branch",
      condition: { mastery: "assessment_failed" },
    },
    {
      edgeId: "e_008",
      from: "blk_qeq_remediation_007",
      to: "blk_qeq_assess_005",
      relationship: "sequence",
      condition: { mastery: "remediation_practice_met" },
    },
  ],
};

/**
 * A second path on purpose: only sequence and one prerequisite, no fail branch.
 * The same learner rules recommend a different next step because the edges differ.
 */
export const LINEAR: PathVersion = {
  schemaVersion: "0.1.0",
  pathId: "path_linear_he_hs_001",
  versionId: "ver_lin_draft_001",
  version: 1,
  status: "draft",
  contentLanguage: "he",
  name: text("משוואות לינאריות", "Linear equations", "المعادلات الخطية"),
  description: text(
    "דרך קצרה בלי ענף כישלון. הצעד הבא הוא פשוט הבלוק הראשון שעדיין פתוח.",
    "A short path with no fail branch. The next step is simply the first block this path still has open.",
    "مسار قصير بلا فرع رسوب. الخطوة التالية هي أول خطوة ما زالت مفتوحة على هذا المسار.",
  ),
  goal: text(
    "לפתור ax + b = c ולהעביר אגפים.",
    "Solve ax + b = c and move terms across.",
    "حل ax + b = c ونقل الحدود.",
  ),
  blocks: [
    {
      blockId: "blk_lin_intro_001",
      type: "explanation",
      concept: "linear_equation_definition",
      title: text("משוואה ממעלה ראשונה", "A first-degree equation", "معادلة من الدرجة الأولى"),
      learningObjective: text("לזהות ax + b = c.", "Recognize ax + b = c.", "تمييز ax + b = c."),
      body: text(
        "במשוואה לינארית אין x². מעבירים איברים ומחלקים במקדם של x, כשהוא אינו אפס.",
        "A linear equation has no x². Move terms, then divide by the coefficient of x when it is not zero.",
        "المعادلة الخطية بلا x². تُنقل الحدود ثم يُقسم على معامل x إذا لم يكن صفراً.",
      ),
      masteryRule: {
        type: "view_and_confirm",
        passingCriterion: text("אישור ההגדרה", "Confirm the definition", "تأكيد التعريف"),
      },
    },
    {
      blockId: "blk_lin_practice_002",
      type: "practice",
      concept: "linear_practice",
      title: text("תרגול העברת אגפים", "Practice moving terms", "تدريب نقل الحدود"),
      learningObjective: text("לפתור שתי משוואות לינאריות.", "Solve two linear equations.", "حل معادلتين خطيتين."),
      body: text(
        "3x + 1 = 10 נותן x = 3.\n\n2x − 4 = 8 נותן x = 6.",
        "3x + 1 = 10 gives x = 3.\n\n2x − 4 = 8 gives x = 6.",
        "3x + 1 = 10 يعطي x = 3.\n\n2x − 4 = 8 يعطي x = 6.",
      ),
      masteryRule: {
        type: "practice_threshold",
        minCorrect: 2,
        total: 2,
        passingCriterion: text("שתי התשובות נכונות", "Both answers correct", "الإجابتان صحيحتان"),
      },
    },
    {
      blockId: "blk_lin_check_003",
      type: "assessment",
      concept: "linear_check",
      title: text("בדיקה קצרה", "A short check", "فحص قصير"),
      learningObjective: text("לפתור משוואה אחת בלי רמז.", "Solve one equation with no hint.", "حل معادلة واحدة بلا تلميح."),
      body: text("5x − 3 = 12. התשובה x = 3.", "5x − 3 = 12. The answer is x = 3.", "5x − 3 = 12. الجواب x = 3."),
      masteryRule: {
        type: "assessment_pass",
        minCorrect: 1,
        total: 1,
        passingCriterion: text("תשובה נכונה", "A correct answer", "إجابة صحيحة"),
      },
    },
  ],
  edges: [
    { edgeId: "e_lin_001", from: "blk_lin_intro_001", to: "blk_lin_practice_002", relationship: "sequence", condition: null },
    {
      edgeId: "e_lin_002",
      from: "blk_lin_practice_002",
      to: "blk_lin_check_003",
      relationship: "prerequisite",
      condition: { mastery: "practice_threshold_met" },
    },
  ],
};

export const PATHS: PathVersion[] = [QUADRATIC, LINEAR];

/** This learner failed the quadratic check, so that path's branch is the next step. */
export const QUADRATIC_PROGRESS: ProgressMap = {
  blk_qeq_intro_001: progressFor("passed"),
  blk_qeq_disc_002: progressFor("passed"),
  blk_qeq_formula_003: progressFor("passed"),
  blk_qeq_practice_004: progressFor("passed", "practice_threshold_met"),
  blk_qeq_assess_005: progressFor("failed", "assessment_failed"),
  blk_qeq_experience_006: progressFor("not_started"),
  blk_qeq_remediation_007: progressFor("incomplete"),
};

/** The same learner, on the linear path, is simply mid-practice. There is no fail branch to follow. */
export const LINEAR_PROGRESS: ProgressMap = {
  blk_lin_intro_001: progressFor("passed"),
  blk_lin_practice_002: progressFor("incomplete"),
  blk_lin_check_003: progressFor("not_started"),
};

export const SEED_PROGRESS: Record<string, ProgressMap> = {
  [QUADRATIC.pathId]: QUADRATIC_PROGRESS,
  [LINEAR.pathId]: LINEAR_PROGRESS,
};

export function blankProgress(ids: string[]): ProgressMap {
  return Object.fromEntries(ids.map((id) => [id, progressFor("not_started")]));
}
