"""Placement result API (issue #152): band, gap and the recommended road as JSON.

``POST /api/placement/result``
    Headers: session cookie (``myroad_session``) and ``X-MyRoad-Request: 1``.
    Body: ``{"answers": [{"questionId": "q1", "correct": true}, ...]}`` (1-200 items).
    200: ``{"band": int, "gap": str, "recommended_road_id": str | null,
    "first_step_id": str | null, "correct": int, "incorrect": int, "completedAt": str}``.
    401 ``unknown_learner`` without a valid session; 403 ``csrf_header_missing``;
    422 for an invalid body.

``GET /api/placement/result``
    200: the last stored result (same shape). 404 ``no_placement_result``.

``band`` is the English series index from ``placement_band`` (1, 3 or 5) and
``gap`` is the series road id at that index. ``recommended_road_id`` is the gap
road when it is published in the catalog, else null (still 200). The result is
stored on the learner's placement progress row (existing ``PathStore`` SQLite
table), so the series map and locks read the same result.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from myroad_core.auth.sessions import SESSION_COOKIE
from myroad_core.content.english_bagrut import SERIES, placement_band
from myroad_core.content.loader import list_catalog_cards
from myroad_core.store_schema import _iso_now

PLACEMENT_ID = SERIES[0][0]
CSRF_HEADER = "X-MyRoad-Request"


class PlacementAnswer(BaseModel):
    questionId: str = Field(min_length=1, max_length=200)
    correct: bool


class PlacementResultBody(BaseModel):
    answers: list[PlacementAnswer] = Field(min_length=1, max_length=200)


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status)


def register_placement_api(app, *, store) -> None:
    def _user_id(request: Request) -> str | None:
        uid = store.get_session_user(request.cookies.get(SESSION_COOKIE))
        if not uid or not store.get_learner(uid):
            return None
        return uid

    def _result(progress: dict[str, Any]) -> dict[str, Any]:
        band = placement_band(progress)
        gap = SERIES[band][0]
        card = next((c for c in list_catalog_cards(store) if c["pathId"] == gap), None)
        first_step = None
        if card:
            doc = store.get_version(gap, card["versionId"]).model_dump(mode="json", by_alias=True)
            blocks = doc.get("blocks") or []
            first_step = blocks[0].get("blockId") if blocks else None
        return {
            "band": band,
            "gap": gap,
            "recommended_road_id": gap if card else None,
            "first_step_id": first_step,
            "correct": int(progress.get("correctTaps") or 0),
            "incorrect": int(progress.get("incorrectTaps") or 0),
            "completedAt": progress.get("completedAt"),
        }

    @app.post("/api/placement/result")
    def post_placement_result(request: Request, body: PlacementResultBody) -> JSONResponse:
        if request.headers.get(CSRF_HEADER) != "1":
            return _error(403, "csrf_header_missing")
        uid = _user_id(request)
        if not uid:
            return _error(401, "unknown_learner")
        correct = sum(1 for a in body.answers if a.correct)
        incorrect = len(body.answers) - correct
        existing = store.get_progress(uid, PLACEMENT_ID) or {}
        progress = store.save_progress(
            uid,
            PLACEMENT_ID,
            version_id=existing.get("versionId"),
            node_index=int(existing.get("nodeIndex") or 0),
            mastered=existing.get("mastered") or set(),
            correct_taps=correct,
            incorrect_taps=incorrect,
            completed_at=_iso_now(),
            needs_practice=False,
        )
        return JSONResponse(_result(progress))

    @app.get("/api/placement/result")
    def get_placement_result(request: Request) -> JSONResponse:
        uid = _user_id(request)
        if not uid:
            return _error(401, "unknown_learner")
        progress = store.get_progress(uid, PLACEMENT_ID)
        if not progress or not progress.get("completedAt"):
            return _error(404, "no_placement_result")
        return JSONResponse(_result(progress))

