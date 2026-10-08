# תוכנית עבודה: אליוט + SuperGrok

עודכן: 08.10.2026, 09:30 (שעון ישראל). משימה: [#77](https://github.com/Eliot100/MyRoad/issues/77).

## למה התוכנית הזו קיימת

מכסת השימוש של צוות הבוטים כמעט נגמרה (88% ומעלה אתמול). כדי ש-MyRoad ימשיך להתקדם למוצר עובד גם בלי הבוטים, העבודה מתחלקת לשניים:
- **אליוט**: רק מה שאליוט יכול לעשות או להחליט (מיזוגים, Cloudflare, החלטות מוצר).
- **SuperGrok** (הצ'אט של אליוט, מחוץ למערכת הבוטים): כתיבת תוכן, מחקר, אפיונים, וקוד שאליוט מדביק ומפרסם בעצמו.

מצב היום (08.10 בבוקר): PR #46 ו-#47 מוזגו ל-main. PR #48 פתוח, מעודכן מול main, בדיקות ירוקות, מחכה לאישור אבטחה ולמיזוג. PR #62 (משימות #49, #50) פתוח עם קונפליקטים מול main, ואבטחה קבעה: אין פריסה ציבורית לפני שהוא מתמזג. PR #66 (משימה #53) פתוח. Path Builder ו-Researcher (#72) מחכים לחיבור Cloudflare.

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

לפי סדר השפעה.

| # | משימה | מה זה משחרר | זמן משוער |
|---|-------|-------------|-----------|
| א1 | **למזג את [PR #48](https://github.com/Eliot100/MyRoad/pull/48)** (שער פרסום, #42). #46 ו-#47 כבר ב-main (בדוק: `git log --oneline -5` מראה את שניהם). ב-#48 לוודא שיש אישור של Cyber security ושהבדיקות ירוקות, ואז Merge. | סוגר את שרשרת האימות (#40 עד #42). אחריו #62 ו-#66 נבנים על main נקי. | 10 דק' |
| א2 | **לחבר את Cloudflare AI Gateway.** לפי [packages/core/docs/cloudflare-ai-gateway.md](../packages/core/docs/cloudflare-ai-gateway.md): ליצור Gateway, לשמור את מפתח xAI ב-Cloudflare Secrets Store (BYOK), ולהגדיר בשרת רק את `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_GATEWAY_ID` ואם צריך `CLOUDFLARE_AI_GATEWAY_TOKEN`. המפתח לא נכנס לריפו ולא לצ'אט. בדיקה: `/add-path` לא מציג "gateway is not configured". | Path Builder (דרך אמיתית מקצה לקצה עם המודל), Researcher #72, ו-#51, #52, #54, #74 שמסומנים "מחכה ל-Cloudflare". | 30 עד 45 דק' |
| א3 | **להחליט על [PR #62](https://github.com/Eliot100/MyRoad/pull/62)** (#49, #50: קודים של 8 ספרות, הגבלות לפי אימייל ו-IP, CAPTCHA). יש בו קונפליקטים מול main אחרי מיזוג #47. החלטה: לאשר את הכיוון ולבקש מ-Backend לפתור קונפליקטים כשהבוטים חוזרים, או לדחות. | פריסה ציבורית (אבטחה חוסמת עד שהוא מתמזג), ו-UI #59 (שדה הקוד). | 15 דק' |
| א4 | **להחליט על [PR #66](https://github.com/Eliot100/MyRoad/pull/66)** (#53: אין שינוי מצב ב-GET, Origin עם פורטים ברירת מחדל). הוא כבר מכוון ל-main. לוודא בדיקות ירוקות ואישור אבטחה, ולמזג או להשאיר בהמתנה. | סוגר חור CSRF לפני פריסה. | 10 דק' |
| א5 | **לסגור או לעדכן את [#26](https://github.com/Eliot100/MyRoad/issues/26)** ("השימוש ב-AI נעצר"). לפי יומן ההחלטות ההחלטה הזו הוחלפה (S2 הוחלפה ב-D5, D6), אבל ה-issue עדיין פתוח ומבלבל את התכנון. | כיוון ברור לבונה הדרכים ול-#16. | 5 דק' |
| א6 | **לבדוק ולמזג את הפלטים של SuperGrok**: PR תוכן ב-MyRoad-content (משימות ס1, ס2), PR קוד (ס4), ותגובות ב-issues (ס3, ס5, ס6, ס7). | זה מה שמזיז את המוצר בזמן שהבוטים לא עובדים. | 15 עד 30 דק' לכל פלט |
| א7 | **להחליט על השאלות הפתוחות** בעזרת המזכר של ס7, ולפתוח PR שמוסיף שורות ל-[05-decisions-log.md](vision/05-decisions-log.md). | מוריד ניחושים מהבוטים כשהם חוזרים. | 30 דק' |

---

## משימות לסופר גרוק

מסודרות לפי ערך למוצר עובד. אף אחת מהן לא צריכה את מפתח Cloudflare.

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

### ס3. reuse-check: ספרייה ל-JSON תקין ממודל שפה (#72)

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

### ס4. תיקון קוד: שפת גיבוי בקטלוג (#70)

- **למה:** בקטלוג של ה-API, דרך שכתובה רק בעברית מופיעה בערבית ובאנגלית עם גיבוי לאנגלית או ריק. המסכים כבר תוקנו (#58, PR #69); ה-API לא. תיקון קטן, מוגדר היטב, עם בדיקות.
- **issues קשורים:** [#70](https://github.com/Eliot100/MyRoad/issues/70).
- **קבצי קלט:** טקסט ה-issue #70, `R` + `packages/core/src/myroad_core/content/loader.py`, `R` + `packages/core/src/myroad_core/ui/i18n.py`, `R` + `packages/core/tests/test_catalog_locale.py`.
- **פלט:** הפונקציה `apply_catalog_locale` המתוקנת, וקובץ `test_catalog_locale.py` המלא אחרי העדכון.
- **לאן:** PR ב-MyRoad, ענף `eliot/70-catalog-locale-fallback`, גוף `Closes #70`. בדיקה מקומית: `cd MyRoad/packages/core && pytest -q tests/test_catalog_locale.py`, ואז `pytest -q`.

```text
You are fixing a small bug in MyRoad (Python 3.12, FastAPI, Pydantic v2, pytest). Read these files first:
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/src/myroad_core/content/loader.py
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/src/myroad_core/ui/i18n.py
- https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/tests/test_catalog_locale.py

Issue #70: `apply_catalog_locale()` in `content/loader.py` calls `localize_path_chrome(...)` without `source_locale`, so the API catalog in `ar`/`en` falls back to English first. Product rule: missing text falls back to the path's own `explain_locale` (usually Hebrew), not English. The UI screens already do this.

Change: pass `source_locale=card.get("explainLocale")` (check the exact card key name and the `localize_path_chrome` signature in the files; adapt if it differs) and keep every other behaviour the same.

Acceptance:
1. A Hebrew-only path requested with `ar` or `en` returns the Hebrew title and blurb, not English and not empty.
2. A path that has an `ar` or `en` title still returns that title for that locale.
3. Existing tests keep passing.

Output exactly:
1. The full new `apply_catalog_locale` function in one code block (drop-in replacement).
2. The full updated `packages/core/tests/test_catalog_locale.py` in one code block, adding tests for both acceptance cases. Use the fixtures and helpers already used in that file; do not invent fixtures that don't exist there.
3. One line: the commit message, "Catalog: fall back to the path's explain locale, not English (#70)".
Do not change any other file. No explanations inside code blocks.
```

### ס5. אפיון: תכנון דרך מהיר בלי מודל (#16, #23, #22)

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

### ס6. מדד יעילות למידה ללומד (#17, #25)

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

### ס7. מזכר החלטות: שאלות פתוחות באפיון

- **למה:** ב-[05-decisions-log.md](vision/05-decisions-log.md) יש 10 שאלות פתוחות, וכמה מהן חוסמות עבודה שתחזור כשהבוטים חוזרים (תפקידים, גרסה חדשה באמצע דרך, אוצר מילים לשלבים, היקף הבגרות). רק אליוט מחליט, אבל SuperGrok יכול להכין את ההחלטה.
- **issues קשורים:** [#27](https://github.com/Eliot100/MyRoad/issues/27) (תפקידים), [#26](https://github.com/Eliot100/MyRoad/issues/26), שאלות 1, 4 עד 9 ב-05.
- **קבצי קלט:** `R` + `docs/vision/01-vision.md`, `R` + `docs/vision/02-product-spec.md`, `R` + `docs/vision/03-agent-and-publish.md`, `R` + `docs/vision/04-architecture-and-roadmap.md`, `R` + `docs/vision/05-decisions-log.md`.
- **פלט:** מזכר Markdown בעברית: לכל שאלה 2 עד 3 אפשרויות, המלצה, ומה משתנה בקוד.
- **לאן:** אליוט מחליט (משימה א7), ואז PR ב-MyRoad שמוסיף שורות D חדשות ל-`docs/vision/05-decisions-log.md` לפי הכללים ב-[README](vision/README.md).

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

---

## סדר מומלץ

**יום 1 (היום, 08.10)**
1. א1: למזג את #48 (אחרי אישור אבטחה). 10 דק'.
2. א2: לחבר Cloudflare AI Gateway. 30 עד 45 דק'. זה הדבר היחיד שרק אליוט יכול לעשות ושמשחרר הכי הרבה.
3. ס1 ב-SuperGrok (דרך אנגלית), בדיקה מקומית, PR ב-MyRoad-content.
4. ס3 במקביל (reuse-check), תגובה ב-#72.
5. א5: לסגור או לעדכן את #26.

**יום 2 (09.10)**
1. א3 ו-א4: החלטות על #62 ו-#66.
2. ס2 (מתמטיקה 4 יחידות), בדיקה מקומית, PR.
3. ס4 (#70), PR קוד קטן. לוודא ש-`core-tests` ירוק.
4. ס7 (מזכר החלטות), לקרוא בערב.

**יום 3 (10.10)**
1. א7: להחליט על השאלות הפתוחות ולפתוח PR ל-05-decisions-log.md.
2. ס5 (אפיון תכנון בלי מודל), תגובה ב-#16.
3. ס6 (מדד יעילות), תגובה ב-#17 ו-PR עם המודול.
4. א6: לעבור על כל ה-PR הפתוחים של SuperGrok ולמזג מה שירוק.

כשהבוטים חוזרים: frank קורא את התגובות ב-#16, #17, #72 ואת יומן ההחלטות, ומחלק משימות לפי הסדר שאליוט קבע.
