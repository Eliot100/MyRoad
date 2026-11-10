import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_am_b5 import B, register
from playwright.sync_api import sync_playwright
OUT = "/workspace/overnight/qa-b5/shots"; PID = "path_english_amirnet_01"
log = {"console": [], "pageerror": [], "bad": [], "notes": []}
with sync_playwright() as p:
    br = p.chromium.launch()
    for view, vp in (("desktop", {"width": 1280, "height": 800}), ("mobile", {"width": 390, "height": 844})):
        ctx = br.new_context(viewport=vp, is_mobile=view == "mobile", has_touch=view == "mobile"); pg = ctx.new_page()
        pg.on("console", lambda m: m.type == "error" and log["console"].append([view, pg.url, m.text[:200]]))
        pg.on("pageerror", lambda e: log["pageerror"].append([view, str(e)[:200]]))
        pg.on("response", lambda r: r.status >= 400 and log["bad"].append([view, r.status, r.url]))
        register(pg, f"am-{view}-{int(time.time())}@example.com")
        for u in ("/?group=amirnet&subject=all", "/?group=psychometric&subject=all", "/roads?group=amirnet", "/roads?group=psychometric"):
            pg.goto(B + u); pg.wait_for_load_state("networkidle"); t = pg.inner_text("main") if pg.query_selector("main") else pg.inner_text("body")
            log["notes"].append([view, u, "AMIRNET" in t or "אמירנט" in t, "אנגלית" in t, re.sub(r"\s+", " ", t)[:300]])
        pg.goto(B + "/?group=amirnet&subject=all"); pg.wait_for_load_state("networkidle")
        if view == "desktop": pg.screenshot(path=f"{OUT}/desktop-06-amirnet-home.png")
        r = pg.goto(B + f"/road/{PID}"); pg.wait_for_load_state("networkidle"); log["notes"].append([view, "road", r.status])
        pg.goto(B + f"/play/{PID}"); pg.wait_for_load_state("networkidle")
        if pg.query_selector(".continue-btn"): pg.click(".continue-btn"); pg.wait_for_load_state("networkidle")
        steps = []
        for _ in range(6):
            if not pg.query_selector("#step-card"): steps.append("no step card " + pg.url); break
            txt = re.sub(r"\s+", " ", pg.inner_text("#step-card"))[:140]
            if pg.query_selector("#step-card button[name=choice]:not([disabled])"):
                pg.click("#step-card button[name=choice] >> nth=0"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
                fb = pg.query_selector("#step-feedback, .feedback"); steps.append(["choice", txt, re.sub(r"\s+", " ", fb.inner_text())[:120] if fb else None])
                if view == "mobile": pg.screenshot(path=f"{OUT}/mobile-06-amirnet-step.png")
                break
            nxt = pg.query_selector("#step-card form[action$='/ack'] button[type=submit]") or pg.query_selector("#step-card a.continue-step")
            steps.append(["learn", txt])
            if not nxt: break
            nxt.click(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
        log["notes"].append([view, "steps", steps, pg.url.replace(B, "")])
        ctx.close()
    br.close()
json.dump(log, open("/workspace/overnight/qa-b5/qa-log-amirnet.json", "w"), ensure_ascii=False, indent=1)
for k, v in log.items():
    print("==", k)
    for x in v: print(x)
