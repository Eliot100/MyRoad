# וריאנטים של שלב

תאריך: 2026-11-01. בעלים: MyRoad PM. סטטוס: החלטת מוצר (D19, issue #161).

מספור: 06 תפוס על ידי [06-מודל-התוכן.md](06-מודל-התוכן.md), לכן המסמך הזה הוא 10.
הקוד כבר תומך בבחירת וריאנט בזמן ריצה: [decisions/0003](../decisions/0003-step-variants.md) (`variant_of`, `variant_when`, `select_variants`). המסמך הזה קובע את כללי המוצר מעל המנגנון.

## שני צירים

כל לומד בוחר שתי הגדרות (`learners.audio_on`, `learners.writing_on`):

- **שמע או בלי שמע.** בלי שמע: אין השמעה ואין דיבור. כל מה שנשמע מוצג כטקסט, כל מה שנאמר הופך לבחירה או להקלדה.
- **כתיבה או בלי כתיבה.** בלי כתיבה: אין הקלדה חופשית. תשובה כתובה הופכת לבחירה מתוך שלוש.

ארבעה צירופים: `a1w0` (ברירת מחדל), `a0w0`, `a1w1`, `a0w1`. כלל: כל שלב שעובר לסיום דרך עובד בכל ארבעת הצירופים, או ע"י הבסיס עצמו או ע"י וריאנט. וריאנט מקבל את ה-blockId של הבסיס, לכן ההתקדמות נספרת אותו דבר.

## לפי סוג שלב

סוגים בסכמה (`NodeType` ב-`schema.py`) ובהחלטות #155 ו-#171.

| סוג | עם שמע | בלי שמע | עם כתיבה | בלי כתיבה | איך נבדק |
|---|---|---|---|---|---|
| `learn` | טקסט + `audio_url` אופציונלי | טקסט בלבד. השמע אף פעם לא נושא תוכן שאין בטקסט | זהה | זהה | לא נבדק, נספר בצפייה |
| `celebrate` | זהה | זהה | זהה | זהה | לא נבדק |
| `practice` | שאלה יכולה להישמע (`audio_url`) | אותה שאלה כתמליל. שאלה שבנויה על צליל ("איזו אות נשמעת") מקבלת וריאנט טקסט | וריאנט `fill_in`: מקלידים את התשובה | שלוש אפשרויות ותשובה אחת | `correct`: בחירה = id, `fill_in` = מחרוזת מנורמלת |
| `check` | כמו `practice` | כמו `practice` | כמו `practice` | כמו `practice` | כמו `practice`, נספר לסף `pass_max_mistakes` |
| `fill_in` (#155) | כמו `practice` | כמו `practice` | הבסיס: הקלדה | וריאנט: שלוש אפשרויות, אחת מהן ה-`correct` | השוואת מחרוזת אחרי נרמול (בערבית: התעלמות מחרכאת, אליף/המזה, תא מרבוטה, אליף מקצורה, #171) |
| `free_text` (#155) | אפשר תשובה בעל פה, בדיקה עצמית | תשובה כתובה | הבסיס: חיבור/תשובה חופשית | וריאנט: בחירת הפתיחה/הנימוק/הסיום הטובים מתוך שלוש | עם כתיבה: לפי `rubric`, אליוט בודק. בלי כתיבה: `correct` |
| `speak` | אומרים את `speak_text`, משווים ל-`expected_answer` בבדיקה עצמית (אין ציון אוטומטי ב-v1) | וריאנט `practice`: בוחרים את המשפט הנכון מתוך שלוש | זהה | זהה | עם שמע: בדיקה עצמית. בלי שמע: `correct` |
| `piano_keys`, `rhythm` | מקלדת/קצב עם צליל | אותו תרגיל בלי צליל, משוב חזותי | זהה | זהה | השוואת `keys`/`pattern` |
| ניתוח פועל בארבעה חלקים (#171) | זהה | זהה | הקלדת ארבעת החלקים | בחירה בכל חלק | לכל חלק `correct` |

## כלל חריגים

רק שלב **מתקדם מאוד שנדרש רק לבחינה** רשאי להיות בלי וריאנט. הוא מסומן `exam_required: true` ונרשם בטבלה כאן עם סיבה. לכל חריג יש וריאנט **הכנה** בלי שמע (`variant_of` + `counts_toward_finish: false`) שלא נספר לסיום הדרך. שלב חריג עצמו גם לא חוסם סיום דרך ללומד בלי שמע.

| חריג | דרך | סיבה | וריאנט הכנה |
|---|---|---|---|
| בחינה בעל פה ערבית 018387, כל שלבי ה-oral | arabic_bagrut5 (שלבי בחינה) | הבחינה עצמה בעל פה. אין דרך להוכיח דיבור בלי דיבור. החלטת PM ב-#161 ו-#171 | בחירת תגובה נכונה + תמליל, לא נספר לסיום |
| `ex_t_oral_say` (חריג מוחלט) | path_english_bagrut5_08_exam | סימולציית החלק בעל פה של בגרות אנגלית | כנ"ל |

כל חריג חדש: שורה בטבלה הזו באותו PR שמוסיף אותו. בלי שורה, הוא תקלה.

## שינוי JSON מינימלי (הכול אופציונלי, דרכי v2 נשארות תקינות)

שדות שכבר הוחלטו ולא מוגדרים כאן מחדש: #155 (`route_path_id`, `pass_max_mistakes`, `free_text`+`rubric`, `review_step_ids`, `expected_answer`, `passages`/`passage_id`, `fill_in`, `audio_url`, `cefr_target`) ו-#171 (`lang`/`dir`, `register`, `transliteration_he`, `exam_required`, `variant_of`).

מה המסמך הזה מוסיף או מחייב:

| שדה | רמה | סוג | משמעות | מקור |
|---|---|---|---|---|
| `variant_of` | שלב | string | id של הבסיס באותה דרך. משותף עם #171, קיים בקוד (0003) | 0003, #171 |
| `variant_when` | שלב | `{audio: bool\|null, writing: bool\|null}` | לאיזה צירוף הווריאנט. קיים בקוד | 0003 |
| `exam_required` | שלב | bool | חריג מותר. משותף עם #171 | #171 |
| `counts_toward_finish` | שלב | bool, ברירת מחדל true | false רק בווריאנט הכנה של חריג | חדש כאן, היחיד |

כללי ולידציה (ל-Dev, בלי שדה חדש): שלב עם `audio_url` או `type: speak` חייב וריאנט עם `audio: false`, אלא אם `exam_required: true`. שלב `free_text` או `fill_in` חייב וריאנט עם `writing: false`, אלא אם `exam_required: true`. `counts_toward_finish: false` מותר רק על וריאנט של שלב `exam_required`.

דוגמה:

```json
{"id": "ex_t_oral_say", "type": "speak", "exam_required": true, "speak_text": "I agree with Nira because customers should choose the fruit.", "expected_answer": "I agree with Nira because ..."},
{"id": "ex_t_oral_say__a0", "type": "practice", "variant_of": "ex_t_oral_say", "variant_when": {"audio": false, "writing": null}, "counts_toward_finish": false,
 "body_he": "איזו תשובה מתאימה לבחינה בעל פה?", "choices": [{"id": "a", "label": "I agree with Nira because customers should choose the fruit."}, {"id": "b", "label": "Nira fruit yes."}, {"id": "c", "label": "Because because."}], "correct": "a"}
```

## בדיקת סדרת אנגלית 5 יחידות

מקור: `Eliot100/MyRoad-content` main @ `3802fe7`, קבצי `adult/path_english_bagrut5_00..08.json` (9 דרכים, 225 שלבים). אין בסדרה אף `variant_of`, `audio_url`, `fill_in` או `free_text`. רוב השלבים הם `learn`/`practice`/`check` טקסט עם שלוש אפשרויות, והם עובדים בכל ארבעת הצירופים בלי וריאנט. חסרים 11 וריאנטים: 7 בלי שמע, 4 עם כתיבה.

| דרך | id | סוג | וריאנט חסר | תיקון מוצע |
|---|---|---|---|---|
| 00_placement | `plc_t_letters_chk` | check | בלי שמע (שואל "איזו אות נשמעת" ואין שמע בכלל) | לשכתב לבסיס טקסט ("באיזו אות נגמרת המילה dog?") והגרסה הנשמעת היא וריאנט `audio: true` עם `audio_url` |
| 00_placement | `plc_t_speak_say` | speak | בלי שמע | וריאנט `practice`: בחירת "I am ready." מתוך שלוש |
| 07_literature_oral | `lit_t_speak_s1` | speak | בלי שמע | וריאנט `practice`: בחירת תגובה לסיפור |
| 07_literature_oral | `lit_t_speak_s2` | speak | בלי שמע | וריאנט `practice`: בחירת נימוק עם because |
| 07_literature_oral | `lit_t_turn_s3` | speak | בלי שמע | וריאנט `practice`: בחירת משפט אישי שמחובר לסיפור |
| 07_literature_oral | `lit_t_turn_s4` | speak | בלי שמע | וריאנט `practice`: בחירת משפט על השיר |
| 08_exam | `ex_t_oral_say` | speak | בלי שמע | חריג מוחלט: `exam_required: true` + וריאנט הכנה בלי שמע שלא נספר |
| 06_module_g | `g_t_essay_open` | practice | עם כתיבה | וריאנט `free_text`: כתבו משפט פתיחה, `rubric` |
| 06_module_g | `g_t_body_p1` | practice | עם כתיבה | וריאנט `free_text`: כתבו סיבה אחת |
| 06_module_g | `g_t_close_p1` | practice | עם כתיבה | וריאנט `free_text`: כתבו משפט סיום |
| 06_module_g | `g_final_check` | check | עם כתיבה | וריאנט `free_text`: חיבור קצר 120 עד 140 מילים לפי `writing_rubric.md` |

הערה: שלבי `practice` רגילים אחרים לא חייבים וריאנט כתיבה. בלי כתיבה הם הבסיס, ועם כתיבה מותר להציג אותם כמו שהם. וריאנטי כתיבה ב-06 נדרשים כי מודול G בוחן כתיבה.

## Next slice: מבדק -> דרך -> תרגול

**Core flow (הזרימה המרכזית):** לומד חדש עושה מבדק (placement), מקבל דרך מומלצת אחת לפי התוצאה, ונכנס ישר לתרגול הראשון שלה, עם הגדרות השמע והכתיבה שלו.

**Owner:** Dev (בוט אחד). UI ו-Content לא משויכים בפרוסה הזו.

קריטריוני קבלה:
1. מבדק אנגלית 5 יחידות (`path_english_bagrut5_00_placement`) מסתיים ב-`POST /api/placement/result` שמחזיר `recommended_road_id` לפי `route_path_id`/`placement_route`. בדיקה: טסט שמריץ תוצאה בכל band ומקבל את הדרך הנכונה.
2. לחיצה אחת אחרי תוצאת המבדק פותחת את השלב האינטראקטיבי הראשון של הדרך המומלצת. בדיקה: טסט API/UI של הזרימה מקצה לקצה.
3. בכל אחד מארבעת הצירופים (`a1w0`, `a0w0`, `a1w1`, `a0w1`) הזרימה עוברת בלי שלב שדורש שמע או כתיבה שהלומד כיבה. בדיקה: טסט שעובר על המבדק ועל הדרך הראשונה בכל צירוף.
4. ולידציה בקוד מתריעה על שלב `speak`/`audio_url` בלי וריאנט `audio: false` ובלי `exam_required`. בדיקה: טסט יחידה עם דרך תקינה ודרך שבורה.
5. דרכי v2 קיימות נטענות בלי שינוי. בדיקה: כל הטסטים הקיימים עוברים.

## החלטות פתוחות לאליוט

- ~~האם `ex_t_oral_say` הוא חריג כמו 018387~~ הוחלט: כן. חריגי בחינה בעל פה מקבלים וריאנט הכנה בלי שמע.
