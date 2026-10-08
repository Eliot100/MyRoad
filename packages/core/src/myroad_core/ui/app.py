"""MyRoad platform UI: catalog + path player + author POC.

Run:
  cd packages/core && pip install -e ".[api]"
  uvicorn myroad_core.ui.app:app --reload --port 8765

Catalog seeds demo content paths as published (explicit sample allow-list).
A signed-in user may publish from the author screen. /add-path runs the agent
path builder (Cloudflare AI Gateway, or demo mode without it).
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from myroad_core.auth.origin import same_origin_ok
from myroad_core.content.loader import default_content_dir, seed_content_paths
from myroad_core.seed import find_repo_freeze_dir, seed_golden_quadratic
from myroad_core.store import PathStore
from myroad_core.tools import AgentTools
from myroad_core.ui.learner_actions import register_learner_actions
from myroad_core.ui.platform_routes import register_platform_routes

UI_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(UI_DIR / "templates"))

ACTOR_LEARNER = "user_learner_poc"
ACTOR_HUMAN = "user_owner_poc"
AGENT_UI = "agent_thin_ui_v0"


def _corr(prefix: str = "ui") -> str:
    return f"corr_{prefix}_{uuid.uuid4().hex[:10]}"


def _block_body(block: dict[str, Any]) -> dict[str, Any]:
    content = block.get("content") or {}
    core = content.get("verifiedCore") or {}
    shell = content.get("generativeShell") or {}
    he = shell.get("he") if isinstance(shell, dict) else None
    return {
        "definition": core.get("definition"),
        "formula": core.get("formula") or core.get("quadraticFormula"),
        "coefficients": core.get("coefficients"),
        "cases": core.get("cases") or core.get("discriminantCases"),
        "steps": core.get("steps"),
        "quiz_items": core.get("items") or [],
        "scenario": core.get("scenario"),
        "setup": core.get("setup"),
        "experience_answer": core.get("answer"),
        "solution": core.get("solution"),
        "shell_he": he,
        "raw_core": core,
    }


def create_learner_app(
    store: PathStore | None = None,
    *,
    db_path: str | None = None,
    seed: bool = True,
    seed_content: bool = True,
) -> FastAPI:
    from myroad_core.ui.db_path import resolve_ui_db_path

    resolved_db = db_path if db_path is not None else resolve_ui_db_path()
    path_store = store or PathStore(resolved_db)
    tools = AgentTools(path_store)
    seeded: dict[str, Any] = {}
    content_seed: dict[str, Any] = {}
    if seed:
        freeze = find_repo_freeze_dir(Path(__file__).resolve())
        seeded = seed_golden_quadratic(path_store, freeze_dir=freeze)
    if seed_content:
        content_dir = default_content_dir()
        if content_dir.is_dir():
            content_seed = seed_content_paths(path_store, content_dir=content_dir)

    app = FastAPI(title="MyRoad", version="0.9.0")
    app.state.store = path_store
    app.state.db_path = resolved_db
    app.state.tools = tools
    app.state.seed = seeded
    app.state.content_seed = content_seed
    app.state.sessions: dict[str, dict[str, Any]] = {}
    app.state.play_sessions: dict[str, dict[str, Any]] = {}
    # Opaque sid -> gateway check passed. Never stores provider keys.
    app.state.author_gateway_ok: dict[str, bool] = {}

    @app.middleware("http")
    async def _same_origin_forms(request: Request, call_next):
        # CSRF: every state-changing form POST must come from this site
        # (Origin/Referer check on top of SameSite=Lax). See auth/origin.py.
        if not same_origin_ok(request):
            return PlainTextResponse("cross-site form submission refused", status_code=403)
        return await call_next(request)

    static_dir = UI_DIR / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def _session(request: Request) -> dict[str, Any]:
        sid = request.cookies.get("myroad_sid")
        if not sid or sid not in app.state.sessions:
            sid = uuid.uuid4().hex
            path_id = seeded.get("pathId") or "path_quadratic_he_hs_001"
            version_ids = seeded.get("versionIds") or []
            version_id = version_ids[0] if version_ids else "ver_qeq_draft_001"
            app.state.sessions[sid] = {
                "sid": sid,
                "pathId": path_id,
                "versionId": version_id,
                "index": 0,
                "mastered": set(),
                "last_grade": None,
                "flash": None,
                "version_diff": None,
                "publish_enabled": False,
            }
        return app.state.sessions[sid]

    def _load_doc(sess: dict[str, Any]) -> dict[str, Any]:
        resp = tools.get_version(
            actor_id=ACTOR_LEARNER,
            correlation_id=_corr("get"),
            path_id=sess["pathId"],
            version_id=sess["versionId"],
        )
        if not resp.ok or not resp.data:
            raise RuntimeError(f"failed to load path: {resp.errors}")
        return resp.data["document"]

    def _render(
        request: Request,
        sess: dict[str, Any],
        *,
        grade: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> HTMLResponse:
        doc = _load_doc(sess)
        blocks = doc.get("blocks") or []
        n = len(blocks)
        idx = max(0, min(sess["index"], n - 1 if n else 0))
        sess["index"] = idx
        block = blocks[idx] if blocks else None
        flash = sess.pop("flash", None)
        version_diff = sess.pop("version_diff", None)
        ctx: dict[str, Any] = {
            "request": request,
            "product": "MyRoad",
            "path_name": doc.get("name"),
            "path_goal": doc.get("goal"),
            "path_id": doc.get("pathId"),
            "version_id": doc.get("versionId"),
            "status": doc.get("status"),
            "blocks": blocks,
            "index": idx,
            "total": n,
            "block": block,
            "body": _block_body(block) if block else {},
            "mastered": sess["mastered"],
            "grade": grade or sess.get("last_grade"),
            "flash": flash,
            "version_diff": version_diff,
            "can_prev": idx > 0,
            "can_next": idx < n - 1,
            "publish_enabled": sess.get("publish_enabled", False),
            "feedback_count": len(doc.get("feedback") or []),
            "author_base": "/author",
        }
        if extra:
            ctx.update(extra)
        response = TEMPLATES.TemplateResponse(request, "learner.html", ctx)
        if request.cookies.get("myroad_sid") != sess["sid"]:
            response.set_cookie("myroad_sid", sess["sid"], httponly=True, samesite="lax")
        return response

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "product": "MyRoad",
            "pathId": seeded.get("pathId"),
            "versionIds": seeded.get("versionIds"),
            "contentPaths": (content_seed or {}).get("count", 0),
        }

    # --- Author / golden-loop POC ---
    @app.get("/author", response_class=HTMLResponse)
    def author_home(request: Request) -> HTMLResponse:
        sess = _session(request)
        return _render(request, sess)

    @app.post("/author/nav/prev")
    def author_nav_prev(request: Request) -> RedirectResponse:
        sess = _session(request)
        sess["index"] = max(0, sess["index"] - 1)
        sess["last_grade"] = None
        resp = RedirectResponse("/author", status_code=303)
        resp.set_cookie("myroad_sid", sess["sid"], httponly=True, samesite="lax")
        return resp

    @app.post("/author/nav/next")
    def author_nav_next(request: Request) -> RedirectResponse:
        sess = _session(request)
        doc = _load_doc(sess)
        blocks = doc.get("blocks") or []
        block = blocks[sess["index"]] if blocks else None
        if block and block.get("type") in ("practice", "assessment", "experience"):
            if block["blockId"] not in sess["mastered"]:
                sess["flash"] = {
                    "level": "warn",
                    "text": "יש להשלים את הבלוק (שליטה) לפני מעבר הלאה.",
                }
                resp = RedirectResponse("/author", status_code=303)
                resp.set_cookie("myroad_sid", sess["sid"], httponly=True, samesite="lax")
                return resp
        sess["index"] = min(len(blocks) - 1, sess["index"] + 1)
        sess["last_grade"] = None
        resp = RedirectResponse("/author", status_code=303)
        resp.set_cookie("myroad_sid", sess["sid"], httponly=True, samesite="lax")
        return resp

    @app.post("/author/ack")
    def author_ack(request: Request) -> RedirectResponse:
        sess = _session(request)
        doc = _load_doc(sess)
        blocks = doc.get("blocks") or []
        block = blocks[sess["index"]] if blocks else None
        if block:
            sess["mastered"].add(block["blockId"])
            sess["flash"] = {"level": "ok", "text": "אושר — אפשר להמשיך לבלוק הבא."}
            if sess["index"] < len(blocks) - 1:
                sess["index"] += 1
                sess["last_grade"] = None
        resp = RedirectResponse("/author", status_code=303)
        resp.set_cookie("myroad_sid", sess["sid"], httponly=True, samesite="lax")
        return resp

    register_learner_actions(
        app,
        tools=tools,
        _session=_session,
        _render=_render,
        _load_doc=_load_doc,
        _block_body=_block_body,
        _corr=_corr,
        route_prefix="/author",
        redirect_path="/author",
    )

    register_platform_routes(
        app,
        templates=TEMPLATES,
        store=path_store,
        tools=tools,
        _corr=_corr,
    )

    return app


# Default app for uvicorn myroad_core.ui.app:app — file SQLite (see db_path.resolve_ui_db_path)
app = create_learner_app()
