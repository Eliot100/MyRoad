"""Per-road metrics screen (GET /play/{id}?view=stats, metrics v2)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from myroad_core.store import PathStore  # noqa: E402
from myroad_core.ui.app import create_learner_app  # noqa: E402
from myroad_core.ui.dates import days_ago, short_date  # noqa: E402
from myroad_core.ui.i18n import t  # noqa: E402
from test_step_player import PID, _at_practice, _path  # noqa: E402

_LOCALES = Path(__file__).resolve().parents[1] / "locales"


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(_path(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "steps.db"))
    application = create_learner_app(store=store, seed=False, seed_content=True)
    yield application
    store.close()


def _main(page: str) -> str:
    return page.split("<main", 1)[1].split("</main>", 1)[0]


def test_mid_road_metrics_screen_layout(app) -> None:
    c = _at_practice(app)
    c.post(f"/play/{PID}/answer", data={"choice": "zzz"})  # one wrong tap
    page = c.get(f"/play/{PID}?view=stats").text
    main = _main(page)
    assert 'class="rm-cols"' in main
    assert t("he", "metrics_path_h") in main and 'class="rm-units"' in main
    assert f'href="/play/{PID}?view=learn"' in main and t("he", "road_continue") in main
    aside = main.split('<aside class="card rm-side"', 1)[1]
    for key in ("metrics_progress", "metrics_current_step", "metrics_accuracy", "metrics_started"):
        assert t("he", key) in aside
    # No goal model exists: quiet empty state, no edit link, no fake numbers.
    assert t("he", "metrics_goals_soon") in aside and "עריכה" not in aside
    assert aside.count("<a ") == 0


def test_metrics_screen_highlights_the_road_in_the_sidebar(app) -> None:
    page = _at_practice(app).get(f"/play/{PID}?view=stats").text
    row = re.search(r'<a class="road[^"]*"[^>]*data-path-id="' + PID + r'"[^>]*>', page)
    assert row and 'aria-current="page"' in row.group(0)


def test_map_links_to_metrics(app) -> None:
    page = _at_practice(app).get(f"/play/{PID}?view=map").text
    assert f'href="/play/{PID}?view=stats"' in page


def test_metrics_get_writes_nothing(app) -> None:
    c = _at_practice(app)
    store = app.state.store
    before = store._conn.execute("SELECT COUNT(*) FROM learner_attempts").fetchone()[0]
    c.get(f"/play/{PID}?view=stats")
    assert store._conn.execute("SELECT COUNT(*) FROM learner_attempts").fetchone()[0] == before


def test_metric_keys_exist_in_every_locale() -> None:
    packs = {c: json.loads((_LOCALES / f"{c}.json").read_text(encoding="utf-8")) for c in ("he", "en", "ar")}
    keys = {k for k in packs["he"] if k.startswith("metrics_")}
    assert keys and all(keys <= {k for k in p if k.startswith("metrics_")} for p in packs.values())


def test_date_filters() -> None:
    now = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
    assert days_ago((now - timedelta(days=2)).isoformat(), now) == 2
    assert days_ago(None) is None and days_ago("junk") is None
    assert short_date(f"{datetime.now(timezone.utc).year}-10-20T08:00:00+00:00") == "20.10"
    assert short_date("") == ""
