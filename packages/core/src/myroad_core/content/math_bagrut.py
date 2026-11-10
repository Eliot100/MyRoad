"""Math 5-unit chain. Each road opens only after the one before it.

The exam stays closed until the last teaching road is finished. There is no
band that skips ahead: a finished placement opens algebra, not the exam.
"""

from __future__ import annotations

SERIES: tuple[tuple[str, str, str], ...] = (
    ("path_math_bagrut5_00_placement", "מבדק פתיחה", "Opening check"),
    ("path_math_bagrut5_01_algebra", "אלגברה", "Algebra"),
    ("path_math_bagrut5_02_geometry", "גיאומטריה אוקלידית", "Euclidean geometry"),
    ("path_math_bagrut5_03_trig", "טריגונומטריה במישור", "Plane trigonometry"),
    ("path_math_bagrut5_04_sequences", "סדרות ואינדוקציה", "Sequences and induction"),
    ("path_math_bagrut5_05_probability", "הסתברות", "Probability"),
    ("path_math_bagrut5_06_functions", "פונקציות ונגזרת", "Functions and the derivative"),
    ("path_math_bagrut5_07_extrema", "חקירה ונקודות קיצון", "Investigation and extrema"),
    ("path_math_bagrut5_08_integrals", "אינטגרלים ושטחים", "Integrals and areas"),
    ("path_math_bagrut5_09_analytic", "גיאומטריה אנליטית", "Analytic geometry"),
    ("path_math_bagrut5_10_vectors", "וקטורים וטריגונומטריה במרחב", "Vectors and space"),
    ("path_math_bagrut5_11_complex", "מספרים מרוכבים", "Complex numbers"),
    ("path_math_bagrut5_12_exp_log", "מעריכית, לוגריתם וגידול", "Exponential and log"),
    ("path_math_bagrut5_13_exam", "בחינת סיום", "Closing check"),
)

TEACHING: tuple[tuple[str, str, str], ...] = SERIES[1:-1]

_INDEX = {row[0]: i for i, row in enumerate(SERIES)}


def is_series(path_id: str) -> bool:
    return path_id in _INDEX


def series_index(path_id: str) -> int | None:
    return _INDEX.get(path_id)


def first_gap(completed: set[str]) -> int:
    """Index of the first road that is not finished. len(SERIES) when all are done."""
    for i, (pid, _he, _en) in enumerate(SERIES):
        if pid not in completed:
            return i
    return len(SERIES)


def road_state(index: int, completed: set[str], weak: set[str] | None = None) -> str:
    """gap, done, review, or locked. The gap is the single road to work now."""
    weak = weak or set()
    gap = first_gap(completed)
    pid = SERIES[index][0]
    if index == gap:
        return "gap"
    if pid in completed:
        return "review" if pid in weak else "done"
    return "locked"
