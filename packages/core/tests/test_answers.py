"""Unit tests for learner answer checking (no FastAPI required)."""

from myroad_core.ui.answers import answers_match, grade_items, mastery_passed


def test_answers_match_scalar_and_bool() -> None:
    assert answers_match(1, "1")
    assert answers_match(0, "0")
    assert answers_match(False, "לא")
    assert answers_match(True, "כן")


def test_answers_match_list_order_insensitive() -> None:
    assert answers_match([2, 3], "3, 2")
    assert answers_match([1, 3], "1 3")


def test_answers_match_dict_width_length() -> None:
    assert answers_match({"width": 6, "length": 8}, {"width": "6", "length": "8"})
    assert answers_match({"width": 6, "length": 8}, "6,8")


def test_grade_items_and_mastery() -> None:
    items = [
        {"itemId": "a", "prompt": "q1", "answer": 1},
        {"itemId": "b", "prompt": "q2", "answer": [2, 3]},
        {"itemId": "c", "prompt": "q3", "answer": 0},
    ]
    correct, total, details = grade_items(items, {"a": "1", "b": "3,2", "c": "1"})
    assert total == 3
    assert correct == 2
    assert details[2]["ok"] is False
    assert mastery_passed({"minCorrect": 2, "total": 3}, correct, total) is True
    assert mastery_passed({"minCorrect": 3, "total": 3}, correct, total) is False
