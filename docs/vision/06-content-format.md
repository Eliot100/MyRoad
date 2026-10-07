# 06 · פורמט התוכן (JSON של דרך), גרסה 2

המקור הקובע הוא `packages/core/src/myroad_core/content/schema.py`. המסמך הזה מסביר אותו. כל קובץ ישן נשאר תקין, כי כל השדות החדשים הם אופציונליים.

## מה חדש בגרסה 2
| שדה | איפה | מה זה | כלל |
|---|---|---|---|
| `group_ids` | דרך | קהל היעד | `grade3`, `agent`, `adult` (מבוגרים מאפס), `psychometric` |
| `subject` | דרך | נושא | נוסף `hebrew` (לחלק המילולי בפסיכומטרי) |
| `estimated_minutes` | דרך | זמן משוער | 1 עד 1200 (20 שעות) |
| `prerequisite_path_ids` | דרך | דרכים שצריך לסיים קודם | מתחיל ב-`path_`, לא הדרך עצמה, בלי כפילויות; במפה הדרך מוצגת נעולה עד שהן הושלמו |
| `score` | דרך | חלק בציון מאוחד | `{"group_id": "psychometric_800", "part_id": "quantitative", "weight": 1}`. החלקים הם `quantitative`, `verbal`, `english`, `writing` |
| `kind` | שלב | למה השלב קיים | `understanding` (הבנה ראשונה) או `review` (תרגול חוזר אחרי זמן) |
| `review_topic_ids` | שלב | נושאים שהחזרה מערבבת | מותר רק כש-`kind` הוא `review`. צריך `topics[]` מפורש, וכל נושא חייב להופיע לפני הנושא שמכיל את השלב |

## סוגי שלבים, רשימה אחת
`NODE_TYPES` בסכמה הוא הרשימה היחידה. `NODE_STAGE` ממפה אותה לסוגי השלבים של הבונה (explanation, practice, check, experience), ו-`NODE_BLOCK` ממפה אותה לסוגי הבלוקים של ה-store. מי שצריך סוג שלב מייבא משם ולא מגדיר רשימה משלו.

## בדיקות בין קבצים
`check_prerequisites(paths)` מחזירה רשימת בעיות: דרישת קדם לדרך שלא קיימת, או מעגל. ה-CI של `MyRoad-content` צריך להריץ אותה על כל הקבצים יחד.

## דוגמה קצרה
```json
{
  "id": "path_math_zero_to_equation",
  "subject": "math",
  "group_ids": ["adult"],
  "estimated_minutes": 600,
  "topics": [
    {"id": "t_order", "titles": {"he": "סדר פעולות"}, "node_ids": ["n1", "n2"]},
    {"id": "t_neg", "titles": {"he": "מספרים שליליים"}, "node_ids": ["n3", "n4"]},
    {"id": "t_mix1", "titles": {"he": "חזרה מעורבת"}, "node_ids": ["n5"]}
  ],
  "nodes": [
    {"id": "n5", "type": "practice", "kind": "review", "review_topic_ids": ["t_order", "t_neg"], "...": "..."}
  ]
}
```
