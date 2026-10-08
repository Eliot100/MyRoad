"""Issue #41: sign-in proves email ownership with a one-time 6-digit code."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from myroad_core.auth.login_codes import (
    CODE_TTL_SECONDS,
    BACKOFF_AFTER_FAILURES,
    MAX_ACTIVE_CODES,
    MAX_VERIFY_ATTEMPTS,
    SEND_LIMITS,
    verify_code_hash,
)
from myroad_core.store import PathStore

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code, request_login_code

from myroad_core.ui.app import create_learner_app

NEW_USER = {"first_name": "Noa", "last_name": "Levi", "email": "noa.code@example.com", "next": "/settings"}


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 10**6:06d}"


# ---------- store level ----------

def test_code_is_six_digits_and_only_hash_is_stored(store: PathStore) -> None:
    cid, code = store.start_login_challenge(email="a@example.com", first_name="A", last_name="B")
    assert len(code) == 6 and code.isdigit()
    row = store._conn.execute("SELECT * FROM login_codes WHERE challenge_id = ?", (cid,)).fetchone()
    assert row["code_hash"] != code
    assert row["code_hash"].startswith("pbkdf2_sha256$")
    assert verify_code_hash(code, row["code_hash"])
    # Plain code appears nowhere in the database
    dump = "\n".join(store._conn.iterdump())
    assert f"'{code}'" not in dump
    assert all(str(v) != code for v in tuple(row))
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(login_codes)").fetchall()}
    assert "code" not in cols and not any("password" in c for c in cols)


def test_same_code_hashes_differently_each_time(store: PathStore) -> None:
    from myroad_core.auth.login_codes import hash_code

    assert hash_code("123456") != hash_code("123456")


def test_new_user_created_only_after_verify(store: PathStore) -> None:
    cid, code = store.start_login_challenge(email="new@example.com", first_name="N", last_name="U")
    assert store.get_learner_by_email("new@example.com") is None
    learner = store.verify_login_challenge(cid, code)
    assert learner["email"] == "new@example.com"
    assert learner["firstName"] == "N"
    assert store.get_learner_by_email("new@example.com")["userId"] == learner["userId"]


def test_new_email_needs_names_returning_email_does_not(store: PathStore) -> None:
    with pytest.raises(ValueError, match="name_required"):
        store.start_login_challenge(email="nobody@example.com")
    store.register_or_login(email="back@example.com", first_name="B", last_name="K")
    cid, code = store.start_login_challenge(email="BACK@example.com ")
    assert store.verify_login_challenge(cid, code)["email"] == "back@example.com"


def test_invalid_email_rejected(store: PathStore) -> None:
    for bad, err in (("", "email_required"), ("not-an-email", "email_invalid")):
        with pytest.raises(ValueError, match=err):
            store.start_login_challenge(email=bad, first_name="A", last_name="B")


def test_code_is_single_use(store: PathStore) -> None:
    cid, code = store.start_login_challenge(email="once@example.com", first_name="O", last_name="N")
    store.verify_login_challenge(cid, code)
    with pytest.raises(ValueError, match="code_used"):
        store.verify_login_challenge(cid, code)


def test_code_expires_after_15_minutes(store: PathStore) -> None:
    t0 = datetime.now(timezone.utc)
    cid, code = store.start_login_challenge(email="exp@example.com", first_name="E", last_name="X", now=t0)
    assert CODE_TTL_SECONDS == 15 * 60
    with pytest.raises(ValueError, match="code_expired"):
        store.verify_login_challenge(cid, code, now=t0 + timedelta(minutes=15, seconds=1))
    cid2, code2 = store.start_login_challenge(email="exp2@example.com", first_name="E", last_name="X", now=t0)
    assert store.verify_login_challenge(cid2, code2, now=t0 + timedelta(minutes=14, seconds=50))


def test_wrong_code_counts_attempts_then_locks(store: PathStore) -> None:
    cid, code = store.start_login_challenge(email="wrong@example.com", first_name="W", last_name="R")
    for _ in range(MAX_VERIFY_ATTEMPTS - 1):
        with pytest.raises(ValueError, match="code_wrong"):
            store.verify_login_challenge(cid, _wrong(code))
    with pytest.raises(ValueError, match="code_locked"):
        store.verify_login_challenge(cid, _wrong(code))
    # Locked: even the right code no longer works (checked from another IP,
    # since this IP is now in backoff and would get code_slow_down first)
    with pytest.raises(ValueError, match="code_locked"):
        store.verify_login_challenge(cid, code, client_ip="10.9.9.9")
    assert store.get_learner_by_email("wrong@example.com") is None


def test_malformed_or_missing_code(store: PathStore) -> None:
    cid, code = store.start_login_challenge(email="m@example.com", first_name="M", last_name="F")
    with pytest.raises(ValueError, match="code_required"):
        store.verify_login_challenge(cid, "  ")
    with pytest.raises(ValueError, match="code_wrong"):
        store.verify_login_challenge(cid, "12345")
    with pytest.raises(ValueError, match="code_invalid"):
        store.verify_login_challenge("no-such-challenge", code)
    with pytest.raises(ValueError, match="code_invalid"):
        store.verify_login_challenge(None, code)
    # Spaces / dashes users paste are fine
    assert store.verify_login_challenge(cid, f"{code[:3]} {code[3:]}")


def test_a_new_code_does_not_cancel_the_previous_ones(store: PathStore) -> None:
    """Lockout abuse: someone else requesting codes must not kill the code I am typing."""
    cid1, code1 = store.start_login_challenge(email="re@example.com", first_name="R", last_name="E")
    others = [store.start_login_challenge(email="re@example.com", first_name="R", last_name="E")
              for _ in range(MAX_ACTIVE_CODES - 1)]
    assert store.verify_login_challenge(cid1, code1)["email"] == "re@example.com"
    cid_x, code_x = others[-1]
    assert store.verify_login_challenge(cid_x, code_x)


def test_only_the_newest_active_codes_stay_usable(store: PathStore) -> None:
    issued = [store.start_login_challenge(email="cap@example.com", first_name="C", last_name="P")
              for _ in range(MAX_ACTIVE_CODES + 1)]
    oldest_cid, oldest_code = issued[0]
    with pytest.raises(ValueError, match="code_used"):
        store.verify_login_challenge(oldest_cid, oldest_code)
    newest_cid, newest_code = issued[-1]
    assert store.verify_login_challenge(newest_cid, newest_code)


def test_attacker_on_another_ip_cannot_lock_out_the_real_user(store: PathStore) -> None:
    """Cyber security re-review: failures count per email+IP, not as one global lock."""
    store.register_or_login(email="victim@example.com", first_name="V", last_name="I")
    t = datetime.now(timezone.utc)
    for _ in range(40):  # far past the old 15-per-email hard lock
        t += timedelta(minutes=16)  # wait out the attacker's own backoff
        cid, code = store.start_login_challenge(email="victim@example.com", client_ip="6.6.6.6", now=t)
        with pytest.raises(ValueError, match="code_wrong"):
            store.verify_login_challenge(cid, _wrong(code), client_ip="6.6.6.6", now=t)
    assert store._email_failures("victim@example.com", t) >= 40
    # The real user, on their own IP, signs in with the correct code right away
    cid, code = store.start_login_challenge(email="victim@example.com", client_ip="1.2.3.4", now=t)
    learner = store.verify_login_challenge(cid, code, client_ip="1.2.3.4", now=t + timedelta(seconds=1))
    assert learner["email"] == "victim@example.com"


def test_backoff_slows_one_email_ip_without_using_attempts(store: PathStore) -> None:
    store.register_or_login(email="slow@example.com", first_name="S", last_name="L")
    t = datetime.now(timezone.utc)
    for _ in range(BACKOFF_AFTER_FAILURES):
        cid, code = store.start_login_challenge(email="slow@example.com", now=t)
        with pytest.raises(ValueError, match="code_wrong"):
            store.verify_login_challenge(cid, _wrong(code), client_ip="7.7.7.7", now=t)
    cid, code = store.start_login_challenge(email="slow@example.com", now=t)
    with pytest.raises(ValueError, match="code_slow_down"):
        store.verify_login_challenge(cid, code, client_ip="7.7.7.7", now=t + timedelta(seconds=1))
    row = store._conn.execute("SELECT attempts FROM login_codes WHERE challenge_id = ?", (cid,)).fetchone()
    assert row[0] == 0  # refused before any attempt or hashing
    assert store.login_backoff_remaining("slow@example.com", "7.7.7.7", t + timedelta(seconds=1)) > 0
    # Another IP is not slowed down
    assert store.login_backoff_remaining("slow@example.com", "8.8.8.8", t) == 0
    # After the wait the right code works from the same IP
    assert store.verify_login_challenge(cid, code, client_ip="7.7.7.7", now=t + timedelta(seconds=3))
    # Delays grow with more failures (capped)
    from myroad_core.auth.login_codes import BACKOFF_MAX_SECONDS, backoff_seconds

    assert [backoff_seconds(n) for n in range(4, 8)] == [0, 2, 4, 8]
    assert backoff_seconds(100) == BACKOFF_MAX_SECONDS


def test_parallel_guesses_never_exceed_the_attempt_limit(tmp_path) -> None:
    import threading

    store = PathStore(str(tmp_path / "race.db"))
    try:
        cid, code = store.start_login_challenge(email="race@example.com", first_name="R", last_name="C")
        wrong = _wrong(code)
        results: list[str] = []
        errors: list[BaseException] = []
        barrier = threading.Barrier(40)

        def guess() -> None:
            barrier.wait()
            try:
                store.verify_login_challenge(cid, wrong)
                results.append("ok")
            except ValueError as exc:
                results.append(str(exc))
            except BaseException as exc:  # noqa: BLE001 - e.g. sqlite misuse
                errors.append(exc)

        threads = [threading.Thread(target=guess) for _ in range(40)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(results) == 40
        # code_slow_down: the IP's own backoff kicked in after 5 failures
        checked = [r for r in results if r in ("code_wrong", "code_locked", "code_slow_down")]
        row = store._conn.execute(
            "SELECT attempts, failures FROM login_codes WHERE challenge_id = ?", (cid,)
        ).fetchone()
        assert row["attempts"] == MAX_VERIFY_ATTEMPTS
        assert row["failures"] == MAX_VERIFY_ATTEMPTS  # only 5 guesses were ever hashed
        assert results.count("code_wrong") <= MAX_VERIFY_ATTEMPTS
        assert len(checked) == 40
        with pytest.raises(ValueError, match="code_locked"):
            store.verify_login_challenge(cid, code, client_ip="10.0.0.2")
    finally:
        store.close()


def test_parallel_correct_code_logs_in_exactly_once(tmp_path) -> None:
    import threading

    store = PathStore(str(tmp_path / "race2.db"))
    try:
        cid, code = store.start_login_challenge(email="once2@example.com", first_name="O", last_name="T")
        results: list[str] = []
        barrier = threading.Barrier(10)

        def go() -> None:
            barrier.wait()
            try:
                store.verify_login_challenge(cid, code)
                results.append("ok")
            except ValueError as exc:
                results.append(str(exc))

        threads = [threading.Thread(target=go) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert results.count("ok") == 1
        assert store._conn.execute("SELECT COUNT(*) FROM learners WHERE email = ?",
                                   ("once2@example.com",)).fetchone()[0] == 1
    finally:
        store.close()


def test_send_limits_per_email_ip_email_and_ip(store: PathStore) -> None:
    store.register_or_login(email="lim@example.com", first_name="L", last_name="M")
    kinds = [store.request_login(email="lim@example.com", client_ip="1.1.1.1").kind
             for _ in range(SEND_LIMITS["email_ip"] + 1)]
    assert kinds[:-1] == ["code"] * SEND_LIMITS["email_ip"] and kinds[-1] == "rate_limited"
    # Another IP may still ask for the same email until the per-email limit
    more = [store.request_login(email="lim@example.com", client_ip=f"2.2.2.{i}").kind
            for i in range(SEND_LIMITS["email"])]
    assert "rate_limited" in more
    assert more.count("code") == SEND_LIMITS["email"] - SEND_LIMITS["email_ip"]
    # Per-IP limit across many emails
    ip_kinds = [store.request_login(email=f"u{i}@example.com", client_ip="9.9.9.9").kind
                for i in range(SEND_LIMITS["ip"] + 1)]
    assert ip_kinds[-1] == "rate_limited"
    assert all(k == "no_account" for k in ip_kinds[:-1])
    # Window passes: allowed again
    later = datetime.now(timezone.utc) + timedelta(minutes=16)
    assert store.request_login(email="lim@example.com", client_ip="1.1.1.1", now=later).kind == "code"


def test_request_login_is_neutral_about_accounts(store: PathStore) -> None:
    store.register_or_login(email="known@example.com", first_name="K", last_name="N")
    known = store.request_login(email="known@example.com", client_ip="3.3.3.3")
    unknown = store.request_login(email="unknown@example.com", client_ip="3.3.3.3")
    assert known.kind == "code" and known.code
    assert unknown.kind == "no_account" and unknown.code is None
    assert len(known.challenge_id) == len(unknown.challenge_id)
    assert store.get_login_challenge_email(unknown.challenge_id) is None
    assert store.get_learner_by_email("unknown@example.com") is None


# ---------- HTTP flow ----------

@pytest.fixture
def ui(tmp_path, monkeypatch):
    monkeypatch.delenv("MYROAD_SMTP_HOST", raising=False)
    store = PathStore(str(tmp_path / "login.db"))
    app = create_learner_app(store=store, seed=False, seed_content=False)
    with TestClient(app) as c:
        yield c, store
    store.close()


def test_post_login_sends_code_but_starts_no_session(ui) -> None:
    c, store = ui
    resp, outbox = request_login_code(c, NEW_USER)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/login/verify")
    assert [e for e, _ in outbox] == ["noa.code@example.com"]
    code = outbox[0][1]
    assert c.cookies.get("myroad_session") is None
    assert c.cookies.get("myroad_uid") is None
    assert store.get_learner_by_email("noa.code@example.com") is None
    # The code never reaches the browser
    assert code not in resp.text and code not in str(resp.headers)
    assert all(code not in v for v in c.cookies.values())
    # Still signed out
    assert c.get("/settings", follow_redirects=False).status_code == 303
    page = c.get(resp.headers["location"])
    assert page.status_code == 200
    assert 'name="code"' in page.text and 'autocomplete="one-time-code"' in page.text
    assert 'action="/login/verify"' in page.text
    assert 'type="password"' not in page.text
    assert code not in page.text
    assert "noa.code@example.com" in page.text


def test_session_starts_only_after_correct_code(ui) -> None:
    c, store = ui
    _, outbox = request_login_code(c, NEW_USER)
    code = outbox[-1][1]
    bad = c.post("/login/verify", data={"code": _wrong(code), "next": "/settings"}, follow_redirects=False)
    assert bad.status_code == 303
    assert bad.headers["location"].startswith("/login/verify") and "error=code_wrong" in bad.headers["location"]
    assert c.cookies.get("myroad_session") is None
    assert c.get("/settings", follow_redirects=False).status_code == 303

    good = c.post("/login/verify", data={"code": code, "next": "/settings"}, follow_redirects=False)
    assert good.status_code == 303 and good.headers["location"] == "/settings"
    sid = c.cookies.get("myroad_session")
    assert sid
    user_id = store.get_session_user(sid)
    assert user_id == store.get_learner_by_email("noa.code@example.com")["userId"]
    assert c.get("/settings").status_code == 200


def test_code_cannot_be_replayed_over_http(ui) -> None:
    c, store = ui
    _, outbox = request_login_code(c, NEW_USER)
    code = outbox[-1][1]
    cid = c.cookies.get("myroad_login")
    assert cid
    assert c.post("/login/verify", data={"code": code}, follow_redirects=False).status_code == 303
    c.cookies.clear()
    c.cookies.set("myroad_login", cid, path="/login")
    again = c.post("/login/verify", data={"code": code, "next": "/"}, follow_redirects=False)
    assert "error=code_used" in again.headers["location"]
    assert c.cookies.get("myroad_session") is None


def test_expired_code_over_http(ui) -> None:
    c, store = ui
    _, outbox = request_login_code(c, NEW_USER)
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    store._conn.execute("UPDATE login_codes SET expires_at = ?", (past,))
    store._conn.commit()
    r = c.post("/login/verify", data={"code": outbox[-1][1], "next": "/"}, follow_redirects=False)
    assert r.headers["location"].startswith("/login?") and "error=code_expired" in r.headers["location"]
    assert c.cookies.get("myroad_session") is None


def test_lockout_over_http(ui) -> None:
    c, _ = ui
    _, outbox = request_login_code(c, NEW_USER)
    code = outbox[-1][1]
    for _ in range(MAX_VERIFY_ATTEMPTS):
        last = c.post("/login/verify", data={"code": _wrong(code)}, follow_redirects=False)
    assert "error=code_locked" in last.headers["location"]
    r = c.post("/login/verify", data={"code": code}, follow_redirects=False)
    assert c.cookies.get("myroad_session") is None
    assert r.headers["location"].startswith("/login")


def test_verify_without_challenge_goes_back_to_login(ui) -> None:
    c, _ = ui
    assert c.get("/login/verify", follow_redirects=False).headers["location"].startswith("/login?")
    r = c.post("/login/verify", data={"code": "123456"}, follow_redirects=False)
    assert r.headers["location"].startswith("/login?")
    assert c.cookies.get("myroad_session") is None


def test_register_form_without_names_is_a_form_error(ui) -> None:
    c, _ = ui
    r, outbox = request_login_code(c, {"email": "fresh@example.com", "next": "/", "mode": "register"})
    assert "mode=register" in r.headers["location"] and "error=name_required" in r.headers["location"]
    assert outbox == []


def _strip_cookie_value(headers) -> list[str]:
    out = []
    for h in headers.get_list("set-cookie"):
        name, _, rest = h.partition("=")
        out.append(name + "=<v>;" + rest.partition(";")[2])
    return out


def test_known_and_unknown_email_get_the_same_response(ui) -> None:
    c, store = ui
    store.register_or_login(email="known.user@example.com", first_name="K", last_name="U")
    notices: list[str] = []
    c.app.state.login_notice_sender = notices.append
    r_known, out_known = request_login_code(c, {"email": "known.user@example.com", "next": "/"})
    c.cookies.clear()
    r_unknown, out_unknown = request_login_code(c, {"email": "nobody.here@example.com", "next": "/"})
    loc = lambda r, e: r.headers["location"].replace(e.replace("@", "%40"), "<email>")  # noqa: E731
    assert r_known.status_code == r_unknown.status_code == 303
    assert loc(r_known, "known.user@example.com") == loc(r_unknown, "nobody.here@example.com")
    assert _strip_cookie_value(r_known.headers) == _strip_cookie_value(r_unknown.headers)
    assert r_known.text == r_unknown.text
    # Only the email content differs: a code for the account, a notice otherwise
    assert [e for e, _ in out_known] == ["known.user@example.com"] and out_unknown == []
    assert notices == ["nobody.here@example.com"]
    # The verify page looks the same too
    p_known = c.get(r_known.headers["location"])
    c.cookies.set("myroad_login", "x", path="/login")
    p_unknown = c.get(r_unknown.headers["location"])
    assert p_known.status_code == p_unknown.status_code == 200
    norm = lambda text, e: text.replace(e, "E").replace(e.replace("@", "%40"), "E")  # noqa: E731
    assert norm(p_known.text, "known.user@example.com") == norm(p_unknown.text, "nobody.here@example.com")
    assert store.get_learner_by_email("nobody.here@example.com") is None


def test_rate_limited_request_gets_the_same_response(ui) -> None:
    c, store = ui
    store.register_or_login(email="rl@example.com", first_name="R", last_name="L")
    responses = [request_login_code(c, {"email": "rl@example.com", "next": "/"})
                 for _ in range(SEND_LIMITS["email_ip"] + 1)]
    sent = [len(out) for _, out in responses]
    assert sent == [1] * SEND_LIMITS["email_ip"] + [0]
    first, last = responses[0][0], responses[-1][0]
    assert first.headers["location"] == last.headers["location"]
    assert _strip_cookie_value(first.headers) == _strip_cookie_value(last.headers)


def test_login_challenge_cookie_is_secure_by_default(ui, monkeypatch) -> None:
    c, _ = ui
    monkeypatch.delenv("MYROAD_DEV_INSECURE_COOKIES", raising=False)
    r, _ = request_login_code(c, NEW_USER)
    (cookie,) = [h for h in r.headers.get_list("set-cookie") if h.startswith("myroad_login=")]
    low = cookie.lower()
    assert "secure" in low and "httponly" in low and "path=/login" in low


def test_no_mail_config_without_dev_flag_fails_closed(ui, monkeypatch, capsys) -> None:
    c, store = ui
    monkeypatch.delenv("MYROAD_DEV_MAIL_CONSOLE", raising=False)
    r = c.post("/login", data=NEW_USER, follow_redirects=False)
    assert "error=mail_failed" in r.headers["location"]
    assert c.cookies.get("myroad_login") is None
    assert "Code for" not in capsys.readouterr().err
    with pytest.raises(Exception, match="MYROAD_SMTP_HOST"):
        from myroad_core.auth.mailer import send_login_code

        send_login_code("x@example.com", "123456")


def test_dev_flag_logs_code_to_console(ui, capsys, monkeypatch) -> None:
    c, store = ui
    monkeypatch.setenv("MYROAD_DEV_MAIL_CONSOLE", "1")
    r = c.post("/login", data=NEW_USER, follow_redirects=False)
    assert r.headers["location"].startswith("/login/verify")
    err = capsys.readouterr().err
    assert "noa.code@example.com" in err
    code = err.split("Code for noa.code@example.com: ")[1][:6]
    assert code.isdigit()
    ok = c.post("/login/verify", data={"code": code, "next": "/settings"}, follow_redirects=False)
    assert ok.headers["location"] == "/settings" and c.cookies.get("myroad_session")


def test_smtp_config_sends_mail_and_does_not_log_code(ui, monkeypatch, capsys) -> None:
    c, _ = ui
    sent: list = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, context=None):
            import ssl

            assert isinstance(context, ssl.SSLContext)
            assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
            sent.append(("starttls",))

        def login(self, user, pw):
            sent.append(("login", user))

        def send_message(self, msg):
            sent.append(("send", msg["To"], msg.get_content()))

    monkeypatch.setattr("myroad_core.auth.mailer.smtplib.SMTP", FakeSMTP)
    monkeypatch.setenv("MYROAD_SMTP_HOST", "smtp.test")
    monkeypatch.setenv("MYROAD_SMTP_USER", "mailer@example.com")
    monkeypatch.setenv("MYROAD_SMTP_PASSWORD", "x")
    r = c.post("/login", data=NEW_USER, follow_redirects=False)
    assert r.headers["location"].startswith("/login/verify")
    assert sent[0] == ("connect", "smtp.test", 587)
    assert ("starttls",) in sent and ("login", "mailer@example.com") in sent
    to, body = sent[-1][1], sent[-1][2]
    assert to == "noa.code@example.com"
    code = body.split("code is ")[1][:6]
    assert code.isdigit()
    assert code not in capsys.readouterr().err


def test_mail_failure_is_reported_without_code(ui, monkeypatch) -> None:
    c, store = ui

    def boom(email, code):
        raise OSError("smtp down")

    c.app.state.login_code_sender = boom
    r = c.post("/login", data=NEW_USER, follow_redirects=False)
    assert "error=mail_failed" in r.headers["location"]
    assert c.cookies.get("myroad_login") is None


def test_returning_user_signs_in_with_code(ui) -> None:
    c, store = ui
    login_with_code(c, NEW_USER)
    uid = store.get_session_user(c.cookies.get("myroad_session"))
    c.cookies.clear()
    r = login_with_code(c, {"email": "noa.code@example.com", "next": "/settings"})
    assert r.status_code == 200
    assert store.get_session_user(c.cookies.get("myroad_session")) == uid
