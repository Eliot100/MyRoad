"""Bracketed math groups in RTL text (#71).

The ``bdi`` filter must wrap a bracketed math group — brackets, commas and spaces
included — as ONE ``<bdi dir="ltr">``, so "כ-(x, y)" no longer renders as "כ-x), (y".
Half-open intervals mix bracket types. A Hebrew prefix with a hyphen (כ-, ו-) stays
outside, attached to the sentence. Brackets holding only Hebrew are left alone.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

from myroad_core.ui.bidi import MAX_WRAP_CHARS, bidi_isolate

L, R = '<bdi dir="ltr">', "</bdi>"


def _w(s: str) -> str:
    return f"{L}{s}{R}"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Issue #71 acceptance strings, inside Hebrew sentences.
        ("כל נקודה כתובה כ-(x, y): קודם", f"כל נקודה כתובה כ-{_w('(x, y)')}: קודם"),
        ("הנקודה (2, -3) על הגרף", f"הנקודה {_w('(2, -3)')} על הגרף"),
        ("בקטע [0, 5] הפונקציה עולה", f"בקטע {_w('[0, 5]')} הפונקציה עולה"),
        ("הפונקציה f(x) = 2x + 1 היא קו ישר", f"הפונקציה {_w('f(x) = 2x + 1')} היא קו ישר"),
        # Half-open intervals: either opening bracket with either closing one.
        ("בקטע (0, 5] הפונקציה חיובית", f"בקטע {_w('(0, 5]')} הפונקציה חיובית"),
        ("בקטע [-2, 3) הפונקציה שלילית", f"בקטע {_w('[-2, 3)')} הפונקציה שלילית"),
        # Standalone negative number: the minus stays with the number.
        ("הפתרון הוא x = -3 בלבד", f"הפתרון הוא {_w('x = -3')} בלבד"),
        ("התשובה היא -3.", f"התשובה היא {_w('-3')}."),
        # Hyphen after a Hebrew prefix letter is a connector, outside the bdi.
        ("ו-7", f"ו-{_w('7')}"),
        ("עובר דרך (1, 2) ו-(3, 8).", f"עובר דרך {_w('(1, 2)')} ו-{_w('(3, 8)')}."),
        # Arabic sentence too.
        ("النقطة (2, -3) على الرسم", f"النقطة {_w('(2, -3)')} على الرسم"),
        # Nested group, sign before a group, exponent after a group.
        ("הנקודה (f(x), 2) על הגרף", f"הנקודה {_w('(f(x), 2)')} על הגרף"),
        ("פתיחת סוגריים: −(x − 3) = −x + 3", f"פתיחת סוגריים: {_w('−(x − 3) = −x + 3')}"),
        ("נכון. גם (−3)² = 9.", f"נכון. גם {_w('(−3)² = 9')}."),
        ("y = (x − 2)² + 3 היא פרבולה", f"{_w('y = (x − 2)² + 3')} היא פרבולה"),
        # Unchanged behaviour from #56.
        ("כמה זה 5 − (−3)?", f"כמה זה {_w('5 − (−3)')}?"),
        ("המספרים 5, 6", f"המספרים {_w('5')}, {_w('6')}"),
    ],
)
def test_bracketed_group_is_one_ltr_run(text: str, expected: str) -> None:
    assert bidi_isolate(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(ראו למטה)", "(ראו למטה)"),
        ("התשובה גדולה יותר (בדרך כלל).", "התשובה גדולה יותר (בדרך כלל)."),
        ("[הערה] קראו שוב", "[הערה] קראו שוב"),
        # A Hebrew bracket around a number: the brackets stay in the RTL text.
        ("(ראו 5)", f"(ראו {_w('5')})"),
        ("(ראו 5)²", f"(ראו {_w('5')})²"),
        ("(עמוד 3] ואז", f"(עמוד {_w('3')}] ואז"),
    ],
)
def test_hebrew_brackets_are_left_alone(text: str, expected: str) -> None:
    assert bidi_isolate(text) == expected


def test_prefix_stays_outside_and_brackets_stay_inside() -> None:
    out = str(bidi_isolate("כ-(x, y)"))
    assert out == f"כ-{L}(x, y){R}"
    # One bdi per group, holding both brackets and the comma.
    assert out.count("<bdi") == 1 and re.search(r"<bdi[^>]*>\(x, y\)</bdi>", out)


def test_groups_are_escaped_and_long_odd_input_stays_fast() -> None:
    # "<" / ">" are comparison signs, so this is a group; it is still escaped.
    assert bidi_isolate("כ-(x, <y>)") == f"כ-{_w('(x, &lt;y&gt;)')}"
    assert bidi_isolate("בקטע (x < 5) בלבד") == f"בקטע {_w('(x &lt; 5)')} בלבד"
    assert bidi_isolate("בקטע (a&b, 1)") == f"בקטע ({_w('a')}&amp;{_w('b')}, {_w('1')})"
    for odd in ("(" * 1999, "([" * 999, "-(" * 999, "( " * 999, "(1, " * 499):
        text = ("א" + odd)[:MAX_WRAP_CHARS]
        t0 = time.perf_counter()
        bidi_isolate(text)
        assert time.perf_counter() - t0 < 0.1, odd[:4]


def test_bagrut_step_body_wraps_the_point_notation() -> None:
    from myroad_core.content.loader import default_content_dir

    f = Path(default_content_dir()) / "adult" / "path_math_bagrut_3_units.json"
    if not f.is_file():
        pytest.skip("path_math_bagrut_3_units not in CONTENT_DIR")
    bodies = [n.get("body_he", "") for n in json.loads(f.read_text(encoding="utf-8"))["nodes"]]
    body = next(b for b in bodies if "כ-(x, y)" in b)
    assert f"כ-{L}(x, y){R}" in str(bidi_isolate(body))
