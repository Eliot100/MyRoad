"""UI polish helpers for feedback→revise and version diff (golden loop)."""
from __future__ import annotations

from typing import Any


def build_revise_change_set(
    *,
    base_version_id: str,
    feedback_id: str,
    summary: str,
) -> dict[str, Any]:
    """Change set for one-click feedback → reviseDraft (draft only, never publish)."""
    return {
        "note": "thin-ui revise after learner feedback",
        "proposedChange": summary,
        "sourceFeedbackIds": [feedback_id],
        "_diff": {
            "fromVersionId": base_version_id,
            "summary": summary,
            "sourceFeedbackIds": [feedback_id],
            "changedBlockIds": [],
        },
    }


def build_version_diff(
    *,
    from_version_id: str,
    to_version_id: str,
    diff_ref: str | None,
    summary: str,
) -> dict[str, Any]:
    """Brief version-diff banner payload (cleared after one render)."""
    return {
        "fromVersionId": from_version_id,
        "toVersionId": to_version_id,
        "diffRef": diff_ref,
        "summary": summary,
        "status": "draft",
        "note": "טיוטה חדשה בלבד — לא פורסם",
    }
