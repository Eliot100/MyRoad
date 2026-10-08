# מומלץ לאליוט ב-SuperGrok

> תוכנית עבודה מלאה לאליוט ול-SuperGrok (7 משימות, סדר ל-3 ימים): [work-plan-eliot-supergrok.md](work-plan-eliot-supergrok.md)

משימה שכדאי להוריד מהבוטים עכשיו: טיוטת תוכן לדרך מתמטיקה 4-5 יחידות, בפורמט ה-JSON של MyRoad-content. מעתיקים את הפרומפט ל-Grok, ומחזירים את התוצאה כמו שכתוב בסוף.

## פרומפט 1: דרך מתמטיקה 4 יחידות (JSON מוכן ל-PR)

```text
אתה כותב תוכן לימודי למוצר MyRoad. המטרה: דרך למידה אחת למבוגרים, הכנה לבגרות במתמטיקה 4 יחידות לפי התוכנית החדשה בישראל, שממשיכה את הדרך הקיימת "מתמטיקה 3 יחידות, התוכנית החדשה".

הפורמט הוא בדיוק הפורמט של הקובץ הקיים:
https://github.com/Eliot100/MyRoad-content/blob/main/adult/path_math_bagrut_3_units.json
הסכמה הקובעת: https://github.com/Eliot100/MyRoad/blob/main/packages/core/src/myroad_core/content/schema.py
קרא את שניהם לפני שאתה כותב. הנה קטע אמיתי מקוצר מהקובץ:

{
  "id": "path_math_bagrut_3_units",
  "titles": {"he": "מתמטיקה 3 יחידות, התוכנית החדשה", "en": "Math 3 units, the new program"},
  "blurbs": {"he": "הכנה לבגרות 3 יחידות לפי שלושת האשכולות של התוכנית החדשה: חברה ומדע, התמצאות במישור ובמרחב, ופיננסי כלכלי. ...", "en": "..."},
  "subject": "math",
  "group_ids": ["adult"],
  "emoji": "📊",
  "estimated_minutes": 360,
  "prerequisite_path_ids": ["path_math_zero_to_equation"],
  "topics": [
    {"id": "t_line", "titles": {"he": "כלים: הקו הישר", "en": "Tools: the straight line"}, "emoji": "📏", "node_ids": ["line_learn", "line_slope"]},
    {"id": "t_review_tools", "titles": {"he": "חזרה מעורבת: כלים", "en": "Mixed review: tools"}, "emoji": "🔁", "node_ids": ["rt_slope"]},
    {"id": "t_final", "titles": {"he": "בדיקה מסכמת", "en": "Final mixed check"}, "emoji": "🏁", "node_ids": ["fin_done"]}
  ],
  "nodes": [
    {"id": "line_learn", "type": "learn", "kind": "understanding", "title": "שיפוע הוא קצב שינוי", "body_he": "בקו y = mx + b, המספר m הוא השיפוע: בכמה y משתנה כש-x עולה ב-1. ..."},
    {"id": "line_slope", "type": "practice", "kind": "understanding", "title": "שיפוע משתי נקודות", "body_he": "מה השיפוע של הקו שעובר דרך (1, 2) ו-(3, 8)?",
     "choices": [{"id": "a", "label": "3"}, {"id": "b", "label": "1/3"}, {"id": "c", "label": "6"}], "correct": "a",
     "feedback_ok": "נכון. (8 − 2) ÷ (3 − 1) = 6 ÷ 2 = 3.", "feedback_try": "שינוי ב-y למעלה, שינוי ב-x למטה."},
    {"id": "rt_slope", "type": "practice", "kind": "review", "review_topic_ids": ["t_line"], "title": "...", "body_he": "...", "choices": [...], "correct": "a", "feedback_ok": "...", "feedback_try": "..."},
    {"id": "fin_done", "type": "celebrate", "title": "סיימת את הדרך", "body_he": "..."}
  ]
}

כללים (הסכמה דוחה כל שדה אחר):
- id של הדרך: "path_math_bagrut_4_units". prerequisite_path_ids: ["path_math_bagrut_3_units"]. group_ids: ["adult"]. subject: "math". estimated_minutes עד 1200.
- type של שלב: learn, practice, check, celebrate. בכל שלב title ו-body_he. בכל practice ו-check יש choices (3 אפשרויות, id a/b/c), correct, feedback_ok, feedback_try.
- kind: "understanding" לשלב הבנה ראשון, "review" לחזרה. review_topic_ids מותר רק עם kind "review", ורק לנושאים שמופיעים לפני הנושא שמכיל את השלב.
- כל node_id בנושא חייב להיות id של שלב שקיים. אין ids כפולים.
- מבנה כמו בקובץ 3 יחידות: לכל נושא שלב learn קצר ואחריו 2 עד 5 תרגילי בחירה קצרים. חזרה מעורבת בסוף כל חלק, ובדיקה מסכמת שמערבבת הכל, ושלב celebrate בסוף.
- תוכן: נושאי 4 יחידות בתוכנית החדשה (למשל חשבון דיפרנציאלי ואינטגרלי בסיסי, סדרות, טריגונומטריה במשולש, גאומטריה אנליטית, הסתברות וסטטיסטיקה), עם שאלות יישומיות בסגנון הבגרות. ציין בתחילת התשובה, בשורה אחת מחוץ ל-JSON, על איזה מקור לתוכנית הסתמכת.
- עברית פשוטה למבוגרים, משפטים קצרים, בלי מקפים ארוכים (em dash). אפשרויות שגויות לפי טעויות נפוצות. בדוק כל חישוב.
- titles ו-blurbs בעברית ובאנגלית.

הפלט: קובץ JSON אחד ותקין, בבלוק קוד אחד, מוכן להדבקה כ-adult/path_math_bagrut_4_units.json ב-PR. בלי הסברים בתוך הבלוק.
```

## פרומפט 2: reuse-check, JSON תקין לפי סכמה ממודל שפה

```text
אני צריך המלצה על ספרייה קיימת ומתוחזקת ב-Python שמוציאה ממודל שפה (Grok דרך API תואם OpenAI, דרך Cloudflare AI Gateway) JSON שעובר ולידציה מול סכמת Pydantic v2 קיימת, עם ניסיון חוזר כשהוולידציה נכשלת. השווה 3 עד 5 אפשרויות (למשל Instructor, Outlines, PydanticAI, structured outputs של ה-SDK עצמו). לכל אחת: רישיון, תאריך הגרסה האחרונה, סימני תחזוקה (commits, issues פתוחים, מספר מתחזקים), אבטחה (CVE ידועים, תלויות כבדות), והאם היא עובדת עם endpoint תואם OpenAI שאינו OpenAI. בדוק את הנתונים בזמן אמת, עם קישורים.
סיים בהמלצה אחת. כתוב את כל התשובה כתגובת Markdown קצרה שאפשר להדביק כמו שהיא ב-issue עם התווית reuse-check, בפורמט:
Bot: researcher (via SuperGrok)
**המלצה:** ...
| ספרייה | רישיון | גרסה אחרונה | תחזוקה | אבטחה | קישור |
**למה:** 3 שורות
**סיכונים:** 2 שורות
```

## איך מחזירים תוצאות
מדביקים את התשובה בצ'אט ל-frank, או פותחים PR (פרומפט 1, ב-MyRoad-content) או מדביקים תגובה ב-issue של reuse-check (פרומפט 2, היום [MyRoad#72](https://github.com/Eliot100/MyRoad/issues/72)).
