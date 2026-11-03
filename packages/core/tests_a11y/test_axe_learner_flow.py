"""axe-core over the core learner flow, 375/1280 px x light/dark (issue #61, decision 0008).

Each test brings the one shared page to a state, then scans it in 4 combos.
Fails on any WCAG 2.0/2.1 A/AA violation not listed in allowlist.json.
The tests run in file order and share one signed-in session.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from axe_playwright_python.sync_playwright import Axe

from conftest import login

HERE = Path(__file__).resolve().parent
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]
VIEWPORTS = [(375, 812), (1280, 900)]
THEMES = ["light", "dark"]
STEP_PATH = "/play/path_a11y_step_player"
PLACEMENT = "/play/path_english_bagrut5_00_placement"

_axe = Axe()
ALLOW = json.loads((HERE / "allowlist.json").read_text(encoding="utf-8"))["allow"]
FOUND: list[dict] = []  # every violation seen, written to a report for CI artifacts


def _allowed(state: str, rule: str, target: str) -> bool:
    return any(
        a["rule"] == rule and a["selector"] == target and a.get("state") in (None, "*", state)
        for a in ALLOW
    )


def scan(page, state: str) -> None:
    """Scan the current page in every viewport x theme; fail on new violations."""
    new: list[str] = []
    for width, height in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
        for theme in THEMES:
            page.emulate_media(color_scheme=theme, reduced_motion="reduce")
            page.wait_for_timeout(50)
            result = _axe.run(page, options={"runOnly": {"type": "tag", "values": TAGS}})
            for v in result.response["violations"]:
                for node in v["nodes"]:
                    target = " ".join(map(str, node["target"]))
                    FOUND.append({"state": state, "viewport": width, "theme": theme,
                                  "rule": v["id"], "impact": v.get("impact"), "selector": target,
                                  "summary": node.get("failureSummary", "")[:300]})
                    if not _allowed(state, v["id"], target):
                        new.append(f"[{state} {width}px {theme}] {v['id']} ({v.get('impact')}): {target}")
    assert not new, "New axe violations (fix, or allowlist with an issue link):\n" + "\n".join(sorted(set(new)))


@pytest.fixture(scope="session", autouse=True)
def _report():
    yield
    out = Path(__import__("os").environ.get("A11Y_REPORT", HERE / "a11y-report.json"))
    out.write_text(json.dumps(FOUND, ensure_ascii=False, indent=1), encoding="utf-8")


def _submit(page, action: str) -> None:
    page.locator(f"form[action='{action}'] [type=submit]").first.click()
    page.wait_for_load_state()


def test_login(page):
    page.goto("/login")
    scan(page, "login")


@pytest.mark.parametrize("url", ["/privacy", "/terms"])
def test_legal_signed_out(page, url):
    """#209: privacy notice and terms before sign in."""
    page.goto(url)
    scan(page, "legal" + url.replace("/", "_") + "_out")


def test_register_legal_links(page):
    page.goto("/login?mode=register")
    scan(page, "login_register")


def test_signed_in(page, server):
    login(page, server[1])
    assert "/login" not in page.url


def test_placement(page):
    page.goto(PLACEMENT)
    _submit(page, f"{PLACEMENT}/start")
    page.locator("#step-card").wait_for()
    scan(page, "placement")


def test_path_head(page):
    page.goto(STEP_PATH)
    page.locator(".path-head").first.wait_for()
    scan(page, "path-head")


def test_map_view(page):
    page.goto(STEP_PATH + "?view=map")
    scan(page, "map")


def test_path_head_session_card(page):
    """After starting, the head shows the engagement session card (.eng-head) when present."""
    page.goto(STEP_PATH)
    _submit(page, f"{STEP_PATH}/start")
    page.goto(STEP_PATH)
    scan(page, "path-head-session")


def test_step_hint_open(page):
    page.goto(STEP_PATH + "?view=learn")
    page.locator("details.step-hint summary").click()
    assert page.locator("details.step-hint[open]").count() == 1
    scan(page, "step-hint")


def test_step_wrong_choice_feedback(page):
    """A miss shows the right answer and the full worked solution, open, in the live region (#215)."""
    page.locator("button.choice-tile[value=a]").click()
    page.locator("#choice-feedback").wait_for()
    page.locator("#step-feedback .solution .solution-method").wait_for()
    assert page.locator("button.choice-tile.is-solution[value=b]").count() == 1
    scan(page, "step-feedback")


def test_step_done(page):
    page.locator("button.choice-tile[value=b]").click()
    page.locator("details.step-hint").wait_for(state="detached")
    scan(page, "step-done")


def test_week_strip_goal_set_open(page):
    """Path head week strip (#193) with the days goal disclosure and mastered skills open."""
    page.goto(STEP_PATH + "?view=map")
    page.locator(".week-strip").wait_for()
    page.locator("details.week-goal-set summary").click()
    skills = page.locator("details.goal-skills summary")
    if skills.count():
        skills.click()
    scan(page, "week-strip")


SESSION_PATH = "/play/path_a11y_session"  # two שלבים of one step each (decision 0010)


def test_stage_end(page):
    """Right answer that closes שלב 1: stage end line + choice, inside the step card (#191)."""
    page.goto(SESSION_PATH)
    _submit(page, f"{SESSION_PATH}/start")
    page.goto(SESSION_PATH + "?view=learn")
    page.locator("button.choice-tile[value=b]").click()
    page.locator(".stage-end").wait_for()
    scan(page, "stage-end")


def test_session_end(page):
    """The last step of the session: real numbers and the end actions, same card (#191)."""
    page.goto(SESSION_PATH + "?view=learn")
    page.locator("button.choice-tile[value=a]").click()
    page.locator(".session-end").wait_for()
    scan(page, "session-end")


MORE_PATH = "/play/path_a11y_session_more"  # seven one step שלבים: the session ends mid road


def test_session_end_continue_first(page):
    """Session end with more road left: continue is the filled button, now-you-can are actions (#215)."""
    page.goto(MORE_PATH)
    _submit(page, f"{MORE_PATH}/start")
    for _ in range(6):
        page.goto(MORE_PATH + "?view=learn")
        page.locator("button.choice-tile[value=a]").click()
        page.locator("#step-feedback.ok").wait_for()
        if page.locator(".session-end").count():
            break
    page.locator(".session-end").wait_for()
    assert page.locator(".session-actions .primary").count() == 1
    assert page.locator(".session-actions .primary.continue-step").count() == 1
    assert page.locator(".cando-action").count() >= 1
    scan(page, "session-end-continue")


def test_placement_result(page):
    """Per domain result above the road's first step (#212): no separate screen."""
    body = page.evaluate("""async () => {
      const r = await fetch('/api/placement/result', {method: 'POST', credentials: 'same-origin',
        headers: {'X-MyRoad-Request': '1', 'Content-Type': 'application/json'},
        body: JSON.stringify({answers: [{questionId: 'a11y_q1', correct: true}]})});
      return {status: r.status, json: await r.json()};
    }""")
    assert body["status"] == 200, body
    road = body["json"].get("recommended_road_id") or body["json"].get("gap")
    page.goto(f"/play/{road}?view=learn&from=placement")
    page.locator("#placement-result").wait_for()
    scan(page, "placement-result")


@pytest.mark.parametrize("url", ["/privacy", "/terms", "/settings"])
def test_legal_signed_in(page, url):
    """#209: the same pages (and the settings links) after sign in."""
    page.goto(url)
    scan(page, "legal" + url.replace("/", "_") + "_in")
