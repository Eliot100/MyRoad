"""Arabic script helpers for the step player (#170).

Alphabet steps show a run of single letters ("ا ب ت ن م ل"). Arabic letters change shape
by position, so the player shows each letter in its four forms. The forms come from the
font's own shaping: a zero-width joiner (U+200D) on a side makes the letter join there,
without a fake neighbour letter. Right-joining letters (ا د ذ ر ز و ...) never join to
the next letter, so their initial form is the isolated one and their medial is the final.
"""

from __future__ import annotations

from typing import TypedDict

ZWJ = "\u200d"

# Letters that join only to the preceding letter (never to the following one).
RIGHT_JOINING = frozenset("اأإآٱدذرزوؤةى")
# Arabic letters (base block). Harakat and digits are excluded on purpose.
_LETTER_RANGES = ((0x0621, 0x064A), (0x0671, 0x06D3))
_HARAKAT = frozenset(chr(c) for c in range(0x064B, 0x0653)) | {"\u0670"}


class LetterForms(TypedDict):
    letter: str
    isolated: str
    initial: str
    medial: str
    final: str
    dual: bool


def _is_letter(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _LETTER_RANGES) and ch != "\u0640"


def forms_of(letter: str) -> LetterForms:
    dual = letter not in RIGHT_JOINING
    return {
        "letter": letter,
        "isolated": letter,
        "initial": letter + ZWJ if dual else letter,
        "medial": ZWJ + letter + ZWJ if dual else ZWJ + letter,
        "final": ZWJ + letter,
        "dual": dual,
    }


def letter_forms(text: str | None) -> list[LetterForms] | None:
    """Forms for each letter when ``text`` is a run of single Arabic letters, else None.

    "ا ب ت" -> three entries. Words, sentences, or letters with harakat return None,
    so ordinary steps keep the plain content line.
    """
    if not text:
        return None
    tokens = text.split()
    if not tokens or len(tokens) > 14:
        return None
    if not all(len(t) == 1 and _is_letter(t) and t not in _HARAKAT for t in tokens):
        return None
    return [forms_of(t) for t in tokens]
