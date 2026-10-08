from __future__ import annotations

from pathlib import Path

import pytest

from myroad_core.seed import find_repo_freeze_dir
from myroad_core.store import PathStore


@pytest.fixture(autouse=True)
def _http_test_client_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    """The test client talks plain http://testserver, which drops Secure cookies.

    Production default is Secure; tests that check the flag unset this.
    """
    monkeypatch.setenv("MYROAD_DEV_INSECURE_COOKIES", "1")


@pytest.fixture
def store() -> PathStore:
    s = PathStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def freeze_dir() -> Path:
    # packages/core/tests -> repo root
    return find_repo_freeze_dir(Path(__file__).resolve())
