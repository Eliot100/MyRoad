"""Physics lab stays blocked until a staged program exists. No invented experiments."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from myroad_core.content.exercise_gen import teaching_generators
from myroad_core.content.loader import load_content_paths
from myroad_core.content.schema import validate_stage_levels
from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

LAB = "path_physics_bagrut5_lab"
CONTENT = Path(__file__).resolve().parents[4] / "MyRoad-content" / "adult" / "path_physics_bagrut5_lab.json"


def test_lab_path_has_no_stages_and_no_generator() -> None:
    paths = load_content_paths()
    lab = next(path for path in paths if path.id == LAB)
    assert lab.unavailable is True
    assert lab.nodes == [] and not lab.topics
    assert validate_stage_levels(lab) == []
    assert all(stage.path_id != LAB for stage in teaching_generators(paths))


def test_lab_road_is_a_calm_empty_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adult = tmp_path / "content" / "adult"
    adult.mkdir(parents=True)
    (adult / "path_physics_bagrut5_lab.json").write_text(CONTENT.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "lab.db"))
    try:
        client = TestClient(create_learner_app(store=store, seed=False, seed_content=True))
        page = client.get(f"/play/{LAB}")
        assert page.status_code == 200
        assert 'data-unavailable="1"' in page.text
        assert "עדיין לא זמין" in page.text
        assert "אין כאן ניסויים" in page.text
        assert "rd-cta" not in page.text
        assert "התחלת הדרך" not in page.text
        started = client.post(f"/play/{LAB}/start", data={"topic": "t"}, follow_redirects=False)
        assert started.status_code == 303
        assert started.headers["location"].endswith(f"/play/{LAB}")
        continued = client.get(f"/play/{LAB}/continue", follow_redirects=False)
        assert continued.status_code == 303
        assert continued.headers["location"].endswith(f"/play/{LAB}")
        detail = client.get(f"/road/{LAB}")
        assert detail.status_code == 200
        assert "עדיין לא זמין" in detail.text
        assert "התחלת הדרך" not in detail.text
    finally:
        store.close()
