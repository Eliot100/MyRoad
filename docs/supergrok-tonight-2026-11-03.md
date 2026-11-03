# SuperGrok הלילה, 3.11.2026

אליוט, אלה 6 משימות ל-SuperGrok להלילה, לפי סדר עדיפות. מריצים כל אחת בצ'אט חדש: מעתיקים את הבלוק כמו שהוא, ואם הוא נעצר כותבים continue. אם יש זמן רק לחלק, 1, 3 ו-4 הכי חשובות.
כשמשימה מסתיימת, מדביקים את כל הפלט (בלוקי הקוד ורשימת DOUBTS) לfrank, ו-frank פותח את ה-PR ומחבר את הקבצים לבנייה.

| # | משימה | issue | קובץ יעד | זמן |
|---|---|---|---|---|
| 1 | אנגלית: דוגמאות פתורות לדרכים 01 עד 04 | #219 | MyRoad-content: scripts/examples/english_bagrut5_01_zero.py, english_bagrut5_02_present.py, english_bagrut5_03_time.py, english_bagrut5_04_accuracy.py | 60 עד 90 דק' |
| 2 | אנגלית: דוגמאות פתורות לדרכים 05 עד 08 | #219 | MyRoad-content: scripts/examples/english_bagrut5_05_module_e.py, _06_module_g.py, _07_literature_oral.py, _08_exam.py | 60 עד 90 דק' |
| 3 | ערבית שלב 1: דוגמאות פתורות, תרגול נוסף ומילון | #220 | MyRoad-content: scripts/examples/arabic_bagrut5_01_script.py, scripts/extra_practice/arabic_bagrut5_01_script.json, scripts/glossary/arabic_stage1.json | 90 עד 120 דק' |
| 4 | אנגלית: תרגול נוסף עם פתרון מלא, דרכים 01 עד 04 | #213, #215 | MyRoad-content: scripts/extra_practice/english_bagrut5_0{1..4}_<name>.json | 90 עד 120 דק' |
| 5 | אנגלית: שתי סימולציות בחינה ושאלות קשות לפי תחום | #221 | MyRoad-content: scripts/exam_sim/english_bagrut5_08_exam.json | 90 עד 120 דק' |
| 6 | טקסטים במסך: שכתוב עברית, אנגלית וערבית למסכי הלומד | #218, #233 (איכות טקסט UX) | MyRoad: packages/core/locales/he.json, en.json, ar.json (רק מפתחות ששונו) | 60 עד 90 דק' |

## 1. אנגלית: דוגמאות פתורות לדרכים 01 עד 04 (זמן משוער: 60 עד 90 דק')

- issue: #219
- קובץ יעד: MyRoad-content: scripts/examples/english_bagrut5_01_zero.py, english_bagrut5_02_present.py, english_bagrut5_03_time.py, english_bagrut5_04_accuracy.py

````text
You are writing learning content for MyRoad, a Hebrew-UI app that teaches adults from the general population English up to the Israeli 5-unit bagrut. Product rule: every topic shows at least 3 worked examples BEFORE practice. Your job: write the worked examples for every topic of English paths 01 to 04 (GitHub issue Eliot100/MyRoad#219).

OUTPUT FORMAT. Worked examples live in Python files, one per path, at MyRoad-content/scripts/examples/<path_name>.py. A build script inserts each row as a "learn" step right after the topic's first learn step. This is the real file that already exists (path 01, topic t_letters is DONE, do not redo it):

```python
"""Worked examples shown as learn steps after a topic's learn step, before its practice.
Keyed by topic id: list of (title, body_he, body_content)."""
E = {
    "t_letters": [
        ("דוגמה: שם וצליל", "לאות יש שם ויש צליל. השם של b הוא בי, והצליל שלה הוא ב, כמו בתחילת bed.", "b: bed, bag, bus"),
        ("דוגמה: צליל ראשון", "אומרים dog לאט: d, o, g. הצליל הראשון הוא d, לכן המילה נפתחת באות d.", "dog: d o g"),
        ("דוגמה: צליל אחרון", "אומרים cup לאט: c, u, p. הצליל האחרון הוא p, לכן המילה נגמרת באות p.", "cup: c u p"),
    ],
}
```

Each row is a tuple of exactly 3 strings:
- title: Hebrew, starts with "דוגמה: ", at most 5 words.
- body_he: Hebrew, 1 to 3 short sentences that SOLVE one concrete example step by step (what we look at, what rule applies, the result). Not a restatement of the rule.
- body_content: the English sentence(s) being taught, short. English only, no Hebrew.

TOPICS (path id | Hebrew title, then topic id (title): the existing learn text and English content). Review topics are excluded on purpose:
## path_english_bagrut5_01_zero | מאפס
- t_letters (אותיות): learn='אומרים את שם האות, ואז קוראים מילה קצרה.' content='A, B, C.' learn_steps=4 practice=2
- t_be (am is are): learn='I הולך עם am. He, she, it עם is. You, we, they עם are.' content='I am a student.' learn_steps=1 practice=2
- t_not (שלילה): learn='שלילה: am not, is not, are not. לא מוסיפים do.' content='She is not late.' learn_steps=1 practice=2
- t_you (you ו we): learn='you, we, they הולכים עם are. לא עם am.' content='You are ready. We are here.' learn_steps=1 practice=2
- t_word (מילה קצרה): learn='קוראים את כל המילה, לא רק את האות הראשונה.' content='sun, map, dog' learn_steps=1 practice=2
- t_sent (משפט): learn='משפט מתחיל באות גדולה ונגמר בנקודה. יש בו מישהו ופועל.' content='I am here.' learn_steps=1 practice=2
## path_english_bagrut5_02_present | הווה ויום יום
- t_simple (Present Simple): learn='הרגל. אחרי he, she, it הפועל מקבל s.' content='She works at home.' learn_steps=1 practice=2
- t_there (there is): learn='יש אחד: there is. יש כמה: there are.' content='There is a book on the desk.' learn_steps=1 practice=2
- t_q (שאלות): learn='שאלה בהווה: Do או Does בהתחלה, והפועל בלי s.' content='Do you live here?' learn_steps=1 practice=2
- t_day (יום רגיל): learn='קטע קצר על יום עבודה. שאלה על הרעיון ושאלה על פרט.' content='Maya works at home. She starts at eight. She drinks water and opens her mail. So' learn_steps=1 practice=2
- t_neg (שלילה בהווה): learn='שלילה: do not או does not, והפועל בלי s.' content='She does not work on Friday.' learn_steps=1 practice=2
- t_freq (תדירות): learn='always ו never באים לפני הפועל העיקרי, ואחרי is.' content='Maya always starts at eight.' learn_steps=1 practice=2
## path_english_bagrut5_03_time | זמן וסיפור
- t_past (Past Simple): learn='אתמול: פועל עם ed, או צורה חריגה כמו went וsaw.' content='Yesterday I walked home.' learn_steps=1 practice=2
- t_fut (עתיד): learn='מחר: will והפועל הבסיסי. תוכנית קרובה: am, is או are, ועוד ing.' content='Tomorrow I will leave early.' learn_steps=1 practice=2
- t_story (סיפור קצר): learn='קראו וזהו את הרעיון ואת ההסקה.' content='Jonah missed the last bus and waited under the pharmacy light. A woman he did no' learn_steps=1 practice=2
- t_irreg (עבר חריג): learn='לא כל עבר הוא ed. go נהיה went. see נהיה saw.' content='Yesterday I went home. I saw the bus.' learn_steps=1 practice=2
- t_ago (מתי): learn='ago מסתכל אחורה. tomorrow מסתכל קדימה. לא מערבבים.' content='I saw her two days ago.' learn_steps=1 practice=2
- t_who (מי ואיפה): learn='who שואל על אדם. where שואל על מקום.' content='Jonah missed the last bus and waited under the pharmacy light. A woman he did no' learn_steps=1 practice=2
## path_english_bagrut5_04_accuracy | דיוק
- t_art (a וthe): learn='a בפעם הראשונה. the כשכבר יודעים על מה מדובר. על דבר כללי ברבים לא שמים מילה בכלל.' content='I saw a bird. The bird was blue. Birds need water.' learn_steps=1 practice=3
- t_perf (זמן פתוח וזמן סגור): learn='have והצורה השלישית כשהזמן עוד פתוח, כמו ever או עד עכשיו. זמן שנגמר, כמו yesterday או 2019, דורש עבר רגיל.' content='I have seen this film. I saw it yesterday.' learn_steps=1 practice=3
- t_if (תנאי ראשון): learn='אחרי if בא הווה. בחלק של התוצאה בא will.' content='If it rains, we will stay home.' learn_steps=1 practice=3
- t_an (an): learn='an לפני צליל תנועה: an apple, an hour. a לפני צליל עיצור: a bird, a university. קובע הצליל, לא האות.' content='I ate an apple.' learn_steps=1 practice=3
- t_order (סדר מילים): learn='נושא, פועל, ואז מושא. תואר בא לפני השם: a red car. never וalways באים לפני הפועל העיקרי.' content='I never drink cold coffee.' learn_steps=1 practice=3
- t_for (for וsince): learn='for עם משך: for two years. since עם נקודת התחלה: since 2020. שניהם באים עם have.' content='I have lived here for two years.' learn_steps=1 practice=3

Rules:
- Exactly 3 examples per topic, except t_letters (skip it). The 3 examples of a topic cover 3 different cases (for t_be: one with I, one with he/she/it, one with you/we/they). The last example of each topic shows the most common mistake and why it is wrong.
- Use only words and grammar taught in this path or earlier paths. Path 01 is real beginners: words of max 5 letters, sentences of max 5 words.
- Reading topics (t_day, t_story, t_who): base examples on the same passage the learn step uses; quote the needed sentence in body_content.
- No example may repeat an existing practice question. Use everyday adult contexts (work, bus, shop, family, health), not school or kids.

HEBREW STYLE RULES (apply to every Hebrew string):
- Simple Hebrew for adults from the general population. Short sentences, plural address (קראו, בחרו), no slang, no childish tone.
- No em dash or en dash (— –). Use a comma or a period instead.
- Explanation text (Hebrew) and target-language tokens (English/Arabic) are kept apart: the Hebrew explanation goes in body_he, the English/Arabic words being taught go in body_content.
- Every fact and every answer must be checked twice. If you are not sure, put the item in the doubts list instead of guessing.

CHECKLIST per item: (1) English is correct and natural; (2) the Hebrew explanation actually solves the example and is correct; (3) level fits the path; (4) 3 different cases per topic, last one = common mistake; (5) no duplicates across all files; (6) tuple has exactly 3 strings, valid Python, Hebrew quotes not breaking strings (use double-quoted Python strings, avoid the " character inside Hebrew, use ״ for abbreviations); (7) no em dash.

Batch = one path (all its topics). TARGET = 4 files, 69 examples total (01: 15 because t_letters is done, 02 to 04: 18 each).

WORK AS A LOOP. Do not stop after the first batch.
1. Generate the next batch (size given below).
2. Self-check every item in the batch against the CHECKLIST below. Write the check as a short table: item id | pass/fail | what was wrong.
3. Fix every failed item and re-check it.
4. Keep a running count. If the count is below TARGET, go back to step 1 with the next batch.
5. When TARGET is reached, do one last pass over ALL items for duplicates and consistency, then print the FINAL OUTPUT exactly as specified: one code block per output file, nothing else inside the blocks. After the blocks, print "DOUBTS:" and a short bullet list (max 10) of items you are not fully sure about, with the reason.
If the chat is cut off, continue from the last finished batch when I write "continue".

FINAL OUTPUT: 4 python code blocks, each starting with a comment line "# file: scripts/examples/<name>.py", containing the docstring and E dict exactly like the example file. File names: english_bagrut5_01_zero.py (keep the existing t_letters rows at the top, unchanged), english_bagrut5_02_present.py, english_bagrut5_03_time.py, english_bagrut5_04_accuracy.py.
````

## 2. אנגלית: דוגמאות פתורות לדרכים 05 עד 08 (זמן משוער: 60 עד 90 דק')

- issue: #219
- קובץ יעד: MyRoad-content: scripts/examples/english_bagrut5_05_module_e.py, _06_module_g.py, _07_literature_oral.py, _08_exam.py

````text
Same task as before, for the harder English paths 05 to 08 of MyRoad (adults, Israeli 5-unit English bagrut, Hebrew UI). GitHub issue Eliot100/MyRoad#219. Product rule: every topic shows at least 3 worked examples BEFORE practice.

OUTPUT FORMAT. One Python file per path at MyRoad-content/scripts/examples/<path_name>.py. A build script inserts each row as a "learn" step after the topic's first learn step. Real example of the format:

```python
"""Worked examples shown as learn steps after a topic's learn step, before its practice.
Keyed by topic id: list of (title, body_he, body_content)."""
E = {
    "t_letters": [
        ("דוגמה: צליל ראשון", "אומרים dog לאט: d, o, g. הצליל הראשון הוא d, לכן המילה נפתחת באות d.", "dog: d o g"),
    ],
}
```

Each row = (title, body_he, body_content): title in Hebrew starting with "דוגמה: " (max 5 words); body_he = 1 to 4 short Hebrew sentences that solve one concrete exam-style example step by step; body_content = the English text being worked on (a short passage line, a question, or a model sentence), English only.

TOPICS (passages are truncated here; full passages are in https://raw.githubusercontent.com/Eliot100/MyRoad-content/main/adult/<path id>.json, read them if you can open links, and quote from them exactly):
## path_english_bagrut5_05_module_e | שאלון E
- t_read (קטע E): learn='קראו פעם אחת בלי לעצור על כל מילה. אחר כך השאלות.' content='When a town moves its market from the square to a closed hall, it solves the rai' learn_steps=1 practice=3
- t_vocab (אוצר מילים): learn='המילה מהמשפט, לא מהמילון לבד.' content='The hall is far from the bus.' learn_steps=1 practice=2
- t_ref (מילת ייחוס): learn='it וthere מצביעים אחורה, לא קדימה אל ניחוש.' content='When a town moves its market from the square to a closed hall, it solves the rai' learn_steps=1 practice=2
- t_detail (פרט): learn='פרט הוא עובדה שכתובה, לא מסקנה שלנו.' content='When a town moves its market from the square to a closed hall, it solves the rai' learn_steps=1 practice=2
- t_infer (הסקה): learn='הסקה נשענת על שתי עובדות בטקסט, לא על ניחוש.' content='When a town moves its market from the square to a closed hall, it solves the rai' learn_steps=1 practice=2
- t_band (מילים מהקטע): learn='חמש מילים מתוך הקטע, במשפט חדש. לא רשימת משרד.' content='The queue was at the loose fruit.' learn_steps=1 practice=2
## path_english_bagrut5_06_module_g | שאלון G
- t_read (קטע G): learn='הכותב לא אומר שהסדנה היא צדקה. הוא אומר שהיא נשארת כשיש חובה ותשלום קטן.' content='Cities tell young people to learn a trade and then act surprised when those peop' learn_steps=1 practice=2
- t_essay (חיבור דעה): learn='120 עד 140 מילים. פתיחה עם דעה, שתי סיבות, ומשפט סיום. לא מתחילים בBecause.' content='In my opinion, a shared workshop should charge a small fee.' learn_steps=1 practice=2
- t_rubric (מחוון): learn='תוכן ושכנוע, ארגון, אוצר מילים, ודיוק. אורך קצר מדי יורד לחוד, לא במקום התוכן.' content='Content, organization, vocabulary, accuracy, and length.' learn_steps=1 practice=2
- t_body (גוף החיבור): learn='אחרי הפתיחה באות שתי סיבות. כל סיבה במשפט שלם, לא ברשימת מילים.' content='A small fee keeps the lease. A duty keeps the skill moving.' learn_steps=1 practice=2
- t_close (סיום): learn='הסיום חוזר לדעה בלי להעתיק את הפתיחה מילה במילה.' content='That is why the room should not be free.' learn_steps=1 practice=2
- t_words (אוצר לחיבור): learn='שלוש מילים מהקטע, לשימוש בחיבור. לא רשימה רשמית.' content='lease, duty, fee' learn_steps=1 practice=2
## path_english_bagrut5_07_literature_oral | ספרות ודיבור
- t_story (סיפור קצר): learn='מי עושה מה, ומה משתנה בסוף. לא צריך את שם המחבר.' content='Jonah missed the last bus and waited under the pharmacy light. A woman he did no' learn_steps=1 practice=2
- t_poem (שיר קצר): learn='חפץ עושה משהו שאדם עושה. זו התמונה, לא חידה עם תשובה אחת.' content='The stair remembers every late key.\nIt does not forgive, and it does not tell.\nI' learn_steps=1 practice=2
- t_speak (דיבור): learn='שלוש פניות: תגובה אישית, סיבה אחת, ומשפט על הטקסט. אומרים, לא קוראים רשימה.' content='I think Jonah is fair because he returns the kindness.' learn_steps=1 practice=0
- t_essay (חיבור על הטקסט): learn='100 עד 120 מילים על הטקסט: מה קורה, מה אתם חושבים, וסיבה מהסיפור. לא ביוגרפיה.' content='Jonah is fair because he leaves the oranges.' learn_steps=1 practice=2
- t_poem2 (שורה): learn="בוחרים שורה ואומרים מה היא עושה, לא מה היא 'באמת אומרת' במשפט אחד סגור." content='The stair remembers every late key.\nIt does not forgive, and it does not tell.\nI' learn_steps=1 practice=2
- t_turn (פנייה שלישית): learn='הפנייה השלישית קושרת אתכם לטקסט במשפט אחד, בלי לקרוא רשימה.' content='The story matters to me because a small gift can come back.' learn_steps=1 practice=0
## path_english_bagrut5_08_exam | בחינה מלאה
- t_mix (קריאה מעורבת): learn='אותן שאלות כמו בשאלונים, על קטע שכבר מהסוג המוכר.' content='When a town moves its market from the square to a closed hall, it solves the rai' learn_steps=1 practice=2
- t_write (חיבור): learn='פתחו בדעה, תנו סיבה מהקטע, וסיימו במשפט אחד. 120 עד 140 מילים כשזה חיבור מלא. כאן בודקים את הצורה.' content='In my opinion, the stall should stay.' learn_steps=1 practice=2
- t_oral (דיבור אחרון): learn='תגובה אישית בלי לקרוא מהדף.' content='I agree with Nira because customers should choose the fruit.' learn_steps=1 practice=0
- t_read2 (הסקה בבחינה): learn='בבחינה ההסקה עדיין חייבת להישען על הקטע.' content='Cities tell young people to learn a trade and then act surprised when those peop' learn_steps=1 practice=2
- t_write2 (אורך ודיוק): learn='בחיבור הדיוק נספר. בקריאה כתיב לבדו לא מוריד. האורך הוא סעיף נפרד.' content='Accuracy counts in the essay. Spelling in a reading answer does not.' learn_steps=1 practice=2
- t_last (משפט אחרון): learn='סוגרים במשפט אחד שאפשר לומר גם בעל פה.' content='I would keep the stall, because the buyers know the fruit.' learn_steps=1 practice=2

Rules:
- Exactly 3 examples per topic. Reading topics (t_read, t_ref, t_detail, t_infer, t_mix, t_read2): each example quotes the exact sentence from the passage and shows how the answer is found in the text (detail = written fact, inference = two facts combined, reference = what the pronoun points back to). Writing topics (t_essay, t_body, t_close, t_write, t_write2, t_last): show a weak sentence, then the improved one, and why. Speaking topics (t_speak, t_turn, t_oral): a model answer of 1 to 2 sentences an adult could say aloud, and why it works.
- Bagrut 5-unit English level (module E and G). Original texts only, never copy real exam passages.
- Do not invent rubric numbers. Use only facts given in the learn text (e.g. 120 to 140 words for the opinion essay in module G, 100 to 120 for the literature essay).

HEBREW STYLE RULES (apply to every Hebrew string):
- Simple Hebrew for adults from the general population. Short sentences, plural address (קראו, בחרו), no slang, no childish tone.
- No em dash or en dash (— –). Use a comma or a period instead.
- Explanation text (Hebrew) and target-language tokens (English/Arabic) are kept apart: the Hebrew explanation goes in body_he, the English/Arabic words being taught go in body_content.
- Every fact and every answer must be checked twice. If you are not sure, put the item in the doubts list instead of guessing.

CHECKLIST per item: (1) quote matches the passage exactly; (2) the reasoning is correct and leads to one answer; (3) level fits; (4) the 3 examples per topic differ; (5) no duplicates across files; (6) valid Python tuple of 3 strings, no stray " inside strings; (7) no em dash.

Batch = one path. TARGET = 4 files, 72 examples (6 topics x 3 per path).

WORK AS A LOOP. Do not stop after the first batch.
1. Generate the next batch (size given below).
2. Self-check every item in the batch against the CHECKLIST below. Write the check as a short table: item id | pass/fail | what was wrong.
3. Fix every failed item and re-check it.
4. Keep a running count. If the count is below TARGET, go back to step 1 with the next batch.
5. When TARGET is reached, do one last pass over ALL items for duplicates and consistency, then print the FINAL OUTPUT exactly as specified: one code block per output file, nothing else inside the blocks. After the blocks, print "DOUBTS:" and a short bullet list (max 10) of items you are not fully sure about, with the reason.
If the chat is cut off, continue from the last finished batch when I write "continue".

FINAL OUTPUT: 4 python code blocks, each starting with "# file: scripts/examples/<name>.py": english_bagrut5_05_module_e.py, english_bagrut5_06_module_g.py, english_bagrut5_07_literature_oral.py, english_bagrut5_08_exam.py.
````

## 3. ערבית שלב 1: דוגמאות פתורות, תרגול נוסף ומילון (זמן משוער: 90 עד 120 דק')

- issue: #220
- קובץ יעד: MyRoad-content: scripts/examples/arabic_bagrut5_01_script.py, scripts/extra_practice/arabic_bagrut5_01_script.json, scripts/glossary/arabic_stage1.json

````text
You are writing Arabic content for MyRoad: a Hebrew-UI app that teaches adult Hebrew speakers Arabic toward the Israeli 5-unit bagrut. Right now ONLY stage 1 is in scope (GitHub issue Eliot100/MyRoad#220): path path_arabic_bagrut5_01_script, which teaches direction, the first 12 letters and first spoken words. Product rules: worked examples before practice; a wrong answer shows a full solution; harakat (vowel marks) are shown on every Arabic word; learners may have audio off, so a Hebrew transliteration with niqqud is given in brackets when needed; answer matching ignores harakat and normalizes alef/hamza, ta marbuta, alef maqsura, so never make two choices that differ only in those.

THE PATH TODAY (topic id (title): first learn text, content):
## path_arabic_bagrut5_01_script | ערבית מאפס
- s0_start (שלב 0: מתחילים): learn='ערבית נכתבת מימין לשמאל, כמו עברית. אין אותיות גדולות. רוב האותיות מתחברות זו לזו בתוך מילה, ולכן לאות יש צורה קצת אחרת בהתחלה, באמצע ובסוף.' content='عَرَبِيّ' learn_steps=3 practice=3
- s1_letters (שלב 1: שש אותיות ראשונות): learn='ا אַלִף (א, וגם תנועה א ארוכה). ب בַּא (ב דגושה, תמיד b). ت תַּא (ת). ن נוּן (נ). م מִים (מ). ل לַאם (ל). שימו לב לנקודות: ب אחת למטה, ت שתיים למעלה, ن אחת למעלה.' content='ا ب ت ن م ل' learn_steps=3 practice=7
- s2_letters (שלב 2: עוד שש אותיות): learn='ي יַא (י, וגם תנועה אִי ארוכה). و וַאו (w, וגם תנועה אוּ ארוכה). س סִין (ס). ر רַא (ר מתגלגלת). د דַּאל (ד). ك כַּאף (כּ, תמיד k).' content='ي و س ر د ك' learn_steps=3 practice=7
- s2_review (חזרה): learn='שתים עשרה אותיות עד עכשיו. ב ת נ י נבדלות רק בנקודות. ا د ر و לא מתחברות שמאלה.' content='ا ب ت ن م ل ي و س ر د ك' learn_steps=1 practice=4
- s2_done (סיום שלב 2): learn='' content='' learn_steps=0 practice=0
Letters taught: s1 = ا ب ت ن م ل ; s2 = ي و س ر د ك. Do not use any other letter in s0/s1/s2 items, except in s0 spoken greetings that already exist (شُو اِسْمَك؟ اِسْمِي, مَرْحَبا).

You produce 3 outputs.

OUTPUT A: worked examples, file scripts/examples/arabic_bagrut5_01_script.py. Same format as the English file:
```python
"""Worked examples shown as learn steps after a topic's learn step, before its practice.
Keyed by topic id: list of (title, body_he, body_content)."""
E = {
    "t_letters": [
        ("דוגמה: צליל ראשון", "אומרים dog לאט: d, o, g. הצליל הראשון הוא d, לכן המילה נפתחת באות d.", "dog: d o g"),
    ],
}
```
For Arabic: keys s0_start, s1_letters, s2_letters, s2_review. 4 examples each (16 total). body_he solves one example step by step and ends with the transliteration in brackets, e.g. "(בַּאב)". body_content = the Arabic word(s) with full harakat. Examples: reading a 2 to 3 letter word letter by letter, the same letter in start/middle/end form, telling ب ت ن ي apart by dots, the 6 non-connecting letters ا د ذ ر ز و (only those already taught).

OUTPUT B: extra practice items with full solutions, file scripts/extra_practice/arabic_bagrut5_01_script.json. A JSON object keyed by topic id, each value a list of practice nodes. One real node from the path (the build script adds the audio/writing variants itself, so write base nodes only, no variant_of/variant_when):
```json
{"id": "z1_dots_p1__a1w0", "type": "practice", "kind": "review", "title": "איזו אות?", "body_he": "איזו אות היא ב?", "body_content": "ب ت ن ي", "speak_text": "ب ت ن ي", "choices": [{"id": "a", "label": "ب"}, {"id": "b", "label": "ت", "feedback": "ت היא ת, עם שתי נקודות למעלה."}, {"id": "c", "label": "ن", "feedback": "ن היא נ, עם נקודה למעלה."}, {"id": "d", "label": "ي", "feedback": "ي היא י, עם שתי נקודות למטה."}], "correct": "a", "feedback_ok": "ב: נקודה אחת למטה.", "feedback_try": "ב היא ب: נקודה אחת למטה.", "can_do": "לזהות את ب לפי הנקודה", "worked_method": "באותיות שנראות דומה סופרים נקודות ובודקים איפה הן: ب אחת למטה, ت שתיים למעלה, ن אחת למעלה בקערה עמוקה, ي שתיים למטה.", "hint": "ספרו את הנקודות ובדקו איפה הן."}
```
Allowed keys only: id, type ("practice"), kind ("understanding" or "review"), title, body_he, body_content, speak_text, choices (3 or 4, ids a/b/c/d, each with label and, for wrong ones, feedback in Hebrew), correct, feedback_ok, feedback_try, worked_method, can_do, hint. Any other key breaks the schema. ids: "x1_<topic>_<n>__a1w0" e.g. "x1_s1_letters_03__a1w0". feedback_try = the FULL solution in Hebrew (why the right answer is right, 1 to 2 sentences), not just "try again". kind "review" only in s2_review.
Counts: s0_start 6, s1_letters 14, s2_letters 14, s2_review 10 (mixing all 12 letters). Total 44. Spread item types: letter to sound, sound to letter, which word is written here, which letter is missing, start/middle/end form, connects or not.

OUTPUT C: stage 1 glossary, file scripts/glossary/arabic_stage1.json. A JSON array of every Arabic word used in outputs A and B plus the existing path, each: {"ar": "بَاب", "ar_plain": "باب", "he_translit": "בַּאבּ", "he": "דלת", "letters": ["ب","ا","ب"], "note": ""}. ar_plain = without harakat. Target about 40 to 60 entries, no duplicates.

HEBREW STYLE RULES (apply to every Hebrew string):
- Simple Hebrew for adults from the general population. Short sentences, plural address (קראו, בחרו), no slang, no childish tone.
- No em dash or en dash (— –). Use a comma or a period instead.
- Explanation text (Hebrew) and target-language tokens (English/Arabic) are kept apart: the Hebrew explanation goes in body_he, the English/Arabic words being taught go in body_content.
- Every fact and every answer must be checked twice. If you are not sure, put the item in the doubts list instead of guessing.
ARABIC RULES: Modern Standard Arabic spelling with full, correct harakat (fatha, kasra, damma, sukun, shadda); spoken greetings marked as spoken (מדוברת) in body_he. Every word must be a real word with the meaning given. Use only taught letters in s1/s2 items.

CHECKLIST per item: (1) Arabic spelling and harakat correct; (2) only allowed letters for that topic; (3) the correct answer is the only correct choice even after normalization (no two choices equal without harakat); (4) Hebrew transliteration matches the harakat; (5) feedback_try is a full solution; (6) valid JSON, allowed keys only, ids unique; (7) no duplicates of existing or earlier items; (8) Hebrew quality, no em dash.

Batches: A (16), then B in batches of 10, then C. TARGET = 16 examples + 44 practice items + glossary covering every word.

WORK AS A LOOP. Do not stop after the first batch.
1. Generate the next batch (size given below).
2. Self-check every item in the batch against the CHECKLIST below. Write the check as a short table: item id | pass/fail | what was wrong.
3. Fix every failed item and re-check it.
4. Keep a running count. If the count is below TARGET, go back to step 1 with the next batch.
5. When TARGET is reached, do one last pass over ALL items for duplicates and consistency, then print the FINAL OUTPUT exactly as specified: one code block per output file, nothing else inside the blocks. After the blocks, print "DOUBTS:" and a short bullet list (max 10) of items you are not fully sure about, with the reason.
If the chat is cut off, continue from the last finished batch when I write "continue".

FINAL OUTPUT: one python block "# file: scripts/examples/arabic_bagrut5_01_script.py", one json block for scripts/extra_practice/arabic_bagrut5_01_script.json, one json block for scripts/glossary/arabic_stage1.json. Then DOUBTS, especially any word whose harakat or meaning you are not 100% sure of.
````

## 4. אנגלית: תרגול נוסף עם פתרון מלא, דרכים 01 עד 04 (זמן משוער: 90 עד 120 דק')

- issue: #213, #215
- קובץ יעד: MyRoad-content: scripts/extra_practice/english_bagrut5_0{1..4}_<name>.json

````text
You are writing extra practice questions for MyRoad (Hebrew UI, adults learning English toward the Israeli 5-unit bagrut). Issues Eliot100/MyRoad#213 (when a learner is below the mastery threshold, the engine serves more questions of the same topic) and #215 (after a wrong answer the app shows a full solution). Each topic today has only 2 to 3 practice questions; we need a pool.

TOPICS (path | topic id (title): learn text, content):
## path_english_bagrut5_01_zero | מאפס
- t_letters (אותיות): learn='אומרים את שם האות, ואז קוראים מילה קצרה.' content='A, B, C.' learn_steps=4 practice=2
- t_be (am is are): learn='I הולך עם am. He, she, it עם is. You, we, they עם are.' content='I am a student.' learn_steps=1 practice=2
- t_not (שלילה): learn='שלילה: am not, is not, are not. לא מוסיפים do.' content='She is not late.' learn_steps=1 practice=2
- t_you (you ו we): learn='you, we, they הולכים עם are. לא עם am.' content='You are ready. We are here.' learn_steps=1 practice=2
- t_word (מילה קצרה): learn='קוראים את כל המילה, לא רק את האות הראשונה.' content='sun, map, dog' learn_steps=1 practice=2
- t_sent (משפט): learn='משפט מתחיל באות גדולה ונגמר בנקודה. יש בו מישהו ופועל.' content='I am here.' learn_steps=1 practice=2
## path_english_bagrut5_02_present | הווה ויום יום
- t_simple (Present Simple): learn='הרגל. אחרי he, she, it הפועל מקבל s.' content='She works at home.' learn_steps=1 practice=2
- t_there (there is): learn='יש אחד: there is. יש כמה: there are.' content='There is a book on the desk.' learn_steps=1 practice=2
- t_q (שאלות): learn='שאלה בהווה: Do או Does בהתחלה, והפועל בלי s.' content='Do you live here?' learn_steps=1 practice=2
- t_day (יום רגיל): learn='קטע קצר על יום עבודה. שאלה על הרעיון ושאלה על פרט.' content='Maya works at home. She starts at eight. She drinks water and opens her mail. So' learn_steps=1 practice=2
- t_neg (שלילה בהווה): learn='שלילה: do not או does not, והפועל בלי s.' content='She does not work on Friday.' learn_steps=1 practice=2
- t_freq (תדירות): learn='always ו never באים לפני הפועל העיקרי, ואחרי is.' content='Maya always starts at eight.' learn_steps=1 practice=2
## path_english_bagrut5_03_time | זמן וסיפור
- t_past (Past Simple): learn='אתמול: פועל עם ed, או צורה חריגה כמו went וsaw.' content='Yesterday I walked home.' learn_steps=1 practice=2
- t_fut (עתיד): learn='מחר: will והפועל הבסיסי. תוכנית קרובה: am, is או are, ועוד ing.' content='Tomorrow I will leave early.' learn_steps=1 practice=2
- t_story (סיפור קצר): learn='קראו וזהו את הרעיון ואת ההסקה.' content='Jonah missed the last bus and waited under the pharmacy light. A woman he did no' learn_steps=1 practice=2
- t_irreg (עבר חריג): learn='לא כל עבר הוא ed. go נהיה went. see נהיה saw.' content='Yesterday I went home. I saw the bus.' learn_steps=1 practice=2
- t_ago (מתי): learn='ago מסתכל אחורה. tomorrow מסתכל קדימה. לא מערבבים.' content='I saw her two days ago.' learn_steps=1 practice=2
- t_who (מי ואיפה): learn='who שואל על אדם. where שואל על מקום.' content='Jonah missed the last bus and waited under the pharmacy light. A woman he did no' learn_steps=1 practice=2
## path_english_bagrut5_04_accuracy | דיוק
- t_art (a וthe): learn='a בפעם הראשונה. the כשכבר יודעים על מה מדובר. על דבר כללי ברבים לא שמים מילה בכלל.' content='I saw a bird. The bird was blue. Birds need water.' learn_steps=1 practice=3
- t_perf (זמן פתוח וזמן סגור): learn='have והצורה השלישית כשהזמן עוד פתוח, כמו ever או עד עכשיו. זמן שנגמר, כמו yesterday או 2019, דורש עבר רגיל.' content='I have seen this film. I saw it yesterday.' learn_steps=1 practice=3
- t_if (תנאי ראשון): learn='אחרי if בא הווה. בחלק של התוצאה בא will.' content='If it rains, we will stay home.' learn_steps=1 practice=3
- t_an (an): learn='an לפני צליל תנועה: an apple, an hour. a לפני צליל עיצור: a bird, a university. קובע הצליל, לא האות.' content='I ate an apple.' learn_steps=1 practice=3
- t_order (סדר מילים): learn='נושא, פועל, ואז מושא. תואר בא לפני השם: a red car. never וalways באים לפני הפועל העיקרי.' content='I never drink cold coffee.' learn_steps=1 practice=3
- t_for (for וsince): learn='for עם משך: for two years. since עם נקודת התחלה: since 2020. שניהם באים עם have.' content='I have lived here for two years.' learn_steps=1 practice=3

OUTPUT FORMAT: one JSON file per path, scripts/extra_practice/<path_name>.json, a JSON object keyed by topic id, value = list of practice nodes. A real node from path 01 (copy this shape exactly):
```json
{"id": "z_t_be_p1", "type": "practice", "kind": "understanding", "title": "I", "body_he": "מה נכון?", "body_content": "I ___ tired.", "choices": [{"id": "a", "label": "am"}, {"id": "b", "label": "is", "feedback": "is הולך עם he, she, it. עם I אומרים am."}, {"id": "c", "label": "are", "feedback": "are הולך עם you, we, they."}], "correct": "a", "feedback_ok": "I am.", "feedback_try": "במשפט יש I, לכן am: I am tired.", "can_do": "להגיד I am", "worked_method": "I הולך עם am, he או she עם is, you, we, they עם are.", "hint": "איזו צורה של to be הולכת עם I?"}
```
Allowed keys only: id, type ("practice"), kind ("understanding"), title (Hebrew, max 4 words), body_he (the Hebrew question), body_content (the English item, use ___ for a gap), choices (exactly 3, ids a/b/c; every WRONG choice has a Hebrew "feedback" explaining that specific mistake), correct, feedback_ok (short), feedback_try (FULL solution in Hebrew: the rule applied to THIS sentence plus the full correct English sentence), worked_method (the general method in 1 to 2 Hebrew sentences), can_do (Hebrew, starts with an infinitive like "לזהות"), hint (Hebrew, a nudge that does not give the answer). Ids: "xp_<path number>_<topic id>_<nn>", e.g. "xp_02_t_simple_07".

Rules:
- 6 new questions per topic (difficulty ramp: 2 easy, 2 medium, 2 hard). Hard still uses only grammar/words taught up to that path.
- Wrong choices = real common mistakes of Hebrew speakers (e.g. dropping the third person s, "I am agree", "since two years", a/an by letter not sound).
- Correct answer position varies: across each file roughly one third a, b, c.
- Reading topics: write a NEW short original passage (3 to 5 sentences, adult life) in body_content of each question, plus the question.
- No question may duplicate an existing one (the examples in the topic list) or another new one.

HEBREW STYLE RULES (apply to every Hebrew string):
- Simple Hebrew for adults from the general population. Short sentences, plural address (קראו, בחרו), no slang, no childish tone.
- No em dash or en dash (— –). Use a comma or a period instead.
- Explanation text (Hebrew) and target-language tokens (English/Arabic) are kept apart: the Hebrew explanation goes in body_he, the English/Arabic words being taught go in body_content.
- Every fact and every answer must be checked twice. If you are not sure, put the item in the doubts list instead of guessing.

CHECKLIST per item: (1) exactly one correct choice, verified by reading every choice into the sentence; (2) English natural and correct; (3) feedback_try is a full solution with the full correct sentence; (4) each wrong choice has its own correct feedback; (5) level fits the path; (6) no duplicates; (7) valid JSON, allowed keys only, unique ids; (8) Hebrew quality, no em dash.

Batch = one topic (6 questions). TARGET = 144 questions (24 topics x 6, t_letters included), in 4 files.

WORK AS A LOOP. Do not stop after the first batch.
1. Generate the next batch (size given below).
2. Self-check every item in the batch against the CHECKLIST below. Write the check as a short table: item id | pass/fail | what was wrong.
3. Fix every failed item and re-check it.
4. Keep a running count. If the count is below TARGET, go back to step 1 with the next batch.
5. When TARGET is reached, do one last pass over ALL items for duplicates and consistency, then print the FINAL OUTPUT exactly as specified: one code block per output file, nothing else inside the blocks. After the blocks, print "DOUBTS:" and a short bullet list (max 10) of items you are not fully sure about, with the reason.
If the chat is cut off, continue from the last finished batch when I write "continue".

FINAL OUTPUT: 4 json blocks, each preceded by a line "file: scripts/extra_practice/<name>.json": english_bagrut5_01_zero.json, english_bagrut5_02_present.json, english_bagrut5_03_time.json, english_bagrut5_04_accuracy.json (36 questions each).
````

## 5. אנגלית: שתי סימולציות בחינה ושאלות קשות לפי תחום (זמן משוער: 90 עד 120 דק')

- issue: #221
- קובץ יעד: MyRoad-content: scripts/exam_sim/english_bagrut5_08_exam.json

````text
You are writing exam-format practice for MyRoad (Hebrew UI, adults, Israeli 5-unit English bagrut, modules E and G level). Issue Eliot100/MyRoad#221: end-of-road mode with timed simulations, a high-difficulty set, and more questions in the domains where the learner's score (KPI) is low. Domains (field "area"): vocabulary, grammar, reading, writing.

OUTPUT FORMAT: one JSON file scripts/exam_sim/english_bagrut5_08_exam.json:
```json
{
  "passages": [{"id": "ps_01", "title_en": "...", "text": "original English passage, 250 to 350 words"}],
  "simulations": [{"id": "sim_1", "title_he": "סימולציה 1", "minutes": 40, "node_ids": ["sim1_01", "..."]}],
  "nodes": [ ...check nodes... ],
  "extra_by_area": {"vocabulary": ["hx_voc_01", "..."], "grammar": [], "reading": [], "writing": []}
}
```
Each node is a "check" step in this exact shape (a real node from path 08):
```json
{"id": "ex_t_write_chk", "type": "check", "kind": "understanding", "title": "בדיקה", "body_he": "מה לא מורידים בקריאה לפי החוברת?", "body_content": "Spelling in a reading answer.", "choices": [{"id": "a", "label": "Spelling alone does not remove the reading points."}, {"id": "b", "label": "One spelling error zeros the paper.", "feedback": "טעות כתיב אחת לא מאפסת את המבחן."}, {"id": "c", "label": "Grammar is ignored in the essay.", "feedback": "בחיבור הדיוק כן נספר."}], "correct": "a", "feedback_ok": "בכתיב בקריאה לא מורידים. בחיבור הדיוק כן נספר.", "feedback_try": "בתשובת קריאה כתיב לבד לא מוריד את נקודות הקריאה. לכן התשובה הראשונה.", "can_do": "לדעת מתי כתיב מוריד נקודות", "worked_method": "בתשובת קריאה בודקים אם הבנת. כתיב לבד לא מוריד שם נקודות. בחיבור הדיוק כן נספר.", "hint": "בשאלת קריאה בודקים אם הבנתם את הקטע."}
```
Plus two extra keys on every node: "area" (one of vocabulary, grammar, reading, writing) and "difficulty" (a number from -4 to 4, 1PL style: 0 = average bagrut 5 student, 1.5+ = hard). Allowed keys only: id, type, kind, title, body_he, body_content, choices (exactly 4, ids a/b/c/d, Hebrew feedback on wrong ones), correct, feedback_ok, feedback_try (FULL solution in Hebrew: quote the line from the passage or state the rule, then why the answer follows), worked_method, can_do, hint, area, difficulty. Questions stay in English inside body_content (like the real exam); body_he holds a short Hebrew instruction. For reading items, body_content = "[ps_01] " + the question (the app will show the passage by id).

Contents:
- 4 original passages (none copied from real exams; adult topics: work, city, health, technology, money).
- sim_1 and sim_2: 20 items each, 40 minutes, mix: 10 reading (2 passages x 5), 4 vocabulary in context, 4 grammar, 2 writing (best opening/closing sentence, best linking word, which sentence fits the opinion essay). Difficulty spread inside each sim: about 30% easy (<0), 40% medium (0 to 1), 30% hard (>1).
- Hard set, ids "hx_<area>_<nn>": 10 per area (40), all difficulty >= 1, can reuse the 4 passages for reading.
TARGET: 80 nodes total (40 sim + 40 hard), 4 passages.

HEBREW STYLE RULES (apply to every Hebrew string):
- Simple Hebrew for adults from the general population. Short sentences, plural address (קראו, בחרו), no slang, no childish tone.
- No em dash or en dash (— –). Use a comma or a period instead.
- Explanation text (Hebrew) and target-language tokens (English/Arabic) are kept apart: the Hebrew explanation goes in body_he, the English/Arabic words being taught go in body_content.
- Every fact and every answer must be checked twice. If you are not sure, put the item in the doubts list instead of guessing.

CHECKLIST per item: (1) exactly one defensible answer, checked against the passage line by line; (2) distractors plausible but clearly wrong for a reason stated in their feedback; (3) area and difficulty fit; (4) feedback_try is a full solution; (5) no duplicates, no two items testing the same exact fact; (6) valid JSON, allowed keys only, every id in simulations/extra_by_area exists in nodes; (7) Hebrew quality, no em dash; (8) answer key spread across a/b/c/d.

Batches: passages first; then 10 items per batch. TARGET as above.

WORK AS A LOOP. Do not stop after the first batch.
1. Generate the next batch (size given below).
2. Self-check every item in the batch against the CHECKLIST below. Write the check as a short table: item id | pass/fail | what was wrong.
3. Fix every failed item and re-check it.
4. Keep a running count. If the count is below TARGET, go back to step 1 with the next batch.
5. When TARGET is reached, do one last pass over ALL items for duplicates and consistency, then print the FINAL OUTPUT exactly as specified: one code block per output file, nothing else inside the blocks. After the blocks, print "DOUBTS:" and a short bullet list (max 10) of items you are not fully sure about, with the reason.
If the chat is cut off, continue from the last finished batch when I write "continue".

FINAL OUTPUT: one json block preceded by "file: scripts/exam_sim/english_bagrut5_08_exam.json". In DOUBTS also list any item where two answers could be argued.
````

## 6. טקסטים במסך: שכתוב עברית, אנגלית וערבית למסכי הלומד (זמן משוער: 60 עד 90 דק')

- issue: #218, #233 (איכות טקסט UX)
- קובץ יעד: MyRoad: packages/core/locales/he.json, en.json, ar.json (רק מפתחות ששונו)

````text
You are the UX writer for MyRoad, a learning app for adults from the general population. UI languages: Hebrew (default, RTL), English (LTR), Arabic (RTL). Accessibility target WCAG 2.2 AA (issue Eliot100/MyRoad#218) and mobile 360 to 412 px wide (issue #233), so labels must be short and clear and every control needs a clear accessible name.

INPUT: the three UI string files (544 keys each, flat JSON key -> string):
https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/locales/he.json
https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/locales/en.json
https://raw.githubusercontent.com/Eliot100/MyRoad/main/packages/core/locales/ar.json
If you cannot open links, tell me and I will paste them. Real entries look like this:
```json
{"product_badge": "פלטפורמת למידה", "hero_title": "דרכי למידה", "hero_lede": "בחרו קבוצה ונושא, ואז פתחו דרך. התוכן מגיע מקבצי נתונים — לא מקוד קשיח.", "next_step": "...", "steps_count": "{n} שלבים"}
```

TASK: rewrite the LEARNER-FACING strings only (home, catalog, road map, step player, answers and feedback, hints, placement, session end, settings, login, errors and offline messages). Skip author/builder/agent/admin/metrics/debug keys (key names containing builder, author, agent, draft, admin, metrics, poc) unless they are shown to learners.

Rules:
- Keep every key name exactly. Keep every placeholder exactly ({n}, {total}, {title}, {done}, {topic} and any other {...}), and keep any HTML tags.
- Hebrew: plural address (בחרו, המשיכו), warm and plain, no developer words (no "קבצי נתונים", "POC", "קוד"), no em dash, consistent terms: דרך (road), שלב (step), נושא (topic), מבדק (placement), חזרה (review). Same term for the same thing everywhere.
- English: plain, sentence case, no em dash. Arabic: Modern Standard Arabic, clear for adults, same meaning as Hebrew, the same consistent terms (طريق، خطوة، موضوع، اختبار تحديد المستوى، مراجعة).
- Length: buttons max 3 words / about 18 characters in all three languages (360 px screen). Error messages say what happened and what to do next.
- Accessibility: if a key is an aria-label or button label, it must describe the action ("השמעה חוזרת של ההקלטה" not "▶"). Do not rely on color words ("הכפתור הירוק").
- Only output keys you actually changed, plus keys that are missing in one language.

CHECKLIST per key: (1) meaning unchanged (or clearly improved); (2) placeholders and tags identical to the original; (3) the three languages say the same thing; (4) length rule; (5) consistent glossary; (6) no em dash; (7) Arabic and Hebrew grammar (gender, plural) correct.

Batch = 60 keys in key order. Go through all 544 keys. TARGET = all learner-facing keys reviewed.

WORK AS A LOOP. Do not stop after the first batch.
1. Generate the next batch (size given below).
2. Self-check every item in the batch against the CHECKLIST below. Write the check as a short table: item id | pass/fail | what was wrong.
3. Fix every failed item and re-check it.
4. Keep a running count. If the count is below TARGET, go back to step 1 with the next batch.
5. When TARGET is reached, do one last pass over ALL items for duplicates and consistency, then print the FINAL OUTPUT exactly as specified: one code block per output file, nothing else inside the blocks. After the blocks, print "DOUBTS:" and a short bullet list (max 10) of items you are not fully sure about, with the reason.
If the chat is cut off, continue from the last finished batch when I write "continue".

FINAL OUTPUT: three json blocks preceded by "file: packages/core/locales/he.json (changed keys only)", same for en.json and ar.json, each a flat object with only the changed keys. Then a short table "glossary used" (he | en | ar), then DOUBTS.
````

## הערות ל-frank ולבוטים

- הקבצים ב-scripts/examples נטענים כבר בבנייה של אנגלית (`add_examples` ב-scripts/build_english_bagrut5.py). בבנייה של ערבית עוד אין `add_examples`, וגם לא קיימת טעינה של scripts/extra_practice, scripts/exam_sim ו-scripts/glossary. צריך לחבר אותן כשהפלט מגיע.
- אחרי חיבור: `python scripts/validate_paths.py` ובדיקות core לפני PR.
