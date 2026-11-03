# בריף החלטה: איפה מארחים את MyRoad כדי שאליוט ייכנס מאנדרואיד (2026-11-03, MyRoad PM)

**השאלה (למריה):** איזו אפשרות אירוח נבחר כדי שאליוט ילמד ב-MyRoad מהטלפון: A, B, C או D?

**המלצת PM:** **D עכשיו** (Wi-Fi ביתי, חינם, לבדיקות מובייל מיד), ו-**A כצעד הבא** (Cloudflare Tunnel + Access, חינם, HTTPS, רק אחרי הקשחת האימות #51 #52 #54). C כשצריך זמינות 24/7 בלי המחשב של אליוט. B לא עכשיו: מחייב שינוי ארכיטקטורה של SQLite.

רקע: FastAPI + Jinja + htmx + SQLite. Service worker ו-PWA דורשים HTTPS (חוץ מ-localhost). כלל סייבר: אין חשיפה ציבורית לפני הקשחת אימות. מפתח המודל נשאר ב-Cloudflare AI Gateway, אף סוד לא בריפו. מימוש: #236.

| | A: Cloudflare Tunnel מהמחשב של אליוט | B: אירוח ב-Cloudflare | C: VPS קטן + Caddy | D: LAN ביתי בלבד |
|---|---|---|---|---|
| עלות | $0: Tunnel ו-Access בתוכנית Zero Trust החינמית, עד 50 משתמשים [1] | Workers Paid מ-$5 לחודש, כולל מכסת Containers [2][3] | Hetzner CX23 ‏€5.49 לחודש + ‏€0.50 IPv4, לפני מע"מ [4]; או Fly.io ‏$2.19 לחודש (256MB) + נפח ‏$0.15 ל-GB [5] | $0 |
| מאמץ הקמה | נמוך: cloudflared כשירות, דומיין ב-Cloudflare, מדיניות Access | גבוה: Containers או Pages+backend, הסבת SQLite ל-D1 או פתרון אחסון | בינוני: שרת, Docker, Caddy, גיבוי, עדכונים | מינימלי: `--host 0.0.0.0` וכתובת IP מקומית |
| אבטחה | Access עם רשימת אימיילים לפני האפליקציה; אין פורט פתוח בבית. עדיין חסום עד #51 #52 #54. מידע נשאר במחשב של אליוט | Access זמין. מידע אצל Cloudflare (D1). חסום עד הקשחת אימות | שרת חשוף לאינטרנט: צריך Access או חומת אש, עדכוני מערכת, גיבוי SQLite. מידע אצל הספק (EU ב-Hetzner) | לא יוצא מהבית; כל מי שברשת ה-Wi-Fi רואה. לא דורש הקשחה לבדיקות dev |
| PWA | HTTPS אמיתי: התקנה ו-service worker עובדים | HTTPS: עובד | Caddy נותן HTTPS אוטומטי: עובד | HTTP בלבד: אין service worker ואין התקנה. רק בדיקת תצוגה ומגע |
| חיסרון עיקרי | עובד רק כשהמחשב של אליוט דולק ומחובר | דיסק הקונטיינר לא מתמיד (לבדוק בתיעוד) ולכן SQLite צריך D1 או שירות אחסון: שינוי קוד גדול | עלות חודשית קבועה ותחזוקה | רק בבית, בלי PWA |

**הפיכות:** כל האפשרויות הפיכות; מחיר טעות נמוך ב-A, C, D (שעות), בינוני ב-B (הסבת DB).
**אם אין תשובה:** ממשיכים עם D לבדיקות #233, ו-#236 נשאר Blocked.

מקורות (נבדקו 2026-11-03):
1. https://www.cloudflare.com/plans/zero-trust-services/
2. https://developers.cloudflare.com/workers/platform/pricing/
3. https://developers.cloudflare.com/containers/platform/pricing/
4. https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/ ו-https://www.hetzner.com/cloud/cost-optimized/ (CX23 הופיע "not available" בדף, לבדוק מלאי)
5. https://fly.io/pricing ו-https://docs.fly.io/about/pricing (אין שכבה חינמית לחשבונות חדשים)
