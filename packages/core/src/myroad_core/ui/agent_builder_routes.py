"""/add-path: multi-step agent path builder (goal, existing, outline, build, review).

The model sits behind PathGenerator. With the Cloudflare AI Gateway env set,
GatewayPathGenerator calls Grok through call_grok_chat (BYOK, no provider key
in MyRoad). Without it, demo mode uses FakePathGenerator.
"""
from __future__ import annotations

import uuid
from typing import Any, Callable

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from myroad_core.agent_builder import (
    PUBLISH_FORMAT_ERROR,
    AgentPathBuilder,
    FakePathGenerator,
    GatewayPathGenerator,
    GenerationError,
    GoalSpec,
    PathGenerator,
    PathOutline,
    check_path_completeness,
    draft_problems,
    list_user_agent_drafts,
    preview_document,
)
from myroad_core.agent_builder.models import (
    AUDIENCE_IDS,
    CHANNELS,
    STEP_KINDS,
    LENGTH_IDS,
    LEVEL_IDS,
    LOCALE_CODES,
    STAGE_TYPES,
    SUBJECT_IDS,
)
from myroad_core.agent_builder.suggest import catalog_entries, completed_path_ids, rank_existing
from myroad_core.content.loader import list_catalog_cards
from myroad_core.errors import StoreError
from myroad_core.ui.cloudflare_gateway import (
    GatewayNotConfigured,
    GatewayRequestError,
    call_grok_chat,
    gateway_is_configured,
    missing_gateway_env,
)

COOKIE_AUTHOR_SID = "myroad_author_sid"
STEPS = ("goal", "existing", "outline", "build", "review")

# Unicode first-strong isolate / pop: keeps ids and titles readable inside RTL text.
_FSI, _PDI = "\u2068", "\u2069"
# At most this many ids per list value, and problems in the blocked-publish flash.
FLASH_CAP = 5


def _isolate(text: Any) -> str:
    """Wrap a title or term so it reads correctly inside RTL (or LTR) flash text."""
    return f"{_FSI}{text}{_PDI}"


def default_generator_factory(mode: str) -> PathGenerator:
    """demo -> FakePathGenerator, anything else -> GatewayPathGenerator."""
    if mode == "demo":
        return FakePathGenerator()
    return GatewayPathGenerator()


def _clip(value: str, limit: int) -> str:
    return " ".join((value or "").split())[:limit]


def _to_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def apply_outline_edits(outline: PathOutline, form: dict[str, Any]) -> PathOutline:
    """Apply edited titles and order from the outline form, then re-validate."""
    data = outline.model_dump(mode="json")
    title = _clip(str(form.get("path_title") or ""), 160)
    if title:
        data["title"] = title
    for i, topic in enumerate(data["topics"]):
        new_title = _clip(str(form.get(f"topic_title_{i}") or ""), 160)
        if new_title:
            topic["title"] = new_title
        topic["order"] = _to_int(form.get(f"topic_order_{i}"), topic["order"])
        for j, stage in enumerate(topic["stages"]):
            st = _clip(str(form.get(f"stage_title_{i}_{j}") or ""), 160)
            if st:
                stage["title"] = st
            stage["order"] = _to_int(form.get(f"stage_order_{i}_{j}"), stage["order"])
    # Stable sort keeps the original order on ties.
    for topic in data["topics"]:
        topic["stages"] = [
            s for _, s in sorted(enumerate(topic["stages"]), key=lambda p: (p[1]["order"], p[0]))
        ]
        for n, stage in enumerate(topic["stages"], start=1):
            stage["order"] = n
    data["topics"] = [
        t for _, t in sorted(enumerate(data["topics"]), key=lambda p: (p[1]["order"], p[0]))
    ]
    for n, topic in enumerate(data["topics"], start=1):
        topic["order"] = n
    return PathOutline.model_validate(data)


def register_agent_builder_routes(
    app,
    *,
    templates: Jinja2Templates,
    store,
    tools,
    shell_ctx: Callable[..., dict[str, Any]],
    current_learner: Callable[[Request], dict[str, Any] | None],
    login_redirect: Callable[[Request], RedirectResponse],
    locale_of: Callable[[Request], str],
) -> None:
    builder = AgentPathBuilder(store, tools)
    if not hasattr(app.state, "builder_sessions"):
        app.state.builder_sessions = {}
    if not hasattr(app.state, "author_gateway_ok"):
        app.state.author_gateway_ok = {}
    if not hasattr(app.state, "path_generator_factory"):
        app.state.path_generator_factory = default_generator_factory
    app.state.path_builder = builder

    from myroad_core.ui.i18n import t

    def _session(learner: dict[str, Any]) -> dict[str, Any]:
        sessions: dict[str, dict[str, Any]] = app.state.builder_sessions
        return sessions.setdefault(learner["userId"], {})

    def _generator(mode: str) -> PathGenerator:
        return app.state.path_generator_factory(mode)

    def _gen_error_text(locale: str, exc: GenerationError) -> str:
        key = {
            "gateway_not_configured": "gen_err_gateway_not_configured",
            "gateway_request": "gen_err_gateway_request",
            "bad_reply": "gen_err_bad_reply",
            "save_failed": "gen_err_save_failed",
        }.get(exc.code, "gen_err_internal")
        return t(locale, key, detail=exc.detail or exc.code)

    def _missing_env_text(locale: str) -> str:
        missing = missing_gateway_env()
        if not missing:
            return ""
        return t(locale, "builder_missing_env", names=", ".join(missing))

    def _author_gate_ok(request: Request) -> bool:
        sid = request.cookies.get(COOKIE_AUTHOR_SID)
        return bool(sid and app.state.author_gateway_ok.get(sid))

    def _stepper(current: str, sess: dict[str, Any]) -> list[dict[str, Any]]:
        reach = {"goal": True}
        reach["existing"] = bool(sess.get("spec"))
        reach["outline"] = bool(sess.get("outline"))
        reach["build"] = bool(sess.get("pathId"))
        reach["review"] = bool(sess.get("pathId"))
        idx = STEPS.index(current)
        links = {
            "goal": "/add-path",
            "existing": "/add-path/existing",
            "outline": "/add-path/outline",
            "build": "/add-path/build",
            "review": "/add-path/review",
        }
        out = []
        for i, step in enumerate(STEPS):
            out.append(
                {
                    "id": step,
                    "n": i + 1,
                    "state": "current" if i == idx else ("done" if i < idx else "todo"),
                    "href": links[step] if reach.get(step) and i != idx else None,
                }
            )
        return out

    def _capped(locale: str, items: list[str], sep: str = ", ") -> str:
        shown = sep.join(items[:FLASH_CAP])
        extra = len(items) - FLASH_CAP
        return shown + (" " + t(locale, "builder_and_more", n=extra) if extra > 0 else "")

    def _problem_view(locale: str, problem: dict[str, Any]) -> dict[str, Any]:
        fmt = {
            k: _FSI
            + (_capped(locale, [str(x) for x in v]) if isinstance(v, (list, tuple)) else str(v))
            + _PDI
            for k, v in problem["params"].items()
        }
        return {**problem, "message": t(locale, problem["message_key"], **fmt)}

    def _live_problems(
        request: Request, sess: dict[str, Any], doc: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Problems in the current draft (saved, or previewed from the outline)."""
        if doc is None and sess.get("pathId"):
            learner = current_learner(request)
            doc = _owned_doc(learner, sess) if learner else None
        if doc is None and sess.get("spec") and sess.get("outline"):
            try:
                doc = preview_document(
                    GoalSpec.model_validate(sess["spec"]), PathOutline.model_validate(sess["outline"])
                )
            except (ValidationError, KeyError, TypeError):
                doc = None
        if doc is None:
            return []
        locale = locale_of(request)
        return [_problem_view(locale, p.as_dict()) for p in draft_problems(doc)]

    def _render(request: Request, step: str, sess: dict[str, Any], **extra: Any) -> HTMLResponse:
        locale = locale_of(request)
        configured = gateway_is_configured()
        ctx = shell_ctx(
            request,
            step=step,
            steps=_stepper(step, sess),
            gateway_configured=configured,
            missing_env=missing_gateway_env(),
            missing_env_text=_missing_env_text(locale),
            gateway_checked=configured and _author_gate_ok(request),
            mode=sess.get("mode") or ("gateway" if configured else "demo"),
            spec=sess.get("spec") or {},
            subject_ids=SUBJECT_IDS,
            level_ids=LEVEL_IDS,
            length_ids=LENGTH_IDS,
            locale_codes=LOCALE_CODES,
            stage_types=STAGE_TYPES,
            channels=CHANNELS,
            audience_ids=AUDIENCE_IDS,
            step_kinds=STEP_KINDS,
            error=extra.pop("error", ""),
            flash_ok=extra.pop("flash_ok", ""),
        )
        problems = extra.pop("draft_problems", None)
        if problems is None:
            problems = _live_problems(request, sess, extra.get("doc"))
        ctx["draft_problems"] = problems
        ctx["blocking_problems"] = [p for p in problems if p["severity"] == "error"]
        ctx["publish_blocked"] = False
        ctx.update(extra)
        return templates.TemplateResponse(request, "add_path.html", ctx)

    def _owned_doc(learner: dict[str, Any], sess: dict[str, Any]) -> dict[str, Any] | None:
        pid, vid = sess.get("pathId"), sess.get("versionId")
        if not pid or not vid:
            return None
        try:
            raw = builder.load(pid, vid)
        except StoreError:
            return None
        if (raw.get("actors") or {}).get("authorId") != learner["userId"]:
            return None
        if not raw.get("agentBuild"):
            return None
        return raw

    # --- step 1: goal ---
    @app.get("/add-path", response_class=HTMLResponse)
    def add_path_goal(request: Request, new: str | None = None) -> HTMLResponse:
        learner = current_learner(request)
        if not learner:
            return login_redirect(request)
        sess = _session(learner)
        if new:
            sess.clear()
        locale = locale_of(request)
        flash_ok = t(locale, "add_path_criterion_met") if (
            gateway_is_configured() and _author_gate_ok(request)
        ) else ""
        return _render(
            request,
            "goal",
            sess,
            drafts=list_user_agent_drafts(store, learner["userId"]),
            flash_ok=flash_ok,
        )

    @app.post("/add-path/goal", response_model=None)
    def add_path_goal_submit(
        request: Request,
        goal: str = Form(""),
        subject: str = Form("general"),
        level: str = Form("beginner"),
        ui_locale: str = Form("he"),
        content_language: str = Form("he"),
        length: str = Form("medium"),
        mode: str = Form("demo"),
        audience: str = Form(""),
    ):
        learner = current_learner(request)
        if not learner:
            return login_redirect(request)
        sess = _session(learner)
        locale = locale_of(request)
        mode = "gateway" if mode == "gateway" else "demo"
        raw_spec = {
            "goal": goal,
            "subject": subject,
            "level": level,
            "ui_locale": ui_locale,
            "content_language": content_language,
            "length": length,
            "audience": audience or None,
        }
        if mode == "gateway" and not gateway_is_configured():
            sess["spec"] = raw_spec
            sess["mode"] = "demo"
            return _render(
                request, "goal", sess,
                drafts=list_user_agent_drafts(store, learner["userId"]),
                error=_missing_env_text(locale),
            )
        try:
            spec = GoalSpec.model_validate(raw_spec)
        except ValidationError:
            sess["spec"] = raw_spec
            sess["mode"] = mode
            return _render(
                request, "goal", sess,
                drafts=list_user_agent_drafts(store, learner["userId"]),
                error=t(locale, "builder_err_goal"),
            )
        sess.clear()
        sess["spec"] = spec.model_dump(mode="json")
        sess["mode"] = mode
        return RedirectResponse("/add-path/existing", status_code=303)

    # --- step 2: existing published paths (goal matches first, then the same subject) ---
    def _existing_cards(request: Request, subject: str) -> list[dict[str, Any]]:
        cards = list_catalog_cards(store, locale=locale_of(request))
        return [c for c in cards if c.get("subject") == subject and c.get("status") == "published"]

    def _match_view(locale: str, match: dict[str, Any], titles: dict[str, str]) -> dict[str, Any]:
        reason = match["reason"]
        if reason["code"] == "required_by":
            text = t(
                locale, "builder_match_reason_required",
                title=_isolate(titles.get(reason["required_by"], reason["required_by"])),
            )
        else:
            text = t(locale, "builder_match_reason_terms", terms=", ".join(_isolate(x) for x in reason["terms"]))
            if reason.get("required_by"):
                text += "; " + t(
                    locale, "builder_match_reason_required",
                    title=_isolate(titles.get(reason["required_by"], reason["required_by"])),
                )
        missing = [r for r in match["prerequisites"] if not r["done"]]
        if missing:
            needs = t(locale, "builder_match_needs", titles=", ".join(_isolate(r["title"]) for r in missing))
        elif match["prerequisites"]:
            needs = t(locale, "builder_match_prereqs_done")
        else:
            needs = ""
        view = {k: v for k, v in match.items() if k != "card"}
        view["reason_text"] = text
        view["prerequisites_text"] = needs
        view["missing_prerequisite_titles"] = [r["title"] for r in missing]
        view["href"] = f"/play/{match['pathId']}"
        view["card"] = dict(match["card"], match=view.copy())
        return view

    def _existing_ctx(request: Request, learner: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
        """existing (cards for the template: matches first) + existing_matches (with reasons)."""
        locale = locale_of(request)
        entries = catalog_entries(store, locale=locale)
        matches = rank_existing(
            str(spec.get("goal") or ""),
            entries,
            subject=spec.get("subject"),
            audience=spec.get("audience"),
            completed=completed_path_ids(store, learner.get("userId")),
        )
        titles = {e.path_id: e.title for e in entries}
        views = [_match_view(locale, m, titles) for m in matches]
        shown = {v["pathId"] for v in views}
        cards = [v["card"] for v in views] + [
            c for c in _existing_cards(request, str(spec.get("subject") or "")) if c.get("pathId") not in shown
        ]
        ctx: dict[str, Any] = {"existing": cards, "existing_matches": views}
        if views:
            items = []
            for v in views:
                line = f"{_isolate(v['title'])}: {v['reason_text']}"
                if v["prerequisites_text"]:
                    line += f" ({v['prerequisites_text']})"
                items.append(line)
            ctx["flash_ok"] = t(locale, "builder_match_found", count=len(views)) + " " + " · ".join(items)
        return ctx

    @app.get("/add-path/existing", response_class=HTMLResponse)
    def add_path_existing(request: Request) -> HTMLResponse:
        learner = current_learner(request)
        if not learner:
            return login_redirect(request)
        sess = _session(learner)
        if not sess.get("spec"):
            return RedirectResponse("/add-path", status_code=303)
        return _render(request, "existing", sess, **_existing_ctx(request, learner, sess["spec"]))

    # --- step 3: outline ---
    @app.post("/add-path/outline", response_model=None)
    def add_path_outline_generate(request: Request):
        learner = current_learner(request)
        if not learner:
            return login_redirect(request)
        sess = _session(learner)
        if not sess.get("spec"):
            return RedirectResponse("/add-path", status_code=303)
        locale = locale_of(request)
        spec = GoalSpec.model_validate(sess["spec"])
        existing_ctx = _existing_ctx(request, learner, sess["spec"])
        # Matches and same-subject paths are the ones the outline may name as prerequisites.
        existing = [{"pathId": c.get("pathId"), "title": c.get("title")} for c in existing_ctx["existing"]]
        try:
            outline = _generator(sess.get("mode") or "demo").outline(spec, existing_paths=existing)
        except GenerationError as exc:
            existing_ctx.pop("flash_ok", None)
            return _render(request, "existing", sess, **existing_ctx, error=_gen_error_text(locale, exc))
        sess["outline"] = outline.model_dump(mode="json")
        sess.pop("pathId", None)
        sess.pop("versionId", None)
        return RedirectResponse("/add-path/outline", status_code=303)

    @app.get("/add-path/outline", response_class=HTMLResponse)
    def add_path_outline(request: Request) -> HTMLResponse:
        learner = current_learner(request)
        if not learner:
            return login_redirect(request)
        sess = _session(learner)
        if not sess.get("outline"):
            return RedirectResponse("/add-path/existing" if sess.get("spec") else "/add-path", status_code=303)
        outline = PathOutline.model_validate(sess["outline"])
        return _render(request, "outline", sess, outline=outline)

    @app.post("/add-path/outline/approve", response_model=None)
    async def add_path_outline_approve(request: Request):
        learner = current_learner(request)
        if not learner:
            return login_redirect(request)
        sess = _session(learner)
        if not sess.get("outline") or not sess.get("spec"):
            return RedirectResponse("/add-path", status_code=303)
        locale = locale_of(request)
        form = dict((await request.form()).items())
        outline = PathOutline.model_validate(sess["outline"])
        try:
            edited = apply_outline_edits(outline, form)
        except ValidationError:
            return _render(request, "outline", sess, outline=outline, error=t(locale, "builder_err_outline_edit"))
        sess["outline"] = edited.model_dump(mode="json")
        spec = GoalSpec.model_validate(sess["spec"])
        mode = sess.get("mode") or "demo"
        generator = _generator(mode)
        try:
            pid, vid = builder.start_draft(
                actor_id=learner["userId"],
                spec=spec,
                outline=edited,
                generator_name=generator.name,
                demo=bool(generator.is_demo),
            )
        except GenerationError as exc:
            return _render(request, "outline", sess, outline=edited, error=_gen_error_text(locale, exc))
        sess["pathId"], sess["versionId"] = pid, vid
        return RedirectResponse("/add-path/build?auto=1", status_code=303)

    @app.get("/add-path/resume/{path_id}/{version_id}", response_model=None)
    def add_path_resume(request: Request, path_id: str, version_id: str):
        learner = current_learner(request)
        if not learner:
            return login_redirect(request)
        sess = _session(learner)
        probe = {"pathId": path_id, "versionId": version_id}
        raw = _owned_doc(learner, probe)
        if raw is None:
            return RedirectResponse("/add-path", status_code=303)
        build = raw["agentBuild"]
        sess.clear()
        sess.update(
            {
                "spec": build["spec"],
                "mode": build.get("mode") or "demo",
                "outline": build["outline"],
                "pathId": path_id,
                "versionId": version_id,
            }
        )
        return RedirectResponse("/add-path/build", status_code=303)

    # --- step 4: build (one model call per topic) ---
    def _build_view(raw: dict[str, Any]) -> dict[str, Any]:
        build = raw["agentBuild"]
        outline = PathOutline.model_validate(build["outline"])
        rows = []
        for i, topic in enumerate(outline.topics):
            st = build["topicStatus"][i]
            rows.append(
                {
                    "index": i,
                    "title": topic.title,
                    "emoji": topic.emoji or "📍",
                    "stages": len(topic.stages),
                    "status": st.get("status") or "pending",
                    "error": st.get("error"),
                    "detail": st.get("detail") or "",
                }
            )
        done = sum(1 for r in rows if r["status"] == "done")
        return {
            "rows": rows,
            "done": done,
            "total": len(rows),
            "pct": int(round(100 * done / len(rows))) if rows else 0,
            "has_pending": any(r["status"] == "pending" for r in rows),
            "has_failed": any(r["status"] == "failed" for r in rows),
        }

    @app.get("/add-path/build", response_class=HTMLResponse)
    def add_path_build(request: Request, auto: str | None = None) -> HTMLResponse:
        learner = current_learner(request)
        if not learner:
            return login_redirect(request)
        sess = _session(learner)
        raw = _owned_doc(learner, sess)
        if raw is None:
            return RedirectResponse("/add-path", status_code=303)
        view = _build_view(raw)
        return _render(
            request, "build", sess,
            doc=raw,
            build=view,
            auto=bool(auto) and view["has_pending"] and not view["has_failed"],
            report=check_path_completeness(raw),
        )

    def _fill(request: Request, topic_index: int | None, *, all_pending: bool = False):
        learner = current_learner(request)
        if not learner:
            return login_redirect(request), None
        sess = _session(learner)
        raw = _owned_doc(learner, sess)
        if raw is None:
            return RedirectResponse("/add-path", status_code=303), None
        generator = _generator(raw["agentBuild"].get("mode") or "demo")
        kwargs = dict(actor_id=learner["userId"], path_id=sess["pathId"], version_id=sess["versionId"])
        if all_pending:
            results = builder.run_pending(generator, **kwargs)
        else:
            if topic_index is None:
                topic_index = builder.next_pending(sess["pathId"], sess["versionId"])
            if topic_index is None:
                return RedirectResponse("/add-path/review", status_code=303), None
            results = [builder.fill_topic(generator, topic_index=topic_index, **kwargs)]
        return None, results

    @app.post("/add-path/build/next", response_model=None)
    def add_path_build_next(request: Request):
        early, results = _fill(request, None)
        if early is not None:
            return early
        ok = all(r.ok for r in results)
        return RedirectResponse("/add-path/build?auto=1" if ok else "/add-path/build", status_code=303)

    @app.post("/add-path/build/all", response_model=None)
    def add_path_build_all(request: Request):
        early, results = _fill(request, None, all_pending=True)
        if early is not None:
            return early
        if results and all(r.ok for r in results):
            return RedirectResponse("/add-path/review", status_code=303)
        return RedirectResponse("/add-path/build", status_code=303)

    @app.post("/add-path/build/topic/{topic_index}", response_model=None)
    def add_path_build_topic(request: Request, topic_index: int):
        early, _results = _fill(request, topic_index)
        if early is not None:
            return early
        return RedirectResponse("/add-path/build", status_code=303)

    # --- step 5: review and publish ---
    @app.get("/add-path/review", response_class=HTMLResponse)
    def add_path_review(
        request: Request, published: str | None = None, blocked: str | None = None
    ) -> HTMLResponse:
        learner = current_learner(request)
        if not learner:
            return login_redirect(request)
        sess = _session(learner)
        raw = _owned_doc(learner, sess)
        if raw is None:
            return RedirectResponse("/add-path", status_code=303)
        locale = locale_of(request)
        outline = PathOutline.model_validate(raw["agentBuild"]["outline"])
        blocks = {b["blockId"]: b for b in raw.get("blocks") or []}
        node_to_block = raw.get("nodeToBlock") or {}
        topics_view = []
        for topic in raw.get("topics") or []:
            stage_rows = []
            for nid in topic.get("node_ids") or []:
                b = blocks.get(node_to_block.get(nid))
                if not b:
                    continue
                content = b.get("content") or {}
                kids = content.get("kids") or {}
                stage_rows.append(
                    {
                        "title": b.get("title"),
                        "type": content.get("stageType"),
                        "channel": content.get("channel"),
                        "objective": b.get("learningObjective"),
                        "body": kids.get("body_ui") or "",
                        "choices": kids.get("choices") or [],
                        "correct": kids.get("correct"),
                        "kind": kids.get("kind") or "understanding",
                        "review_topic_ids": kids.get("review_topic_ids") or [],
                    }
                )
            titles = topic.get("titles") or {}
            topics_view.append(
                {
                    "id": topic.get("id"),
                    "title": next((v for v in titles.values() if v), topic.get("id")),
                    "emoji": topic.get("emoji"),
                    "requires": topic.get("requires") or [],
                    "stages": stage_rows,
                }
            )
        versions = store.list_versions(raw["pathId"])
        published_versions = [v for v in versions if v["status"] == "published"]
        problems = _live_problems(request, sess, raw)
        blocking = [p for p in problems if p["severity"] == "error"]
        publish_blocked = bool(blocked) and bool(blocking) and raw.get("status") != "published"
        error = ""
        if publish_blocked:
            # One list only (the blocking problems), capped; autoescaped by the template.
            error = t(locale, "builder_publish_blocked", count=len(blocking)) + " " + _capped(
                locale, [p["message"] for p in blocking], sep=" · "
            )
        return _render(
            request, "review", sess,
            draft_problems=problems,
            publish_blocked=publish_blocked,
            error=error,
            doc=raw,
            outline=outline,
            topics_view=topics_view,
            report=check_path_completeness(raw),
            versions=versions,
            published_versions=published_versions,
            edge_counts={
                "sequence": sum(1 for e in raw.get("edges") or [] if e.get("relationship") == "sequence"),
                "prerequisite": sum(
                    1 for e in raw.get("edges") or [] if e.get("relationship") == "prerequisite"
                ),
            },
            flash_ok=t(locale, "builder_published_ok") if published else "",
        )

    @app.post("/add-path/publish", response_model=None)
    def add_path_publish(request: Request, by: str = Form("user")):
        learner = current_learner(request)
        if not learner:
            return login_redirect(request)
        sess = _session(learner)
        raw = _owned_doc(learner, sess)
        if raw is None:
            return RedirectResponse("/add-path", status_code=303)
        resp = builder.publish(
            actor_id=learner["userId"],
            path_id=sess["pathId"],
            version_id=sess["versionId"],
            by_agent=(by == "agent"),
        )
        if not resp.ok:
            if any(e.get("code") == PUBLISH_FORMAT_ERROR for e in resp.errors):
                return RedirectResponse("/add-path/review?blocked=1", status_code=303)
            return RedirectResponse("/add-path/review", status_code=303)
        return RedirectResponse("/add-path/review?published=1", status_code=303)

    @app.post("/add-path/feedback", response_model=None)
    def add_path_feedback(
        request: Request,
        comment: str = Form(""),
        topic: str = Form(""),
    ):
        learner = current_learner(request)
        if not learner:
            return login_redirect(request)
        sess = _session(learner)
        raw = _owned_doc(learner, sess)
        if raw is None or raw.get("status") != "published" or not comment.strip():
            return RedirectResponse("/add-path/review", status_code=303)
        topic_index = _to_int(topic, -1) if topic.strip() else -1
        resp = builder.submit_feedback(
            actor_id=learner["userId"],
            path_id=sess["pathId"],
            version_id=sess["versionId"],
            comment=comment,
            topic_index=topic_index if topic_index >= 0 else None,
        )
        if resp.ok and resp.versionId:
            sess["versionId"] = resp.versionId
        if topic_index >= 0:
            return RedirectResponse("/add-path/build?auto=1", status_code=303)
        return RedirectResponse("/add-path/review", status_code=303)

    # --- optional connection test (no provider key is read or sent) ---
    @app.post("/add-path/check-gateway", response_model=None)
    def add_path_check_gateway(request: Request):
        learner = current_learner(request)
        if not learner:
            return login_redirect(request)
        sess = _session(learner)
        locale = locale_of(request)
        drafts = list_user_agent_drafts(store, learner["userId"])
        try:
            call_grok_chat([{"role": "user", "content": "Reply with the single word ok."}])
        except GatewayNotConfigured:
            return _render(request, "goal", sess, drafts=drafts, error=t(locale, "err_gateway_not_configured"))
        except GatewayRequestError:
            return _render(request, "goal", sess, drafts=drafts, error=t(locale, "err_gateway_request"))
        sid = request.cookies.get(COOKIE_AUTHOR_SID) or uuid.uuid4().hex
        app.state.author_gateway_ok[sid] = True
        resp = RedirectResponse("/add-path", status_code=303)
        # Opaque session id only. Never a provider key.
        resp.set_cookie(COOKIE_AUTHOR_SID, sid, httponly=True, samesite="lax", max_age=3600)
        return resp
