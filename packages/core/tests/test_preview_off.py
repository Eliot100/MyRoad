"""MYROAD_UI_PREVIEW sample data is off unless the env var is set to 1."""
from myroad_core.ui import tv_home


def test_preview_off_by_default(monkeypatch):
    monkeypatch.delenv("MYROAD_UI_PREVIEW", raising=False)
    assert tv_home.preview_enabled() is False
    monkeypatch.setenv("MYROAD_UI_PREVIEW", "0")
    assert tv_home.preview_enabled() is False
    monkeypatch.setenv("MYROAD_UI_PREVIEW", "1")
    assert tv_home.preview_enabled() is True
