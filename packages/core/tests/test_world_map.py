"""Road world map (option B): real stages and tiles in, no game mechanics, sample levels only in preview."""
from __future__ import annotations

import json
import re
from pathlib import Path

from test_adult_learner_flow import LONG, N_TOPICS, _client, adult_app  # noqa: F401

STATIC = Path(__file__).resolve().parents[1] / "src" / "myroad_core" / "ui" / "static"


def _cards(page: str) -> list[str]:
    grid = page[page.index('class="stage-grid"'):]
    return re.findall(r'<li class="stage-card [^"]*"[^>]*>', grid)


def test_road_dashboard_uses_real_stages_and_tiles(adult_app) -> None:  # noqa: F811
    """The world map canvas is replaced by the road dashboard (arena c3): same real data, no JS needed."""
    app, _store = adult_app
    page = _client(app).get(f"/play/{LONG}").text
    cards = _cards(page)
    assert len(cards) == N_TOPICS and f'data-stages="{N_TOPICS}"' in page
    assert "is-here" in cards[0] and 'id="here"' in cards[0]
    assert page.count('class="tile-row is-here"') == 1 and page.count('aria-current="step"') == 1
    assert "worldmap.js" not in page and "world-map" not in page
    assert 'name="node"' in page  # tiles start through the existing POST /start form


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
