"""Bidi isolation for step text: keep math, numbers and Latin runs readable in RTL.

Hebrew and Arabic sentences often carry math ("5 − (−3)"), numbers and English
words. Without isolation the browser's bidi algorithm can reorder the neutral
characters (minus signs, parentheses, "=") so the expression reads scrambled.
The content is left untouched; at render time the ``bdi`` template filter wraps
each run of digits / operators / Latin letters in ``<bdi dir="ltr">``.

A bracketed math group — ``(x, y)``, ``[0, 5]``, half-open ``(0, 5]`` / ``[-2, 3)`` —
is one run, brackets included (#71): wrapping its parts separately left the
brackets and commas in the RTL context, where they mirror (``כ-x), (y``). Brackets
the run does not close (``(ראו 5)``) stay outside the ``<bdi>``, with the Hebrew text
they belong to; brackets holding only Hebrew are never touched.

Safety: the input is always treated as plain text. Every piece is HTML-escaped
before it is joined with the ``<bdi>`` tags, and only then marked safe, so the
filter never lets markup from the content through.
"""
from __future__ import annotations

import re
from typing import Any

from markupsafe import Markup, escape

# Inline spaces only, so a run never spans lines.
_SP = r"[ \u00a0\u202f]*"
# 12  3.5  1,000  3/4  12:30  50%  2²
_NUM = r"[0-9]+(?:[.,:/][0-9]+)*[²³]?%?"
# x  red  don't  e-mail  x²
_WORD = r"[A-Za-z]+(?:['’\-][A-Za-z]+)*[²³]?"
_SYM = r"[π∞]"
_OPERAND = rf"(?:{_NUM}|{_WORD}|{_SYM})"
# Opening brackets and unary signs before an operand: (−3), -5, √9
_PREFIX = r"[(\[−\-+±√]"
# A closing bracket may carry an exponent: (−3)², (x − 2)².
_SUFFIX = r"[)\]][²³]?"
# Binary operators between operands (ASCII hyphen-minus counts as minus).
_OP = r"[+\-−–×·÷*/=≠<>≤≥±^]"
# Inside a bracketed group: operands, operators, list separators and spaces — never
# Hebrew/Arabic letters, so "(ראו למטה)" is not a group. One nested level: "(f(x), 2)".
_GCH = r"[0-9A-Za-z.,;:/²³%π∞'’+\-−–×·÷*=≠<>≤≥±^ \u00a0\u202f]"
_OPEN, _CLOSE = "([", ")]"
# Either opening bracket with either closing one, so half-open intervals match too.
_GROUP = rf"[(\[](?:{_GCH}|[(\[]{_GCH}*+[)\]])*+[)\]][²³]?"
# Leading signs before a group ("−(2, 3)"); nesting brackets are part of the group itself.
_GSIGN = r"[−\-+±√]"
# Prefix repeats are bounded and possessive (no prefix char can start what follows), so
# a long run of "(" or "-" costs linear time, not quadratic.
_TERM = (
    rf"(?:(?:{_GSIGN}{_SP}){{0,8}}+{_GROUP}|(?:{_PREFIX}{_SP}){{0,8}}+{_OPERAND})(?:{_SP}{_SUFFIX})*"
)
# A run: terms joined by operators or spaces; "= ?" may close an exercise ("487 + 256 = ?").
# Possessive operator loop keeps matching linear on long strings of signs.
_RUN = re.compile(rf"{_TERM}(?:{_SP}(?:{_OP}{_SP})*+{_TERM})*(?:{_SP}={_SP}\?)?")
_SIGNS = "−-+±"
# Step texts are short (the longest in MyRoad-content is under 300 chars). Past this
# length the text is only escaped, which bounds the regex cost on odd input.
MAX_WRAP_CHARS = 2000
# Hebrew, Arabic (incl. Syriac/Thaana/NKo ranges) and their presentation forms.
_RTL = re.compile(r"[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]")
_LATIN = re.compile(r"[A-Za-z]")


def _trim_unpaired(text: str, start: int, end: int) -> tuple[int, int]:
    """Drop opening brackets at the start / closing ones at the end that the run doesn't pair.

    "(ראו 5)" matches the run "5)"; its ")" closes a Hebrew bracket, so it must stay
    in the RTL text (inside an LTR ``<bdi>`` it would not mirror). Any opener pairs with
    any closer, which keeps half-open intervals like "[-2, 3)" whole.
    """
    while True:
        opens: list[int] = []
        lone_close: list[int] = []
        for i in range(start, end):
            if text[i] in _OPEN:
                opens.append(i)
            elif text[i] in _CLOSE:
                if opens:
                    opens.pop()
                else:
                    lone_close.append(i)
        old = (start, end)
        if opens and opens[0] == start:
            start += 1
        if lone_close and text[lone_close[-1] + 1:end] in ("", "²", "³"):
            end = lone_close[-1]
        while start < end and text[start] in " \u00a0\u202f":
            start += 1
        while end > start and text[end - 1] in " \u00a0\u202f":
            end -= 1
        if (start, end) == old:
            return start, end


def _has_operand(run: str) -> bool:
    return any(ch.isascii() and ch.isalnum() for ch in run) or any(ch in "π∞" for ch in run)


def bidi_isolate(value: Any) -> Markup:
    """Escape ``value`` and wrap each math / number / Latin run in ``<bdi dir="ltr">``.

    Runs are wrapped when the text has Hebrew/Arabic letters, or when it has no
    letters at all (a bare "−8" or "5 − (−3)" label). English-only prose is returned
    escaped but unwrapped.

    ``None`` renders as an empty string. Markup input is treated as text too
    (its tags are escaped), so the result is always safe to render.
    """
    if value is None:
        return Markup("")
    # Plain ``str`` copy: Markup input is escaped like any other text.
    text = str.__str__(value) if isinstance(value, str) else str(value)
    if len(text) > MAX_WRAP_CHARS:
        return Markup(str(escape(text)))
    if not _RTL.search(text) and _LATIN.search(text):
        # Plain LTR prose (an English step): nothing to isolate it from, and leaving it
        # bare lets dir="auto" on the element pick LTR. Pure math ("−8") is still wrapped.
        return Markup(str(escape(text)))
    out: list[str] = []
    pos = 0
    for m in _RUN.finditer(text):
        start = m.start()
        # A sign glued to a preceding letter is a connector, not a minus: keep
        # "ו-7" / "מ-80" as "ו-" + run("7"), so the hyphen stays beside its word.
        while start < m.end() and text[start] in _SIGNS and start > 0 and text[start - 1].isalpha():
            start += 1
        start, end = _trim_unpaired(text, start, m.end())
        if not _has_operand(text[start:end]):
            continue
        out.append(str(escape(text[pos:start])))
        out.append('<bdi dir="ltr">' + str(escape(text[start:end])) + "</bdi>")
        pos = end
    out.append(str(escape(text[pos:])))
    return Markup("".join(out))
