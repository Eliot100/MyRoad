"""Shell chrome i18n (he / en / ar). Path content stays mostly Hebrew for demos."""

from __future__ import annotations

from typing import Any

LOCALES = ("he", "en", "ar")
DEFAULT_LOCALE = "he"
RTL_LOCALES = frozenset({"he", "ar"})

COOKIE_LOCALE = "myroad_locale"
COOKIE_USER = "myroad_uid"

_STRINGS: dict[str, dict[str, str]] = {
    "he": {
        "product_badge": "פלטפורמת למידה",
        "catalog": "קטלוג",
        "author_poc": "ממשק מחבר (POC)",
        "hero_title": "דרכי למידה",
        "hero_lede": "בחרו קבוצה ונושא, ואז פתחו דרך. התוכן מגיע מקבצי נתונים — לא מקוד קשיח.",
        "groups": "קבוצות",
        "subjects": "נושאים",
        "all": "הכל",
        "mins": "דק׳",
        "empty_catalog": "אין דרכים בקטלוג הזה עדיין.",
        "footer_catalog": "קטלוג מבוסס תוכן · פרסום אנושי לדרכים חדשות · דמו כיתה ג׳ נטען מראש",
        "back_catalog": "קטלוג",
        "who_am_i": "מי אני?",
        "who_guest": "אורח/ת",
        "login_title": "בחרו שם לתלמיד/ה",
        "login_lede": "שם תצוגה פשוט + מזהה יציב בדפדפן (POC בלי OAuth).",
        "display_name": "שם תצוגה",
        "save_identity": "שמירה והמשך",
        "switch_user": "החלפת משתמש",
        "resume": "המשך מאיפה שעצרתם",
        "completed": "הושלם",
        "in_progress": "בתהליך",
        "path_map": "מפת הדרך",
        "path_map_lede": "כל ריבוע הוא נושא — בתוכו כמה שלבי למידה. בחרו נושא או התחילו מההתחלה.",
        "start": "התחל",
        "start_path": "התחל את הדרך",
        "enter_topic": "כניסה לנושא",
        "steps_count": "שלבים",
        "progress_label": "שלב {n} מתוך {total} · הושלמו {done}",
        "speak": "הקראה",
        "record": "הקלטה",
        "record_hint": "הקלטה אופציונלית — אם הדפדפן תומך.",
        "continue": "הבנתי — המשך",
        "finish": "סיום 🎉",
        "continue_speak": "המשכתי / סיימתי",
        "prev": "הקודם",
        "next": "הבא",
        "check_sequence": "בדקו את הרצף",
        "done_free": "סיימתי להתנסות",
        "check_rhythm": "בדקו קצב",
        "reset": "איפוס",
        "stats_title": "סיכום הדרך",
        "stats_time": "זמן משוער",
        "stats_nodes": "שלבים שהושלמו",
        "stats_correct": "לחיצות נכונות",
        "stats_incorrect": "לחיצות שגויות",
        "stats_mastery": "אחוז שליטה",
        "stats_message": "כל הכבוד — סיימתם את הדרך!",
        "stats_message_ok": "עבודה יפה — המשיכו לתרגל!",
        "stats_message_retry": "שווה לחזור על כמה שלבים לחיזוק.",
        "back_to_catalog": "חזרה לקטלוג",
        "replay": "לשחק שוב",
        "seconds": "שניות",
        "minutes": "דקות",
        "language": "שפה",
        "gate_practice": "סיימו את השלב לפני המעבר הלאה.",
        "footer_play": "חזרה לקטלוג",
        "nodes": "שלבים",
        "topic_progress": "הושלם בנושא",
    },
    "en": {
        "product_badge": "Learning platform",
        "catalog": "Catalog",
        "author_poc": "Author UI (POC)",
        "hero_title": "Learning paths",
        "hero_lede": "Pick a group and subject, then open a path. Content comes from data files — not hard-coded UI.",
        "groups": "Groups",
        "subjects": "Subjects",
        "all": "All",
        "mins": "min",
        "empty_catalog": "No paths in this catalog yet.",
        "footer_catalog": "Content-driven catalog · human publish for new paths · Grade-3 demos preloaded",
        "back_catalog": "Catalog",
        "who_am_i": "Who am I?",
        "who_guest": "Guest",
        "login_title": "Choose a learner name",
        "login_lede": "Simple display name + stable browser id (POC, no OAuth).",
        "display_name": "Display name",
        "save_identity": "Save & continue",
        "switch_user": "Switch user",
        "resume": "Resume where you left off",
        "completed": "Completed",
        "in_progress": "In progress",
        "path_map": "Path map",
        "path_map_lede": "Each square is a topic — with learning steps inside. Pick a topic or start from the beginning.",
        "start": "Start",
        "start_path": "Start the path",
        "enter_topic": "Enter topic",
        "steps_count": "steps",
        "progress_label": "Step {n} of {total} · done {done}",
        "speak": "Speak",
        "record": "Record",
        "record_hint": "Optional recording — if the browser supports it.",
        "continue": "Got it — continue",
        "finish": "Finish 🎉",
        "continue_speak": "I continued / done",
        "prev": "Previous",
        "next": "Next",
        "check_sequence": "Check sequence",
        "done_free": "Done exploring",
        "check_rhythm": "Check rhythm",
        "reset": "Reset",
        "stats_title": "Path summary",
        "stats_time": "Approx. time",
        "stats_nodes": "Steps completed",
        "stats_correct": "Correct taps",
        "stats_incorrect": "Incorrect taps",
        "stats_mastery": "Mastery %",
        "stats_message": "Great job — you finished the path!",
        "stats_message_ok": "Nice work — keep practicing!",
        "stats_message_retry": "Worth revisiting a few steps to strengthen.",
        "back_to_catalog": "Back to catalog",
        "replay": "Play again",
        "seconds": "sec",
        "minutes": "min",
        "language": "Language",
        "gate_practice": "Finish this step before moving on.",
        "footer_play": "Back to catalog",
        "nodes": "steps",
        "topic_progress": "done in topic",
    },
    "ar": {
        "product_badge": "منصة تعلّم",
        "catalog": "الفهرس",
        "author_poc": "واجهة المؤلف (POC)",
        "hero_title": "مسارات التعلّم",
        "hero_lede": "اختر مجموعة وموضوعًا ثم افتح مسارًا. المحتوى من ملفات بيانات — وليس من واجهة ثابتة.",
        "groups": "المجموعات",
        "subjects": "المواضيع",
        "all": "الكل",
        "mins": "د",
        "empty_catalog": "لا توجد مسارات في هذا الفهرس بعد.",
        "footer_catalog": "فهرس مبني على المحتوى · نشر بشري للمسارات الجديدة · عروض الصف الثالث محمّلة مسبقًا",
        "back_catalog": "الفهرس",
        "who_am_i": "من أنا؟",
        "who_guest": "زائر",
        "login_title": "اختر اسمًا للمتعلّم",
        "login_lede": "اسم عرض بسيط ومعرّف ثابت في المتصفح (POC بدون OAuth).",
        "display_name": "اسم العرض",
        "save_identity": "حفظ ومتابعة",
        "switch_user": "تبديل المستخدم",
        "resume": "تابع من حيث توقفت",
        "completed": "مكتمل",
        "in_progress": "جارٍ",
        "path_map": "خريطة المسار",
        "path_map_lede": "كل مربع موضوع — وفيه خطوات تعلّم. اختر موضوعًا أو ابدأ من البداية.",
        "start": "ابدأ",
        "start_path": "ابدأ المسار",
        "enter_topic": "ادخل الموضوع",
        "steps_count": "خطوات",
        "progress_label": "الخطوة {n} من {total} · أُنجز {done}",
        "speak": "قراءة",
        "record": "تسجيل",
        "record_hint": "تسجيل اختياري — إن دعمه المتصفح.",
        "continue": "فهمت — متابعة",
        "finish": "إنهاء 🎉",
        "continue_speak": "تابعت / انتهيت",
        "prev": "السابق",
        "next": "التالي",
        "check_sequence": "تحقق من التسلسل",
        "done_free": "انتهيت من التجربة",
        "check_rhythm": "تحقق من الإيقاع",
        "reset": "إعادة",
        "stats_title": "ملخص المسار",
        "stats_time": "وقت تقريبي",
        "stats_nodes": "خطوات مكتملة",
        "stats_correct": "نقرات صحيحة",
        "stats_incorrect": "نقرات خاطئة",
        "stats_mastery": "نسبة الإتقان",
        "stats_message": "أحسنت — أنهيت المسار!",
        "stats_message_ok": "عمل جميل — واصل التمرين!",
        "stats_message_retry": "يُستحسن إعادة بعض الخطوات للتعزيز.",
        "back_to_catalog": "العودة للفهرس",
        "replay": "العب مجددًا",
        "seconds": "ث",
        "minutes": "د",
        "language": "اللغة",
        "gate_practice": "أنهِ هذه الخطوة قبل المتابعة.",
        "footer_play": "العودة للفهرس",
        "nodes": "خطوات",
        "topic_progress": "مكتمل في الموضوع",
    },
}


def normalize_locale(raw: str | None) -> str:
    if not raw:
        return DEFAULT_LOCALE
    code = raw.strip().lower().split("-")[0]
    return code if code in LOCALES else DEFAULT_LOCALE


def t(locale: str, key: str, **kwargs: Any) -> str:
    loc = normalize_locale(locale)
    text = _STRINGS.get(loc, _STRINGS[DEFAULT_LOCALE]).get(key) or _STRINGS[DEFAULT_LOCALE].get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def dir_for(locale: str) -> str:
    return "rtl" if normalize_locale(locale) in RTL_LOCALES else "ltr"


def html_lang(locale: str) -> str:
    return normalize_locale(locale)


def subject_label(subject: str, locale: str) -> str:
    meta = SUBJECTS_SAFE.get(subject) or SUBJECTS_SAFE["general"]
    loc = normalize_locale(locale)
    return meta.get(loc) or meta.get("he") or subject


# Avoid circular import of schema SUBJECTS at module load for typing clarity
from myroad_core.content.schema import SUBJECTS as SUBJECTS_SAFE  # noqa: E402
