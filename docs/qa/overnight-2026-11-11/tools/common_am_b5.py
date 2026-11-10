import re, time
B="http://127.0.0.1:8772"
LOG="/workspace/overnight/qa-b5/server-amirnet.log"
def code(email):
    for _ in range(40):
        lines=[l for l in open(LOG).read().splitlines() if email in l or "code" in l.lower()]
        txt="\n".join(open(LOG).read().split("[MyRoad login]")[-1:])
        if email in txt:
            m=re.findall(r"\b(\d{3,4}[ -]?\d{3,4}[ -]?\d{0,4})\b", txt)
            if m: return m[-1]
        time.sleep(0.3)
    raise RuntimeError("no code")
def register(pg, email):
    pg.goto(B+"/login?mode=register")
    pg.fill("#first_name","QA"); pg.fill("#last_name","Night"); pg.fill("#email",email)
    pg.click("form.login-form button[type=submit]"); pg.wait_for_load_state()
    c=code(email); pg.fill("#code", c)
    if "/login/verify" in pg.url:
        try: pg.click("form button[type=submit]", timeout=3000)
        except Exception: pass
    pg.wait_for_load_state("networkidle")
    return pg.url
