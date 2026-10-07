"""Schema v2: adult/psychometric groups, long paths, step kind, interleaved review, prerequisites, unified score."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from myroad_core.content.schema import (
    NODE_BLOCK,
    NODE_STAGE,
    NODE_TYPES,
    check_prerequisites,
    validate_content_path,
)


def _path(**over):
    base = {
        "id": "path_math_zero",
        "titles": {"he": "מתמטיקה מאפס"},
        "blurbs": {"he": "מספרים עד משוואה"},
        "subject": "math",
        "group_ids": ["adult"],
        "emoji": "🔢",
        "estimated_minutes": 600,
        "topics": [
            {"id": "t1", "titles": {"he": "סדר פעולות"}, "node_ids": ["a1", "a2"]},
            {"id": "t2", "titles": {"he": "שליליים"}, "node_ids": ["b1", "b2"]},
            {"id": "t3", "titles": {"he": "חזרה"}, "node_ids": ["c1"]},
        ],
        "nodes": [
            {"id": "a1", "type": "learn", "title": "הסבר", "body_he": "כפל וחילוק משמאל לימין", "kind": "understanding"},
            {"id": "a2", "type": "practice", "title": "תרגול", "body_he": "12/3*2",
             "choices": [{"id": "x", "label": "8"}, {"id": "y", "label": "2"}], "correct": "x"},
            {"id": "b1", "type": "learn", "title": "הסבר", "body_he": "5-(-3)"},
            {"id": "b2", "type": "check", "title": "בדיקה", "body_he": "5-(-3)",
             "choices": [{"id": "x", "label": "8"}, {"id": "y", "label": "2"}], "correct": "x"},
            {"id": "c1", "type": "practice", "title": "חזרה מעורבת", "body_he": "מעורב", "kind": "review",
             "review_topic_ids": ["t1", "t2"],
             "choices": [{"id": "x", "label": "1"}], "correct": "x"},
        ],
    }
    base.update(over)
    return base


def test_adult_long_path_with_interleaved_review_validates():
    p = validate_content_path(_path())
    assert p.group_ids == ["adult"]
    assert p.nodes[-1].review_topic_ids == ["t1", "t2"]
    assert p.nodes[0].kind == "understanding"


def test_review_topic_must_come_earlier():
    data = _path()
    data["nodes"][-1]["review_topic_ids"] = ["t1", "t3"]
    with pytest.raises(ValidationError, match="earlier"):
        validate_content_path(data)


def test_review_topic_must_exist():
    data = _path()
    data["nodes"][-1]["review_topic_ids"] = ["nope"]
    with pytest.raises(ValidationError, match="unknown review topic"):
        validate_content_path(data)


def test_review_topics_require_review_kind():
    data = _path()
    data["nodes"][-1]["kind"] = "understanding"
    with pytest.raises(ValidationError, match="kind 'review'"):
        validate_content_path(data)


def test_unknown_kind_rejected():
    data = _path()
    data["nodes"][0]["kind"] = "drill"
    with pytest.raises(ValidationError):
        validate_content_path(data)


def test_minutes_cap_is_twenty_hours():
    validate_content_path(_path(estimated_minutes=1200))
    with pytest.raises(ValidationError):
        validate_content_path(_path(estimated_minutes=1201))


def test_score_link_psychometric():
    p = validate_content_path(_path(group_ids=["psychometric"],
                                    score={"group_id": "psychometric_800", "part_id": "quantitative"}))
    assert p.score.weight == 1.0
    with pytest.raises(ValidationError):
        validate_content_path(_path(score={"group_id": "psychometric_800", "part_id": "chemistry"}))
    with pytest.raises(ValidationError):
        validate_content_path(_path(score={"group_id": "sat", "part_id": "math"}))


def test_hebrew_subject_allowed():
    validate_content_path(_path(subject="hebrew"))


def test_prerequisite_shape():
    validate_content_path(_path(prerequisite_path_ids=["path_numbers"]))
    for bad in (["numbers"], ["path_math_zero"], ["path_a", "path_a"]):
        with pytest.raises(ValidationError):
            validate_content_path(_path(prerequisite_path_ids=bad))


def test_check_prerequisites_unknown_and_cycle():
    a = validate_content_path(_path(id="path_a", prerequisite_path_ids=["path_b"]))
    b = validate_content_path(_path(id="path_b", prerequisite_path_ids=["path_a"]))
    c = validate_content_path(_path(id="path_c", prerequisite_path_ids=["path_missing"]))
    problems = check_prerequisites([a, b, c])
    assert any("cycle" in x for x in problems)
    assert any("path_missing" in x for x in problems)
    assert check_prerequisites([validate_content_path(_path(id="path_x"))]) == []


def test_step_type_maps_cover_every_node_type():
    assert set(NODE_STAGE) == set(NODE_TYPES) == set(NODE_BLOCK)
    assert set(NODE_STAGE.values()) <= {"explanation", "practice", "check", "experience"}


def test_old_files_still_valid_without_new_fields():
    data = _path(group_ids=["grade3"], estimated_minutes=15)
    for n in data["nodes"]:
        n.pop("kind", None)
        n.pop("review_topic_ids", None)
    validate_content_path(data)
