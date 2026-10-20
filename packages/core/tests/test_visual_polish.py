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


def test_demo_accent_passes_aa_with_white_text():
    accent = re.search(r"body\.tone-demo\s*\{[^}]*--accent:\s*(#[0-9a-fA-F]{6})", CSS).group(1)
    assert contrast(accent, "#ffffff") >= 4.5


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
