"""Learner action routes: submit, feedback→revise, gated publish."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import Form, Request
from fastapi.responses import HTMLResponse

from myroad_core.ui.answers import answers_match, grade_items, mastery_passed
from myroad_core.ui.polish import build_revise_change_set, build_version_diff

ACTOR_LEARNER = "user_learner_poc"
ACTOR_HUMAN = "user_owner_poc"
AGENT_UI = "agent_thin_ui_v0"


def register_learner_actions(
    app,
    *,
    tools,
    _session: Callable,
    _render: Callable,
    _load_doc: Callable,
    _block_body: Callable,
    _corr: Callable,
) -> None:
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
            # One-click feedback → reviseDraft: new draft only (never publishes).
            base_vid = sess["versionId"]
            summary = (proposed_change or comment or "thin-ui revise after learner feedback").strip()
            change_set = build_revise_change_set(
                base_version_id=base_vid,
                feedback_id=fb.data["feedbackId"],
                summary=summary,
            )
            rev = tools.revise_draft(
                actor_id=ACTOR_LEARNER,
                agent_id=AGENT_UI,
                correlation_id=_corr("revise"),
                path_id=sess["pathId"],
                base_version_id=base_vid,
                feedback_ids=[fb.data["feedbackId"]],
                change_set=change_set,
            )
            if rev.ok and rev.versionId:
                sess["version_diff"] = build_version_diff(
                    from_version_id=base_vid,
                    to_version_id=rev.versionId,
                    diff_ref=rev.diffRef,
                    summary=summary,
                )
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
            path_id=sess["versionId"],
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

