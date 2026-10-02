"""Platform catalog + path player (age-agnostic shell; content drives tone)."""

from __future__ import annotations

import uuid
from typing import Any, Callable

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from myroad_core.content.loader import group_catalog, list_catalog_cards
from myroad_core.content.schema import GROUPS, SUBJECTS

ACTOR_LEARNER = "user_learner_poc"


def _kids_payload(block: dict[str, Any] | None) -> dict[str, Any]:
    if not block:
        return {}
    content = block.get("content") or {}
    kids = content.get("kids") or {}
    return kids if isinstance(kids, dict) else {}


def register_platform_routes(
    app,
    *,
    templates: Jinja2Templates,
    store,
    tools,
    _corr: Callable[[str], str],
) -> None:
    def _play_session(request: Request, path_id: str) -> dict[str, Any]:
        sid = request.cookies.get("myroad_play")
        sessions: dict[str, dict[str, Any]] = app.state.play_sessions
        if not sid or sid not in sessions or sessions[sid].get("pathId") != path_id:
            sid = uuid.uuid4().hex
            latest = store.get_path_latest(path_id)
            sessions[sid] = {
                "sid": sid,
                "pathId": path_id,
                "versionId": latest.versionId,
                "index": 0,
                "mastered": set(),
                "last_result": None,
                "flash": None,
            }
        return sessions[sid]

    def _load_play_doc(sess: dict[str, Any]) -> dict[str, Any]:
        resp = tools.get_version(
            actor_id=ACTOR_LEARNER,
            correlation_id=_corr("play_get"),
            path_id=sess["pathId"],
            version_id=sess["versionId"],
        )
        if not resp.ok or not resp.data:
            raise RuntimeError(f"failed to load path: {resp.errors}")
        return resp.data["document"]

    def _card_meta(doc: dict[str, Any]) -> dict[str, Any]:
        subject = doc.get("subject") or "general"
        meta = SUBJECTS.get(subject, SUBJECTS["general"])
        return {
            "subject": subject,
            "subjectLabel": doc.get("subjectLabelHe") or meta["he"],
            "subjectColor": doc.get("subjectColor") or meta["color"],
            "emoji": doc.get("emoji") or meta["emoji"],
            "kidsDemo": bool(doc.get("kidsDemo")),
            "estimatedMinutes": doc.get("estimatedMinutes"),
            "groupIds": doc.get("groupIds") or [],
        }

    @app.get("/", response_class=HTMLResponse)
    def platform_home(request: Request, group: str | None = "grade3", subject: str | None = "all") -> HTMLResponse:
        cards = list_catalog_cards(store)
        catalog = group_catalog(cards, group_id=group or None, subject=subject)
        # Default land on grade3 demo group if it has cards; else all catalog
        if (group == "grade3") and catalog["total"] == 0 and cards:
            catalog = group_catalog(cards, group_id=None, subject=subject)
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "request": request,
                "product": "MyRoad",
                "catalog": catalog,
                "active_group": group or "all",
                "active_subject": subject or "all",
                "groups": GROUPS,
                "subjects": SUBJECTS,
            },
        )

    @app.get("/play/{path_id}", response_class=HTMLResponse)
    def play_path(request: Request, path_id: str) -> HTMLResponse:
        # Ensure play session exists with correct path
        sid = request.cookies.get("myroad_play")
        sessions: dict[str, dict[str, Any]] = app.state.play_sessions
        if not sid or sid not in sessions or sessions[sid].get("pathId") != path_id:
            sid = uuid.uuid4().hex
            latest = store.get_path_latest(path_id)
            sessions[sid] = {
                "sid": sid,
                "pathId": path_id,
                "versionId": latest.versionId,
                "index": 0,
                "mastered": set(),
                "last_result": None,
                "flash": None,
            }
        sess = sessions[sid]
        doc = _load_play_doc(sess)
        blocks = doc.get("blocks") or []
        n = len(blocks)
        idx = max(0, min(sess["index"], n - 1 if n else 0))
        sess["index"] = idx
        block = blocks[idx] if blocks else None
        kids = _kids_payload(block)
        meta = _card_meta(doc)
        flash = sess.pop("flash", None)
        result = sess.get("last_result")
        progress = int(round(100 * len(sess["mastered"]) / n)) if n else 0
        ctx = {
            "request": request,
            "product": "MyRoad",
            "doc": doc,
            "meta": meta,
            "blocks": blocks,
            "block": block,
            "kids": kids,
            "index": idx,
            "total": n,
            "progress": progress,
            "mastered": sess["mastered"],
            "flash": flash,
            "result": result,
            "can_prev": idx > 0,
            "can_next": idx < n - 1,
            "is_done": n > 0 and len(sess["mastered"]) >= n,
        }
        response = templates.TemplateResponse(request, "play.html", ctx)
        response.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
        return response

    @app.post("/play/{path_id}/ack")
    def play_ack(path_id: str, request: Request) -> RedirectResponse:
        sess = _play_session(request, path_id)
        doc = _load_play_doc(sess)
        blocks = doc.get("blocks") or []
        block = blocks[sess["index"]] if blocks else None
        if block:
            sess["mastered"].add(block["blockId"])
            sess["last_result"] = None
            kids = _kids_payload(block)
            sess["flash"] = {
                "level": "ok",
                "text": kids.get("feedback_ok") or "מעולה — אפשר להמשיך!",
            }
            if sess["index"] < len(blocks) - 1:
                sess["index"] += 1
        resp = RedirectResponse(f"/play/{path_id}", status_code=303)
        resp.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
        return resp

    @app.post("/play/{path_id}/answer")
    def play_answer(
        path_id: str,
        request: Request,
        choice: str = Form(""),
        sequence: str = Form(""),
    ) -> RedirectResponse:
        sess = _play_session(request, path_id)
        doc = _load_play_doc(sess)
        blocks = doc.get("blocks") or []
        block = blocks[sess["index"]] if blocks else None
        if not block:
            resp = RedirectResponse(f"/play/{path_id}", status_code=303)
            return resp
        kids = _kids_payload(block)
        node_type = kids.get("type") or (block.get("content") or {}).get("nodeType")
        ok = False
        if node_type in ("practice", "check") and kids.get("choices"):
            correct = kids.get("correct")
            if isinstance(correct, list):
                ok = choice in correct
            else:
                ok = choice == correct
        elif node_type == "piano_keys":
            target = kids.get("target_sequence") or []
            given = [p for p in sequence.split(",") if p]
            if not target:
                # free play — ack on any submit
                ok = True
            else:
                ok = given == target
        elif node_type == "rhythm":
            pattern = kids.get("pattern") or []
            given = []
            for p in sequence.split(","):
                p = p.strip()
                if p == "":
                    continue
                given.append(int(p))
            ok = given == list(pattern)
        else:
            ok = True

        if ok:
            sess["mastered"].add(block["blockId"])
            sess["last_result"] = {"ok": True, "text": kids.get("feedback_ok") or "נכון!"}
            sess["flash"] = {"level": "ok", "text": kids.get("feedback_ok") or "נכון!"}
            if sess["index"] < len(blocks) - 1:
                sess["index"] += 1
                sess["last_result"] = None
        else:
            sess["last_result"] = {
                "ok": False,
                "text": kids.get("feedback_try") or "לא בדיוק — נסו שוב!",
            }
            sess["flash"] = {
                "level": "warn",
                "text": kids.get("feedback_try") or "לא בדיוק — נסו שוב!",
            }
        resp = RedirectResponse(f"/play/{path_id}", status_code=303)
        resp.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
        return resp

    @app.post("/play/{path_id}/nav")
    def play_nav(
        path_id: str,
        request: Request,
        direction: str = Form("next"),
    ) -> RedirectResponse:
        sess = _play_session(request, path_id)
        doc = _load_play_doc(sess)
        blocks = doc.get("blocks") or []
        sess["last_result"] = None
        if direction == "prev":
            sess["index"] = max(0, sess["index"] - 1)
        else:
            block = blocks[sess["index"]] if blocks else None
            if block and block["blockId"] not in sess["mastered"]:
                kids = _kids_payload(block)
                # allow next on celebrate/learn only after ack; gate practice
                ntype = kids.get("type")
                if ntype in ("practice", "check", "piano_keys", "rhythm"):
                    sess["flash"] = {
                        "level": "warn",
                        "text": "סיימו את השלב לפני המעבר הלאה.",
                    }
                    resp = RedirectResponse(f"/play/{path_id}", status_code=303)
                    resp.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
                    return resp
            sess["index"] = min(len(blocks) - 1, sess["index"] + 1)
        resp = RedirectResponse(f"/play/{path_id}", status_code=303)
        resp.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
        return resp
