"""Arabic script rendering (#170): letter forms, font, and CSS that keeps joins intact."""

from pathlib import Path

from myroad_core.ui.arabic import ZWJ, forms_of, letter_forms

UI = Path(__file__).resolve().parents[1] / "src" / "myroad_core" / "ui"


def test_dual_joining_letter_gets_four_zwj_forms():
    f = forms_of("ب")
    assert (f["isolated"], f["initial"], f["medial"], f["final"]) == ("ب", "ب" + ZWJ, ZWJ + "ب" + ZWJ, ZWJ + "ب")
    assert f["dual"]


def test_right_joining_letter_never_joins_forward():
    f = forms_of("د")
    assert f["initial"] == "د" and f["medial"] == ZWJ + "د" and not f["dual"]


def test_letter_forms_only_for_runs_of_single_letters():
    assert [f["letter"] for f in letter_forms("ا ب ت ن م ل")] == list("ابتنمل")
    assert letter_forms("بَاب") is None
    assert letter_forms("ب + ا + ب = بَاب") is None
    assert letter_forms("a b c") is None
    assert letter_forms("") is None


def test_font_is_self_hosted_with_arabic_unicode_range():
    css = (UI / "static" / "platform.css").read_text(encoding="utf-8")
    assert '"MyRoad Naskh"' in css and "unicode-range: U+0600-06FF" in css
    assert (UI / "static" / "fonts" / "noto-naskh-arabic-wght.woff2").stat().st_size > 50_000
    assert ":lang(ar) { letter-spacing: 0 !important; text-transform: none !important" in css


def test_content_token_is_not_forced_ltr():
    tpl = (UI / "templates" / "_step_card.html").read_text(encoding="utf-8")
    assert "letter_forms" in tpl
    assert "lang=\"{{ content_locale or 'en' }}\" dir=\"ltr\"" not in tpl
