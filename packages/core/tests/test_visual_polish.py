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
