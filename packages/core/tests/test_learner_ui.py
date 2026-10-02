"""Smoke tests for thin learner UI (requires [api] extras)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app


@pytest.fixture
def client(tmp_path):
    store = PathStore(str(tmp_path / "ui.db"))
    app = create_learner_app(store=store, seed=True)
    with TestClient(app) as c:
        yield c
    store.close()


def test_health_and_home(client: TestClient) -> None:
    h = client.get("/health")
    assert h.status_code == 200
    body = h.json()
    assert body["status"] == "ok"
    assert body["product"] == "MyRoad"
    assert body["pathId"] == "path_quadratic_he_hs_001"

    r = client.get("/author")
    assert r.status_code == 200
    assert "MyRoad" in r.text
    assert "משוואות ריבועיות" in r.text
    assert "פרסם מסלול" in r.text
    assert 'id="publish-btn" disabled' in r.text or 'disabled' in r.text


def test_ack_advances_and_feedback_records(client: TestClient) -> None:
    home = client.get("/author")
    assert home.status_code == 200
    ack = client.post("/author/ack", follow_redirects=True)
    assert ack.status_code == 200
    assert "אושר" in ack.text or "הדיסקרימיננטה" in ack.text

    fb = client.post(
        "/author/feedback",
        data={
            "rating": "4",
            "comment": "צריך עוד דוגמה",
            "proposed_change": "add numeric example",
        },
    )
    assert fb.status_code == 200
    assert "משוב נשמר" in fb.text


def test_practice_mastery_gate_and_no_autopublish(client: TestClient) -> None:
    # Jump to practice by acking explanations (3) then stay on practice
    for _ in range(3):
        client.post("/author/ack", follow_redirects=True)

    # Wrong answers — should not master
    r = client.post(
        "/author/submit",
        data={"prac_001": "0", "prac_002": "1", "prac_003": "9"},
    )
    assert r.status_code == 200
    assert "עדיין לא בשליטה" in r.text

    # Correct enough for minCorrect=2
    r2 = client.post(
        "/author/submit",
        data={"prac_001": "1", "prac_002": "2,3", "prac_003": "0"},
    )
    assert r2.status_code == 200
    assert "שליטה הושגה" in r2.text

    # Publish without human confirm must refuse
    denied = client.post("/author/publish", data={"publisher_id": "user_owner_poc"})
    assert denied.status_code == 200
    assert "נדרש אישור אנושי" in denied.text


def test_feedback_revise_one_click_shows_version_diff(client: TestClient) -> None:
    """Primary feedback action revises draft and surfaces a brief version diff."""
    home = client.get("/author")
    assert home.status_code == 200
    assert "ver_qeq_draft_001" in home.text or "גרסה:" in home.text

    fb = client.post(
        "/author/feedback",
        data={
            "rating": "2",
            "comment": "חסר תרגול",
            "proposed_change": "add remediation after feedback",
            "also_revise": "true",
        },
    )
    assert fb.status_code == 200
    assert "משוב נשמר" in fb.text
    assert "גרסת טיוטה חדשה" in fb.text
    assert "version-diff" in fb.text or "הפרש גרסאות" in fb.text
    assert "לא פורסם" in fb.text
    assert "published" not in fb.text.lower() or "לא פורסם" in fb.text


def test_feedback_only_without_revise(client: TestClient) -> None:
    before = client.get("/author")
    assert before.status_code == 200
    fb = client.post(
        "/author/feedback",
        data={
            "rating": "5",
            "comment": "מצוין",
            "proposed_change": "",
        },
    )
    assert fb.status_code == 200
    assert "משוב נשמר" in fb.text
    assert "הפרש גרסאות" not in fb.text
