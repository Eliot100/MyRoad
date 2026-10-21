# מה graphify מיפה

נבנה ב-2026-10-21 מהקוד של `packages/core/src/myroad_core`. 1104 צמתים, 2867 קשתות. בלי מודל שפה: רק ניתוח מבנה.

זה מתאר מה הקוד עושה. לא מה המוצר צריך להיות. כיוון המוצר בסט המסמכים.

צמתים מרכזיים: `register_platform_routes`, `PathStore`, `ContentPath`, `create_learner_app`. נעילת הסדרה יושבת ב-`english_bagrut.py` (`placement_band`, `open_through`, `recommended_index`, `extra_lock`) ומחוברת למסכי הפלטפורמה.

הגרף המלא: `graphify-out/graph.json` ליד הקובץ הזה, אם הועתק. אחרת ב-`/tmp/graphify-myroad/graphify-out/graph.json`.
