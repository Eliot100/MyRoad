# תוכנית עבודה: אליוט + SuperGrok

עודכן: 20.10.2026 (שעון ישראל).

**הפוקוס עכשיו:** ממשק הלומד (זרימת לומד, מפת דרך, נגן שלבים, קטלוג, בית, הגדרות), כך שלומד יעבור דרך שלמה מתחילה ועד סוף. ושתי דרכי פיילוט כ-JSON סטטי ב-MyRoad-content: אנגלית מאפס למבוגרים ומתמטיקה 4 יחידות.

## החלטות של אליוט מ-20.10

- אליוט לא מטפל ב-Cloudflare כרגע. אין פיצ'רים של סוכן או מודל כרגע: בונה הדרכים עם המודל, קריאות למודל, ו-reuse-check (#72) נדחו.
- עבודת אבטחה מושהית כי עוד אין מוצר עובד. בוט Cyber security מושהה. PR #66 ו-#53 נדחו, בלי rebase עכשיו.
- בוטים פעילים: MyRoad PM, UI, MyRoad Content, Dev (CI ובדיקות רק כשצריך).
- מושהים עד הודעה חדשה: Cyber security, MyRoad Backend, Algo, MLOps, Data Scientist, QA, Budy, Path Builder, UX, Researcher.
- רציפות: שגרת התוכנית היומית רצה כל יום ב-09:10 שעון ישראל (גם בסופ"ש). היא נותנת לבוטים הפעילים את ה-issue הבא שלהם גם כשאליוט לא פעיל, ופונה לאליוט רק להחלטות.

## מצב היום (20.10)

- מוזג מאז 15.10: PR #81 (קטלוג: גיבוי לשפת ההסבר של הדרך, #70) ו-PR #82 (רענון STATUS.md).
- PR פתוח ב-MyRoad: רק #66 (אבטחה, נדחה).
- ב-MyRoad-content אין PR או issue פתוחים.
- שני קבצי הפיילוט עוד לא קיימים: `adult/path_english_zero_to_sentences.json` ו-`adult/path_math_bagrut_4_units.json`.

## איך משתמשים

1. בוחרים משימה לפי הסדר בסעיף "סדר מומלץ".
2. פותחים צ'אט חדש ב-SuperGrok, מצרפים את הקבצים שברשימה "קבצי קלט" (או מדביקים את הקישורים ה-raw; שני הריפו ציבוריים, אז SuperGrok יכול לקרוא אותם ישירות).
3. מעתיקים את הפרומפט מהבלוק כמו שהוא.
4. מחזירים את התוצאה לפי השורה "לאן הפלט הולך": PR (בריפו המתאים), תגובה ב-issue, או הדבקה בצ'אט ל-frank כשהבוטים חוזרים.

**בדיקה מקומית של קובץ JSON לפני PR** (חמש דקות, חוסך סבב CI):
```bash
git clone https://github.com/Eliot100/MyRoad.git
git clone https://github.com/Eliot100/MyRoad-content.git
pip install -e "MyRoad/packages/core[dev,api]"
cp ~/Downloads/<file>.json MyRoad-content/adult/
python MyRoad-content/scripts/validate_paths.py
cd MyRoad/packages/core && CONTENT_DIR=../../../MyRoad-content pytest -q
```
אם יש שגיאה, מדביקים אותה כמו שהיא חזרה ל-SuperGrok באותו צ'אט ומבקשים קובץ מתוקן.

**פתיחת PR** (לכל פלט שהולך לריפו):
```bash
git checkout -b eliot/<issue>-<short-name>
git add <files> && git commit -m "<title> (#<issue>)"
git push -u origin HEAD
gh pr create --fill --body "Closes #<issue>"
gh pr merge --auto --squash
```
בריפו MyRoad הבדיקות הן `core-tests` ו-`validate-freeze-json`. בריפו MyRoad-content הבדיקה היא `validate`. auto-merge ממזג כשהן ירוקות.

---

## משימות לאליוט

| # | משימה | מה זה משחרר | זמן משוער |
|---|-------|-------------|-----------|
| א1 | **להריץ ב-SuperGrok את פרומפט ס1 (אנגלית)** ולהדביק את הפלט: PR ב-MyRoad-content, או הדבקה בצ'אט ל-frank. | דרך פיילוט ראשונה באנגלית. | 30 עד 60 דק' |
| א2 | **להריץ ב-SuperGrok את פרומפט ס2 (מתמטיקה 4 יחידות)** ולהדביק את הפלט באותה דרך. | דרך פיילוט במתמטיקה. | 30 עד 60 דק' |
| א3 | **לנסות את זרימת הלומד** מקצה לקצה (בית, קטלוג, מפת דרך, נגן שלבים, סיום) ולכתוב משוב קצר ב-issue או בצ'אט. | ה-UI מתקן את מה שבאמת מפריע. | 20 דק' |
| א4 | **להחליט על שאלות מוצר פתוחות** כשהשגרה היומית שואלת. | הבוטים הפעילים לא נתקעים. | לפי הצורך |

---

## משימות לסופר גרוק

מסודרות לפי הפוקוס: קודם דרכי הפיילוט, אחר כך עזרה בטקסטים ובאפיון ל-UI. אף אחת לא צריכה מודל בתוך המוצר.

קיצורים לקישורים:
- `R` = `https://raw.githubusercontent.com/Eliot100/MyRoad/main/`
- `C` = `https://raw.githubusercontent.com/Eliot100/MyRoad-content/main/`

### ס1. דרך אנגלית למבוגרים: מאפס למשפטים בסיסיים

- **למה:** ה-POC (החלטה D1, אבן דרך 5 ב-04) הוא מאפס לבגרות במתמטיקה **ובאנגלית**. למתמטיקה למבוגרים יש כבר שתי דרכים; לאנגלית למבוגרים אין אף אחת. זה הפער הגדול ביותר בתוכן.
- **issues קשורים:** אין issue פתוח. מבוסס על D1, אבן דרך 5 ב-[04](vision/04-architecture-and-roadmap.md), ושאלה פתוחה 8 ב-[05](vision/05-decisions-log.md).
- **קבצי קלט:**
  - `packages/core/src/myroad_core/content/schema.py`: `R` + `packages/core/src/myroad_core/content/schema.py`
  - `packages/core/src/myroad_core/content/locale_rules.py`: `R` + `packages/core/src/myroad_core/content/locale_rules.py`
  - `docs/vision/06-content-format.md`: `R` + `docs/vision/06-content-format.md`
  - דוגמה לאנגלית (ילדים): `C` + `grade3/path_grade3_english_hello.json`
  - דוגמה למבוגרים: `C` + `adult/path_math_zero_to_equation.json`
- **פלט:** קובץ JSON אחד שעובר `schema.py` ו-`locale_rules.py`.
- **לאן:** PR ב-MyRoad-content, קובץ `adult/path_english_zero_to_sentences.json`. בדיקה: `validate`.

```text
אתה כותב תוכן לימודי למוצר MyRoad. המטרה: דרך למידה אחת למבוגרים דוברי עברית שמתחילים אנגלית מאפס, הצעד הראשון בדרך לבגרות באנגלית. ההסברים בעברית, המילים והמשפטים הנלמדים באנגלית.

קרא קודם את הקבצים האלה (כולם ציבוריים):
- הסכמה הקובעת: https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/src/myroad_core/content/schema.py
- כללי שפה לדרכי אנגלית: https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/src/myroad_core/content/locale_rules.py
- הסבר הפורמט: https://raw.githubusercontent.com/Eliot100/MyRoad/main/docs/vision/06-content-format.md
- דוגמת אנגלית קצרה (לילדים, אותו מבנה שדות): https://raw.githubusercontent.com/Eliot100/MyRoad-content/main/grade3/path_grade3_english_hello.json
- דוגמת דרך ארוכה למבוגרים (מבנה נושאים, חזרה מעורבת, בדיקה מסכמת): https://raw.githubusercontent.com/Eliot100/MyRoad-content/main/adult/path_math_zero_to_equation.json

שדות הדרך:
- "id": "path_english_zero_to_sentences", "subject": "english", "group_ids": ["adult"], "explain_locale": "he", "content_locale": "en", "emoji": אחד, "estimated_minutes": בין 300 ל-600, בלי "grade", בלי prerequisite_path_ids.
- "titles" ו-"blurbs" עם he ו-en (ar אם אתה בטוח בניסוח).

כללים שהבדיקות אוכפות (כל שדה שלא בסכמה נדחה):
- type של שלב: learn, practice, check, speak, celebrate. לכל שלב "id" ייחודי, "title", ו-"body_he" בעברית.
- בכל practice, check ו-speak חייב להיות "body_content" (המילה או המשפט באנגלית שנלמדים בשלב) ו/או "speak_text" (מה שמושמע באנגלית). גם ב-learn כדאי.
- body_he נשאר בעברית. אל תכתוב בו משפט אנגלי שלם בלי עברית סביבו; את האנגלית שם ב-body_content.
- feedback_ok ו-feedback_try בעברית (מילה אנגלית בודדת בתוכם מותרת).
- בכל practice ו-check: "choices" עם 3 אפשרויות (id: a, b, c, label באנגלית או בעברית לפי השאלה), "correct" שמצביע על אחת מהן, feedback_ok, feedback_try.
- "kind": "understanding" לשלבי הבנה ראשונה, "review" לחזרה. "review_topic_ids" רק עם kind "review", ורק לנושאים שמופיעים לפני הנושא שמכיל את השלב.
- כל node_id בנושא הוא id של שלב קיים. אין ids כפולים. כל שלב שייך לנושא אחד.

מבנה ותוכן:
- 8 עד 12 נושאים (topics), כל אחד: שלב learn קצר, ואחריו 2 עד 5 תרגילים קצרים. אחרי כל 3 נושאים נושא "חזרה מעורבת" עם 2 עד 4 שלבי review. בסוף נושא "בדיקה מסכמת" שמערבב הכל, ושלב celebrate.
- התקדמות מאפס: האלפבית וצלילים בסיסיים, ברכות ונימוס, אני/אתה והפועל to be, מספרים, שאלות בסיסיות (What, Where, Who), Present Simple, there is / there are, תיאור אנשים ומקומות, קריאת משפט קצר ושאלת הבנה. מילים שימושיות למבוגרים (עבודה, קניות, תחבורה, בריאות).
- אפשרויות שגויות לפי טעויות נפוצות של דוברי עברית (סדר מילים, to be חסר, s בגוף שלישי, תרגום מילולי).
- עברית פשוטה, משפטים קצרים, בלי מקף ארוך (em dash).

הפלט: שורה אחת מחוץ ל-JSON שמסכמת על מה התבססת, ואז קובץ JSON אחד תקין בבלוק קוד אחד, מוכן להדבקה כ-adult/path_english_zero_to_sentences.json. בלי הערות בתוך הבלוק.
```

### ס2. דרך מתמטיקה 4 יחידות (הפרומפט הקיים, מעודכן)

- **למה:** ממשיך את שרשרת המתמטיקה למבוגרים (`path_math_zero_to_equation` ← `path_math_bagrut_3_units` ← 4 יחידות). אבן דרך 5.
- **issues קשורים:** [content#4](https://github.com/Eliot100/MyRoad-content/issues/4) (3 יחידות, נסגר ב-content#5) כבסיס; אין issue ל-4 יחידות.
- **קבצי קלט:** `C` + `adult/path_math_bagrut_3_units.json`, `R` + `packages/core/src/myroad_core/content/schema.py`, `R` + `docs/vision/06-content-format.md`.
- **פלט:** קובץ JSON אחד שעובר `schema.py`.
- **לאן:** PR ב-MyRoad-content, קובץ `adult/path_math_bagrut_4_units.json`. בדיקה: `validate` (כולל `check_prerequisites`, כלומר `path_math_bagrut_3_units` חייב להיות קיים, והוא קיים).

הפרומפט המלא נמצא ב-[supergrok-next.md, פרומפט 1](supergrok-next.md#פרומפט-1-דרך-מתמטיקה-4-יחידות-json-מוכן-ל-pr). מוסיפים בסופו את השורות האלה:

```text
תוספות:
- קרא את הקובץ המלא כאן ולא רק את הקטע: https://raw.githubusercontent.com/Eliot100/MyRoad-content/main/adult/path_math_bagrut_3_units.json
- הוסף "explain_locale": "he" ו-"content_locale": "he".
- לכל שלב "id" ייחודי באנגלית קטנה עם קו תחתון, וכל שלב שייך לנושא אחד בדיוק.
- כוון ל-40 עד 70 שלבים ול-estimated_minutes בין 600 ל-1200.
- אם הפלט ארוך מדי לתשובה אחת, כתוב אותו בשני חלקים לפי בקשה ("המשך"), באותו בלוק JSON אחד שאני אחבר.
```

### ס3. טקסטים ואפיון לזרימת הלומד

- **למה:** ה-UI הוא הפוקוס. SuperGrok יכול לנסח טקסטים במסכים ולמצוא חורים בזרימה, בלי מודל במוצר.
- **קבצי קלט:** `R` + `docs/vision/02-product-spec.md`, ותבניות המסכים ב-`packages/core/src/myroad_core/ui/templates/`.
- **פלט:** רשימת טקסטים מוצעים לכל מסך (בית, קטלוג, מפת דרך, נגן שלבים, הגדרות, סיום), ורשימת פערים בזרימה.
- **לאן:** תגובה ב-issue של UI שהשגרה היומית פתחה, או הדבקה בצ'אט ל-frank.

```text
אתה עוזר לצוות UI של MyRoad, פלטפורמת למידה שבה לומד עובר דרך של נושאים ושלבים. קרא:
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/docs/vision/02-product-spec.md
- את התבניות בתיקייה https://github.com/Eliot100/MyRoad/tree/main/packages/core/src/myroad_core/ui/templates
המטרה: לומד מבוגר עובר דרך שלמה מתחילה ועד סוף בלי להיתקע.
כתוב בעברית: (1) לכל מסך (בית, קטלוג, מפת דרך, נגן שלבים, הגדרות, סיום): הטקסטים הקיימים שכדאי לשנות, והצעה קצרה לכל אחד. (2) עד 7 פערים בזרימה, לכל אחד: מה קורה, מה צריך לקרות, תנאי קבלה בשורה. עברית פשוטה, משפטים קצרים, בלי מקף ארוך (em dash). אל תמציא קבצים שלא ראית.
```

### ס4. מזכר החלטות: שאלות פתוחות באפיון

- **למה:** ב-[05-decisions-log.md](vision/05-decisions-log.md) יש 10 שאלות פתוחות, וכמה מהן חוסמות עבודה שתחזור כשהבוטים חוזרים (תפקידים, גרסה חדשה באמצע דרך, אוצר מילים לשלבים, היקף הבגרות). רק אליוט מחליט, אבל SuperGrok יכול להכין את ההחלטה.
- **issues קשורים:** [#27](https://github.com/Eliot100/MyRoad/issues/27) (תפקידים), [#26](https://github.com/Eliot100/MyRoad/issues/26), שאלות 1, 4 עד 9 ב-05.
- **קבצי קלט:** `R` + `docs/vision/01-vision.md`, `R` + `docs/vision/02-product-spec.md`, `R` + `docs/vision/03-agent-and-publish.md`, `R` + `docs/vision/04-architecture-and-roadmap.md`, `R` + `docs/vision/05-decisions-log.md`.
- **פלט:** מזכר Markdown בעברית: לכל שאלה 2 עד 3 אפשרויות, המלצה, ומה משתנה בקוד.
- **לאן:** אליוט מחליט (משימה א4), ואז PR ב-MyRoad שמוסיף שורות D חדשות ל-`docs/vision/05-decisions-log.md` לפי הכללים ב-[README](vision/README.md).

```text
אתה עוזר למנהל מוצר להחליט. המוצר: MyRoad, פלטפורמת למידה עם דרכים (גרף נושאים ושלבים), מצב בנייה ומצב למידה, וסוכן שרשאי לפרסם. קרא את כל מסמכי החזון:
https://raw.githubusercontent.com/Eliot100/MyRoad/main/docs/vision/01-vision.md
https://raw.githubusercontent.com/Eliot100/MyRoad/main/docs/vision/02-product-spec.md
https://raw.githubusercontent.com/Eliot100/MyRoad/main/docs/vision/03-agent-and-publish.md
https://raw.githubusercontent.com/Eliot100/MyRoad/main/docs/vision/04-architecture-and-roadmap.md
https://raw.githubusercontent.com/Eliot100/MyRoad/main/docs/vision/05-decisions-log.md

עדכון מצב מעבר למסמכים: אימות בעלות על אימייל (קוד חד-פעמי) ואימות ל-/tools/* כבר מוזגו ל-main (PR #46, #47). שער פרסום עם ולידציה (שאלה 4) נמצא ב-PR #48. אוצר מילים אחד לסוגי שלבים כבר קיים ב-schema.py (NODE_TYPES), ונשארה רק השאלה אם "הסבר" (learn) נשאר סוג נפרד.

כתוב מזכר החלטות בעברית, עד 2 עמודים, על השאלות הפתוחות 1, 4, 5, 6, 7, 8, 9 ברשימה בסוף 05-decisions-log.md, ועל issue #26 ("להוציא את ה-AI ממסלול המוצר", שנשען על החלטה S2 שהוחלפה). לכל שאלה:
### <מספר>. <השאלה בשורה אחת>
- **אפשרויות:** 2 עד 3, שורה לכל אחת
- **המלצה:** אחת, ולמה, ב-2 שורות
- **מה משתנה בקוד או בתוכן:** שמות קבצים מהמסמכים בלבד, בלי להמציא
- **שורה מוכנה ליומן:** | D<מספר> | <תאריך ריק> | <ההחלטה> | אליוט |
בסוף: סדר מומלץ להחלטה (מה חוסם הכי הרבה עבודה). עברית פשוטה, בלי מקף ארוך (em dash). מה שלא ידוע, כתוב "פתוח" ואל תנחש.
```

## נדחה

לא עובדים על זה עכשיו. הטקסט נשמר לפעם הבאה.

- **אליוט: חיבור Cloudflare AI Gateway.** לפי [packages/core/docs/cloudflare-ai-gateway.md](../packages/core/docs/cloudflare-ai-gateway.md). נדחה עד שיש מוצר עובד.
- **אליוט: החלטות אבטחה** (PR #66, #53, #62). נדחו, בלי rebase עכשיו.
- **ס4 הקודם (#70):** כבר תוקן ומוזג ב-PR #81.

### (נדחה) reuse-check, reuse-check: ספרייה ל-JSON תקין ממודל שפה (#72)

- **למה:** Path Builder צריך לייצר נושא שלם עם המודל ולתקן פלט לא תקין אוטומטית. המחקר לא צריך את המפתח, ואחרי החיבור של א2 Path Builder יכול להתחיל מיד.
- **issues קשורים:** [#72](https://github.com/Eliot100/MyRoad/issues/72).
- **קבצי קלט:** טקסט ה-issue #72 (להדביק), `R` + `packages/core/src/myroad_core/agent_builder/generator.py`, `R` + `packages/core/src/myroad_core/agent_builder/parsing.py`, `R` + `packages/core/pyproject.toml`.
- **פלט:** תגובת Markdown קצרה.
- **לאן:** תגובה ב-[#72](https://github.com/Eliot100/MyRoad/issues/72) (`gh issue comment 72 --body-file reply.md`).

```text
אני צריך המלצה על ספרייה קיימת ומתוחזקת ב-Python שמוציאה ממודל שפה (Grok דרך API תואם OpenAI, דרך Cloudflare AI Gateway) JSON שעובר ולידציה מול סכמת Pydantic v2 קיימת, עם ניסיון חוזר שמחזיר למודל את שגיאות הוולידציה.
ההקשר: הסכמה היא ContentPath ב-https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/src/myroad_core/content/schema.py. הקוד הנוכחי שולח response_format json_object ומפרסר ידנית: https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/src/myroad_core/agent_builder/generator.py ו-https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/src/myroad_core/agent_builder/parsing.py. התלויות: https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/pyproject.toml
דרישות: עובד בתוך FastAPI, מעט תלויות, רישיון מתירני, עברית וערבית עוברות שלמות, עובד מול endpoint תואם OpenAI שאינו OpenAI (base_url של Cloudflare), בלי לשלוח מפתח ספק מהקוד שלנו.
השווה עד 3 אפשרויות (למשל Instructor, PydanticAI, Outlines, או structured outputs / json_schema של ה-SDK עצמו). לכל אחת: רישיון, תאריך הגרסה האחרונה, סימני תחזוקה (commits, issues פתוחים, מתחזקים), אבטחה (CVE ידועים, תלויות כבדות), והאם היא עובדת עם endpoint תואם OpenAI שאינו OpenAI. בדוק את הנתונים בזמן אמת, עם קישורים. הוסף דוגמת קוד של עד 20 שורות שמראה איך ההמלצה עוטפת את ContentPath עם retry.
סיים בהמלצה אחת. כתוב את כל התשובה כתגובת Markdown קצרה שאפשר להדביק כמו שהיא ב-issue עם התווית reuse-check, בפורמט:
Bot: researcher (via SuperGrok)
**המלצה:** ...
| ספרייה | רישיון | גרסה אחרונה | תחזוקה | אבטחה | קישור |
**למה:** 3 שורות
**סיכונים:** 2 שורות
**דוגמה:** בלוק קוד קצר
```

### (נדחה) אפיון: תכנון דרך מהיר בלי מודל (#16, #23, #22)

- **למה:** לפי #16 "המהירות של תכנון החומר היא המוצר". מסך שמרכיב דרך מנושאים ושלבים קיימים עובד בלי Cloudflare, ונותן למצב הבנייה ערך גם כשאין מודל. היום יש רק בונה עם סוכן (`/add-path`) ובדיקת "דרך קיימת" (PR #45).
- **issues קשורים:** [#16](https://github.com/Eliot100/MyRoad/issues/16), [#23](https://github.com/Eliot100/MyRoad/issues/23), [#22](https://github.com/Eliot100/MyRoad/issues/22).
- **קבצי קלט:** טקסט #16, #22, #23 (להדביק), `R` + `docs/vision/02-product-spec.md`, `R` + `docs/vision/03-agent-and-publish.md`, `R` + `docs/vision/06-content-format.md`, `R` + `packages/core/docs/agent-path-builder.md`, `R` + `packages/core/src/myroad_core/agent_builder/suggest.py`, `R` + `packages/core/src/myroad_core/agent_builder/completeness.py`.
- **פלט:** אפיון Markdown בעברית.
- **לאן:** תגובה ב-[#16](https://github.com/Eliot100/MyRoad/issues/16). אחרי שאליוט מאשר, PM מפרק למשימות כשהבוטים חוזרים.

```text
אתה כותב אפיון מוצר בעברית ל-MyRoad, פלטפורמת למידה שבה דרך היא גרף של נושאים ושלבים. קרא קודם:
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/docs/vision/02-product-spec.md
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/docs/vision/03-agent-and-publish.md
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/docs/vision/06-content-format.md
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/docs/agent-path-builder.md
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/src/myroad_core/agent_builder/suggest.py
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/src/myroad_core/agent_builder/completeness.py

המשימות (טקסט מקורי):
#16 תכנון דרך מהיר, בלי מודל. מה: מסך שבו מרכיבים דרך מנושאים ושלבים קיימים, ושומרים טיוטה. למה: המהירות של תכנון החומר היא המוצר. לא: קריאה ל-Grok או ל-Cloudflare.
#23 קודם דרך קיימת. מה: כשמבקשים ללמוד נושא, המערכת מציגה דרכים שכבר פורסמו לאותו סיווג לפני שפותחים טיוטה חדשה. לא: סוכן שמתכנן לבד.
#22 סיווג נושאים רקורסיבי. מה: כל דרך משויכת לתחום על ולנושאים הספציפיים שמתחתיו. לא: ספריית בגרויות מלאה.

כתוב אפיון אחד, עד 2 עמודים, בפורמט:
Bot: pm (via SuperGrok)
## מטרה ומדד הצלחה (למשל: מורה מרכיב דרך של 3 נושאים ו-12 שלבים בפחות מ-10 דקות)
## זרימת משתמש (צעדים ממוספרים: חיפוש, "דרך קיימת קודם", בחירת נושאים ושלבים מדרכים מפורסמות, שינוי סדר, שמירת טיוטה, בדיקת שלמות, פרסום)
## מה כבר קיים בקוד ואפשר לעשות בו שימוש חוזר (שמות קבצים ופונקציות מהקבצים שקראת בלבד, בלי להמציא)
## מודל נתונים: איך שלב שנלקח מדרך אחרת נשמר (העתקה או הפניה), ומה קורה כשהדרך המקורית מקבלת גרסה חדשה. תן המלצה אחת וסיבה
## סיווג רקורסיבי: הצעת מבנה JSON מינימלי לתחום ותת-נושא, תואם לסכמה הקיימת (שדות אופציונליים בלבד)
## מחוץ להיקף
## שאלות פתוחות לאליוט (עד 5, כל אחת עם המלצה)
## פירוק למשימות (4 עד 7 שורות, לכל אחת: צוות אחראי מתוך Backend, UI, UX, Path Builder, PM, ותנאי קבלה בשורה אחת)
עברית פשוטה, משפטים קצרים, בלי מקף ארוך (em dash). אל תמציא קבצים או פונקציות שלא ראית.
```

### (נדחה) מדד יעילות למידה ללומד (#17, #25)

- **למה:** החלטה D1: "שיפור מדיד". שאלה פתוחה 9: אין עדיין מדדים רשמיים. הנתונים כבר נשמרים (`learner_attempts`: משך, שלבים, לחיצות נכונות ושגויות, אחוז שליטה), חסרים הגדרה וחישוב. אליוט הוא דאטה סיינטיסט, אז קל לו לבדוק את ההגדרה.
- **issues קשורים:** [#17](https://github.com/Eliot100/MyRoad/issues/17), [#25](https://github.com/Eliot100/MyRoad/issues/25).
- **קבצי קלט:** טקסט #17 ו-#25, `R` + `packages/core/src/myroad_core/learner_progress.py`, `R` + `packages/core/src/myroad_core/ui/templates/stats.html`, `R` + `docs/vision/02-product-spec.md`.
- **פלט:** (א) הגדרת מדד ב-Markdown, (ב) מודול Python טהור + בדיקות pytest.
- **לאן:** (א) תגובה ב-[#17](https://github.com/Eliot100/MyRoad/issues/17). (ב) PR ב-MyRoad: `packages/core/src/myroad_core/metrics/__init__.py`, `packages/core/src/myroad_core/metrics/efficiency.py`, `packages/core/tests/test_efficiency_metric.py`, גוף `Refs #17` (לא Closes, כי עוד אין תצוגה במסך).

```text
You are a data scientist and Python engineer working on MyRoad, a learning platform. Read first:
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/src/myroad_core/learner_progress.py (SQLite tables learner_progress and learner_attempts)
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/src/myroad_core/ui/templates/stats.html (the end-of-path stats screen)
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/docs/vision/02-product-spec.md (section 7, measurement)

Issues:
#17 Learning efficiency metric: per learner, time spent versus mastery of a topic, shown on the end-of-path screen. Efficiency is the metric, not marking a card as done. Not a full school dashboard.
#25 Learner measurement: a log of time, attempts and mastery result per learner and per step. The basis for efficiency and improvement, no automatic A/B. No A/B experiments on minors at this stage.

Deliver two things.

Part A, a short metric definition in Hebrew (Markdown, at most one page), starting with the line "Bot: data-scientist (via SuperGrok)":
- The formula for a per-attempt and per-path efficiency score using only columns that exist today in learner_attempts / learner_progress (name them exactly). Explain units and range.
- How to handle edge cases: zero duration, abandoned attempts, very long idle time (propose a cap), repeated attempts on the same path, review steps.
- What is missing for a per-step log (#25): propose the minimal new table or columns, with types, without writing a migration.
- 3 sanity checks Eliot can run on real data.

Part B, code:
- `packages/core/src/myroad_core/metrics/efficiency.py`: pure functions (no DB access, no FastAPI), typed, docstrings, standard library only. Input: plain dicts or a small dataclass mirroring learner_attempts rows. Functions: `attempt_efficiency(row) -> float | None`, `path_efficiency(rows) -> dict` (summary for one user and path: best, latest, trend), `capped_duration_sec(row, cap_sec=...)`.
- `packages/core/src/myroad_core/metrics/__init__.py` exporting them.
- `packages/core/tests/test_efficiency_metric.py`: pytest tests for normal cases and every edge case from Part A.
Output each file in its own code block with the path as the first line comment. Do not modify existing files.
```

---

## סדר ל-3 ימים

**יום 1 (20.10)**
1. א1: ס1 (אנגלית) ב-SuperGrok, בדיקה מקומית, PR ב-MyRoad-content.
2. UI ממשיך ב-issue הבא שלו לפי השגרה היומית.

**יום 2 (21.10)**
1. א2: ס2 (מתמטיקה 4 יחידות), בדיקה מקומית, PR.
2. ס3: טקסטים ופערים בזרימת הלומד.

**יום 3 (22.10)**
1. א3: לעבור דרך שלמה כלומד ולתת משוב.
2. ס4: מזכר החלטות, ואליוט מחליט על מה שחוסם.

השגרה היומית ב-09:10 ממשיכה לחלק issues לבוטים הפעילים גם בלי אליוט.
