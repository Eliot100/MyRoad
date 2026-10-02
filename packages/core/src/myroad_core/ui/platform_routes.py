"""Platform catalog + path player (age-agnostic shell; content drives tone)."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from myroad_core.content.loader import group_catalog, list_catalog_cards
from myroad_core.content.schema import GROUPS, SUBJECTS
from myroad_core.ui.i18n import (
    COOKIE_LOCALE,
    COOKIE_USER,
    LOCALES,
    dir_for,
    html_lang,
    normalize_locale,
    subject_label,
    t,
)

ACTOR_LEARNER = "user_learner_poc"


def _kids_payload(block: dict[str, Any] | None) -> dict[str, Any]:
    if not block:
        return {}
    content = block.get("content") or {}
    kids = content.get("kids") or {}
    return kids if isinstance(kids, dict) else {}


def _parse_iso(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def register_platform_routes(
    app,
    *,
    templates: Jinja2Templates,
    store,
    tools,
    _corr: Callable[[str], str],
) -> None:
    def _locale(request: Request) -> str:
        return normalize_locale(request.cookies.get(COOKIE_LOCALE))

    def _learner(request: Request) -> dict[str, Any] | None:
        uid = request.cookies.get(COOKIE_USER)
        if not uid:
            return None
        return store.get_learner(uid)

    def _ensure_user(request: Request) -> dict[str, Any]:
        uid = request.cookies.get(COOKIE_USER)
        learner = store.get_learner(uid) if uid else None
        if learner:
            return learner
        # Anonymous stable id until they pick a name
        new_id = uid or f"usr_{uuid.uuid4().hex[:12]}"
        return store.ensure_learner(new_id, "Learner")

    def _set_identity_cookies(resp, learner: dict[str, Any], locale: str) -> None:
        resp.set_cookie(COOKIE_USER, learner["userId"], httponly=True, samesite="lax", max_age=86400 * 400)
        resp.set_cookie(COOKIE_LOCALE, locale, httponly=False, samesite="lax", max_age=86400 * 400)

    def _shell_ctx(request: Request, **extra: Any) -> dict[str, Any]:
        locale = _locale(request)
        learner = _learner(request)
        ctx = {
            "request": request,
            "product": "MyRoad",
            "locale": locale,
            "html_lang": html_lang(locale),
            "html_dir": dir_for(locale),
            "locales": LOCALES,
            "learner": learner,
            "t": lambda key, **kw: t(locale, key, **kw),
            "subject_label_fn": lambda sid: subject_label(sid, locale),
        }
        ctx.update(extra)
        return ctx

    def _play_session(request: Request, path_id: str, *, resume: bool = True) -> dict[str, Any]:
        sid = request.cookies.get("myroad_play")
        sessions: dict[str, dict[str, Any]] = app.state.play_sessions
        learner = _ensure_user(request)
        user_id = learner["userId"]

        if not sid or sid not in sessions or sessions[sid].get("pathId") != path_id:
            sid = uuid.uuid4().hex
            latest = store.get_path_latest(path_id)
            progress = store.get_progress(user_id, path_id) if resume else None
            sessions[sid] = {
                "sid": sid,
                "pathId": path_id,
                "versionId": latest.versionId,
                "userId": user_id,
                "index": (progress or {}).get("nodeIndex", 0) if resume else 0,
                "mastered": set((progress or {}).get("mastered") or set()) if resume else set(),
                "correct_taps": int((progress or {}).get("correctTaps") or 0) if resume else 0,
                "incorrect_taps": int((progress or {}).get("incorrectTaps") or 0) if resume else 0,
                "started_at": (progress or {}).get("startedAt") or datetime.now(timezone.utc).isoformat(),
                "started_monotonic": time.monotonic(),
                "last_result": None,
                "flash": None,
                "view": "map",
                "attempt_saved": False,
            }
            # If already mid-path, jump to learn view
            if progress and (progress.get("mastered") or progress.get("nodeIndex", 0) > 0):
                if not progress.get("completedAt"):
                    sessions[sid]["view"] = "learn"
        sess = sessions[sid]
        sess["userId"] = user_id
        return sess

    def _persist_progress(sess: dict[str, Any], *, completed: bool = False) -> None:
        user_id = sess.get("userId")
        if not user_id:
            return
        completed_at = datetime.now(timezone.utc).isoformat() if completed else None
        store.save_progress(
            user_id,
            sess["pathId"],
            version_id=sess.get("versionId"),
            node_index=int(sess.get("index") or 0),
            mastered=sess.get("mastered") or set(),
            correct_taps=int(sess.get("correct_taps") or 0),
            incorrect_taps=int(sess.get("incorrect_taps") or 0),
            started_at=sess.get("started_at"),
            completed_at=completed_at,
        )

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

    def _card_meta(doc: dict[str, Any], locale: str) -> dict[str, Any]:
        subject = doc.get("subject") or "general"
        meta = SUBJECTS.get(subject, SUBJECTS["general"])
        title = doc.get("name")
        if locale == "en" and doc.get("titleEn"):
            title = doc["titleEn"]
        blurb = doc.get("description") or ""
        if locale == "en" and doc.get("blurbEn"):
            blurb = doc["blurbEn"]
        return {
            "subject": subject,
            "subjectLabel": subject_label(subject, locale),
            "subjectColor": doc.get("subjectColor") or meta["color"],
            "emoji": doc.get("emoji") or meta["emoji"],
            "kidsDemo": bool(doc.get("kidsDemo")),
            "estimatedMinutes": doc.get("estimatedMinutes"),
            "groupIds": doc.get("groupIds") or [],
            "title": title,
            "blurb": blurb,
        }

    def _topics_for_ui(doc: dict[str, Any], blocks: list[dict], locale: str) -> list[dict[str, Any]]:
        topics = doc.get("topics") or []
        node_to_block = doc.get("nodeToBlock") or {}
        block_by_id = {b["blockId"]: b for b in blocks}
        # Build reverse: blockId -> index
        index_by_block = {b["blockId"]: i for i, b in enumerate(blocks)}
        out: list[dict[str, Any]] = []
        for topic in topics:
            title = topic.get("title_he") or topic.get("id")
            if locale == "en" and topic.get("title_en"):
                title = topic["title_en"]
            elif locale == "ar" and topic.get("title_ar"):
                title = topic["title_ar"]
            node_ids = topic.get("node_ids") or []
            block_ids = []
            for nid in node_ids:
                bid = node_to_block.get(nid)
                if bid:
                    block_ids.append(bid)
            # Fallback: if mapping missing, skip
            start_index = 0
            if block_ids:
                start_index = min(index_by_block.get(bid, 0) for bid in block_ids)
            out.append(
                {
                    "id": topic.get("id"),
                    "title": title,
                    "emoji": topic.get("emoji") or doc.get("emoji") or "📍",
                    "nodeIds": node_ids,
                    "blockIds": block_ids,
                    "stepCount": len(block_ids) or len(node_ids),
                    "startIndex": start_index,
                    "blocks": [block_by_id[b] for b in block_ids if b in block_by_id],
                }
            )
        return out

    def _stats_message(locale: str, mastery: float) -> str:
        if mastery >= 85:
            return t(locale, "stats_message")
        if mastery >= 60:
            return t(locale, "stats_message_ok")
        return t(locale, "stats_message_retry")

    def _finalize_attempt(sess: dict[str, Any], doc: dict[str, Any], locale: str) -> dict[str, Any]:
        blocks = doc.get("blocks") or []
        n = len(blocks)
        mastered = sess.get("mastered") or set()
        nodes_completed = len(mastered)
        mastery = round(100.0 * nodes_completed / n, 1) if n else 0.0
        started_ts = _parse_iso(sess.get("started_at"))
        now_ts = time.time()
        duration = int(max(0, now_ts - started_ts)) if started_ts else int(
            max(0, time.monotonic() - float(sess.get("started_monotonic") or time.monotonic()))
        )
        # Prefer monotonic wall within session if ISO parse odd
        mono = sess.get("started_monotonic")
        if mono is not None:
            duration = max(duration, int(time.monotonic() - float(mono)))
        message = _stats_message(locale, mastery)
        if not sess.get("attempt_saved"):
            attempt = store.record_attempt(
                user_id=sess["userId"],
                path_id=sess["pathId"],
                version_id=sess.get("versionId"),
                started_at=sess.get("started_at") or datetime.now(timezone.utc).isoformat(),
                duration_sec=duration,
                nodes_completed=nodes_completed,
                nodes_total=n,
                correct_taps=int(sess.get("correct_taps") or 0),
                incorrect_taps=int(sess.get("incorrect_taps") or 0),
                mastery_pct=mastery,
                message=message,
            )
            sess["attempt_saved"] = True
            sess["last_attempt"] = attempt
        else:
            attempt = sess.get("last_attempt") or store.latest_attempt(sess["userId"], sess["pathId"])
        _persist_progress(sess, completed=True)
        return attempt or {}

    def _maybe_done(sess: dict[str, Any], n: int) -> bool:
        return n > 0 and len(sess.get("mastered") or set()) >= n

    # --- Identity / locale ---
    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, next: str = "/") -> HTMLResponse:
        locale = _locale(request)
        learner = _learner(request)
        return templates.TemplateResponse(
            request,
            "login.html",
            _shell_ctx(
                request,
                next_url=next or "/",
                current_name=(learner or {}).get("displayName") or "",
            ),
        )

    @app.post("/login")
    def login_submit(
        request: Request,
        display_name: str = Form(""),
        next: str = Form("/"),
    ) -> RedirectResponse:
        locale = _locale(request)
        uid = request.cookies.get(COOKIE_USER) or f"usr_{uuid.uuid4().hex[:12]}"
        learner = store.upsert_learner(uid, display_name or "Learner", locale=locale)
        dest = next if next.startswith("/") else "/"
        resp = RedirectResponse(dest, status_code=303)
        _set_identity_cookies(resp, learner, locale)
        return resp

    @app.post("/locale")
    def set_locale(
        request: Request,
        locale: str = Form("he"),
        next: str = Form("/"),
    ) -> RedirectResponse:
        loc = normalize_locale(locale)
        learner = _learner(request)
        if learner:
            store.upsert_learner(learner["userId"], learner["displayName"], locale=loc)
        dest = next if next.startswith("/") else "/"
        resp = RedirectResponse(dest, status_code=303)
        resp.set_cookie(COOKIE_LOCALE, loc, httponly=False, samesite="lax", max_age=86400 * 400)
        if learner:
            resp.set_cookie(COOKIE_USER, learner["userId"], httponly=True, samesite="lax", max_age=86400 * 400)
        return resp

    @app.get("/", response_class=HTMLResponse)
    def platform_home(
        request: Request,
        group: str | None = "grade3",
        subject: str | None = "all",
    ) -> HTMLResponse:
        locale = _locale(request)
        cards = list_catalog_cards(store)
        # Enrich cards with per-user progress
        learner = _learner(request)
        progress_map: dict[str, Any] = {}
        if learner:
            for row in store.list_user_progress(learner["userId"]):
                progress_map[row["pathId"]] = row
        for c in cards:
            # Localized labels
            if locale == "en":
                if c.get("titleEn"):
                    c["title"] = c["titleEn"]
                if c.get("blurbEn"):
                    c["blurb"] = c["blurbEn"]
                if c.get("subjectLabelEn"):
                    c["subjectLabel"] = c["subjectLabelEn"]
            else:
                c["subjectLabel"] = subject_label(c["subject"], locale)
            prog = progress_map.get(c["pathId"])
            c["userProgress"] = prog
            if prog and prog.get("completedAt"):
                c["progressStatus"] = "completed"
            elif prog and prog.get("masteredCount", 0) > 0:
                c["progressStatus"] = "in_progress"
            else:
                c["progressStatus"] = None

        catalog = group_catalog(cards, group_id=group or None, subject=subject)
        if (group == "grade3") and catalog["total"] == 0 and cards:
            catalog = group_catalog(cards, group_id=None, subject=subject)

        # Localized group banner
        group_banner = catalog.get("group")
        if group_banner and locale != "he":
            group_banner = dict(group_banner)
            if locale == "en":
                group_banner["title_display"] = group_banner.get("title_en") or group_banner.get("title_he")
                group_banner["blurb_display"] = group_banner.get("blurb_en") or group_banner.get("blurb_he")
            elif locale == "ar":
                group_banner["title_display"] = group_banner.get("title_ar") or group_banner.get("title_he")
                group_banner["blurb_display"] = group_banner.get("blurb_ar") or group_banner.get("blurb_he")
            else:
                group_banner["title_display"] = group_banner.get("title_he")
                group_banner["blurb_display"] = group_banner.get("blurb_he")
        elif group_banner:
            group_banner = dict(group_banner)
            group_banner["title_display"] = group_banner.get("title_he")
            group_banner["blurb_display"] = group_banner.get("blurb_he")

        # Localized subject chips
        subjects_ui = {}
        for sid, meta in SUBJECTS.items():
            subjects_ui[sid] = {
                **meta,
                "label": subject_label(sid, locale),
            }

        groups_ui = {}
        for gid, g in GROUPS.items():
            title = g.get("title_he")
            if locale == "en":
                title = g.get("title_en") or title
            elif locale == "ar":
                title = g.get("title_ar") or title
            groups_ui[gid] = {**g, "title_display": title}

        response = templates.TemplateResponse(
            request,
            "home.html",
            _shell_ctx(
                request,
                catalog={**catalog, "group": group_banner},
                active_group=group or "all",
                active_subject=subject or "all",
                groups=groups_ui,
                subjects=subjects_ui,
            ),
        )
        # Ensure anonymous cookie exists for resume later
        if not request.cookies.get(COOKIE_USER):
            anon = _ensure_user(request)
            _set_identity_cookies(response, anon, locale)
        return response

    @app.get("/play/{path_id}", response_class=HTMLResponse)
    def play_path(
        request: Request,
        path_id: str,
        view: str | None = None,
        topic: str | None = None,
    ) -> HTMLResponse:
        locale = _locale(request)
        sess = _play_session(request, path_id)
        doc = _load_play_doc(sess)
        blocks = doc.get("blocks") or []
        n = len(blocks)
        meta = _card_meta(doc, locale)
        topics = _topics_for_ui(doc, blocks, locale)

        # Explicit view overrides
        if view == "map":
            sess["view"] = "map"
        elif view == "learn":
            sess["view"] = "learn"
        elif view == "stats":
            sess["view"] = "stats"

        if topic:
            match = next((tp for tp in topics if tp["id"] == topic), None)
            if match:
                sess["index"] = match["startIndex"]
                sess["view"] = "learn"

        if _maybe_done(sess, n) and sess.get("view") != "map":
            sess["view"] = "stats"

        if sess.get("view") == "stats":
            attempt = _finalize_attempt(sess, doc, locale)
            ctx = _shell_ctx(
                request,
                doc=doc,
                meta=meta,
                attempt=attempt,
                total=n,
            )
            response = templates.TemplateResponse(request, "stats.html", ctx)
            response.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
            if not request.cookies.get(COOKIE_USER):
                _set_identity_cookies(response, store.get_learner(sess["userId"]), locale)
            return response

        if sess.get("view") != "learn":
            # Topic map first
            mastered = sess.get("mastered") or set()
            for tp in topics:
                done = sum(1 for bid in tp["blockIds"] if bid in mastered)
                tp["doneCount"] = done
                tp["complete"] = tp["stepCount"] > 0 and done >= tp["stepCount"]
            ctx = _shell_ctx(
                request,
                doc=doc,
                meta=meta,
                topics=topics,
                mastered=mastered,
                total=n,
                progress=int(round(100 * len(mastered) / n)) if n else 0,
                can_resume=bool(mastered) or sess.get("index", 0) > 0,
                resume_index=sess.get("index", 0),
            )
            response = templates.TemplateResponse(request, "map.html", ctx)
            response.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
            if not request.cookies.get(COOKIE_USER):
                _set_identity_cookies(response, store.get_learner(sess["userId"]), locale)
            return response

        # Learn view
        idx = max(0, min(sess["index"], n - 1 if n else 0))
        sess["index"] = idx
        block = blocks[idx] if blocks else None
        kids = _kids_payload(block)
        flash = sess.pop("flash", None)
        result = sess.get("last_result")
        progress = int(round(100 * len(sess["mastered"]) / n)) if n else 0
        ctx = _shell_ctx(
            request,
            doc=doc,
            meta=meta,
            blocks=blocks,
            block=block,
            kids=kids,
            index=idx,
            total=n,
            progress=progress,
            mastered=sess["mastered"],
            flash=flash,
            result=result,
            can_prev=idx > 0,
            can_next=idx < n - 1,
            is_done=_maybe_done(sess, n),
            topics=topics,
        )
        response = templates.TemplateResponse(request, "play.html", ctx)
        response.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
        if not request.cookies.get(COOKIE_USER):
            _set_identity_cookies(response, store.get_learner(sess["userId"]), locale)
        return response

    @app.post("/play/{path_id}/start")
    def play_start(
        path_id: str,
        request: Request,
        topic: str = Form(""),
        reset: str = Form(""),
    ) -> RedirectResponse:
        sess = _play_session(request, path_id, resume=not bool(reset))
        if reset:
            sess["index"] = 0
            sess["mastered"] = set()
            sess["correct_taps"] = 0
            sess["incorrect_taps"] = 0
            sess["started_at"] = datetime.now(timezone.utc).isoformat()
            sess["started_monotonic"] = time.monotonic()
            sess["attempt_saved"] = False
            sess["last_attempt"] = None
        if topic:
            doc = _load_play_doc(sess)
            blocks = doc.get("blocks") or []
            topics = _topics_for_ui(doc, blocks, _locale(request))
            match = next((tp for tp in topics if tp["id"] == topic), None)
            if match:
                sess["index"] = match["startIndex"]
        sess["view"] = "learn"
        _persist_progress(sess)
        resp = RedirectResponse(f"/play/{path_id}?view=learn", status_code=303)
        resp.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
        return resp

    @app.post("/play/{path_id}/ack")
    def play_ack(path_id: str, request: Request) -> RedirectResponse:
        locale = _locale(request)
        sess = _play_session(request, path_id)
        sess["view"] = "learn"
        doc = _load_play_doc(sess)
        blocks = doc.get("blocks") or []
        block = blocks[sess["index"]] if blocks else None
        if block:
            sess["mastered"].add(block["blockId"])
            sess["last_result"] = None
            kids = _kids_payload(block)
            sess["flash"] = {
                "level": "ok",
                "text": kids.get("feedback_ok") or t(locale, "continue"),
            }
            if sess["index"] < len(blocks) - 1:
                sess["index"] += 1
        _persist_progress(sess, completed=_maybe_done(sess, len(blocks)))
        if _maybe_done(sess, len(blocks)):
            sess["view"] = "stats"
            resp = RedirectResponse(f"/play/{path_id}?view=stats", status_code=303)
        else:
            resp = RedirectResponse(f"/play/{path_id}?view=learn", status_code=303)
        resp.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
        return resp

    @app.post("/play/{path_id}/answer")
    def play_answer(
        path_id: str,
        request: Request,
        choice: str = Form(""),
        sequence: str = Form(""),
    ) -> RedirectResponse:
        locale = _locale(request)
        sess = _play_session(request, path_id)
        sess["view"] = "learn"
        doc = _load_play_doc(sess)
        blocks = doc.get("blocks") or []
        block = blocks[sess["index"]] if blocks else None
        if not block:
            resp = RedirectResponse(f"/play/{path_id}?view=learn", status_code=303)
            return resp
        kids = _kids_payload(block)
        node_type = kids.get("type") or (block.get("content") or {}).get("nodeType")
        ok = False
        scored = False
        if node_type in ("practice", "check") and kids.get("choices"):
            scored = True
            correct = kids.get("correct")
            if isinstance(correct, list):
                ok = choice in correct
            else:
                ok = choice == correct
        elif node_type == "piano_keys":
            scored = True
            target = kids.get("target_sequence") or []
            given = [p for p in sequence.split(",") if p]
            if not target:
                ok = True
                scored = False
            else:
                ok = given == target
        elif node_type == "rhythm":
            scored = True
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

        if scored:
            if ok:
                sess["correct_taps"] = int(sess.get("correct_taps") or 0) + 1
            else:
                sess["incorrect_taps"] = int(sess.get("incorrect_taps") or 0) + 1

        if ok:
            sess["mastered"].add(block["blockId"])
            sess["last_result"] = {"ok": True, "text": kids.get("feedback_ok") or "✓"}
            sess["flash"] = {"level": "ok", "text": kids.get("feedback_ok") or "✓"}
            if sess["index"] < len(blocks) - 1:
                sess["index"] += 1
                sess["last_result"] = None
        else:
            sess["last_result"] = {
                "ok": False,
                "text": kids.get("feedback_try") or t(locale, "gate_practice"),
            }
            sess["flash"] = {
                "level": "warn",
                "text": kids.get("feedback_try") or t(locale, "gate_practice"),
            }
        _persist_progress(sess, completed=_maybe_done(sess, len(blocks)))
        if _maybe_done(sess, len(blocks)):
            sess["view"] = "stats"
            resp = RedirectResponse(f"/play/{path_id}?view=stats", status_code=303)
        else:
            resp = RedirectResponse(f"/play/{path_id}?view=learn", status_code=303)
        resp.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
        return resp

    @app.post("/play/{path_id}/nav")
    def play_nav(
        path_id: str,
        request: Request,
        direction: str = Form("next"),
    ) -> RedirectResponse:
        locale = _locale(request)
        sess = _play_session(request, path_id)
        sess["view"] = "learn"
        doc = _load_play_doc(sess)
        blocks = doc.get("blocks") or []
        sess["last_result"] = None
        if direction == "prev":
            sess["index"] = max(0, sess["index"] - 1)
        else:
            block = blocks[sess["index"]] if blocks else None
            if block and block["blockId"] not in sess["mastered"]:
                kids = _kids_payload(block)
                ntype = kids.get("type")
                if ntype in ("practice", "check", "piano_keys", "rhythm"):
                    sess["flash"] = {
                        "level": "warn",
                        "text": t(locale, "gate_practice"),
                    }
                    resp = RedirectResponse(f"/play/{path_id}?view=learn", status_code=303)
                    resp.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
                    return resp
            sess["index"] = min(len(blocks) - 1, sess["index"] + 1)
        _persist_progress(sess)
        resp = RedirectResponse(f"/play/{path_id}?view=learn", status_code=303)
        resp.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
        return resp
