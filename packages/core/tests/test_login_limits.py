"""Issues #49 and #50: 8-digit codes, per-email and per-IP send/verify limits.

- codes are 8 digits (login and email change);
- an email + IP that signed in before is trusted: per-email limits never apply
  to it, so an attacker on other IPs cannot stop the real user's code send nor
  lock their correct code;
- the rotating-IP guess budget per email is EMAIL_FAILURE_BUDGET (30) per day;
- over the per-email caps nothing is dropped silently: a CAPTCHA (optional)
  lets the user through, else they are told to wait.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest

from myroad_core.auth import login_codes as lc
from myroad_core.auth.login_codes import (
    CODE_DIGITS,
    EMAIL_FAILURE_BUDGET,
    IP_FAILURE_BUDGET,
    SEND_LIMITS,
    TRUST_DAYS,
)
from myroad_core.store import PathStore

pytest.importorskip("fastapi")
from auth_helpers import login_with_code, request_login_code  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from myroad_core.auth.email_change import EMAIL_CHANGE_COOKIE  # noqa: E402
from myroad_core.ui.app import create_learner_app  # noqa: E402

VICTIM = "victim@example.com"


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 10**8:08d}"


def _user(store: PathStore, email: str = VICTIM) -> str:
    return store.register_or_login(email=email, first_name="V", last_name="I")["userId"]


def _sign_in(store: PathStore, email: str, ip: str, now: datetime | None = None) -> None:
    cid, code = store.start_login_challenge(email=email, client_ip=ip, now=now)
    store.verify_login_challenge(cid, code, client_ip=ip, now=now)


def _burn_budget(store: PathStore, email: str, now: datetime | None = None, *, purpose_login: bool = True) -> int:
    """Rotating-IP attacker: one wrong guess per fresh IP until refused. Returns hashed guesses."""
    hashed = 0
    for i in range(EMAIL_FAILURE_BUDGET + 20):
        ip = f"10.66.{i // 250}.{i % 250}"
        cid, code = store.start_login_challenge(email=email, client_ip=ip, now=now)
        try:
            store.verify_login_challenge(cid, _wrong(code), client_ip=ip, now=now)
        except ValueError as exc:
            if str(exc) == "code_wrong":
                hashed += 1
            else:
                assert str(exc) == "account_limited"
    return hashed


# ---------- 8-digit codes ----------

def test_codes_are_eight_digits_for_login_and_email_change(store: PathStore) -> None:
    assert CODE_DIGITS == 8
    uid = _user(store)
    req = store.request_login(email=VICTIM, client_ip="1.1.1.1")
    assert req.kind == "code" and len(req.code) == 8 and req.code.isdigit()
    change = store.start_email_change(uid, "new@example.com", client_ip="1.1.1.1")
    assert len(change.current_code) == 8 and len(change.new_code) == 8
    # A 6-digit prefix of the right code is just wrong
    with pytest.raises(ValueError, match="code_wrong"):
        store.verify_login_challenge(req.challenge_id, req.code[:6], client_ip="1.1.1.1")
    assert store.verify_login_challenge(req.challenge_id, req.code, client_ip="1.1.1.1")


# ---------- verify limits ----------

def test_rotating_ip_guess_budget_is_30_per_email_per_day(store: PathStore) -> None:
    _user(store)
    t = datetime.now(timezone.utc)
    assert _burn_budget(store, VICTIM, t) == EMAIL_FAILURE_BUDGET == 30
    assert store._email_failures(VICTIM, t, untrusted_only=True) == 30
    # A fresh IP is refused before any attempt is used or any hash is computed
    cid, code = store.start_login_challenge(email=VICTIM, client_ip="10.99.0.1", now=t)
    with pytest.raises(ValueError, match="account_limited"):
        store.verify_login_challenge(cid, code, client_ip="10.99.0.1", now=t)
    row = store._conn.execute("SELECT attempts FROM login_codes WHERE challenge_id = ?", (cid,)).fetchone()
    assert row[0] == 0
    # 24 hours later the budget is back
    later = t + timedelta(hours=24, minutes=1)
    cid, code = store.start_login_challenge(email=VICTIM, client_ip="10.99.0.1", now=later)
    with pytest.raises(ValueError, match="code_wrong"):
        store.verify_login_challenge(cid, _wrong(code), client_ip="10.99.0.1", now=later)


def test_attacker_on_other_ips_cannot_lock_the_trusted_users_correct_code(store: PathStore) -> None:
    _user(store)
    t = datetime.now(timezone.utc)
    _sign_in(store, VICTIM, "1.2.3.4", t)  # signed in from here before: trusted
    # The real user asks for a code, then the attack starts
    cid, code = store.start_login_challenge(email=VICTIM, client_ip="1.2.3.4", now=t)
    _burn_budget(store, VICTIM, t)
    assert store.captcha_required_for(cid, "1.2.3.4", t) is False
    assert store.captcha_required_for(cid, "10.99.0.1", t) is True
    learner = store.verify_login_challenge(cid, code, client_ip="1.2.3.4", now=t)
    assert learner["email"] == VICTIM


def test_codes_requested_from_other_ips_do_not_cancel_the_users_code(store: PathStore) -> None:
    _user(store)
    cid, code = store.start_login_challenge(email=VICTIM, client_ip="1.2.3.4")
    for i in range(10):
        store.start_login_challenge(email=VICTIM, client_ip=f"10.70.0.{i}")
    assert store.verify_login_challenge(cid, code, client_ip="1.2.3.4")


def test_new_device_after_attack_gets_through_with_captcha(store: PathStore) -> None:
    _user(store)
    t = datetime.now(timezone.utc)
    _burn_budget(store, VICTIM, t)
    cid, code = store.start_login_challenge(email=VICTIM, client_ip="5.5.5.5", now=t)
    with pytest.raises(ValueError, match="account_limited"):
        store.verify_login_challenge(cid, code, client_ip="5.5.5.5", now=t)
    assert store.verify_login_challenge(cid, code, client_ip="5.5.5.5", now=t, captcha_ok=True)
    # Now trusted: the next sign-in from that IP needs nothing extra
    assert store._is_trusted(VICTIM, "5.5.5.5", t)
    cid, code = store.start_login_challenge(email=VICTIM, client_ip="5.5.5.5", now=t)
    assert store.verify_login_challenge(cid, code, client_ip="5.5.5.5", now=t)


def test_per_ip_failure_budget_across_emails(store: PathStore) -> None:
    t = datetime.now(timezone.utc)
    results = []
    for i in range(IP_FAILURE_BUDGET + 5):
        email = f"spray{i}@example.com"
        cid, code = store.start_login_challenge(email=email, first_name="S", last_name="P", client_ip="7.7.7.7", now=t)
        try:
            store.verify_login_challenge(cid, _wrong(code), client_ip="7.7.7.7", now=t)
        except ValueError as exc:
            results.append(str(exc))
    assert results[:IP_FAILURE_BUDGET] == ["code_wrong"] * IP_FAILURE_BUDGET
    assert set(results[IP_FAILURE_BUDGET:]) == {"code_slow_down"}
    # Another IP is unaffected
    cid, code = store.start_login_challenge(email="spray0@example.com", first_name="S", last_name="P",
                                            client_ip="7.7.7.8", now=t)
    assert store.verify_login_challenge(cid, code, client_ip="7.7.7.8", now=t)


def test_parallel_untrusted_guesses_never_exceed_the_email_budget(tmp_path) -> None:
    store = PathStore(str(tmp_path / "budget.db"))
    try:
        _user(store)
        now = lc._ts(datetime.now(timezone.utc))
        for i in range(EMAIL_FAILURE_BUDGET - 4):  # 4 checks left
            store._conn.execute(
                "INSERT INTO login_failures (email, client_ip, failed_at, trusted) VALUES (?,?,?,0)",
                (VICTIM, f"10.1.0.{i}", now),
            )
        store._conn.commit()
        issued = [store.start_login_challenge(email=VICTIM, client_ip="10.2.0.1") for _ in range(3)]
        results: list[str] = []
        barrier = threading.Barrier(15)

        def guess(n: int) -> None:
            cid, code = issued[n % 3]
            barrier.wait()
            try:
                store.verify_login_challenge(cid, _wrong(code), client_ip=f"10.3.0.{n}")
                results.append("ok")
            except ValueError as exc:
                results.append(str(exc))

        threads = [threading.Thread(target=guess, args=(n,)) for n in range(15)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert results.count("code_wrong") == 4
        assert results.count("account_limited") == 11
        assert store._email_failures(VICTIM, datetime.now(timezone.utc)) == EMAIL_FAILURE_BUDGET
    finally:
        store.close()


def test_trust_expires_and_unknown_ip_is_never_trusted(store: PathStore) -> None:
    _user(store)
    t = datetime.now(timezone.utc)
    _sign_in(store, VICTIM, "1.2.3.4", t)
    _sign_in(store, VICTIM, "unknown", t)
    assert store._is_trusted(VICTIM, "1.2.3.4", t + timedelta(days=TRUST_DAYS - 1))
    assert not store._is_trusted(VICTIM, "1.2.3.4", t + timedelta(days=TRUST_DAYS + 1))
    assert not store._is_trusted(VICTIM, "unknown", t)


# ---------- send limits ----------

def test_attacker_on_other_ips_cannot_stop_the_real_users_code_send(store: PathStore) -> None:
    _user(store)
    t = datetime.now(timezone.utc)
    _sign_in(store, VICTIM, "1.2.3.4", t)
    kinds = [store.request_login(email=VICTIM, client_ip=f"10.77.0.{i}", now=t).kind for i in range(60)]
    assert kinds.count("code") == SEND_LIMITS["email"]
    assert set(kinds[SEND_LIMITS["email"]:]) == {"email_limited"}
    # The real user's code still goes out from their usual IP
    req = store.request_login(email=VICTIM, client_ip="1.2.3.4", now=t)
    assert req.kind == "code" and len(req.code) == 8
    # ... and their own email+IP bucket was not touched by the attacker
    for _ in range(SEND_LIMITS["email_ip"] - 2):
        assert store.request_login(email=VICTIM, client_ip="1.2.3.4", now=t).kind == "code"


def test_per_email_cap_asks_instead_of_dropping(store: PathStore) -> None:
    t = datetime.now(timezone.utc)
    for i in range(SEND_LIMITS["email"]):
        store.request_login(email="cap@example.com", client_ip=f"10.8.0.{i}", now=t)
    # Same answer for known and unknown emails
    assert store.request_login(email="cap@example.com", client_ip="10.9.0.1", now=t).kind == "email_limited"
    assert store.send_captcha_required("cap@example.com", "10.9.0.1", t)
    assert store.request_login(email="cap@example.com", client_ip="10.9.0.1", now=t, captcha_ok=True).kind == "no_account"
    _user(store, "cap@example.com")
    req = store.request_login(email="cap@example.com", client_ip="10.9.0.2", now=t, captcha_ok=True)
    assert req.kind == "code"


def test_trusted_pair_still_has_its_own_ip_buckets(store: PathStore) -> None:
    _user(store)
    t = datetime.now(timezone.utc)
    _sign_in(store, VICTIM, "1.2.3.4", t)
    kinds = [store.request_login(email=VICTIM, client_ip="1.2.3.4", now=t).kind
             for _ in range(SEND_LIMITS["email_ip"] + 1)]
    assert kinds[-1] == "rate_limited"
    assert store.request_login(email=VICTIM, client_ip="1.2.3.4", now=t, captcha_ok=True).kind == "rate_limited"


def test_every_new_send_path_hashes_once(store: PathStore, monkeypatch) -> None:
    calls = [0]
    real = lc.hash_code

    def counting(code: str) -> str:
        calls[0] += 1
        return real(code)

    monkeypatch.setattr(lc, "hash_code", counting)
    t = datetime.now(timezone.utc)
    for i in range(SEND_LIMITS["email"]):
        store.request_login(email="h@example.com", client_ip=f"10.4.0.{i}", now=t)
    before = calls[0]
    assert store.request_login(email="h@example.com", client_ip="10.5.0.1", now=t).kind == "email_limited"
    assert calls[0] - before == 1


# ---------- email change ----------

def test_email_change_codes_follow_the_same_limits(store: PathStore) -> None:
    uid = _user(store)
    t = datetime.now(timezone.utc)
    _sign_in(store, VICTIM, "1.2.3.4", t)
    req = store.start_email_change(uid, "new@example.com", client_ip="1.2.3.4", now=t)
    # Attacker burns the budget of the CURRENT address from rotating IPs
    _burn_budget(store, VICTIM, t)
    # From a new device the check is refused (needs CAPTCHA), from the trusted IP ...
    with pytest.raises(ValueError, match="account_limited"):
        store.confirm_email_change(uid, req.change_id, current_code=req.current_code, new_code=req.new_code,
                                   client_ip="5.5.5.5", now=t)
    # ... the trusted pair is not limited for the current address; the new address is
    # untrusted but its own budget is untouched, so the change goes through
    out = store.confirm_email_change(uid, req.change_id, current_code=req.current_code, new_code=req.new_code,
                                     client_ip="1.2.3.4", now=t)
    assert out["new_email"] == "new@example.com"
    assert store._is_trusted("new@example.com", "1.2.3.4", t)


def test_email_change_new_device_with_captcha(store: PathStore) -> None:
    uid = _user(store)
    t = datetime.now(timezone.utc)
    req = store.start_email_change(uid, "new@example.com", client_ip="5.5.5.5", now=t)
    _burn_budget(store, VICTIM, t)
    with pytest.raises(ValueError, match="account_limited"):
        store.confirm_email_change(uid, req.change_id, current_code=req.current_code, new_code=req.new_code,
                                   client_ip="5.5.5.5", now=t)
    out = store.confirm_email_change(uid, req.change_id, current_code=req.current_code, new_code=req.new_code,
                                     client_ip="5.5.5.5", now=t, captcha_ok=True)
    assert out["new_email"] == "new@example.com"


def test_email_change_send_over_cap_is_email_limited_not_dropped(store: PathStore) -> None:
    uid = _user(store)
    t = datetime.now(timezone.utc)
    for i in range(SEND_LIMITS["email"]):
        store.request_login(email="target@example.com", client_ip=f"10.6.0.{i}", now=t)
    assert store.start_email_change(uid, "target@example.com", client_ip="5.5.5.5", now=t).kind == "email_limited"
    ok = store.start_email_change(uid, "target@example.com", client_ip="5.5.5.5", now=t, captcha_ok=True)
    assert ok.kind == "codes" and len(ok.new_code) == 8


# ---------- HTTP ----------

@pytest.fixture
def ui(tmp_path, monkeypatch):
    monkeypatch.delenv("MYROAD_SMTP_HOST", raising=False)
    monkeypatch.delenv("MYROAD_CAPTCHA_PROVIDER", raising=False)
    store = PathStore(str(tmp_path / "limits.db"))
    app = create_learner_app(store=store, seed=False, seed_content=False)
    app.state.login_notice_sender = lambda email: None
    with TestClient(app) as c:
        c.cookies.set("myroad_locale", "en")
        yield c, store
    store.close()


def _with_captcha(c) -> None:
    c.app.state.captcha_verifier = lambda token, ip: token == "good-token"
    c.app.state.captcha_site_key = "site-key-test"


def _fill_email_cap(store: PathStore, email: str) -> None:
    for i in range(SEND_LIMITS["email"]):
        store.request_login(email=email, client_ip=f"10.20.0.{i}")


def test_verify_page_asks_for_eight_digits(ui) -> None:
    c, _ = ui
    request_login_code(c, {"email": "p@example.com", "first_name": "P", "last_name": "Q", "mode": "register"})
    page = c.get("/login/verify?email=p@example.com").text
    assert 'pattern="[0-9]{8}"' in page and 'maxlength="8"' in page and "8-digit" in page


def test_http_send_over_cap_without_captcha_says_wait(ui) -> None:
    c, store = ui
    _user(store)
    _fill_email_cap(store, VICTIM)
    _fill_email_cap(store, "nobody@example.com")
    for email in (VICTIM, "nobody@example.com"):
        resp, outbox = request_login_code(c, {"email": email})
        assert outbox == []
        assert "error=too_many_codes" in resp.headers["location"]
    page = c.get(resp.headers["location"]).text
    assert "device you used before" in page and "cf-turnstile" not in page


def test_http_send_over_cap_with_captcha_sends_after_solving(ui) -> None:
    c, store = ui
    _with_captcha(c)
    _user(store)
    _fill_email_cap(store, VICTIM)
    resp, outbox = request_login_code(c, {"email": VICTIM})
    assert outbox == [] and "error=captcha_required" in resp.headers["location"]
    page = c.get(resp.headers["location"]).text
    assert 'class="cf-turnstile"' in page and "site-key-test" in page
    resp, outbox = request_login_code(c, {"email": VICTIM, "captcha_token": "bad"})
    assert outbox == []
    resp, outbox = request_login_code(c, {"email": VICTIM, "captcha_token": "good-token"})
    assert resp.headers["location"].startswith("/login/verify") and len(outbox[-1][1]) == 8


def test_http_trusted_device_is_not_asked(ui) -> None:
    c, store = ui
    _with_captcha(c)
    login_with_code(c, {"email": VICTIM, "first_name": "V", "last_name": "I", "mode": "register"})
    _fill_email_cap(store, VICTIM)
    resp, outbox = request_login_code(c, {"email": VICTIM})
    assert resp.headers["location"].startswith("/login/verify") and outbox


def test_http_verify_after_budget_burn(ui) -> None:
    c, store = ui
    _user(store)
    resp, outbox = request_login_code(c, {"email": VICTIM})
    code = outbox[-1][1]
    _burn_budget(store, VICTIM)
    # No CAPTCHA configured: an explicit message, the code stays usable later
    r = c.post("/login/verify", data={"code": code, "next": "/"}, follow_redirects=False)
    assert "error=account_limited" in r.headers["location"]
    assert "Too many wrong codes" in c.get(r.headers["location"]).text
    # With a CAPTCHA: asked for it, then the correct code signs in
    _with_captcha(c)
    r = c.post("/login/verify", data={"code": code, "next": "/"}, follow_redirects=False)
    assert "error=captcha_required" in r.headers["location"]
    r = c.post("/login/verify", data={"code": code, "next": "/", "captcha_token": "good-token"},
               follow_redirects=False)
    assert r.headers["location"] == "/" and c.cookies.get("myroad_session")


def test_http_email_change_send_over_cap_with_captcha(ui) -> None:
    c, store = ui
    login_with_code(c, {"email": VICTIM, "first_name": "V", "last_name": "I", "mode": "register"})
    _with_captcha(c)
    sent: list = []
    c.app.state.email_change_sender = lambda kind, to, payload: sent.append((kind, to, payload))
    _fill_email_cap(store, "target@example.com")
    r = c.post("/settings/email", data={"new_email": "target@example.com"}, follow_redirects=False)
    assert "error=captcha_send" in r.headers["location"] and sent == []
    page = c.get(r.headers["location"]).text
    assert 'class="cf-turnstile"' in page and 'value="target@example.com"' in page
    r = c.post("/settings/email", data={"new_email": "target@example.com", "captcha_token": "good-token"},
               follow_redirects=False)
    assert r.headers["location"].startswith("/settings?pending_new=")
    assert c.cookies.get(EMAIL_CHANGE_COOKIE)
    kinds = {k for k, _, _ in sent}
    assert kinds == {"code_current", "code_new"}
    assert all(len(p) == 8 for k, _, p in sent)
    page = c.get("/settings").text
    assert page.count('pattern="[0-9]{8}"') == 2
