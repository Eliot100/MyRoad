"""Completeness rule and live draft problems for agent-built paths.

The rules moved unchanged to ``myroad_core.content.publish_rules`` (issue #42)
so the store and the /tools API can use them without importing the builder.
This module re-exports them so existing imports keep working (temporary
re-export; new code should import from ``myroad_core.content.publish_rules``).
"""
from __future__ import annotations

from myroad_core.content.publish_rules import (  # noqa: F401  (re-exports)
    _BLOCK_TO_STAGE,
    BLOCKING_CODES,
    MIN_STAGES,
    MIN_TOPICS,
    PROBLEM_CODES,
    PROBLEM_KEY_PREFIX,
    PUBLISH_FORMAT_ERROR,
    PUBLISH_NOT_COMPLETE,
    REQUIRED_STAGE_TYPES,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    STAGE_TYPES,
    CompletenessReport,
    DraftProblem,
    blocking_problems,
    check_path_completeness,
    draft_problems,
)

__all__ = [
    "BLOCKING_CODES",
    "MIN_STAGES",
    "MIN_TOPICS",
    "PROBLEM_CODES",
    "PROBLEM_KEY_PREFIX",
    "PUBLISH_FORMAT_ERROR",
    "PUBLISH_NOT_COMPLETE",
    "REQUIRED_STAGE_TYPES",
    "SEVERITY_ERROR",
    "SEVERITY_WARNING",
    "STAGE_TYPES",
    "CompletenessReport",
    "DraftProblem",
    "blocking_problems",
    "check_path_completeness",
    "draft_problems",
]
