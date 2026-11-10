"""Overnight QA 2026-11-11: screenshots, console errors, failed requests, placement bands."""
import json, math, os, re, sys, time
sys.path.insert(0, "/workspace/overnight/qa-b1/tools")
from common import B, register
from playwright.sync_api import sync_playwright
OUT = "/workspace/overnight/qa-b1/app/docs/qa/overnight-2026-11-11"
CD = os.environ["CONTENT_DIR"]
os.makedirs(OUT, exist_ok=True)
VIEWS = {"desktop": {"width": 1280, "height": 800}, "mobile": {"width": 390, "height": 844}}
log = {"console": [], "pageerror": [], "failed": [], "bad_status": [], "shots": [], "notes": [], "bands": []}
cur = {"page": ""}

def nodes(pid):
    d = json.load(open(f"{CD}/adult/{pid}.json"))
    out = {}
    for n in [x for x in d["nodes"] if x.get("correct")]:
        for k in ("body_content", "body_he"):
            if n.get(k): out.setdefault(n[k].strip(), n)
    return out

def hook(pg, view):
    pg.on("console", lambda m: m.type in ("error", "warning") and log["console"].append([view, cur["page"], m.type, m.text[:300]]))
    pg.on("pageerror", lambda e: log["pageerror"].append([view, cur["page"], str(e)[:300]]))
    pg.on("requestfailed", lambda r: log["failed"].append([view, cur["page"], r.url, r.failure]))
    pg.on("response", lambda r: r.status >= 400 and log["bad_status"].append([view, cur["page"], r.status, r.url]))

def shot(pg, view, name, url=None, full=True):
    cur["page"] = name
    st = None
    if url:
        resp = pg.goto(B + url); pg.wait_for_load_state("networkidle")
        st = resp.status if resp else None
    pg.wait_for_timeout(400)
    path = f"{OUT}/{view}-{name}.png"
    pg.screenshot(path=path, full_page=full)
    log["shots"].append([view, name, pg.url.replace(B, ""), st, os.path.relpath(path, "/workspace/overnight/qa-b1/app")])
    return st

def answer_one(pg, ns, ok):
    speak = pg.get_attribute("#step-card [data-speak]", "data-speak") or ""
    n = ns.get(speak.strip())
    if n is None:
        log["notes"].append(f"no content match for step text {speak[:60]!r}")
        pg.click("#step-card button[name=choice] >> nth=0"); pg.wait_for_load_state("networkidle"); return None
    if isinstance(n["correct"], list):
        n = dict(n, correct=n["correct"][0])
        ok = True
    if not ok:
        wrong = next(c["id"] for c in n["choices"] if c["id"] != n["correct"])
        pg.click(f"#step-card button[name=choice][value='{wrong}']"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
        if pg.query_selector(f"#step-card button[name=choice][value='{n['correct']}']:not([disabled])"):
            pg.click(f"#step-card button[name=choice][value='{n['correct']}']")
    else:
        pg.click(f"#step-card button[name=choice][value='{n['correct']}']")
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
    return n["id"]

def play_placement(pg, pid, frac, view, tag):
    ns = nodes(pid)
    pg.goto(B + f"/play/{pid}"); pg.wait_for_load_state("networkidle")
    pg.click(".continue-btn"); pg.wait_for_load_state("networkidle")
    i = 0; seq = []
    for guard in range(40):
        if os.environ.get("DBG"): print(guard, pg.url.replace(B, ""), bool(pg.query_selector("#step-card")), bool(pg.query_selector("#step-card button[name=choice]:not([disabled])")), flush=True)
        if "/play/" + pid not in pg.url or not pg.query_selector("#step-card"):
            break
        if not pg.query_selector("#step-card button[name=choice]:not([disabled])"):
            nxt = pg.query_selector("#step-card form[action$='/ack'] button[type=submit]") or pg.query_selector("#step-card a.continue-step")
            if not nxt:
                break
            nxt.click(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300); continue
        ok = math.floor((i + 1) * frac) > math.floor(i * frac)
        if i == 1 and tag:
            shot(pg, view, f"10-placement-question-{tag}", full=False)
        nid = answer_one(pg, ns, ok); seq.append((nid, ok)); i += 1
        cont = pg.query_selector("#step-card a.continue-step")
        if cont:
            cont.click(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
        else:
            break
    if tag:
        log["notes"].append(f"{view} {pid}: answered {len(seq)} items, end url {pg.url.replace(B, '')}")
    res = pg.evaluate(f"fetch('/api/placement/result?placementId={pid}',{{headers:{{'X-MyRoad-Request':'1'}}}}).then(r=>r.json())")
    return seq, res

with sync_playwright() as p:
    br = p.chromium.launch()
    for view, vp in (VIEWS.items() if os.environ.get("SHOTS","1")=="1" else []):
        ctx = br.new_context(viewport=vp, device_scale_factor=1, is_mobile=(view == "mobile"), has_touch=(view == "mobile"))
        pg = ctx.new_page(); hook(pg, view)
        shot(pg, view, "01-home-guest", "/")
        shot(pg, view, "02-login", "/login")
        for u in ("/privacy", "/terms"):
            st = shot(pg, view, "03-" + u.strip("/"), u)
            log["notes"].append(f"{view} GET {u} -> {st}")
        cur["page"] = "register"; register(pg, f"qa-{view}@example.com")
        shot(pg, view, "04-home-signed-in", "/")
        shot(pg, view, "05-home-subject-math", "/?subject=math")
        shot(pg, view, "06-roads", "/roads")
        shot(pg, view, "07-series-english", "/series/english-bagrut5")
        shot(pg, view, "08-road-math-analysis", "/road/path_math_bagrut5_01_analysis")
        shot(pg, view, "09-road-map-math-analysis", "/play/path_math_bagrut5_01_analysis?view=map")
        seq, res = play_placement(pg, "path_math_bagrut5_00_placement", 0.5, view, "math")
        log["bands"].append([view, "math", 0.5, len(seq), sum(o for _, o in seq), res.get("band"), res.get("recommended_road_id")])
        shot(pg, view, "11-after-placement", None)
        shot(pg, view, "12-home-after-placement", "/")
        cur["page"] = "lesson"
        pg.goto(B + "/play/path_math_bagrut5_01_analysis"); pg.wait_for_load_state("networkidle")
        if pg.query_selector(".continue-btn"):
            pg.click(".continue-btn"); pg.wait_for_load_state("networkidle")
        shot(pg, view, "13-lesson-tile", None)
        if pg.query_selector("#step-card button[name=choice]:not([disabled])"):
            pg.click("#step-card button[name=choice] >> nth=1"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(400)
            shot(pg, view, "14-lesson-after-answer", None)
        else:
            cont = pg.query_selector("#step-card a.continue-step, #step-card button.primary")
            log["notes"].append(f"{view}: first lesson step has no choices (teaching stage); continue={bool(cont)}")
        shot(pg, view, "15-metrics-math-placement", "/metrics/path_math_bagrut5_00_placement")
        shot(pg, view, "16-metrics-math-analysis", "/metrics/path_math_bagrut5_01_analysis")
        shot(pg, view, "17-settings", "/settings")
        shot(pg, view, "18-add-path", "/add-path")
        shot(pg, view, "19-physics-lab-road", "/road/path_physics_bagrut5_lab")
        ctx.close()
    json.dump(log, open(os.environ.get("LOGF","/workspace/overnight/qa-b1/qa-log.json"), "w"), ensure_ascii=False, indent=1)
    if os.environ.get("SWEEP", "1") == "1":
        for subj in os.environ.get("SUBJ","math english physics arabic").split():
            pid = f"path_{subj}_bagrut5_00_placement"
            for k, frac in enumerate((0.0, 0.3, 0.5, 0.7, 1.0)):
                ctx = br.new_context(viewport=VIEWS["desktop"]); pg = ctx.new_page(); hook(pg, "desktop-sweep")
                cur["page"] = f"sweep-{subj}-{frac}"
                register(pg, f"sweep-{subj}-{k}-{int(time.time())}@example.com")
                seq, res = play_placement(pg, pid, frac, "desktop", None)
                log["bands"].append(["sweep", subj, frac, len(seq), sum(o for _, o in seq), res.get("band"), res.get("recommended_road_id")])
                print("band", subj, frac, len(seq), sum(o for _, o in seq), res.get("band"), res.get("recommended_road_id"), flush=True)
                ctx.close()
    br.close()
json.dump(log, open(os.environ.get("LOGF","/workspace/overnight/qa-b1/qa-log.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: len(v) for k, v in log.items()}))
