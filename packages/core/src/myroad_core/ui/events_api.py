"""Client analytics batches (issue #208): ``POST /api/events``.

Headers: session cookie (``myroad_session``) and ``X-MyRoad-Request: 1``.
Body: ``{"events": [{"type": "tap"|"screen_view"|"answer_submit", "screen": str?,
"ts": int?, "props": {...}}]}`` (1-50 events, <= 16 KB). Schema in docs/analytics-events.md.

204 stored (or analytics switched off); 401 ``unknown_learner``; 403 ``csrf_header_missing``;
413 ``payload_too_large``; 422 invalid body, unknown event type or PII; 429 ``rate_limited``.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from typing import Literal

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from myroad_core.analytics import PiiError, analytics_enabled
from myroad_core.auth.sessions import SESSION_COOKIE

CSRF_HEADER = "X-MyRoad-Request"
MAX_BODY_BYTES = 16 * 1024
MAX_EVENTS = 50
RATE_BATCHES = 30  # per learner per window
RATE_WINDOW_SEC = 60.0

_TOKEN = r"^[A-Za-z0-9_./:\-]{1,160}$"


class ClientProps(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str | None = Field(default=None, pattern=_TOKEN)
    from_screen: str | None = Field(default=None, pattern=_TOKEN)
    ms: int | None = Field(default=None, ge=0, le=24 * 3600 * 1000)
    path_id: str | None = Field(default=None, pattern=_TOKEN)
    block_id: str | None = Field(default=None, pattern=_TOKEN)
    latency_ms: int | None = Field(default=None, ge=0, le=24 * 3600 * 1000)


class ClientEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["tap", "screen_view", "answer_submit"]
    screen: str | None = Field(default=None, pattern=_TOKEN)
    ts: int | None = Field(default=None, ge=0)
    props: ClientProps = Field(default_factory=ClientProps)


class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[ClientEvent] = Field(min_length=1, max_length=MAX_EVENTS)


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status)


def register_events_api(app, *, store) -> None:
    hits: dict[str, deque] = defaultdict(deque)

    def _rate_ok(uid: str) -> bool:
        now = time.monotonic()
        q = hits[uid]
        while q and now - q[0] > RATE_WINDOW_SEC:
            q.popleft()
        if len(q) >= RATE_BATCHES:
            return False
        q.append(now)
        return True

    @app.post("/api/events")
    async def post_events(request: Request) -> Response:
        if request.headers.get(CSRF_HEADER) != "1":
            return _error(403, "csrf_header_missing")
        uid = store.get_session_user(request.cookies.get(SESSION_COOKIE))
        if not uid or not store.get_learner(uid):
            return _error(401, "unknown_learner")
        try:
            declared = int(request.headers.get("content-length") or 0)
        except ValueError:
            declared = 0
        if declared > MAX_BODY_BYTES:
            return _error(413, "payload_too_large")
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            return _error(413, "payload_too_large")
        if not _rate_ok(uid):
            return _error(429, "rate_limited")
        try:
            batch = EventBatch.model_validate(json.loads(raw or b"null"))
        except (ValueError, ValidationError):
            return _error(422, "invalid_events")
        if not analytics_enabled():
            return Response(status_code=204)
        events = [e.model_dump(exclude_none=True) for e in batch.events]
        for e in events:
            e["props"] = {k: v for k, v in (e.get("props") or {}).items() if v is not None}
        try:
            store.record_analytics_events(uid, events, source="client")
        except PiiError:
            return _error(422, "pii_rejected")
        except ValueError:
            return _error(422, "invalid_events")
        return Response(status_code=204)
