"""Platform catalog + path player (age-agnostic shell; content drives tone)."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from myroad_core.auth.captcha import captcha_site_key, captcha_verifier_from_env
from myroad_core.auth.email_change import EMAIL_CHANGE_COOKIE
from myroad_core.auth.login_codes import CODE_TTL_SECONDS
from myroad_core.auth.mailer import (
    send_email_change_code,
    send_email_change_taken_notice,
    send_email_changed_notice,
    send_login_code,
    send_no_account_notice,
)
from myroad_core.auth.sessions import SESSION_COOKIE, SESSION_TTL_SECONDS, cookie_secure
from myroad_core.content.loader import group_catalog, list_catalog_cards
from myroad_core.content.locale_rules import resolve_node_display
from myroad_core.content.schema import GROUPS, SUBJECTS
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
    subject_label,
    t,
)
from myroad_core.ui.agent_builder_routes import register_agent_builder_routes

ACTOR_LEARNER = "user_learner_poc"
# Opaque id of the pending email-code challenge (not the code itself).
COOKIE_LOGIN_CHALLENGE = "myroad_login"


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
        }

    def _topics_for_ui(doc: dict[str, Any], blocks: list[dict], locale: str) -> list[dict[str, Any]]:
        topics = doc.get("topics") or []
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
            title = pick(topic_titles, locale, default=topic.get("id") or "")
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
        needs = mastery < 85.0 or int(sess.get("incorrect_taps") or 0) >= 2
        _persist_progress(sess, completed=True, needs_practice=needs)
        return attempt or {}

    def _maybe_done(sess: dict[str, Any], n: int) -> bool:
        return n > 0 and len(sess.get("mastered") or set()) >= n

    # --- Identity / locale (email registration; cookie = opaque user id only) ---
    def _login_error(locale: str, error: str | None) -> str:
        codes = {
            "email_required": "err_email_required",
            "email_invalid": "err_email_invalid",
            "name_required": "err_name_required",
            "email_taken": "err_email_taken",
            "too_many_codes": "err_too_many_codes",
            "mail_failed": "err_mail_failed",
            "code_required": "err_code_required",
            "code_wrong": "err_code_wrong",
            "code_expired": "err_code_expired",
            "code_used": "err_code_used",
            "code_locked": "err_code_locked",
            "code_invalid": "err_code_expired",
            "email_change_disabled": "err_email_change_disabled",
            "email_same": "err_email_same",
            "code_slow_down": "err_code_slow_down",
            "captcha_required": "err_captcha_required",
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

    def _client_ip(request: Request) -> str:
        # Direct peer address. Behind a reverse proxy, configure uvicorn's
        # --proxy-headers / --forwarded-allow-ips so this is the real client.
        return (request.client.host if request.client else "") or "unknown"

    def _verify_url(dest: str, email: str, error: str | None = None) -> str:
        url = "/login/verify?next=" + quote(dest, safe="") + "&email=" + quote(email, safe="")
        return url + ("&error=" + quote(error, safe="") if error else "")

    def _captcha_verifier():
        # Pluggable (app.state.captcha_verifier), else from env; None = CAPTCHA off.
        hook = getattr(app.state, "captcha_verifier", None)
        return hook if hook is not None else captcha_verifier_from_env()

    def _captcha_site_key() -> str:
        return getattr(app.state, "captcha_site_key", None) or captcha_site_key()

    def _captcha_needed(request: Request, challenge_ids) -> bool:
        return _captcha_verifier() is not None and store.captcha_required_for(challenge_ids, _client_ip(request))

    def _captcha_passes(request: Request, challenge_ids, token: str) -> bool:
        """False only when a CAPTCHA is configured, required here, and not solved."""
        verifier = _captcha_verifier()
        if verifier is None or not store.captcha_required_for(challenge_ids, _client_ip(request)):
            return True
        return bool(token) and bool(verifier(token, _client_ip(request)))

    @app.post("/login")
    def login_submit(
        request: Request,
        first_name: str = Form(""),
        last_name: str = Form(""),
        email: str = Form(""),
        next: str = Form("/"),
        mode: str = Form("signin"),
    ) -> RedirectResponse:
        """Step 1: email a one-time code. No session (and no new account) yet.

        The response is the same whether or not the email has an account and
        whether or not a send limit was hit; only the email content differs.
        """
        locale = _locale(request)
        dest = _safe_next(next)
        typed = (email or "").strip()

        def _back(code: str) -> RedirectResponse:
            show_mode = "register" if code == "name_required" or mode == "register" else "signin"
            qs = (
                "/login?next=" + quote(dest, safe="")
                + "&mode=" + show_mode
                + "&error=" + quote(code, safe="")
                + "&email=" + quote(typed, safe="")
            )
            return RedirectResponse(qs, status_code=303)

        if mode == "register" and (not first_name.strip() or not last_name.strip()):
            return _back("name_required")  # form check; same for known and unknown emails
        try:
            req = store.request_login(
                email=email,
                first_name=first_name,
                last_name=last_name,
                locale=locale,
                client_ip=_client_ip(request),
            )
        except ValueError as exc:
            return _back(str(exc) or "email_invalid")
        try:
            if req.kind == "code":
                sender = getattr(app.state, "login_code_sender", None) or send_login_code
                sender(req.email, req.code)
            elif req.kind == "no_account":
                notice = getattr(app.state, "login_notice_sender", None) or send_no_account_notice
                notice(req.email)
        except Exception:  # noqa: BLE001 - SMTP failure or mail not configured: fail closed
            return _back("mail_failed")
        resp = RedirectResponse(_verify_url(dest, typed), status_code=303)
        resp.set_cookie(
            COOKIE_LOGIN_CHALLENGE, req.challenge_id, httponly=True, samesite="lax",
            max_age=CODE_TTL_SECONDS, path="/login", secure=cookie_secure(),
        )
        return resp

    @app.get("/login/verify", response_class=HTMLResponse)
    def login_verify_page(
        request: Request,
        next: str = "/",
        email: str = "",
        error: str | None = None,
    ):
        locale = _locale(request)
        dest = _safe_next(next)
        if not request.cookies.get(COOKIE_LOGIN_CHALLENGE):
            return RedirectResponse("/login?next=" + quote(dest, safe=""), status_code=303)
        # The page only echoes what the user typed; it never reveals whether
        # a code was really sent.
        return templates.TemplateResponse(
            request,
            "login.html",
            _shell_ctx(
                request,
                next_url=dest,
                mode="verify",
                current_email=email.strip()[:120],
                error=_login_error(locale, error),
                captcha_needed=_captcha_needed(request, request.cookies.get(COOKIE_LOGIN_CHALLENGE)),
                captcha_site_key=_captcha_site_key(),
            ),
        )

    @app.post("/login/verify")
    def login_verify_submit(
        request: Request,
        code: str = Form(""),
        next: str = Form("/"),
        email: str = Form(""),
        captcha_token: str = Form(""),
        turnstile_token: str = Form("", alias="cf-turnstile-response"),
    ) -> RedirectResponse:
        """Step 2: the session starts only after the emailed code checks out."""
        locale = _locale(request)
        dest = _safe_next(next)
        typed = email.strip()[:120]
        challenge_id = request.cookies.get(COOKIE_LOGIN_CHALLENGE)
        if challenge_id and not _captcha_passes(request, challenge_id, captcha_token or turnstile_token):
            return RedirectResponse(_verify_url(dest, typed, "captcha_required"), status_code=303)
        try:
            learner = store.verify_login_challenge(challenge_id, code, client_ip=_client_ip(request))
        except ValueError as exc:
            err = str(exc) or "code_wrong"
            if err in ("code_wrong", "code_required", "code_slow_down"):
                return RedirectResponse(_verify_url(dest, typed, err), status_code=303)
            resp = RedirectResponse(
                "/login?next=" + quote(dest, safe="") + "&error=" + quote(err, safe="")
                + "&email=" + quote(typed, safe=""),
                status_code=303,
            )
            resp.delete_cookie(COOKIE_LOGIN_CHALLENGE, path="/login", secure=cookie_secure(), httponly=True)
            return resp
        resp = RedirectResponse(dest, status_code=303)
        _start_session(request, resp, learner, learner.get("locale") or locale)
        resp.delete_cookie(COOKIE_LOGIN_CHALLENGE, path="/login", secure=cookie_secure(), httponly=True)
        return resp

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(
        request: Request,
        error: str | None = None,
        saved: str | None = None,
        email_changed: str | None = None,
        pending_new: str | None = None,
    ) -> HTMLResponse:
        learner = _require_learner(request)
        if not learner:
            return _login_redirect(request)
        locale = learner.get("locale") or _locale(request)
        change_id = request.cookies.get(EMAIL_CHANGE_COOKIE)
        pending = store.pending_email_change(learner["userId"], change_id)
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
                email_changed=bool(email_changed),
                pending_email=(pending or {}).get("new_email") or (pending_new or "").strip()[:120]
                if change_id else "",
                captcha_needed=_captcha_needed(request, store.email_change_challenges(change_id)),
                captcha_site_key=_captcha_site_key(),
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

    def _email_change_mail(kind: str, to: str, code: str | None = None, new_email: str | None = None) -> None:
        hook = getattr(app.state, "email_change_sender", None)
        if hook is not None:
            hook(kind, to, code or new_email)
        elif kind == "code_current":
            send_email_change_code(to, code or "", role="current")
        elif kind == "code_new":
            send_email_change_code(to, code or "", role="new")
        elif kind == "taken_notice":
            send_email_change_taken_notice(to)
        elif kind == "changed_notice":
            send_email_changed_notice(to, new_email or "")

    def _settings_error(code: str, *, drop_change: bool = False) -> RedirectResponse:
        resp = RedirectResponse("/settings?error=" + quote(code, safe=""), status_code=303)
        if drop_change:
            resp.delete_cookie(EMAIL_CHANGE_COOKIE, path="/settings", secure=cookie_secure(), httponly=True)
        return resp

    @app.post("/settings/email")
    def email_change_start(request: Request, new_email: str = Form("")) -> RedirectResponse:
        """Step 1 of an email change: codes to the current AND the new address.

        Same response whether or not the new address has an account and
        whether or not a send limit was hit. Nothing changes yet.
        """
        learner = _require_learner(request)
        if not learner:
            return _login_redirect(request)
        try:
            req = store.start_email_change(learner["userId"], new_email, client_ip=_client_ip(request))
        except ValueError as exc:
            return _settings_error(str(exc) or "email_invalid")
        try:
            if req.kind == "codes":
                _email_change_mail("code_current", req.old_email, req.current_code)
                if req.new_code:
                    _email_change_mail("code_new", req.new_email, req.new_code)
                else:
                    _email_change_mail("taken_notice", req.new_email)
        except Exception:  # noqa: BLE001 - mail not configured or SMTP failure: fail closed
            return _settings_error("mail_failed")
        resp = RedirectResponse(
            "/settings?pending_new=" + quote(req.new_email, safe=""), status_code=303
        )
        resp.set_cookie(
            EMAIL_CHANGE_COOKIE, req.change_id, httponly=True, samesite="lax",
            max_age=CODE_TTL_SECONDS, path="/settings", secure=cookie_secure(),
        )
        return resp

    @app.post("/settings/email/verify")
    def email_change_verify(
        request: Request,
        code_current: str = Form(""),
        code_new: str = Form(""),
        captcha_token: str = Form(""),
        turnstile_token: str = Form("", alias="cf-turnstile-response"),
    ) -> RedirectResponse:
        """Step 2: both codes must check out; then the email switches and every
        session ends (this browser gets a fresh one); the old address is told."""
        learner = _require_learner(request)
        if not learner:
            return _login_redirect(request)
        change_id = request.cookies.get(EMAIL_CHANGE_COOKIE)
        if change_id and not _captcha_passes(
            request, store.email_change_challenges(change_id), captcha_token or turnstile_token
        ):
            return _settings_error("captcha_required")
        try:
            result = store.confirm_email_change(
                learner["userId"], change_id,
                current_code=code_current, new_code=code_new, client_ip=_client_ip(request),
            )
        except ValueError as exc:
            err = str(exc) or "code_wrong"
            return _settings_error(err, drop_change=err not in ("code_wrong", "code_required", "code_slow_down"))
        try:
            _email_change_mail("changed_notice", result["old_email"], new_email=result["new_email"])
        except Exception:  # noqa: BLE001 - the change is done; a failed notice must not undo it
            pass
        updated = result["learner"]
        resp = RedirectResponse("/settings?saved=1&email_changed=1", status_code=303)
        _start_session(request, resp, updated, updated.get("locale") or "he")
        resp.delete_cookie(EMAIL_CHANGE_COOKIE, path="/settings", secure=cookie_secure(), httponly=True)
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
        group: str | None = "grade3",
        subject: str | None = "all",
        tab: str | None = None,
        view: str | None = "status",
    ) -> HTMLResponse:
        locale = _locale(request)
        cards = list_catalog_cards(store, locale=locale)
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

        continue_card = None
        contenders = [c for c in cards if c.get("progressStatus") == "in_progress"]
        if contenders:
            contenders.sort(key=lambda c: c.get("updatedTs") or 0, reverse=True)
            top = dict(contenders[0])
            prog = top.get("userProgress") or {}
            total_nodes = int(top.get("nodeCount") or 0)
            done_nodes = int(prog.get("masteredCount") or 0)
            top["continuePct"] = int(round(100 * done_nodes / total_nodes)) if total_nodes else 0
            continue_card = top

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
            return response

        # Learn view
        idx = max(0, min(sess["index"], n - 1 if n else 0))
        sess["index"] = idx
        block = blocks[idx] if blocks else None
        kids = _kids_payload(block)
        display = resolve_node_display(
            kids,
            ui_locale=locale,
            content_locale=doc.get("contentLocale") or doc.get("contentLanguage"),
        )
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
            topics=topics,
        )
        response = templates.TemplateResponse(request, "play.html", ctx)
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
