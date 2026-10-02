"""Thin learner UI over AgentTools + PathStore seed.

Run:
  cd packages/core && pip install -e ".[api]"
  uvicorn myroad_core.ui.app:app --reload --port 8765

Never auto-publishes. Publish requires an explicit human confirmation checkbox.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from myroad_core.seed import find_repo_freeze_dir, seed_golden_quadratic
from myroad_core.store import PathStore
from myroad_core.tools import AgentTools
from myroad_core.ui.answers import grade_items, mastery_passed

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
    db_path: str = ":memory:",
    seed: bool = True,
) -> FastAPI:
    path_store = store or PathStore(db_path)
    tools = AgentTools(path_store)
    seeded: dict[str, Any] = {}
    if seed:
        freeze = find_repo_freeze_dir(Path(__file__).resolve())
        seeded = seed_golden_quadratic(path_store, freeze_dir=freeze)

    app = FastAPI(title="MyRoad Learner UI", version="0.1.0")
    app.state.store = path_store
    app.state.tools = tools
    app.state.seed = seeded
    app.state.sessions: dict[str, dict[str, Any]] = {}

    static_dir = UI_DIR / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def _session(request: Request) -> dict[str, Any]:
        sid = request.cookies.get("myroad_sid")
        if not sid or sid not in app.state.sessions:
            sid = uuid.uuid4().hex
            path_id = seeded.get("pathId") or "path_quadratic_he_hs_001"
            version_ids = seeded.get("versionIds") or []
            # Prefer v1 (before feedback) for the learner loop
            version_id = version_ids[0] if version_ids else "ver_qeq_draft_001"
            app.state.sessions[sid] = {
                "sid": sid,
                "pathId": path_id,
                "versionId": version_id,
                "index": 0,
                "mastered": set(),
                "last_grade": None,
                "flash": None,
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
            "can_prev": idx > 0,
            "can_next": idx < n - 1,
            "publish_enabled": sess.get("publish_enabled", False),
            "feedback_count": len(doc.get("feedback") or []),
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
        }

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        sess = _session(request)
        return _render(request, sess)

    @app.post("/nav/prev")
    def nav_prev(request: Request) -> RedirectResponse:
        sess = _session(request)
        sess["index"] = max(0, sess["index"] - 1)
        sess["last_grade"] = None
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("myroad_sid", sess["sid"], httponly=True, samesite="lax")
        return resp

    @app.post("/nav/next")
    def nav_next(request: Request) -> RedirectResponse:
        sess = _session(request)
        doc = _load_doc(sess)
        blocks = doc.get("blocks") or []
        block = blocks[sess["index"]] if blocks else None
        # Gate advance for practice/assessment until mastered
        if block and block.get("type") in ("practice", "assessment", "experience"):
            if block["blockId"] not in sess["mastered"]:
                sess["flash"] = {
                    "level": "warn",
                    "text": "יש להשלים את הבלוק (שליטה) לפני מעבר הלאה.",
                }
                resp = RedirectResponse("/", status_code=303)
                resp.set_cookie("myroad_sid", sess["sid"], httponly=True, samesite="lax")
                return resp
        sess["index"] = min(len(blocks) - 1, sess["index"] + 1)
        sess["last_grade"] = None
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("myroad_sid", sess["sid"], httponly=True, samesite="lax")
        return resp

    @app.post("/ack")
    def ack_block(request: Request) -> RedirectResponse:
        """Mark explanation as viewed/confirmed (mastery view_and_confirm)."""
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
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("myroad_sid", sess["sid"], httponly=True, samesite="lax")
        return resp

    @app.post("/submit", response_class=HTMLResponse)
    async def submit_answers(request: Request) -> HTMLResponse:
        sess = _session(request)
        form = await request.form()
        doc = _load_doc(sess)
        blocks = doc.get("blocks") or []
        block = blocks[sess["index"]] if blocks else None
        if not block:
            sess["flash"] = {"level": "warn", "text": "אין בלוק פעיל."}
            return _render(request, sess)

        btype = block.get("type")
        body = _block_body(block)
        grade: dict[str, Any]

        if btype in ("practice", "assessment"):
            items = body["quiz_items"]
            submissions = {item["itemId"]: str(form.get(item["itemId"], "")) for item in items}
            correct, total, details = grade_items(items, submissions)
            rule = block.get("masteryRule") or {}
            passed = mastery_passed(rule if isinstance(rule, dict) else None, correct, total)
            grade = {
                "correct": correct,
                "total": total,
                "passed": passed,
                "details": details,
            }
            if passed:
                sess["mastered"].add(block["blockId"])
                sess["flash"] = {
                    "level": "ok",
                    "text": f"שליטה הושגה ({correct}/{total}). אפשר להמשיך.",
                }
            else:
                sess["flash"] = {
                    "level": "warn",
                    "text": f"עדיין לא בשליטה ({correct}/{total}). נסו שוב.",
                }
        elif btype == "experience":
            width = str(form.get("width", "")).strip()
            length = str(form.get("length", "")).strip()
            expected = body.get("experience_answer") or {}
            from myroad_core.ui.answers import answers_match

            ok = answers_match(expected, {"width": width, "length": length})
            grade = {
                "correct": 1 if ok else 0,
                "total": 1,
                "passed": ok,
                "details": [
                    {
                        "itemId": "experience",
                        "ok": ok,
                        "prompt": body.get("scenario"),
                        "given": f"width={width}, length={length}",
                        "expected": expected,
                        "solution": body.get("solution"),
                    }
                ],
            }
            if ok:
                sess["mastered"].add(block["blockId"])
                sess["flash"] = {"level": "ok", "text": "נכון! החוויה הושלמה."}
            else:
                sess["flash"] = {"level": "warn", "text": "לא מדויק — בדקו שוב את הפתרון."}
        else:
            grade = {"correct": 0, "total": 0, "passed": False, "details": []}
            sess["flash"] = {"level": "warn", "text": "סוג בלוק זה לא דורש הגשה."}

        sess["last_grade"] = grade
        return _render(request, sess, grade=grade)

    @app.post("/feedback", response_class=HTMLResponse)
    def record_feedback(
        request: Request,
        comment: str = Form(""),
        rating: int = Form(3),
        proposed_change: str = Form(""),
        also_revise: str | None = Form(None),
    ) -> HTMLResponse:
        sess = _session(request)
        doc = _load_doc(sess)
        blocks = doc.get("blocks") or []
        block = blocks[sess["index"]] if blocks else None
        block_id = block["blockId"] if block else None
        do_revise = str(also_revise or "").lower() in {"true", "1", "on", "yes"}

        fb = tools.record_feedback(
            actor_id=ACTOR_LEARNER,
            agent_id=AGENT_UI,
            correlation_id=_corr("fb"),
            path_id=sess["pathId"],
            version_id=sess["versionId"],
            target_block_id=block_id,
            rating=rating,
            comment=comment or None,
            proposed_change=proposed_change or None,
        )
        msg = "משוב נשמר."
        if not fb.ok:
            sess["flash"] = {
                "level": "warn",
                "text": f"שמירת משוב נכשלה: {fb.errors}",
            }
            return _render(request, sess)

        msg += f" (feedbackId={fb.data.get('feedbackId')})"

        if do_revise:
            # Conceptual reviseDraft path: new draft version from current + feedback ids
            change_set = {
                "note": "thin-ui revise after learner feedback",
                "proposedChange": proposed_change or comment,
                "sourceFeedbackIds": [fb.data.get("feedbackId")],
            }
            rev = tools.revise_draft(
                actor_id=ACTOR_LEARNER,
                agent_id=AGENT_UI,
                correlation_id=_corr("revise"),
                path_id=sess["pathId"],
                base_version_id=sess["versionId"],
                feedback_ids=[fb.data["feedbackId"]],
                change_set=change_set,
            )
            if rev.ok and rev.versionId:
                sess["versionId"] = rev.versionId
                sess["mastered"] = set()
                sess["index"] = 0
                sess["last_grade"] = None
                msg += f" · נוצרה גרסת טיוטה חדשה {rev.versionId} (לא פורסם)."
            else:
                msg += f" · reviseDraft נכשל: {rev.errors}"

        sess["flash"] = {"level": "ok", "text": msg}
        return _render(request, sess)

    @app.post("/publish", response_class=HTMLResponse)
    def publish_path(
        request: Request,
        human_confirm: str | None = Form(None),
        publisher_id: str = Form(ACTOR_HUMAN),
    ) -> HTMLResponse:
        """Publish only with explicit human confirmation. Never auto-publish."""
        sess = _session(request)
        confirmed = str(human_confirm or "").lower() in {"true", "1", "on", "yes"}
        if not confirmed:
            sess["flash"] = {
                "level": "warn",
                "text": "פרסום מבוטל — נדרש אישור אנושי מפורש (סימון התיבה).",
            }
            return _render(request, sess)

        # Human path: request_publish then publish with human_publisher, no agentId
        req = tools.request_publish(
            actor_id=publisher_id,
            agent_id=None,
            correlation_id=_corr("reqpub"),
            path_id=sess["pathId"],
            version_id=sess["versionId"],
            require_valid=True,
        )
        if not req.ok:
            # Allow publish attempt even if still draft-only gate; show validation
            sess["flash"] = {
                "level": "warn",
                "text": f"בקשת פרסום נכשלה (אולי ולידציה): {req.errors}",
            }
            return _render(request, sess)

        pub = tools.publish(
            actor_id=publisher_id,
            agent_id=None,
            correlation_id=_corr("pub"),
            path_id=sess["pathId"],
            version_id=sess["versionId"],
            publisher_id=publisher_id,
            human_publisher=True,
        )
        if pub.ok:
            sess["flash"] = {
                "level": "ok",
                "text": f"פורסם באישור אנושי. status={pub.status}",
            }
        else:
            sess["flash"] = {
                "level": "warn",
                "text": f"פרסום נדחה: {pub.errors}",
            }
        return _render(request, sess)

    return app


# Default app for uvicorn myroad_core.ui.app:app
app = create_learner_app()
