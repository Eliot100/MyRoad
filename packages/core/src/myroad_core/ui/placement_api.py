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
``gap`` is the series road id at that index. ``recommended_road_id`` is the published
road whose ``placement_route`` (content) covers the band, else null (still 200). The result is
stored on the learner's placement progress row (existing ``PathStore`` SQLite
table), so the series map and locks read the same result.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from myroad_core.auth.sessions import SESSION_COOKIE
from myroad_core.content.english_bagrut import SERIES, placement_band
from myroad_core.content.loader import list_catalog_cards
from myroad_core.content.variants import route_by_band, select_variants
from myroad_core.ui.i18n import COOKIE_LOCALE, normalize_locale
from myroad_core.store_schema import _iso_now

PLACEMENT_ID = SERIES[0][0]
CSRF_HEADER = "X-MyRoad-Request"


class PlacementAnswer(BaseModel):
    questionId: str = Field(min_length=1, max_length=200)
    correct: bool


class PlacementResultBody(BaseModel):
    answers: list[PlacementAnswer] = Field(min_length=1, max_length=200)
    # Optional (docs/decisions/0003): another placement path, e.g. the Arabic one. Routing then
    # uses each path's placement_route instead of the English series.
    placementId: str | None = Field(default=None, min_length=1, max_length=200)


class StepSettingsBody(BaseModel):
    audio: bool | None = None
    writing: bool | None = None


class WeeklyGoalBody(BaseModel):
    goal: Literal[2, 3, 5]


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status)


# Series page per subject. A fallback never leaves the placement's subject.
SUBJECT_SERIES_PAGE: dict[str, str] = {"english": "/series/english-bagrut5"}


def _published_docs(store) -> list[dict[str, Any]]:
    docs = []
    for c in list_catalog_cards(store):
        try:
            docs.append(store.get_version(c["pathId"], c["versionId"]).model_dump(mode="json", by_alias=True))
        except Exception:
            continue
    return docs


def placement_routes(store) -> list[dict[str, Any]]:
    """Published path docs that declare a placement_route (decision 0003)."""
    return [d for d in _published_docs(store) if d.get("placementRoute")]


def routed_road_id(store, placement_id: str, band: int) -> str | None:
    return route_by_band(placement_routes(store), placement_id, band) if band else None


def placement_target(store, placement_id: str, band: int) -> dict[str, Any]:
    """Road for a finished placement: ``{road, routing_gap, fallback_url}``.

    A matching placement_route wins (``routing_gap`` false). English with no match keeps the
    #152/#174 behaviour (no road, English series page). Any other placement with no match is a
    routing gap: the highest published road of the placement's subject whose band_min <= band,
    else the lowest such road (by path id); with no road at all, the subject's series page or "/".
    """
    docs = _published_docs(store)
    routes = [d for d in docs if d.get("placementRoute")]
    road = route_by_band(routes, placement_id, band) if band else None
    if road or placement_id == PLACEMENT_ID:
        return {"road": road, "routing_gap": False, "fallback_url": SUBJECT_SERIES_PAGE["english"]}
    placement = next((d for d in docs if d.get("pathId") == placement_id), None)
    subject = (placement or {}).get("subject")
    roads = sorted(
        (d for d in docs if subject and d.get("subject") == subject and d.get("pathId") != placement_id),
        key=lambda d: d["pathId"],
    )
    fitting = [d for d in roads if int((d.get("placementRoute") or {}).get("band_min", 10**6)) <= band]
    pick = max(fitting, key=lambda d: (int(d["placementRoute"]["band_min"]), d["pathId"])) if fitting else (
        roads[0] if roads else None
    )
    return {
        "road": pick["pathId"] if pick else None,
        "routing_gap": True,
        "fallback_url": SUBJECT_SERIES_PAGE.get(subject or "", "/"),
    }


def register_placement_api(app, *, store) -> None:
    def _user_id(request: Request) -> str | None:
        uid = store.get_session_user(request.cookies.get(SESSION_COOKIE))
        if not uid or not store.get_learner(uid):
            return None
        return uid

    def _result(progress: dict[str, Any], placement_id: str = PLACEMENT_ID) -> dict[str, Any]:
        band = placement_band(progress)
        target = placement_target(store, placement_id, band)
        road = target["road"]
        first_step = None
        card = next((c for c in list_catalog_cards(store) if c["pathId"] == road), None) if road else None
        if card:
            doc = store.get_version(road, card["versionId"]).model_dump(mode="json", by_alias=True)
            blocks = doc.get("blocks") or []
            first_step = blocks[0].get("blockId") if blocks else None
        return {
            "band": band,
            # English: the series chain road at the band (what the series page marks as the gap).
            "gap": SERIES[band][0] if placement_id == PLACEMENT_ID else road,
            "recommended_road_id": road,
            # True when no placement_route matched and the in-subject fallback picked the road.
            "routing_gap": target["routing_gap"],
            "placement_id": placement_id,
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
        pid = body.placementId or PLACEMENT_ID
        existing = store.get_progress(uid, pid) or {}
        progress = store.save_progress(
            uid,
            pid,
            version_id=existing.get("versionId"),
            node_index=int(existing.get("nodeIndex") or 0),
            mastered=existing.get("mastered") or set(),
            correct_taps=correct,
            incorrect_taps=incorrect,
            completed_at=_iso_now(),
            needs_practice=False,
        )
        result = _result(progress, pid)
        if result["routing_gap"]:
            store.record_placement_gap(uid, pid, result["band"])
        return JSONResponse(result)

    @app.get("/api/placement/result")
    def get_placement_result(request: Request, placementId: str | None = None) -> JSONResponse:
        uid = _user_id(request)
        if not uid:
            return _error(401, "unknown_learner")
        pid = placementId or PLACEMENT_ID
        progress = store.get_progress(uid, pid)
        if not progress or not progress.get("completedAt"):
            return _error(404, "no_placement_result")
        return JSONResponse(_result(progress, pid))

    @app.get("/api/settings/steps")
    def get_step_settings(request: Request) -> JSONResponse:
        uid = _user_id(request)
        if not uid:
            return _error(401, "unknown_learner")
        return JSONResponse(store.get_step_settings(uid))

    @app.post("/api/settings/steps")
    def post_step_settings(request: Request, body: StepSettingsBody) -> JSONResponse:
        """Learner step settings (audio on/off, writing on/off) that pick step variants."""
        if request.headers.get(CSRF_HEADER) != "1":
            return _error(403, "csrf_header_missing")
        uid = _user_id(request)
        if not uid:
            return _error(401, "unknown_learner")
        return JSONResponse(store.set_step_settings(uid, audio=body.audio, writing=body.writing))


    # --- Engagement (#192, docs/decisions/0004-session-model.md) -------------------------

    def _engagement_doc(uid: str, path_id: str) -> dict[str, Any] | None:
        card = next((c for c in list_catalog_cards(store) if c["pathId"] == path_id), None)
        if not card:
            return None
        doc = store.get_version(path_id, card["versionId"]).model_dump(mode="json", by_alias=True)
        return select_variants(doc, store.get_step_settings(uid))

    def _engagement_locale(request: Request, uid: str) -> str:
        cookie = request.cookies.get(COOKIE_LOCALE)
        return normalize_locale(cookie or (store.get_learner(uid) or {}).get("locale"))

    def _engagement_response(request: Request, path_id: str, *, new: bool) -> JSONResponse:
        if request.headers.get(CSRF_HEADER) != "1":
            return _error(403, "csrf_header_missing")
        uid = _user_id(request)
        if not uid:
            return _error(401, "unknown_learner")
        doc = _engagement_doc(uid, path_id)
        if doc is None:
            return _error(404, "unknown_path")
        from myroad_core.engagement import engagement_for  # lazy: engagement imports ui.dates

        return JSONResponse(engagement_for(store, uid, doc, _engagement_locale(request, uid), new_session=new))

    @app.get("/api/path/{path_id}/engagement")
    def get_engagement(request: Request, path_id: str) -> JSONResponse:
        return _engagement_response(request, path_id, new=False)

    @app.post("/api/path/{path_id}/session/next")
    def post_next_session(request: Request, path_id: str) -> JSONResponse:
        return _engagement_response(request, path_id, new=True)

    @app.get("/api/settings/weekly-goal")
    def get_weekly_goal(request: Request) -> JSONResponse:
        if request.headers.get(CSRF_HEADER) != "1":
            return _error(403, "csrf_header_missing")
        uid = _user_id(request)
        if not uid:
            return _error(401, "unknown_learner")
        return JSONResponse(store.get_weekly_goal(uid))

    @app.post("/api/settings/weekly-goal")
    def post_weekly_goal(request: Request, body: WeeklyGoalBody) -> JSONResponse:
        """Weekly active-days goal: 2, 3 or 5 (anything else is 422)."""
        if request.headers.get(CSRF_HEADER) != "1":
            return _error(403, "csrf_header_missing")
        uid = _user_id(request)
        if not uid:
            return _error(401, "unknown_learner")
        return JSONResponse(store.set_weekly_goal(uid, body.goal))
