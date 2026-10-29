"""Road world map (option B): real stages and tiles in, no game mechanics, sample levels only in preview."""
from __future__ import annotations

import html as _html
import json
import re
from pathlib import Path

from test_adult_learner_flow import LONG, N_TOPICS, _client, adult_app  # noqa: F401

STATIC = Path(__file__).resolve().parents[1] / "src" / "myroad_core" / "ui" / "static"


def _stages(page: str) -> list[dict]:
    m = re.search(r'data-stages="([^"]*)"', page)
    assert m, "world map data missing"
    return json.loads(_html.unescape(m.group(1)))


def test_world_map_uses_real_stages_and_tiles(adult_app, monkeypatch) -> None:  # noqa: F811
    monkeypatch.delenv("MYROAD_UI_PREVIEW", raising=False)
    app, _store = adult_app
    page = _client(app).get(f"/play/{LONG}").text
    stages = _stages(page)
    assert len(stages) == N_TOPICS
    assert all(s["tiles"] and s["total"] == len(s["tiles"]) for s in stages)
    assert stages[0]["state"] == "cur" and stages[0]["tiles"][0]["state"] == "cur"
    assert 'data-preview="0"' in page and "world-sample" not in page
    assert '<script src="/static/worldmap.js" defer></script>' in page
    assert 'id="world-go"' in page  # tiles start through the existing POST /start form


def test_world_map_preview_flag_only_with_env(adult_app, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setenv("MYROAD_UI_PREVIEW", "1")
    app, _store = adult_app
    page = _client(app).get(f"/play/{LONG}").text
    assert 'data-preview="1"' in page and 'class="world-sample"' in page


def test_world_map_has_no_game_mechanics() -> None:
    js = (STATIC / "worldmap.js").read_text(encoding="utf-8").lower()
    for word in ("streak", "leaderboard", "achievement", "points", "star"):
        code = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
        assert word not in code, word


def test_world_map_strings_are_neutral_and_dashless() -> None:
    root = Path(__file__).resolve().parents[1] / "locales"
    for loc in ("he", "ar", "en"):
        d = json.loads((root / f"{loc}.json").read_text(encoding="utf-8"))
        for k, v in d.items():
            if k.startswith("world_"):
                assert "—" not in v and "–" not in v and " - " not in v, (loc, k)
    he = json.loads((root / "he.json").read_text(encoding="utf-8"))
    assert he["world_here"] == "כאן עכשיו" and "אתה" not in he["world_here"]
    assert he["station_of"].startswith("שלב") and he["progress_label"].startswith("משבצת")
