"""Visual-quality guards for the learner shell (2026-10 UI pass).

These read the shipped CSS directly, so a regression in layering, contrast
or tokens fails fast without a browser.
"""
from __future__ import annotations

import re
from pathlib import Path

_STATIC = Path(__file__).resolve().parents[1] / "src" / "myroad_core" / "ui" / "static"
CSS = (_STATIC / "platform.css").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert m, f"missing rule {selector}"
    return m.group(1)


def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    ch = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_map_connector_is_behind_stations_and_ignores_clicks():
    line = _rule(".topic-diagram::before")
    assert "pointer-events: none" in line
    assert "z-index: 0" in line
    station = _rule(".topic-station")
    assert "position: relative" in station and "z-index: 1" in station


def test_one_accent_passes_aa_in_light_and_dark():
    # Ink & teal shell: a single accent everywhere (no per-tone override), AA both ways.
    assert not re.search(r"body\.tone-demo\s*\{[^}]*--accent:", CSS)
    light = re.search(r":root\s*\{[^}]*--accent:\s*(#[0-9a-fA-F]{6})", CSS).group(1)
    on_light = re.search(r":root\s*\{[^}]*--on-accent:\s*(#[0-9a-fA-F]{6})", CSS).group(1)
    assert light.lower() == "#0f766e" and contrast(light, on_light) >= 4.5 and contrast(light, "#ffffff") >= 4.5
    dark_root = CSS[CSS.index("@media (prefers-color-scheme: dark)"):]
    dark = re.search(r"--accent:\s*(#[0-9a-fA-F]{6})", dark_root).group(1)
    on_dark = re.search(r"--on-accent:\s*(#[0-9a-fA-F]{6})", dark_root).group(1)
    bg_dark = re.search(r"--bg:\s*(#[0-9a-fA-F]{6})", dark_root).group(1)
    assert dark.lower() == "#5fd4c4" and contrast(dark, on_dark) >= 4.5 and contrast(dark, bg_dark) >= 4.5


def test_one_button_system_52px_radius_14():
    root = _root_block()
    assert "--btn-h: 52px" in root and "--btn-radius: 14px" in root
    assert re.search(r"button, \.primary, \.secondary, a\.link-btn \{[^}]*min-block-size: var\(--btn-h\)", CSS)


def _root_block() -> str:
    return re.search(r":root\s*\{([^}]*)\}", CSS).group(1)


def test_design_tokens_define_colour_spacing_and_type_scales():
    root = _root_block()
    for tok in ("--surface", "--surface-2", "--on-accent", "--tint-ok", "--tint-warn",
                "--space-1", "--space-4", "--text-sm", "--text-xl", "--radius-md"):
        assert re.search(re.escape(tok) + r":", root), tok


def test_components_use_tokens_not_raw_hex():
    body = CSS.split("* { box-sizing: border-box; }", 1)[1]
    # Theme-only blocks (dark mode) and the demo tone may set raw values.
    body = re.sub(r"@media \(prefers-color-scheme: dark\)\s*\{.*?\n\}\n", "", body, flags=re.S)
    leftovers = [
        line.strip() for line in body.splitlines()
        if re.search(r"#[0-9a-fA-F]{3,6}\b", line)
        and "tone-demo" not in line and "a11y-placeholder" not in line
        and "--accent:" not in line and "linear-gradient" not in line
    ]
    assert leftovers == []


def _dark_root() -> str:
    m = re.search(r"@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([^}]*)\}", CSS)
    assert m, "dark theme block missing"
    return m.group(1)


def _tok(block: str, name: str) -> str:
    return re.search(re.escape(name) + r":\s*(#[0-9a-fA-F]{6})", block).group(1)


def test_dark_theme_follows_system_and_declares_color_scheme():
    assert "color-scheme: light dark" in _root_block()
    _dark_root()


def test_dark_theme_text_pairs_pass_aa():
    d = _dark_root()
    pairs = [("--ink", "--bg"), ("--ink", "--card"), ("--muted", "--card"), ("--muted", "--bg"),
             ("--on-accent", "--accent"), ("--accent", "--card"), ("--ok-ink", "--tint-ok"),
             ("--warn-ink", "--tint-warn"), ("--agent-ink", "--tint-agent"), ("--ink", "--surface")]
    for fg, bg in pairs:
        assert contrast(_tok(d, fg), _tok(d, bg)) >= 4.5, (fg, bg)


def test_no_hard_coded_white_in_colour_mixes():
    assert ", white)" not in CSS


def test_every_learner_screen_has_one_main_landmark_and_skip_link():
    from pathlib import Path as _P
    tpl = _P(__file__).resolve().parents[1] / "src" / "myroad_core" / "ui" / "templates"
    for name in ("home.html", "map.html", "play.html", "settings.html", "login.html",
                 "accessibility.html", "stats.html"):
        html = (tpl / name).read_text(encoding="utf-8")
        assert html.count("<main") == 1, name
        assert 'id="main"' in html, name
        assert '<a class="skip-link" href="#main">' in html, name
        # Skip link is the first focusable thing in the body.
        assert html.index("skip-link") < html.index("<header") if "<header" in html else True


def test_skip_link_is_translated_in_every_locale():
    import json
    loc = Path(__file__).resolve().parents[1] / "locales"
    for code in ("he", "en", "ar"):
        assert json.loads((loc / f"{code}.json").read_text(encoding="utf-8"))["skip_to_main"].strip()


def _login_client():
    import os
    os.environ.setdefault("MYROAD_DEV_INSECURE_COOKIES", "1")
    from fastapi.testclient import TestClient
    from myroad_core.store import PathStore
    from myroad_core.ui.app import create_learner_app
    app = create_learner_app(store=PathStore(":memory:"), seed=False, seed_content=False)
    return TestClient(app, headers={"Origin": "http://testserver"})


def test_login_offers_language_switch_that_returns_to_login():
    c = _login_client()
    page = c.get("/login?mode=register").text
    assert 'class="auth-lang"' in page
    for code in ("he", "en", "ar"):
        assert f'name="locale" value="{code}"' in page
    assert 'name="next" value="/login?mode=register"' in page
    r = c.post("/locale", data={"locale": "en", "next": "/login?mode=register"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login?mode=register"
    en = c.get("/login?mode=register").text
    assert 'lang="en"' in en and 'dir="ltr"' in en
    assert 'value="en" lang="en" class="lang-btn active" aria-pressed="true"' in en


def test_login_footer_stacks_under_card():
    rule = _rule(".auth-screen")
    assert "flex-direction: column" in rule


def test_map_primary_action_sticks_to_bottom_on_phones():
    phone = CSS[CSS.index("@media (max-width: 480px)"):]
    rule = re.search(r"\.map-view \.map-actions\s*\{([^}]*)\}", phone).group(1)
    assert "position: sticky" in rule and "inset-block-end: 0" in rule
    assert "safe-area-inset-bottom" in rule
    assert "background: var(--card)" in rule  # opaque so stations scroll beneath it


def test_type_scale_drives_headings_and_heading_order_is_not_inverted():
    assert "body.platform :where(h1) { font-size: var(--text-xl); }" in CSS
    assert "body.platform :where(h2) { font-size: var(--text-lg); }" in CSS
    # Phones shrink via tokens, never below the next level down.
    phone = re.search(r":root \{ --text-xl: ([0-9.]+)rem; --text-lg: ([0-9.]+)rem;", CSS)
    assert phone and float(phone.group(1)) > float(phone.group(2)) > 1.05


def test_plain_links_inside_main_use_accent():
    assert "body.platform :where(main a:not([class])) { color: var(--accent);" in CSS


def test_step_player_marks_pending_answer_visually_and_for_assistive_tech():
    js = (_STATIC / "platform.js").read_text(encoding="utf-8")
    assert 'tile.setAttribute("data-pending", "")' in js
    assert '"htmx:beforeRequest"' in js and 'card.setAttribute("aria-busy", "true")' in js
    assert '"htmx:afterRequest"' in js and 'card.removeAttribute("aria-busy")' in js
    assert "form.htmx-request .choice-tile:not([data-pending]) { opacity: .55; }" in CSS
    assert ".choice-tile[data-pending] {" in CSS
    # The fade only animates when the learner has not asked for reduced motion.
    motion = CSS[CSS.index(".choice-tile[data-pending] {"):]
    assert motion.index("@media (prefers-reduced-motion: no-preference)") < motion.index("transition: opacity .15s")
