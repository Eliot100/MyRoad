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


@pytest.fixture(autouse=True)
def _test_client_sends_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Browsers send Origin on form POSTs; the UI refuses unsafe requests without it.

    Give every TestClient a same-origin Origin header by default, like a browser
    on the site. Tests of the check override or remove it.
    """
    from starlette.testclient import TestClient

    original = TestClient.__init__

    def init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        original(self, *args, **kwargs)
        self.headers.setdefault("Origin", str(self.base_url).rstrip("/"))

    monkeypatch.setattr(TestClient, "__init__", init)


@pytest.fixture
def store() -> PathStore:
    s = PathStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def freeze_dir() -> Path:
    # packages/core/tests -> repo root
    return find_repo_freeze_dir(Path(__file__).resolve())
