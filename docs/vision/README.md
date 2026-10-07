> **EN summary:** Canonical vision docs for MyRoad (product, spec, agent and publish policy, architecture and roadmap, decisions log).
> This folder on `main` is the source of truth; Notion is a read-only copy for Eliot. Change a decision only through a PR that also updates `05-decisions-log.md`.

# MyRoad — מסמכי חזון (`docs/vision/`)

## מקור האמת

- **התיקייה הזו (`docs/vision/`) בענף `main` של `Eliot100/MyRoad` היא המקור הקנוני** לחזון, לאפיון ולהחלטות המוצר.
- **Notion הוא עותק לקריאה בלבד עבור אליוט.** לא עורכים שם. כשיש סתירה בין Notion לבין הריפו, הריפו קובע.
- מסמכים ישנים יותר (טיוטות האפיון הראשונות, `docs/design-extraction.md`, תיאורי PR ישנים) הם היסטוריה. כשהם סותרים את התיקייה הזו, התיקייה הזו גוברת. סתירות ידועות מתועדות ב-[05-decisions-log.md](05-decisions-log.md).
- אין בתיקייה הזו סודות: אין מפתחות, אין טוקנים, אין ערכי משתני סביבה. מופיעים רק שמות של משתנים.

## אינדקס

| קובץ | תוכן | בעלים |
|------|------|-------|
| [01-vision.md](01-vision.md) | המוצר, למי הוא מיועד, מה נחשב הצלחה, מה מחוץ ל-POC | PM |
| [02-product-spec.md](02-product-spec.md) | תפקידים, מצבים, דרך (path), גרף שלבים, ערוצים, עטיפה אישית, מדידה, i18n ו-RTL, התחברות והגדרות | PM, UX |
| [03-agent-and-publish.md](03-agent-and-publish.md) | זרימת הסוכן, מדיניות הפרסום (סוכן רשאי לפרסם), כלל ה-Gateway, חוזה כלים מתוקן בקצרה | PM, Path Builder, MLOps |
| [04-architecture-and-roadmap.md](04-architecture-and-roadmap.md) | מה יש ב-main היום (מאומת מול הריפו), הרחבות סכמה מתוכננות, טבלת בעלות צוותים, אבני דרך הבאות | PM, Dev |
| [05-decisions-log.md](05-decisions-log.md) | יומן החלטות מתוארך, כולל החלטות שהוחלפו | PM |
| [06-content-format.md](06-content-format.md) | פורמט ה-JSON של דרך, גרסה 2: קהלים, סוג שלב, חזרה מעורבת, דרישות קדם, ציון מאוחד | PM |

מסמכים קשורים מחוץ לתיקייה:

- `freeze/v0/` — הקפאת v0: דרך הזהב (משוואות ריבועיות) לפני ואחרי משוב, חוזה הכלים, השוואה לפיגום הראשון.
- `packages/core/docs/agent-path-builder.md` — בונה הדרכים של הסוכן (`/add-path`).
- `packages/core/docs/cloudflare-ai-gateway.md` — חיבור למודל דרך Cloudflare AI Gateway (BYOK).
- `packages/core/docs/how-to-add-locale.md`, `locale-consistency.md`, `kids-platform.md`.
- הריפו `Eliot100/MyRoad-content` — תוכן הדרכים (JSON).

## איך משנים החלטה

1. **רק אליוט מחליט** על שינוי החלטת מוצר. צוות (או בוט) יכול להציע שינוי, אבל ההצעה לא נכנסת לתוקף עד שאליוט מאשר.
2. ה-PM כותב את השינוי. Dev פותח PR מול `main` (עם `gh`). אף אחד לא דוחף ישירות ל-`main`.
3. באותו PR:
   - מוסיפים שורה חדשה ב-`05-decisions-log.md` עם תאריך, ההחלטה, מה היא מחליפה, ומקור (למשל "הודעה של אליוט").
   - **לא מוחקים** את ההחלטה הישנה. מסמנים אותה "הוחלפה" ומפנים לשורה החדשה.
   - מעדכנים את המסמכים בתיקייה שמושפעים מהשינוי, וגם מסמכים אחרים בריפו שסותרים את ההחלטה (למשל `freeze/v0/`, `README.md`).
4. Cyber security בודק כל שינוי שנוגע בהתחברות, בהרשאות, בפרסום או בסודות.
5. אחרי המיזוג, מעדכנים את עותק ה-Notion כך שישקף את `main`.
6. מה שלא ידוע או לא הוחלט מסומן **פתוח** ולא ממולא בניחוש.
