"""Seed golden quadratic path drafts from freeze/v0 JSON into the store."""

from __future__ import annotations

import json
from pathlib import Path

from myroad_core.models import PathVersion
from myroad_core.store import PathStore

DEFAULT_FREEZE_DIR = Path(__file__).resolve().parents[4] / "freeze" / "v0"

BEFORE = "01-path-before-feedback.json"
AFTER = "02-path-after-feedback.json"


def load_freeze_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def seed_golden_quadratic(
    store: PathStore,
    *,
    freeze_dir: Path | None = None,
    actor_id: str = "user_owner_poc",
    correlation_id: str = "corr_seed_golden_v0",
) -> dict:
    """
    Load both golden path versions as drafts into the store.

    Returns summary with pathId and versionIds.
    """
    root = freeze_dir or DEFAULT_FREEZE_DIR
    before_path = root / BEFORE
    after_path = root / AFTER
    if not before_path.is_file() or not after_path.is_file():
        raise FileNotFoundError(
            f"freeze JSON missing under {root} (need {BEFORE} and {AFTER})"
        )

    before = PathVersion.model_validate(load_freeze_json(before_path))
    after = PathVersion.model_validate(load_freeze_json(after_path))

    # Insert v1 draft
    r1 = store.save_version(
        actor_id=actor_id,
        agent_id="agent_myroad_draft_v0",
        correlation_id=f"{correlation_id}_v1",
        document=before,
    )
    # Insert v2 draft (post-feedback)
    r2 = store.save_version(
        actor_id=actor_id,
        agent_id="agent_myroad_revise_v0",
        correlation_id=f"{correlation_id}_v2",
        document=after,
    )

    return {
        "pathId": before.pathId,
        "versionIds": [before.versionId, after.versionId],
        "auditEventIds": [r1.auditEventId, r2.auditEventId],
        "versions": store.list_versions(before.pathId),
    }


def find_repo_freeze_dir(start: Path | None = None) -> Path:
    """Walk up from start (or this file) to find freeze/v0."""
    cur = (start or Path(__file__).resolve()).resolve()
    if cur.is_file():
        cur = cur.parent
    for parent in [cur, *cur.parents]:
        candidate = parent / "freeze" / "v0"
        if (candidate / BEFORE).is_file():
            return candidate
    raise FileNotFoundError("could not locate freeze/v0 in parents")
