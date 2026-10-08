"""Verified email change, purpose-bound codes, CAPTCHA hook, uniform timing.

Cyber security re-review of #46/#47:
- email change needs a code from the CURRENT and the NEW address; the old
  address is notified; the new address is not claimable until verified;
- login codes and email-change codes are not interchangeable;
- one PBKDF2 hash on every sign-in request path (timing);
- pluggable CAPTCHA after repeated failures (off by default).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from myroad_core.auth import login_codes as lc
from myroad_core.auth.captcha import TurnstileVerifier, captcha_verifier_from_env
from myroad_core.auth.email_change import EMAIL_CHANGE_COOKIE
from myroad_core.store import PathStore

pytest.importorskip("fastapi")
from auth_helpers import login_with_code, request_login_code  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from myroad_core.ui.app import create_learner_app  # noqa: E402


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 10**6:06d}"


def _user(store: PathStore, email: str = "alice@example.com") -> str:
    return store.register_or_login(email=email, first_name="A", last_name="L")["userId"]


# ---------- store level ----------

def test_change_needs_both_codes_then_switches_and_revokes(store: PathStore) -> None:
    uid = _user(store)
    other_device = store.create_session(uid)
    login_cid, _ = store.start_login_challenge(email="alice@example.com")
    req = store.start_email_change(uid, "Alice.New@Example.com", client_ip="1.1.1.1")
    assert req.kind == "codes" and req.current_code and req.new_code
    assert (req.old_email, req.new_email) == ("alice@example.com", "alice.new@example.com")
    # Nothing changes before both codes check out
    assert store.get_learner(uid)["email"] == "alice@example.com"
    assert store.get_learner_by_email("alice.new@example.com") is None
    out = store.confirm_email_change(
        uid, req.change_id, current_code=req.current_code, new_code=req.new_code, client_ip="1.1.1.1"
    )
    assert out["old_email"] == "alice@example.com" and out["new_email"] == "alice.new@example.com"
    assert store.get_learner(uid)["email"] == "alice.new@example.com"
    assert store.get_session_user(other_device) is None  # every session revoked
    with pytest.raises(ValueError, match="code_used"):  # pending login codes for the old address are dead
        store.verify_login_challenge(login_cid, "000000")
    with pytest.raises(ValueError, match="code_used"):  # single use
        store.confirm_email_change(uid, req.change_id, current_code=req.current_code, new_code=req.new_code)


def test_attack_stolen_session_cannot_move_the_account(store: PathStore) -> None:
    """Attacker holds the victim's session and controls attacker@ (gets the NEW code),
    but never sees the code sent to the victim's CURRENT address."""
    uid = _user(store, "victim@example.com")
    req = store.start_email_change(uid, "attacker@example.com", client_ip="6.6.6.6")
    for _ in range(lc.MAX_VERIFY_ATTEMPTS):
        with pytest.raises(ValueError, match="code_wrong|code_locked"):
            store.confirm_email_change(
                uid, req.change_id, current_code=_wrong(req.current_code), new_code=req.new_code,
                client_ip="6.6.6.6",
            )
    # The current-address code is now locked; even the right pair fails
    with pytest.raises(ValueError, match="code_locked|code_slow_down"):
        store.confirm_email_change(
            uid, req.change_id, current_code=req.current_code, new_code=req.new_code, client_ip="6.6.6.7"
        )
    assert store.get_learner(uid)["email"] == "victim@example.com"
    assert store.get_learner_by_email("attacker@example.com") is None
    # The victim still signs in with their own address
    cid, code = store.start_login_challenge(email="victim@example.com")
    assert store.verify_login_challenge(cid, code, client_ip="1.2.3.4")["userId"] == uid


def test_attack_pointing_an_account_at_a_newcomers_address(store: PathStore) -> None:
    """Alice tries to set her email to unregistered newcomer@ so the newcomer
    would later sign in to Alice's account."""
    alice = _user(store, "alice@example.com")
    req = store.start_email_change(alice, "newcomer@example.com")
    # Alice has her current code but not the newcomer's code
    with pytest.raises(ValueError, match="code_wrong"):
        store.confirm_email_change(alice, req.change_id, current_code=req.current_code,
                                   new_code=_wrong(req.new_code))
    # The address is not reserved or claimed while pending
    assert store.get_learner_by_email("newcomer@example.com") is None
    # The newcomer registers normally and gets their OWN account
    cid, code = store.start_login_challenge(email="newcomer@example.com", first_name="N", last_name="C")
    newcomer = store.verify_login_challenge(cid, code)
    assert newcomer["userId"] != alice
    # Even with both right codes, Alice can no longer take the address
    with pytest.raises(ValueError, match="email_taken"):
        store.confirm_email_change(alice, req.change_id, current_code=req.current_code, new_code=req.new_code)
    assert store.get_learner(alice)["email"] == "alice@example.com"
    assert store.get_learner_by_email("newcomer@example.com")["userId"] == newcomer["userId"]


def test_address_with_an_account_gets_a_notice_not_a_code(store: PathStore) -> None:
    alice = _user(store, "alice@example.com")
    _user(store, "bob@example.com")
    req = store.start_email_change(alice, "bob@example.com")
    assert req.kind == "codes" and req.current_code and req.new_code is None
    with pytest.raises(ValueError):
        store.confirm_email_change(alice, req.change_id, current_code=req.current_code, new_code="123456")
    assert store.get_learner(alice)["email"] == "alice@example.com"


def test_login_and_email_change_codes_are_not_interchangeable(store: PathStore) -> None:
    uid = _user(store)
    req = store.start_email_change(uid, "alice2@example.com")
    ids = store.email_change_challenges(req.change_id)
    assert len(ids) == 2
    # An email-change challenge never signs anyone in
    for cid, code in zip(ids, (req.current_code, req.new_code)):
        for c in (req.current_code, req.new_code):
            with pytest.raises(ValueError, match="code_invalid"):
                store.verify_login_challenge(cid, c)
    # A login code for the current address is not accepted as the email-change code
    _, login_code = store.start_login_challenge(email="alice@example.com")
    if login_code != req.current_code:
        with pytest.raises(ValueError, match="code_wrong"):
            store.confirm_email_change(uid, req.change_id, current_code=login_code, new_code=req.new_code)
    # Another user's session cannot use this change
    bob = _user(store, "bob@example.com")
    with pytest.raises(ValueError, match="code_invalid"):
        store.confirm_email_change(bob, req.change_id, current_code=req.current_code, new_code=req.new_code)


def test_same_or_invalid_new_email_and_send_limits(store: PathStore) -> None:
    uid = _user(store)
    with pytest.raises(ValueError, match="email_same"):
        store.start_email_change(uid, "ALICE@example.com")
    with pytest.raises(ValueError, match="email_invalid"):
        store.start_email_change(uid, "nope")
    kinds = [store.start_email_change(uid, f"n{i}@example.com", client_ip="5.5.5.5").kind
             for i in range(lc.SEND_LIMITS["email_ip"] + 1)]
    assert kinds[-1] == "rate_limited" and kinds[:-1] == ["codes"] * lc.SEND_LIMITS["email_ip"]


def test_a_new_change_cancels_the_previous_one(store: PathStore) -> None:
    uid = _user(store)
    first = store.start_email_change(uid, "one@example.com")
    second = store.start_email_change(uid, "two@example.com")
    with pytest.raises(ValueError, match="code_used"):
        store.confirm_email_change(uid, first.change_id, current_code=first.current_code, new_code=first.new_code)
    store.confirm_email_change(uid, second.change_id, current_code=second.current_code, new_code=second.new_code)
    assert store.get_learner(uid)["email"] == "two@example.com"


# ---------- timing: one PBKDF2 hash on every path ----------

def _count_hashes(monkeypatch) -> list[int]:
    calls = [0]
    real = lc.hash_code

    def counting(code, **kw):
        calls[0] += 1
        return real(code, **kw)

    monkeypatch.setattr(lc, "hash_code", counting)
    monkeypatch.setattr("myroad_core.auth.email_change.hash_code", counting)
    return calls


def test_every_sign_in_request_path_hashes_exactly_once(store: PathStore, monkeypatch) -> None:
    _user(store, "known@example.com")
    calls = _count_hashes(monkeypatch)

    def run(**kw) -> tuple[str, int]:
        before = calls[0]
        kind = store.request_login(**kw).kind
        return kind, calls[0] - before

    assert run(email="known@example.com", client_ip="2.2.2.2") == ("code", 1)
    assert run(email="fresh@example.com", first_name="F", last_name="R", client_ip="2.2.2.2") == ("code", 1)
    assert run(email="unknown@example.com", client_ip="2.2.2.2") == ("no_account", 1)
    for _ in range(lc.SEND_LIMITS["email_ip"]):
        store.request_login(email="flood@example.com", client_ip="3.3.3.3")
    assert run(email="flood@example.com", client_ip="3.3.3.3") == ("rate_limited", 1)


def test_every_email_change_request_path_hashes_twice(store: PathStore, monkeypatch) -> None:
    uid = _user(store)
    _user(store, "bob@example.com")
    calls = _count_hashes(monkeypatch)
    for target, ip, kind in (("free@example.com", "4.4.4.4", "codes"), ("bob@example.com", "4.4.4.4", "codes")):
        before = calls[0]
        assert store.start_email_change(uid, target, client_ip=ip).kind == kind
        assert calls[0] - before == 2
    for i in range(lc.SEND_LIMITS["email"]):
        store.start_email_change(uid, f"x{i}@example.com", client_ip=f"9.9.9.{i}")
    before = calls[0]
    assert store.start_email_change(uid, "late@example.com", client_ip="4.4.4.5").kind == "rate_limited"
    assert calls[0] - before == 2


# ---------- CAPTCHA hook ----------

def test_captcha_is_off_by_default_and_env_configurable(monkeypatch) -> None:
    monkeypatch.delenv("MYROAD_CAPTCHA_PROVIDER", raising=False)
    assert captcha_verifier_from_env() is None
    monkeypatch.setenv("MYROAD_CAPTCHA_PROVIDER", "turnstile")
    monkeypatch.delenv("MYROAD_CAPTCHA_SECRET", raising=False)
    with pytest.raises(ValueError, match="MYROAD_CAPTCHA_SECRET"):
        captcha_verifier_from_env()
    monkeypatch.setenv("MYROAD_CAPTCHA_SECRET", "test-only-value")
    assert isinstance(captcha_verifier_from_env(), TurnstileVerifier)
    monkeypatch.setenv("MYROAD_CAPTCHA_PROVIDER", "mystery")
    with pytest.raises(ValueError):
        captcha_verifier_from_env()


def test_turnstile_fails_closed_on_network_error(monkeypatch) -> None:
    def boom(*a, **k):
        raise OSError("no network")

    monkeypatch.setattr("myroad_core.auth.captcha.urlopen", boom)
    v = TurnstileVerifier("test-only-value")
    assert v("tok", "1.2.3.4") is False
    assert v("", "1.2.3.4") is False


def test_captcha_threshold_per_ip_and_per_email(store: PathStore) -> None:
    _user(store, "cap@example.com")
    t = datetime.now(timezone.utc)
    cid, code = store.start_login_challenge(email="cap@example.com", now=t)
    assert not store.captcha_required_for(cid, "1.1.1.1", t)
    for _ in range(lc.CAPTCHA_AFTER_FAILURES):
        with pytest.raises(ValueError):
            store.verify_login_challenge(cid, _wrong(code), client_ip="1.1.1.1", now=t)
    assert store.captcha_required_for(cid, "1.1.1.1", t)
    assert not store.captcha_required_for(cid, "2.2.2.2", t)  # other IPs: not yet
    # Distributed guessing: enough failures for the email from many IPs -> CAPTCHA for everyone
    for i in range(lc.CAPTCHA_AFTER_EMAIL_FAILURES):
        c2, k2 = store.start_login_challenge(email="cap@example.com", now=t)
        with pytest.raises(ValueError):
            store.verify_login_challenge(c2, _wrong(k2), client_ip=f"10.0.{i}.1", now=t)
    assert store.captcha_required_for(cid, "2.2.2.2", t)


# ---------- HTTP ----------

@pytest.fixture
def ui(tmp_path, monkeypatch):
    monkeypatch.delenv("MYROAD_SMTP_HOST", raising=False)
    monkeypatch.delenv("MYROAD_CAPTCHA_PROVIDER", raising=False)
    store = PathStore(str(tmp_path / "chg.db"))
    app = create_learner_app(store=store, seed=False, seed_content=False)
    mail: list[tuple[str, str, str | None]] = []
    app.state.email_change_sender = lambda kind, to, payload: mail.append((kind, to, payload))
    with TestClient(app) as c:
        yield c, store, mail
    store.close()


def _signin(c, email: str = "alice@example.com") -> str:
    login_with_code(c, {"first_name": "A", "last_name": "L", "email": email, "next": "/settings"})
    return c.app.state.store.get_session_user(c.cookies.get("myroad_session"))


def _codes(mail, kind):
    return [(to, p) for k, to, p in mail if k == kind]


def test_http_verified_email_change(ui) -> None:
    c, store, mail = ui
    uid = _signin(c)
    other_device = store.create_session(uid)
    r = c.post("/settings/email", data={"new_email": "alice.new@example.com"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/settings?pending_new=")
    (cookie,) = [h for h in r.headers.get_list("set-cookie") if h.startswith(EMAIL_CHANGE_COOKIE + "=")]
    assert "httponly" in cookie.lower() and "path=/settings" in cookie.lower()
    [(to_cur, code_cur)] = _codes(mail, "code_current")
    [(to_new, code_new)] = _codes(mail, "code_new")
    assert (to_cur, to_new) == ("alice@example.com", "alice.new@example.com")
    page = c.get(r.headers["location"])
    assert 'action="/settings/email/verify"' in page.text and 'name="code_current"' in page.text
    assert code_cur not in page.text and code_new not in page.text
    assert store.get_learner(uid)["email"] == "alice@example.com"
    r = c.post("/settings/email/verify", data={"code_current": code_cur, "code_new": code_new},
               follow_redirects=False)
    assert r.status_code == 303 and "email_changed=1" in r.headers["location"]
    assert store.get_learner(uid)["email"] == "alice.new@example.com"
    assert _codes(mail, "changed_notice") == [("alice@example.com", "alice.new@example.com")]
    assert store.get_session_user(other_device) is None
    assert store.get_session_user(c.cookies.get("myroad_session")) == uid  # fresh session here
    # Sign in later with the new address reaches the same account
    c.cookies.clear()
    login_with_code(c, {"email": "alice.new@example.com", "next": "/settings"})
    assert store.get_session_user(c.cookies.get("myroad_session")) == uid


def test_http_stolen_session_cannot_complete(ui) -> None:
    c, store, mail = ui
    uid = _signin(c, "victim@example.com")
    c.post("/settings/email", data={"new_email": "attacker@example.com"})
    [(_, code_new)] = _codes(mail, "code_new")  # the attacker controls this inbox
    [(victim_inbox, _)] = _codes(mail, "code_current")
    assert victim_inbox == "victim@example.com"  # the victim is alerted with the other code
    r = c.post("/settings/email/verify", data={"code_current": "000000", "code_new": code_new},
               follow_redirects=False)
    assert "error=code_wrong" in r.headers["location"] or "error=code_locked" in r.headers["location"]
    assert store.get_learner(uid)["email"] == "victim@example.com"
    assert store.get_learner_by_email("attacker@example.com") is None


def test_http_profile_form_still_refuses_a_direct_email_edit(ui) -> None:
    c, store, _ = ui
    uid = _signin(c)
    r = c.post("/settings", data={"first_name": "A", "last_name": "L", "email": "x@example.com"},
               follow_redirects=False)
    assert "error=email_change_disabled" in r.headers["location"]
    assert store.get_learner(uid)["email"] == "alice@example.com"


def test_http_taken_and_free_addresses_look_the_same(ui) -> None:
    c, store, mail = ui
    store.register_or_login(email="bob@example.com", first_name="B", last_name="O")
    _signin(c)
    free = c.post("/settings/email", data={"new_email": "free@example.com"}, follow_redirects=False)
    taken = c.post("/settings/email", data={"new_email": "bob@example.com"}, follow_redirects=False)
    norm = lambda r, e: r.headers["location"].replace(e.replace("@", "%40"), "E")  # noqa: E731
    assert norm(free, "free@example.com") == norm(taken, "bob@example.com")
    names = lambda r: sorted(h.split("=", 1)[0] for h in r.headers.get_list("set-cookie"))  # noqa: E731
    assert names(free) == names(taken)
    assert [k for k, _, _ in mail] == ["code_current", "code_new", "code_current", "taken_notice"]


def test_http_email_change_needs_same_origin_and_session(ui) -> None:
    c, store, mail = ui
    r = c.post("/settings/email", data={"new_email": "x@example.com"}, follow_redirects=False)
    assert r.status_code == 303 and "/login" in r.headers["location"]  # not signed in
    _signin(c)
    del c.headers["Origin"]
    r = c.post("/settings/email", data={"new_email": "x@example.com"},
               headers={"Origin": "https://evil.example"}, follow_redirects=False)
    assert r.status_code == 403 and mail == []


def test_http_mail_failure_fails_closed(ui) -> None:
    c, store, _ = ui
    _signin(c)

    def boom(kind, to, payload):
        raise OSError("smtp down")

    c.app.state.email_change_sender = boom
    r = c.post("/settings/email", data={"new_email": "x@example.com"}, follow_redirects=False)
    assert "error=mail_failed" in r.headers["location"]
    assert EMAIL_CHANGE_COOKIE not in r.headers.get("set-cookie", "")


def test_http_captcha_hook_after_repeated_failures(ui) -> None:
    c, store, _ = ui
    c.app.state.captcha_verifier = lambda token, ip: token == "solved"
    c.app.state.captcha_site_key = "site-key-for-test"
    store.register_or_login(email="cap@example.com", first_name="C", last_name="P")
    resp, outbox = request_login_code(c, {"email": "cap@example.com", "next": "/"})
    code = outbox[-1][1]
    for _ in range(lc.CAPTCHA_AFTER_FAILURES):
        r = c.post("/login/verify", data={"code": _wrong(code)}, follow_redirects=False)
        assert "error=code_wrong" in r.headers["location"]
    # Now the right code alone is not enough: solve the CAPTCHA first (no attempt used)
    r = c.post("/login/verify", data={"code": code}, follow_redirects=False)
    assert "error=captcha_required" in r.headers["location"]
    page = c.get(r.headers["location"])
    assert 'data-sitekey="site-key-for-test"' in page.text
    row = store._conn.execute("SELECT attempts FROM login_codes WHERE email = ?", ("cap@example.com",)).fetchone()
    assert row[0] == lc.CAPTCHA_AFTER_FAILURES
    r = c.post("/login/verify", data={"code": code, "captcha_token": "nope"}, follow_redirects=False)
    assert "error=captcha_required" in r.headers["location"]
    r = c.post("/login/verify", data={"code": code, "captcha_token": "solved"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert c.cookies.get("myroad_session")


def test_http_no_captcha_configured_means_no_captcha(ui) -> None:
    c, store, _ = ui
    store.register_or_login(email="nocap@example.com", first_name="N", last_name="C")
    _, outbox = request_login_code(c, {"email": "nocap@example.com", "next": "/"})
    code = outbox[-1][1]
    for _ in range(lc.CAPTCHA_AFTER_FAILURES):
        c.post("/login/verify", data={"code": _wrong(code)})
    page = c.get("/login/verify?next=/")
    assert "cf-turnstile" not in page.text
    r = c.post("/login/verify", data={"code": code}, follow_redirects=False)
    assert r.headers["location"] == "/"
