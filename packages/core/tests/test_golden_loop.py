"""Tests for the golden loop E2E demo."""

from __future__ import annotations

from myroad_core.golden_loop import main, run_golden_loop
from myroad_core.models import PathStatus
from myroad_core.store import PathStore


def test_golden_loop_seed_path_human_publish_only(tmp_path) -> None:
    db = str(tmp_path / "golden_seed.db")
    summary = run_golden_loop(use_seed=True, db_path=db)

    assert summary["neverAutoPublish"] is True
    assert summary["origin"] == "seed_golden_quadratic"
    assert summary["pathId"] == "path_quadratic_he_hs_001"
    assert summary["status"] == PathStatus.published.value
    assert summary["feedbackId"]
    assert summary["revisedVersionId"] != summary["baseVersionId"]
    assert summary["diffRef"]
    assert len(summary["attempts"]) >= 1

    ops = [s["op"] for s in summary["steps"]]
    assert "publish_agent_denied" in ops
    assert "requestPublish" in ops
    assert "publish_human" in ops

    denied_step = next(s for s in summary["steps"] if s["op"] == "publish_agent_denied")
    assert denied_step["denied"] is True
    assert denied_step["code"] == "RBAC_DENY"

    store = PathStore(db)
    doc = store.get_version(summary["pathId"], summary["revisedVersionId"])
    assert doc.status == PathStatus.published
    assert any(b.blockId == "blk_golden_remediation" for b in doc.blocks)
    store.close()


def test_golden_loop_create_draft_path(tmp_path) -> None:
    summary = run_golden_loop(use_seed=False, db_path=str(tmp_path / "golden_draft.db"))
    assert summary["origin"] == "createDraft"
    assert summary["status"] == PathStatus.published.value
    assert summary["blockCount"] >= 3  # 2 created + remediation


def test_golden_loop_cli_exits_zero(tmp_path, capsys) -> None:
    code = main(["--db", str(tmp_path / "cli.db")])
    assert code == 0
    out = capsys.readouterr().out
    assert "golden loop OK" in out
    assert "DENIED" in out
