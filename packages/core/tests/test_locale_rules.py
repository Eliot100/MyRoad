"""Locale consistency: explanations follow UI locale; content tokens stay in content_locale."""

from __future__ import annotations

import copy

import pytest

from myroad_core.content.loader import default_content_dir, load_content_paths
from myroad_core.content.locale_rules import (
    assert_locale_consistent,
    resolve_node_display,
    validate_locale_consistency,
)
from myroad_core.content.schema import validate_content_path


def test_all_paths_locale_rules_pass() -> None:
    paths = load_content_paths(default_content_dir())
    assert len(paths) == 10
    for p in paths:
        errs = validate_locale_consistency(p)
        assert errs == [], errs
        assert_locale_consistent(p)


def test_english_paths_declare_locale_split() -> None:
    paths = {p.id: p for p in load_content_paths(default_content_dir())}
    for pid in (
        "path_grade3_english_colors",
        "path_grade3_english_animals",
        "path_grade3_english_hello",
    ):
        p = paths[pid]
        assert p.explain_locale == "he"
        assert p.content_locale == "en"
        with_content = [n for n in p.nodes if n.body_content]
        assert len(with_content) >= 5
        # Explanations exist in HE; EN UI explanations also present
        assert all(n.body_he for n in p.nodes)
        assert all(n.body_en for n in p.nodes)


def test_resolve_node_display_switches_ui_keeps_content() -> None:
    paths = {p.id: p for p in load_content_paths(default_content_dir())}
    node = next(n for n in paths["path_grade3_english_colors"].nodes if n.id == "practice_red")
    he = resolve_node_display(node, ui_locale="he", content_locale="en")
    en = resolve_node_display(node, ui_locale="en", content_locale="en")
    assert "אדום" in he["body"] or "אנגלית" in he["body"]
    assert "English" in en["body"] or "red" in en["body"].lower()
    assert he["body_content"] == en["body_content"] == "red"
    assert "red" in he["speak"].lower()


def test_unexplained_english_chrome_fails() -> None:
    paths = load_content_paths(default_content_dir())
    base = next(p for p in paths if p.id == "path_grade3_english_hello")
    data = base.model_dump(mode="json")
    # Corrupt first node: English-only explanation, no body_content
    data["nodes"][0]["body_he"] = "Today we learn hello goodbye thank you please words together"
    data["nodes"][0]["body_ui"] = None
    data["nodes"][0]["body_content"] = None
    data["nodes"][0]["speak_text"] = None
    bad = validate_content_path(data)
    errs = validate_locale_consistency(bad)
    assert errs, "expected locale consistency failure"
    assert any("unexplained" in e.lower() or "missing body_content" in e.lower() or "speak_text" in e for e in errs)


def test_english_subject_requires_content_locale_en() -> None:
    paths = load_content_paths(default_content_dir())
    base = next(p for p in paths if p.id == "path_grade3_english_hello")
    data = base.model_dump(mode="json")
    data["content_locale"] = "he"
    # schema defaults english subject back to en — force via object copy after validate
    path = validate_content_path(data)
    # After validate, subject=english may coerce content_locale to en
    if path.content_locale == "en":
        # manually break for rule check
        object.__setattr__(path, "content_locale", "he")
    errs = validate_locale_consistency(path)
    assert any("content_locale" in e for e in errs)
