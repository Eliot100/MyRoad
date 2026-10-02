"""Load content/*.json into PathStore as published demo seeds (human gate)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from myroad_core.content.schema import (
    GROUPS,
    SUBJECTS,
    ContentNode,
    ContentPath,
    infer_topics,
    validate_content_path,
)
from myroad_core.models import (
    Block,
    BlockType,
    Edge,
    EdgeRelationship,
    PathStatus,
    PathVersion,
)
from myroad_core.store import PathStore
from myroad_core.store_schema import _iso_now

# packages/core/src/myroad_core/content -> packages/core/content
_PKG_CORE = Path(__file__).resolve().parents[3]
DEFAULT_CONTENT_DIR = _PKG_CORE / "content"


def default_content_dir() -> Path:
    return DEFAULT_CONTENT_DIR


def _find_json_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.json"))


def load_content_paths(content_dir: Path | None = None) -> list[ContentPath]:
    root = content_dir or default_content_dir()
    paths: list[ContentPath] = []
    for fp in _find_json_files(root):
        with fp.open(encoding="utf-8") as f:
            data = json.load(f)
        paths.append(validate_content_path(data))
    return paths


_NODE_TO_BLOCK: dict[str, BlockType] = {
    "learn": BlockType.explanation,
    "celebrate": BlockType.explanation,
    "practice": BlockType.practice,
    "check": BlockType.assessment,
    "speak": BlockType.experience,
    "piano_keys": BlockType.experience,
    "rhythm": BlockType.experience,
}


def _node_to_block(node: ContentNode, index: int) -> Block:
    nid = node.id or f"n{index:03d}_{node.type}"
    block_id = f"blk_{index:03d}_{node.type}"
    kids = node.model_dump(mode="json", exclude_none=True)
    kids["id"] = nid
    content: dict[str, Any] = {"kids": kids, "nodeType": node.type, "nodeId": nid}
    if node.choices:
        content["verifiedCore"] = {
            "items": [
                {
                    "itemId": "choice",
                    "prompt": node.body_he,
                    "answer": node.correct,
                    "choices": [c.model_dump() for c in node.choices],
                }
            ]
        }
    mastery = None
    if node.type in ("practice", "check", "piano_keys", "rhythm"):
        mastery = {
            "type": "tap_correct" if node.choices else "complete_interaction",
            "passingCriterion": "correct_choice_or_sequence",
        }
    elif node.type in ("learn", "celebrate", "speak"):
        mastery = {"type": "view_and_confirm", "passingCriterion": "ack"}
    return Block(
        blockId=block_id,
        type=_NODE_TO_BLOCK[node.type],
        title=node.title,
        learningObjective=node.body_he[:120] if node.body_he else None,
        content=content,
        masteryRule=mastery,  # type: ignore[arg-type]
        editable=False,
    )


def content_to_path_version(path: ContentPath, *, version_id: str | None = None) -> PathVersion:
    now = _iso_now()
    blocks = [_node_to_block(n, i) for i, n in enumerate(path.nodes)]
    edges: list[Edge] = []
    for i in range(len(blocks) - 1):
        edges.append(
            Edge.model_validate(
                {
                    "edgeId": f"edge_{i:03d}",
                    "from": blocks[i].blockId,
                    "to": blocks[i + 1].blockId,
                    "relationship": EdgeRelationship.sequence.value,
                }
            )
        )
    subject_meta = SUBJECTS.get(path.subject, SUBJECTS["general"])
    vid = version_id or f"ver_{path.id}_demo_001"
    topics = [t.model_dump(mode="json") for t in infer_topics(path)]
    # Map node_id -> blockId for UI
    node_to_block: dict[str, str] = {}
    for i, n in enumerate(path.nodes):
        nid = n.id or f"n{i:03d}_{n.type}"
        node_to_block[nid] = blocks[i].blockId
    return PathVersion(
        schemaVersion="0.1.0",
        pathId=path.id,
        versionId=vid,
        version=1,
        status=PathStatus.draft,
        contentLanguage="he",
        uiLocale="he-IL",
        name=path.title_he,
        description=path.blurb_he,
        goal=path.blurb_he,
        audience={
            "level": "elementary" if path.grade else "general",
            "gradeHint": f"כיתה {path.grade}" if path.grade else None,
            "ageRange": "8-9" if path.grade == 3 else None,
        },
        createdAt=now,
        updatedAt=now,
        actors={
            "authorId": "user_owner_poc",
            "agentId": None,
            "lastEditorId": "user_owner_poc",
        },
        provenance={
            "origin": "demo_content_seed",
            "credit": "MyRoad sample content (content-as-data)",
            "basedOnPathId": None,
            "verifiedCoreBoundary": "answers in content.kids.correct",
        },
        sources=[],
        blocks=blocks,
        edges=edges,
        publishedImmutableNote=(
            "Demo sample path seeded as published for platform demo. "
            "Future paths still require human publish gate."
        ),
        subject=path.subject,
        subjectLabelHe=subject_meta["he"],
        subjectLabelEn=subject_meta.get("en"),
        subjectColor=subject_meta["color"],
        emoji=path.emoji,
        groupIds=path.group_ids,
        grade=path.grade,
        estimatedMinutes=path.estimated_minutes,
        blurbHe=path.blurb_he,
        blurbEn=path.blurb_en,
        titleEn=path.title_en,
        topics=topics,
        nodeToBlock=node_to_block,
        contentSource="packages/core/content",
        kidsDemo=path.grade == 3,
    )


def seed_content_paths(
    store: PathStore,
    *,
    content_dir: Path | None = None,
    actor_id: str = "user_owner_poc",
    correlation_id: str = "corr_seed_content_demo",
    publish: bool = True,
) -> dict[str, Any]:
    """
    Load all content JSON files into the store.

    When publish=True (default for the demo samples only), each path is
    saved as draft then published via the human publish gate (no agentId).
    Does not auto-publish arbitrary future drafts created through AgentTools.
    """
    loaded = load_content_paths(content_dir)
    seeded: list[dict[str, Any]] = []
    for i, path in enumerate(loaded):
        doc = content_to_path_version(path)
        corr = f"{correlation_id}_{i:02d}"
        store.save_version(
            actor_id=actor_id,
            agent_id=None,
            correlation_id=f"{corr}_save",
            document=doc,
        )
        if publish:
            store.request_publish(
                actor_id=actor_id,
                agent_id=None,
                correlation_id=f"{corr}_req",
                path_id=doc.pathId,
                version_id=doc.versionId,
            )
            store.publish(
                actor_id=actor_id,
                agent_id=None,
                correlation_id=f"{corr}_pub",
                path_id=doc.pathId,
                version_id=doc.versionId,
                publisher_id=actor_id,
            )
        seeded.append(
            {
                "pathId": path.id,
                "versionId": doc.versionId,
                "title": path.title_he,
                "subject": path.subject,
                "groupIds": path.group_ids,
                "published": publish,
                "nodeCount": len(path.nodes),
                "topicCount": len(infer_topics(path)),
            }
        )
    return {
        "count": len(seeded),
        "paths": seeded,
        "groups": list(GROUPS.values()),
        "subjects": SUBJECTS,
    }


def list_catalog_cards(store: PathStore) -> list[dict[str, Any]]:
    """Latest version of each path that carries catalog metadata (subject/group)."""
    rows = store._conn.execute(
        "SELECT path_id, document_json FROM versions v "
        "WHERE version_num = ("
        "  SELECT MAX(version_num) FROM versions v2 WHERE v2.path_id = v.path_id"
        ") ORDER BY path_id"
    ).fetchall()
    cards: list[dict[str, Any]] = []
    for row in rows:
        doc = PathVersion.model_validate_json(row["document_json"])
        raw = doc.model_dump(mode="json", by_alias=True)
        subject = raw.get("subject")
        if not subject:
            continue  # skip non-catalog paths (e.g. golden quadratic)
        subject_meta = SUBJECTS.get(subject, SUBJECTS["general"])
        topics = raw.get("topics") or []
        cards.append(
            {
                "pathId": doc.pathId,
                "versionId": doc.versionId,
                "status": doc.status.value if hasattr(doc.status, "value") else doc.status,
                "title": doc.name,
                "titleEn": raw.get("titleEn"),
                "blurb": raw.get("blurbHe") or doc.description or "",
                "blurbEn": raw.get("blurbEn") or "",
                "emoji": raw.get("emoji") or subject_meta["emoji"],
                "subject": subject,
                "subjectLabel": raw.get("subjectLabelHe") or subject_meta["he"],
                "subjectLabelEn": raw.get("subjectLabelEn") or subject_meta.get("en"),
                "subjectColor": raw.get("subjectColor") or subject_meta["color"],
                "groupIds": raw.get("groupIds") or [],
                "grade": raw.get("grade"),
                "estimatedMinutes": raw.get("estimatedMinutes"),
                "kidsDemo": bool(raw.get("kidsDemo")),
                "nodeCount": len(doc.blocks or []),
                "topicCount": len(topics),
            }
        )
    return cards


def group_catalog(
    cards: list[dict[str, Any]],
    *,
    group_id: str | None = None,
    subject: str | None = None,
) -> dict[str, Any]:
    filtered = cards
    gid = None if (not group_id or group_id == "all") else group_id
    if gid:
        filtered = [c for c in filtered if gid in (c.get("groupIds") or [])]
    if subject and subject != "all":
        filtered = [c for c in filtered if c.get("subject") == subject]
    group_meta = GROUPS.get(gid or "", {})
    return {
        "group": group_meta or None,
        "groups": list(GROUPS.values()),
        "subjects": SUBJECTS,
        "cards": filtered,
        "total": len(filtered),
    }
