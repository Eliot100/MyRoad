"""Platform catalog + path player (age-agnostic shell; content drives tone)."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from myroad_core.agent_builder.suggest import catalog_entries, completed_path_ids
from myroad_core.auth.sessions import SESSION_COOKIE, SESSION_TTL_SECONDS, cookie_secure
from myroad_core.content.loader import group_catalog, list_catalog_cards
from myroad_core.content.locale_rules import resolve_node_display
from myroad_core.content.schema import GROUPS, SUBJECTS
from myroad_core.ui.a11y_statement import statement_details
from myroad_core.ui.i18n import (
    COOKIE_LOCALE,
    COOKIE_USER,
    LOCALES,
    dir_for,
    html_lang,
    localize_path_chrome,
    locale_meta,
    normalize_locale,
    pick,
    pick_content,
    content_lang,
    subject_label,
    t,
)
from myroad_core.ui.agent_builder_routes import register_agent_builder_routes
from myroad_core.ui.bidi import bidi_isolate

ACTOR_LEARNER = "user_learner_poc"


def _kids_payload(block: dict[str, Any] | None) -> dict[str, Any]:
    if not block:
        return {}
    content = block.get("content") or {}
    kids = content.get("kids") or {}
    return kids if isinstance(kids, dict) else {}


def _is_htmx(request: Request) -> bool:
    """htmx swap request (not a history restore, which wants the full page)."""
    return (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-History-Restore-Request") != "true"
    )


def _hx_redirect(url: str) -> Response:
    """Tell htmx to do a full navigation instead of swapping a fragment."""
    return Response(status_code=200, headers={"HX-Redirect": url, "Vary": "HX-Request"})


def _explain_locale(doc: dict[str, Any]) -> str:
    """The path's own language: content falls back to it when the UI locale is missing."""
    return str(doc.get("explainLocale") or "he").strip().lower().split("-")[0] or "he"


def _step_langs(kids: dict[str, Any], doc: dict[str, Any], locale: str) -> dict[str, str]:
    """Language of each step string as resolve_node_display / the templates pick it.

    Mirrors content.locale_rules.resolve_node_display (en: body_en → body_ui → body_he;
    other UI locales: body_ui → body_he → body_en) so fallback text can carry ``lang``.
    """
    explain = _explain_locale(doc)
    loc = (locale or "he").split("-")[0].lower()
    if loc == "en" and kids.get("body_en"):
        body = "en"
    elif kids.get("body_ui"):
        body = explain
    elif kids.get("body_he"):
        body = "he"
    elif kids.get("body_en"):
        body = "en"
    else:
        body = explain
    return {
        "title": "en" if loc == "en" and kids.get("title_en") else explain,
        "body": body,
        # Choice labels are content tokens in the path's content locale (label_en for the en UI).
        "choice": str(doc.get("contentLocale") or doc.get("contentLanguage") or explain).split("-")[0].lower(),
        "feedback": explain,
    }


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
        # Identity = server-side session only. A user id in a cookie is not trusted.
        uid = store.get_session_user(request.cookies.get(SESSION_COOKIE))
        if not uid:
            return None
        return store.get_learner(uid)

    def _safe_next(raw: str | None, default: str = "/") -> str:
        if not raw:
            return default
        dest = raw.strip()
        if not dest.startswith("/") or dest.startswith("//") or "\\" in dest:
            return default
        return dest

    def _login_redirect(request: Request) -> RedirectResponse:
        path = request.url.path
        nxt = f"{path}?{request.url.query}" if request.url.query else path
        return RedirectResponse("/login?next=" + quote(nxt, safe=""), status_code=303)

    def _require_learner(request: Request) -> dict[str, Any] | None:
        return _learner(request)

    def _set_locale_cookie(resp, locale: str) -> None:
        resp.set_cookie(COOKIE_LOCALE, locale, httponly=False, samesite="lax", max_age=86400 * 400)

    def _start_session(request: Request, resp, learner: dict[str, Any], locale: str) -> None:
        """Start a fresh server-side session (old one revoked) and set its cookie."""
        store.revoke_session(request.cookies.get(SESSION_COOKIE))
        sid = store.create_session(learner["userId"])
        resp.set_cookie(
            SESSION_COOKIE, sid, httponly=True, samesite="lax", max_age=SESSION_TTL_SECONDS,
            secure=cookie_secure(),
        )
        resp.delete_cookie(COOKIE_USER)  # legacy user-id cookie, no longer used
        _set_locale_cookie(resp, locale)

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
        ctx["locale_labels"] = {
            code: (locale_meta(code).get("nativeLabel") or code) for code in LOCALES
        }
        ctx.update(extra)
        return ctx

    @app.middleware("http")
    async def _auth_gate(request: Request, call_next):
        path = request.url.path
        if (
            path.startswith("/static")
            or path in {"/health", "/login", "/locale"}
            or path.startswith("/login")
        ):
            return await call_next(request)
        protected = (
            path == "/"
            or path.startswith("/play")
            or path.startswith("/add-path")
            or path.startswith("/author")
            or path.startswith("/settings")
        )
        if protected and not _learner(request):
            return _login_redirect(request)
        return await call_next(request)

    def _play_session(request: Request, path_id: str, *, resume: bool = True) -> dict[str, Any]:
        sid = request.cookies.get("myroad_play")
        sessions: dict[str, dict[str, Any]] = app.state.play_sessions
        learner = _require_learner(request)
        if not learner:
            raise RuntimeError("auth required")
        user_id = learner["userId"]

        if not sid or sid not in sessions or sessions[sid].get("pathId") != path_id:
            sid = uuid.uuid4().hex
            # Learners play the newest published version; a newer draft stays private.
            latest = store.get_path_latest_published(path_id) or store.get_path_latest(path_id)
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

    def _persist_progress(
        sess: dict[str, Any],
        *,
        completed: bool = False,
        needs_practice: bool | None = None,
    ) -> None:
        user_id = sess.get("userId")
        if not user_id:
            return
        completed_at = datetime.now(timezone.utc).isoformat() if completed else None
        # Keep prior completed_at if already completed and not re-completing
        if not completed:
            prior = store.get_progress(user_id, sess["pathId"])
            if prior and prior.get("completedAt"):
                completed_at = prior["completedAt"]
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
            needs_practice=needs_practice,
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
        titles = dict(doc.get("titles") or {})
        blurbs = dict(doc.get("blurbs") or {})
        if doc.get("name"):
            titles.setdefault("he", doc.get("name"))
        if doc.get("titleEn"):
            titles.setdefault("en", doc.get("titleEn"))
        if doc.get("titleAr"):
            titles.setdefault("ar", doc.get("titleAr"))
        if doc.get("blurbHe") or doc.get("description"):
            blurbs.setdefault("he", doc.get("blurbHe") or doc.get("description") or "")
        if doc.get("blurbEn"):
            blurbs.setdefault("en", doc.get("blurbEn"))
        if doc.get("blurbAr"):
            blurbs.setdefault("ar", doc.get("blurbAr"))
        chrome = localize_path_chrome(
            locale=locale,
            titles=titles,
            blurbs=blurbs,
            subject=subject,
            source_locale=_explain_locale(doc),
        )
        return {
            "subject": subject,
            "subjectLabel": chrome["subjectLabel"],
            "subjectColor": doc.get("subjectColor") or meta["color"],
            "emoji": doc.get("emoji") or meta["emoji"],
            "kidsDemo": bool(doc.get("kidsDemo")),
            "estimatedMinutes": doc.get("estimatedMinutes"),
            "groupIds": doc.get("groupIds") or [],
            "title": chrome["title"],
            "blurb": chrome["blurb"],
            "titleLang": chrome["titleLang"],
            "blurbLang": chrome["blurbLang"],
        }

    def _topics_for_ui(doc: dict[str, Any], blocks: list[dict], locale: str) -> list[dict[str, Any]]:
        topics = doc.get("topics") or []
        explain = _explain_locale(doc)
        node_to_block = doc.get("nodeToBlock") or {}
        block_by_id = {b["blockId"]: b for b in blocks}
        # Build reverse: blockId -> index
        index_by_block = {b["blockId"]: i for i, b in enumerate(blocks)}
        out: list[dict[str, Any]] = []
        for topic in topics:
            topic_titles = dict(topic.get("titles") or {})
            if topic.get("title_he"):
                topic_titles.setdefault("he", topic.get("title_he"))
            if topic.get("title_en"):
                topic_titles.setdefault("en", topic.get("title_en"))
            if topic.get("title_ar"):
                topic_titles.setdefault("ar", topic.get("title_ar"))
            # Content: a missing translation falls back to the path's own language, not English.
            title, title_lang = pick_content(
                topic_titles, locale, source_locale=explain, default=topic.get("id") or ""
            )
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
            steps = []
            for bid in block_ids:
                blk = block_by_id.get(bid)
                if not blk:
                    continue
                kids = _kids_payload(blk)
                steps.append(
                    {
                        "blockId": bid,
                        "index": index_by_block.get(bid, 0),
                        "title": kids.get("title_en") if locale == "en" and kids.get("title_en") else blk.get("title"),
                        "titleLang": "en" if locale == "en" and kids.get("title_en") else explain,
                        "type": kids.get("type") or (blk.get("content") or {}).get("nodeType"),
                        "kind": kids.get("kind") or "understanding",
                        "reviewTopicIds": list(kids.get("review_topic_ids") or []),
                    }
                )
            review_steps = sum(1 for st in steps if st["kind"] == "review")
            out.append(
                {
                    "id": topic.get("id"),
                    "title": title,
                    "titleLang": title_lang or explain,
                    "emoji": topic.get("emoji") or doc.get("emoji") or "📍",
                    "nodeIds": node_ids,
                    "blockIds": block_ids,
                    "stepCount": len(block_ids) or len(node_ids),
                    "startIndex": start_index,
                    "blocks": [block_by_id[b] for b in block_ids if b in block_by_id],
                    "steps": steps,
                    "reviewCount": review_steps,
                    "isReview": bool(steps) and review_steps == len(steps),
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
        needs = mastery < 85.0 or int(sess.get("incorrect_taps") or 0) >= 2
        _persist_progress(sess, completed=True, needs_practice=needs)
        return attempt or {}

    def _maybe_done(sess: dict[str, Any], n: int) -> bool:
        return n > 0 and len(sess.get("mastered") or set()) >= n

    # --- schema v2 prerequisite_path_ids: a path stays locked (read-only) until they are finished ---
    def _prereq_index(locale: str) -> tuple[dict[str, list[str]], dict[str, str]]:
        """({pathId: prerequisite_path_ids}, {pathId: localized title}) for published catalog paths."""
        try:
            entries = catalog_entries(store, locale=locale)
        except Exception:  # a broken row must not break the learner screens
            return {}, {}
        return (
            {e.path_id: list(e.prerequisite_path_ids) for e in entries},
            {e.path_id: e.title for e in entries},
        )

    def _title_langs(locale: str) -> dict[str, str]:
        """{pathId: language of its displayed title} for lock links (content fallback)."""
        try:
            cards = list_catalog_cards(store)
        except Exception:
            return {}
        return {
            c["pathId"]: localize_path_chrome(
                locale=locale, titles=c.get("titles"), source_locale=c.get("explainLocale")
            )["titleLang"]
            for c in cards
        }

    def _locked_by(
        path_id: str,
        prereqs: dict[str, list[str]],
        titles: dict[str, str],
        completed: set[str],
    ) -> list[dict[str, str]]:
        # Unknown prerequisites (not in the catalog) cannot be finished, so they do not lock.
        return [
            {"pathId": pid, "title": titles[pid]}
            for pid in prereqs.get(path_id, [])
            if pid in titles and pid not in completed
        ]

    def _with_title_langs(items: list[dict[str, str]], locale: str) -> list[dict[str, str]]:
        if items:  # only look the languages up when there is something to show
            langs = _title_langs(locale)
            for it in items:
                it["titleLang"] = langs.get(it["pathId"], "")
        return items

    def _lock_state(request: Request, path_id: str) -> list[dict[str, str]]:
        learner = _learner(request)
        completed = completed_path_ids(store, learner["userId"] if learner else None)
        prereqs, titles = _prereq_index(_locale(request))
        return _with_title_langs(_locked_by(path_id, prereqs, titles, completed), _locale(request))

    def _unlocked_next(request: Request, path_id: str) -> list[dict[str, str]]:
        """Paths that list ``path_id`` as a prerequisite and are now fully open."""
        learner = _learner(request)
        completed = completed_path_ids(store, learner["userId"] if learner else None)
        completed.add(path_id)
        prereqs, titles = _prereq_index(_locale(request))
        return _with_title_langs([
            {"pathId": pid, "title": titles[pid]}
            for pid, needs in prereqs.items()
            if path_id in needs and pid in titles and not _locked_by(pid, prereqs, titles, completed)
        ], _locale(request))

    def _read_only_redirect(request: Request, sess: dict[str, Any], path_id: str) -> RedirectResponse:
        sess["view"] = "learn"
        sess["last_result"] = None
        sess["flash"] = {"level": "warn", "text": t(_locale(request), "read_only_blocked")}
        resp = RedirectResponse(f"/play/{path_id}?view=learn", status_code=303)
        resp.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
        return resp

    # --- Identity / locale (email registration; cookie = opaque user id only) ---
    def _login_error(locale: str, error: str | None) -> str:
        codes = {
            "email_required": "err_email_required",
            "email_invalid": "err_email_invalid",
            "name_required": "err_name_required",
            "email_taken": "err_email_taken",
            "email_change_disabled": "err_email_change_disabled",
        }
        key = codes.get(error or "")
        return t(locale, key) if key else ""

    @app.get("/login", response_class=HTMLResponse)
    def login_page(
        request: Request,
        next: str = "/",
        error: str | None = None,
        mode: str = "signin",
        email: str = "",
    ) -> HTMLResponse:
        locale = _locale(request)
        dest = _safe_next(next)
        show_register = mode == "register" or error == "name_required"
        return templates.TemplateResponse(
            request,
            "login.html",
            _shell_ctx(
                request,
                next_url=dest,
                mode="register" if show_register else "signin",
                current_email=email or "",
                error=_login_error(locale, error),
            ),
        )

    @app.post("/login")
    def login_submit(
        request: Request,
        first_name: str = Form(""),
        last_name: str = Form(""),
        email: str = Form(""),
        next: str = Form("/"),
        mode: str = Form("signin"),
    ) -> RedirectResponse:
        locale = _locale(request)
        dest = _safe_next(next)
        try:
            learner = store.register_or_login(
                email=email,
                first_name=first_name,
                last_name=last_name,
                locale=locale,
            )
        except ValueError as exc:
            code = str(exc) or "email_invalid"
            show_mode = "register" if code == "name_required" or mode == "register" else "signin"
            qs = (
                "/login?next=" + quote(dest, safe="")
                + "&mode=" + show_mode
                + "&error=" + quote(code, safe="")
                + "&email=" + quote((email or "").strip(), safe="")
            )
            return RedirectResponse(qs, status_code=303)
        resp = RedirectResponse(dest, status_code=303)
        _start_session(request, resp, learner, learner.get("locale") or locale)
        return resp

    @app.get("/accessibility", response_class=HTMLResponse)
    def accessibility_statement(request: Request) -> HTMLResponse:
        """Accessibility statement (#60), public like /login: reachable without signing in."""
        return templates.TemplateResponse(
            request, "accessibility.html", _shell_ctx(request, statement=statement_details())
        )

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(
        request: Request,
        error: str | None = None,
        saved: str | None = None,
    ) -> HTMLResponse:
        learner = _require_learner(request)
        if not learner:
            return _login_redirect(request)
        locale = learner.get("locale") or _locale(request)
        return templates.TemplateResponse(
            request,
            "settings.html",
            _shell_ctx(
                request,
                learner=learner,
                locale=locale,
                html_lang=html_lang(locale),
                html_dir=dir_for(locale),
                error=_login_error(locale, error),
                saved=bool(saved),
            ),
        )

    @app.post("/settings")
    def settings_save(
        request: Request,
        first_name: str = Form(""),
        last_name: str = Form(""),
        email: str = Form(""),
    ) -> RedirectResponse:
        learner = _require_learner(request)
        if not learner:
            return _login_redirect(request)
        try:
            updated = store.update_learner_profile(
                learner["userId"],
                first_name=first_name,
                last_name=last_name,
                email=email,
                locale=learner.get("locale") or _locale(request),
            )
        except ValueError as exc:
            code = str(exc) or "email_invalid"
            return RedirectResponse("/settings?error=" + quote(code, safe=""), status_code=303)
        resp = RedirectResponse("/settings?saved=1", status_code=303)
        _set_locale_cookie(resp, updated.get("locale") or "he")
        return resp

    @app.post("/logout")
    def logout(request: Request) -> RedirectResponse:
        store.revoke_session(request.cookies.get(SESSION_COOKIE))
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(SESSION_COOKIE, httponly=True, samesite="lax", secure=cookie_secure())
        return resp

    register_agent_builder_routes(
        app,
        templates=templates,
        store=store,
        tools=tools,
        shell_ctx=_shell_ctx,
        current_learner=_learner,
        login_redirect=_login_redirect,
        locale_of=_locale,
    )

    @app.post("/locale")
    def set_locale(
        request: Request,
        locale: str = Form("he"),
        next: str = Form("/"),
    ) -> RedirectResponse:
        loc = normalize_locale(locale)
        learner = _learner(request)
        if learner:
            store.upsert_learner(
            learner["userId"], learner["displayName"], locale=loc,
            first_name=learner.get("firstName") or None,
            last_name=learner.get("lastName") or None,
            email=learner.get("email") or None,
        )
        dest = next if next.startswith("/") else "/"
        resp = RedirectResponse(dest, status_code=303)
        resp.set_cookie(COOKIE_LOCALE, loc, httponly=False, samesite="lax", max_age=86400 * 400)
        return resp

    @app.get("/", response_class=HTMLResponse)
    def platform_home(
        request: Request,
        group: str | None = None,
        subject: str | None = "all",
        tab: str | None = None,
        view: str | None = "status",
    ) -> HTMLResponse:
        locale = _locale(request)
        cards = list_catalog_cards(store, locale=locale)
        for c in cards:
            # Title/blurb are content: fall back to the path's own language, not English.
            chrome = localize_path_chrome(
                locale=locale,
                titles=c.get("titles"),
                blurbs=c.get("blurbs"),
                source_locale=c.get("explainLocale"),
            )
            c.update(title=chrome["title"], blurb=chrome["blurb"],
                     titleLang=chrome["titleLang"], blurbLang=chrome["blurbLang"])
        learner = _learner(request)
        progress_map: dict[str, Any] = {}
        if learner:
            for row in store.list_user_progress(learner["userId"]):
                progress_map[row["pathId"]] = row

        now_ts = time.time()
        recent_cutoff = 7 * 24 * 3600  # 7 days

        for c in cards:
            prog = progress_map.get(c["pathId"])
            c["userProgress"] = prog
            status = None
            needs = False
            updated_ts = None
            if prog:
                status = prog.get("progressStatus")
                if prog.get("completedAt"):
                    status = "completed"
                elif prog.get("startedAt") or prog.get("masteredCount", 0) > 0 or prog.get("nodeIndex", 0) > 0:
                    status = "in_progress"
                needs = bool(prog.get("needsPractice"))
                updated_ts = _parse_iso(prog.get("updatedAt")) or _parse_iso(prog.get("startedAt"))
            c["progressStatus"] = status
            c["needsPractice"] = needs
            c["updatedTs"] = updated_ts
            if updated_ts is None:
                c["timeBucket"] = "never"
            elif now_ts - updated_ts <= recent_cutoff:
                c["timeBucket"] = "recent"
            else:
                c["timeBucket"] = "older"

        # Locked paths (schema v2 prerequisite_path_ids not finished yet).
        prereqs, prereq_titles = _prereq_index(locale)
        completed = {c["pathId"] for c in cards if c.get("progressStatus") == "completed"}
        card_langs = {c["pathId"]: c.get("titleLang", "") for c in cards}
        for c in cards:
            c["lockedBy"] = _locked_by(c["pathId"], prereqs, prereq_titles, completed)
            for it in c["lockedBy"]:
                it["titleLang"] = card_langs.get(it["pathId"], "")

        # "Continue" resumes the most recently touched path at the step the learner was on.
        continue_card = None
        contenders = [c for c in cards if c.get("progressStatus") == "in_progress"]
        if contenders:
            contenders.sort(key=lambda c: c.get("updatedTs") or 0, reverse=True)
            top = dict(contenders[0])
            prog = top.get("userProgress") or {}
            total_nodes = int(top.get("nodeCount") or 0)
            done_nodes = int(prog.get("masteredCount") or 0)
            top["continuePct"] = int(round(100 * done_nodes / total_nodes)) if total_nodes else 0
            step_index = int(prog.get("nodeIndex") or 0)
            if total_nodes:
                step_index = max(0, min(step_index, total_nodes - 1))
            top["continueStep"] = step_index + 1
            top["continueTotal"] = total_nodes
            top["continueTopic"] = ""
            try:
                cdoc = store.get_version(top["pathId"], top["versionId"]).model_dump(mode="json", by_alias=True)
                cblocks = cdoc.get("blocks") or []
                if 0 <= step_index < len(cblocks):
                    bid = cblocks[step_index]["blockId"]
                    for tp in _topics_for_ui(cdoc, cblocks, locale):
                        if bid in tp["blockIds"]:
                            top["continueTopic"] = tp["title"]
                            top["continueTopicLang"] = tp.get("titleLang", "")
                            break
            except Exception:  # the card still works without the topic name
                pass
            top["continueHref"] = f"/play/{top['pathId']}?view=learn"
            continue_card = top

        # Default group: the group of the path the learner is on (e.g. adult), else grade3.
        if group is None:
            group = "grade3"
            if continue_card and continue_card.get("groupIds"):
                group = continue_card["groupIds"][0]

        catalog = group_catalog(cards, group_id=group or None, subject=subject)
        if (group == "grade3") and catalog["total"] == 0 and cards:
            catalog = group_catalog(cards, group_id=None, subject=subject)

        filtered_cards = list(catalog["cards"])
        active_view = view if view in ("status", "time") else "status"
        if tab in ("in_progress", "completed", "practice", "catalog"):
            active_tab = tab
        else:
            # First visit with no progress → catalog; otherwise land on in-progress
            active_tab = "in_progress" if progress_map else "catalog"
        if active_view == "status":
            if active_tab == "in_progress":
                filtered_cards = [c for c in filtered_cards if c.get("progressStatus") == "in_progress"]
            elif active_tab == "completed":
                filtered_cards = [c for c in filtered_cards if c.get("progressStatus") == "completed"]
            elif active_tab == "practice":
                filtered_cards = [
                    c
                    for c in filtered_cards
                    if c.get("needsPractice")
                    or (
                        c.get("progressStatus") == "in_progress"
                        and (c.get("userProgress") or {}).get("incorrectTaps", 0) >= 1
                    )
                ]
            # catalog = all filtered by group/subject
            elif active_tab == "catalog":
                pass
            else:
                active_tab = "catalog"
        else:
            # time view: keep all catalog cards; template groups by time + subject
            active_tab = "catalog"

        # Counts for tab badges (within group/subject filter)
        base_cards = list(catalog["cards"])
        tab_counts = {
            "in_progress": sum(1 for c in base_cards if c.get("progressStatus") == "in_progress"),
            "completed": sum(1 for c in base_cards if c.get("progressStatus") == "completed"),
            "practice": sum(
                1
                for c in base_cards
                if c.get("needsPractice")
                or (
                    c.get("progressStatus") == "in_progress"
                    and (c.get("userProgress") or {}).get("incorrectTaps", 0) >= 1
                )
            ),
            "catalog": len(base_cards),
        }

        # Time + subject grouping for time view
        time_groups: list[dict[str, Any]] = []
        if active_view == "time":
            for bucket, label_key in (
                ("recent", "time_recent"),
                ("older", "time_older"),
                ("never", "time_never"),
            ):
                bucket_cards = [c for c in base_cards if c.get("timeBucket") == bucket]
                by_subject: dict[str, list] = {}
                for c in bucket_cards:
                    by_subject.setdefault(c["subject"], []).append(c)
                subjects_blocks = []
                for sid, scards in sorted(by_subject.items(), key=lambda kv: subject_label(kv[0], locale)):
                    subjects_blocks.append(
                        {
                            "subject": sid,
                            "label": subject_label(sid, locale),
                            "emoji": SUBJECTS.get(sid, SUBJECTS["general"]).get("emoji", "📚"),
                            "color": SUBJECTS.get(sid, SUBJECTS["general"]).get("color"),
                            "cards": scards,
                        }
                    )
                time_groups.append(
                    {
                        "bucket": bucket,
                        "label": t(locale, label_key),
                        "subjects": subjects_blocks,
                        "count": len(bucket_cards),
                    }
                )

        group_banner = catalog.get("group")
        if group_banner:
            group_banner = dict(group_banner)
            g_titles = dict(group_banner.get("titles") or {})
            g_blurbs = dict(group_banner.get("blurbs") or {})
            for code in ("he", "en", "ar"):
                if group_banner.get(f"title_{code}"):
                    g_titles.setdefault(code, group_banner.get(f"title_{code}"))
                if group_banner.get(f"blurb_{code}"):
                    g_blurbs.setdefault(code, group_banner.get(f"blurb_{code}"))
            group_banner["title_display"] = pick(g_titles, locale, default=group_banner.get("title_he") or "")
            group_banner["blurb_display"] = pick(g_blurbs, locale, default=group_banner.get("blurb_he") or "")

        subjects_ui = {}
        for sid, meta in SUBJECTS.items():
            subjects_ui[sid] = {**meta, "label": subject_label(sid, locale)}

        groups_ui: dict[str, Any] = {}
        for gid, g in GROUPS.items():
            g_titles = dict(g.get("titles") or {})
            for code in ("he", "en", "ar"):
                if g.get(f"title_{code}"):
                    g_titles.setdefault(code, g.get(f"title_{code}"))
            title = pick(g_titles, locale, default=g.get("title_he") or gid)
            groups_ui[gid] = {**g, "title_display": title}

        # Tab order: RTL puts first item on the right (Hebrew emphasis); LTR left for English
        if dir_for(locale) == "rtl":
            tab_order = ["in_progress", "completed", "practice", "catalog"]
        else:
            tab_order = ["catalog", "in_progress", "completed", "practice"]

        response = templates.TemplateResponse(
            request,
            "home.html",
            _shell_ctx(
                request,
                continue_card=continue_card,
                catalog={**catalog, "group": group_banner, "cards": filtered_cards},
                active_group=group or "all",
                active_subject=subject or "all",
                active_tab=active_tab,
                active_view=active_view,
                tab_counts=tab_counts,
                tab_order=tab_order,
                time_groups=time_groups,
                groups=groups_ui,
                subjects=subjects_ui,
            ),
        )
        return response

    # Step text (titles, bodies, choices, feedback) renders through this filter so math
    # and Latin runs stay readable inside Hebrew/Arabic sentences. See ui/bidi.py.
    templates.env.filters["bdi"] = bidi_isolate
    # `` lang="xx"`` on content text shown in a language other than the UI locale (see i18n.py).
    templates.env.filters["content_lang"] = content_lang

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
        locked_by = _lock_state(request, path_id)
        read_only = bool(locked_by)
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
        if read_only and sess.get("view") == "stats":
            # Read-only paths never record an attempt or a completion.
            sess["view"] = "map"

        if _is_htmx(request) and sess.get("view") != "learn":
            # Only the learn view has a step card to swap; map and summary load as pages.
            return _hx_redirect(f"/play/{path_id}")

        if sess.get("view") == "stats":
            attempt = _finalize_attempt(sess, doc, locale)
            ctx = _shell_ctx(
                request,
                doc=doc,
                meta=meta,
                attempt=attempt,
                total=n,
                unlocked_next=_unlocked_next(request, path_id),
            )
            response = templates.TemplateResponse(request, "stats.html", ctx)
            response.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
            return response

        if sess.get("view") != "learn":
            # Topic map first
            mastered = sess.get("mastered") or set()
            resume_index = int(sess.get("index", 0) or 0)
            current_bid = blocks[resume_index]["blockId"] if 0 <= resume_index < n else None
            current_station = 0
            for i, tp in enumerate(topics):
                done = sum(1 for bid in tp["blockIds"] if bid in mastered)
                tp["doneCount"] = done
                tp["complete"] = tp["stepCount"] > 0 and done >= tp["stepCount"]
                tp["pct"] = int(round(100 * done / tp["stepCount"])) if tp["stepCount"] else 0
                tp["current"] = current_bid is not None and current_bid in tp["blockIds"]
                if tp["current"]:
                    current_station = i + 1
                for st in tp["steps"]:
                    st["done"] = st["blockId"] in mastered
                    st["current"] = st["blockId"] == current_bid
            ctx = _shell_ctx(
                request,
                doc=doc,
                meta=meta,
                topics=topics,
                mastered=mastered,
                total=n,
                progress=int(round(100 * len(mastered) / n)) if n else 0,
                can_resume=bool(mastered) or sess.get("index", 0) > 0,
                resume_index=resume_index,
                current_station=current_station,
                stations_done=sum(1 for tp in topics if tp["complete"]),
                locked_by=locked_by,
                read_only=read_only,
            )
            response = templates.TemplateResponse(request, "map.html", ctx)
            response.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
            return response

        # Learn view
        return _render_step(request, sess, doc, locked_by=locked_by, swap_focus="step-title")

    def _render_step(
        request: Request,
        sess: dict[str, Any],
        doc: dict[str, Any],
        *,
        locked_by: list[dict[str, str]],
        idx: int | None = None,
        answer: dict[str, Any] | None = None,
        continue_url: str | None = None,
        swap_focus: str | None = None,
    ) -> Response:
        """Render the step player: the full page, or only the step card for htmx.

        ``idx`` defaults to the session's current step. After a right answer over htmx it
        is the step just answered (the session has already moved on), so the learner sees
        the feedback under the choices and continues with ``continue_url``.
        """
        locale = _locale(request)
        blocks = doc.get("blocks") or []
        n = len(blocks)
        hx = _is_htmx(request)
        if idx is None:
            idx = max(0, min(sess["index"], n - 1 if n else 0))
            sess["index"] = idx
        block = blocks[idx] if blocks else None
        if hx and not block:
            return _hx_redirect(f"/play/{sess['pathId']}")
        kids = _kids_payload(block)
        display = resolve_node_display(
            kids,
            ui_locale=locale,
            content_locale=doc.get("contentLocale") or doc.get("contentLanguage"),
        )
        if answer is None:
            # No-JS path: a wrong pick redirects here; show its feedback under the choices once.
            pending = sess.pop("answer_feedback", None)
            if pending and block and pending.get("blockId") == block.get("blockId"):
                answer = pending
        flash = None if hx else sess.pop("flash", None)
        result = sess.get("last_result")
        progress = int(round(100 * len(sess["mastered"]) / n)) if n else 0
        ctx = _shell_ctx(
            request,
            doc=doc,
            meta=_card_meta(doc, locale),
            blocks=blocks,
            block=block,
            kids=kids,
            display=display,
            content_locale=doc.get("contentLocale") or doc.get("contentLanguage") or "he",
            explain_locale=doc.get("explainLocale") or "he",
            index=idx,
            total=n,
            progress=progress,
            mastered=sess["mastered"],
            flash=flash,
            result=result,
            can_prev=idx > 0,
            can_next=idx < n - 1,
            is_done=_maybe_done(sess, n),
            topics=_topics_for_ui(doc, blocks, locale),
            locked_by=locked_by,
            read_only=bool(locked_by),
            answer=answer,
            step_langs=_step_langs(kids, doc, locale),
            continue_url=continue_url,
            continue_hx=bool(continue_url) and "view=learn" in (continue_url or ""),
            swap_focus=swap_focus if hx else None,
            status_oob=hx,
        )
        template = "_step_swap.html" if hx else "play.html"
        response = templates.TemplateResponse(request, template, ctx)
        response.headers["Vary"] = "HX-Request"
        response.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
        return response

    @app.post("/play/{path_id}/start")
    def play_start(
        path_id: str,
        request: Request,
        topic: str = Form(""),
        reset: str = Form(""),
    ) -> RedirectResponse:
        sess = _play_session(request, path_id, resume=not bool(reset))
        if _lock_state(request, path_id):
            # Read-only: open the path (or a topic) without writing any progress.
            if topic:
                doc = _load_play_doc(sess)
                blocks = doc.get("blocks") or []
                match = next(
                    (tp for tp in _topics_for_ui(doc, blocks, _locale(request)) if tp["id"] == topic), None
                )
                if match:
                    sess["index"] = match["startIndex"]
            sess["view"] = "learn"
            resp = RedirectResponse(f"/play/{path_id}?view=learn", status_code=303)
            resp.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
            return resp
        if reset:
            sess["index"] = 0
            sess["mastered"] = set()
            sess["correct_taps"] = 0
            sess["incorrect_taps"] = 0
            sess["started_at"] = datetime.now(timezone.utc).isoformat()
            sess["started_monotonic"] = time.monotonic()
            sess["attempt_saved"] = False
            sess["last_attempt"] = None
            # Clear completion so the path returns to in-progress bookmarks
            store.save_progress(
                sess["userId"],
                sess["pathId"],
                version_id=sess.get("versionId"),
                node_index=0,
                mastered=set(),
                correct_taps=0,
                incorrect_taps=0,
                started_at=sess["started_at"],
                completed_at=None,
                needs_practice=False,
            )
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
        if _lock_state(request, path_id):
            return _read_only_redirect(request, sess, path_id)
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
    ) -> Response:
        locale = _locale(request)
        hx = _is_htmx(request)
        sess = _play_session(request, path_id)
        if _lock_state(request, path_id):
            resp = _read_only_redirect(request, sess, path_id)
            return _hx_redirect(resp.headers["location"]) if hx else resp
        sess["view"] = "learn"
        doc = _load_play_doc(sess)
        blocks = doc.get("blocks") or []
        block = blocks[sess["index"]] if blocks else None
        if not block:
            if hx:
                return _hx_redirect(f"/play/{path_id}?view=learn")
            resp = RedirectResponse(f"/play/{path_id}?view=learn", status_code=303)
            return resp
        answered_idx = sess["index"]
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

        feedback = {
            "blockId": block["blockId"],
            "choice": choice,
            "ok": ok,
            "text": (kids.get("feedback_ok") or "✓") if ok else (kids.get("feedback_try") or t(locale, "gate_practice")),
        }
        if ok:
            sess["mastered"].add(block["blockId"])
            sess["last_result"] = {"ok": True, "text": kids.get("feedback_ok") or "✓"}
            # No-JS: the next step opens with this note (the answered card is htmx-only).
            sess["flash"] = {"level": "ok", "text": kids.get("feedback_ok") or "✓"}
            sess.pop("answer_feedback", None)
            if sess["index"] < len(blocks) - 1:
                sess["index"] += 1
                sess["last_result"] = None
        else:
            sess["last_result"] = {"ok": False, "text": feedback["text"]}
            # Shown under the choices of this same step (not as a page-top flash).
            sess["answer_feedback"] = feedback
        _persist_progress(sess, completed=_maybe_done(sess, len(blocks)))
        if hx:
            # htmx: answer in place. Wrong -> same card with the explanation; right -> the
            # answered card with its feedback and a button to the next step (or the summary).
            sess.pop("answer_feedback", None)
            continue_url = None
            if ok:
                sess.pop("flash", None)
                done = _maybe_done(sess, len(blocks))
                continue_url = f"/play/{path_id}?view=stats" if done else f"/play/{path_id}?view=learn"
            return _render_step(
                request,
                sess,
                doc,
                locked_by=[],
                idx=answered_idx,
                answer=feedback,
                continue_url=continue_url,
                swap_focus="step-feedback",
            )
        if not ok:
            # The fragment brings the feedback into view after the full-page reload.
            resp = RedirectResponse(f"/play/{path_id}?view=learn#step-feedback", status_code=303)
        elif _maybe_done(sess, len(blocks)):
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
        if _lock_state(request, path_id):
            # Read-only browsing: move freely, never gate and never persist.
            if direction == "prev":
                sess["index"] = max(0, sess["index"] - 1)
            else:
                sess["index"] = min(max(len(blocks) - 1, 0), sess["index"] + 1)
            resp = RedirectResponse(f"/play/{path_id}?view=learn", status_code=303)
            resp.set_cookie("myroad_play", sess["sid"], httponly=True, samesite="lax")
            return resp
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
