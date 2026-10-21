"""English 5-unit series: placement decides which road opens first.

The chain is still 00 then 01 … 08. A finished placement does not force a
beginner through every earlier road, and it does not open the exam roads
before the weak band. Progress fields already stored on the placement path
are enough: completedAt, incorrectTaps, needsPractice.
"""

from __future__ import annotations

from typing import Any

SERIES: tuple[tuple[str, str, str], ...] = (
    ("path_english_bagrut5_00_placement", "מבדק רמה", "Level check"),
    ("path_english_bagrut5_01_zero", "מאפס", "First letters"),
    ("path_english_bagrut5_02_present", "הווה ויום יום", "Present and daily life"),
    ("path_english_bagrut5_03_time", "זמן וסיפור", "Time and story"),
    ("path_english_bagrut5_04_accuracy", "דיוק", "Accuracy"),
    ("path_english_bagrut5_05_module_e", "שאלון E", "Module E"),
    ("path_english_bagrut5_06_module_g", "שאלון G", "Module G"),
    ("path_english_bagrut5_07_literature_oral", "ספרות ודיבור", "Literature and speaking"),
    ("path_english_bagrut5_08_exam", "בחינה מלאה", "Full exam"),
)

_INDEX = {row[0]: i for i, row in enumerate(SERIES)}


def is_series(path_id: str) -> bool:
    return path_id in _INDEX


def series_index(path_id: str) -> int | None:
    return _INDEX.get(path_id)


def placement_band(progress: dict[str, Any] | None) -> int:
    """Highest road index (1-8) the learner should work now. 0 means still on the placement."""
    if not progress or not progress.get("completedAt"):
        return 0
    wrong = int(progress.get("incorrectTaps") or 0)
    if progress.get("needsPractice") or wrong >= 4:
        return 1
    if wrong >= 1:
        return 3
    return 5


def open_through(progress: dict[str, Any] | None, completed: set[str]) -> int:
    """Last series index that is open. Roads above it stay locked.

    Roads before the band stay open as optional review. From the band on,
    the next road opens only after the current one is finished. Finishing
    the first weak road does not open the exam.
    """
    band = placement_band(progress)
    if band == 0:
        return 0
    ceiling = band
    for i in range(band, len(SERIES) - 1):
        if SERIES[i][0] in completed:
            ceiling = i + 1
        else:
            break
    return ceiling


def recommended_index(
    progress: dict[str, Any] | None,
    completed: set[str],
    weak: set[str] | None = None,
) -> int:
    """The road to highlight: the placement, a weak open road, or the first gap."""
    band = placement_band(progress)
    if band == 0:
        return 0
    weak = weak or set()
    ceiling = open_through(progress, completed)
    for i in range(band, ceiling + 1):
        pid = SERIES[i][0]
        if pid not in completed or pid in weak:
            return i
    return ceiling


def extra_lock(
    path_id: str,
    progress: dict[str, Any] | None,
    completed: set[str],
) -> dict[str, str] | None:
    """A lock beyond prerequisite_path_ids, or None if this road may open."""
    index = series_index(path_id)
    if index is None or index == 0:
        return None
    ceiling = open_through(progress, completed)
    if index <= ceiling:
        return None
    if ceiling == 0:
        hold = SERIES[0]
    else:
        hold = SERIES[ceiling]
    return {"pathId": hold[0], "title": hold[1]}
