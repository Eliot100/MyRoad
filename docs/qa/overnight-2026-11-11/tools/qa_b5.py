"""Overnight QA B5 2026-11-11: re-run after pad() filler removal (content PR #56)."""
import json, math, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_b5 import B, register
from playwright.sync_api import sync_playwright
OUT = os.environ.get("OUT", "/workspace/overnight/qa-b5/shots")
CD = os.environ["CONTENT_DIR"]
os.makedirs(OUT, exist_ok=True)
VIEWS = {"desktop": {"width": 1280, "height": 800}, "mobile": {"width": 390, "height": 844}}
FILLER = re.compile(r"בדיקה \d+: \d+ ועוד 1")
log = {"console": [], "pageerror": [], "failed": [], "bad_status": [], "shots": [], "notes": [], "sweep": []}
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
    pg.on("response", lambda r: r.status >= 400 and "/api/placement/result" not in r.url and log["bad_status"].append([view, cur["page"], r.status, r.url]))

def overflow(pg):
    return pg.evaluate("""() => {
      const w = document.documentElement.clientWidth, bad = [];
      for (const el of document.querySelectorAll('#step-card, #step-card *')) {
        const r = el.getBoundingClientRect();
        if (r.width && (r.right > w + 1 || r.left < -1)) bad.push(el.tagName + '.' + el.className);
      }
      return {scrollW: document.documentElement.scrollWidth, clientW: w, bad: bad.slice(0, 5)};
    }""")

def shot(pg, view, name, url=None, save=True):
    cur["page"] = name
    st = None
    if url:
        resp = pg.goto(B + url); pg.wait_for_load_state("networkidle")
        st = resp.status if resp else None
    pg.wait_for_timeout(400)
    if save:
        path = f"{OUT}/{view}-{name}.png"
        pg.screenshot(path=path, full_page=False)
        log["shots"].append([view, name, pg.url.replace(B, ""), st, os.path.basename(path)])
    return st

def card_text(pg):
    return pg.inner_text("#step-card") if pg.query_selector("#step-card") else ""

def answer_one(pg, ns, ok):
    speak = pg.get_attribute("#step-card [data-speak]", "data-speak") or ""
    n = ns.get(speak.strip())
    if n is None:
        pg.click("#step-card button[name=choice] >> nth=0"); pg.wait_for_load_state("networkidle"); return None
    if isinstance(n["correct"], list):
        n = dict(n, correct=n["correct"][0]); ok = True
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
    i = 0
    for guard in range(40):
        if "/play/" + pid not in pg.url or not pg.query_selector("#step-card"):
            break
        if not pg.query_selector("#step-card button[name=choice]:not([disabled])"):
            nxt = pg.query_selector("#step-card form[action$='/ack'] button[type=submit]") or pg.query_selector("#step-card a.continue-step")
            if not nxt: break
            nxt.click(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300); continue
        ok = math.floor((i + 1) * frac) > math.floor(i * frac)
        if i == 1 and tag:
            shot(pg, view, "05-placement-question")
        answer_one(pg, ns, ok); i += 1
        cont = pg.query_selector("#step-card a.continue-step")
        if cont:
            cont.click(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
        else:
            break
    res = pg.evaluate(f"fetch('/api/placement/result?placementId={pid}',{{headers:{{'X-MyRoad-Request':'1'}}}}).then(r=>r.json())")
    log["notes"].append(f"{view} placement {pid} frac={frac}: {i} items, band {res.get('band')} -> {res.get('recommended_road_id')}, end url {pg.url.replace(B,'')}")
    return res

ROADS = sorted(f[:-5] for f in os.listdir(f"{CD}/adult") if "bagrut5" in f and f.endswith(".json") and "placement" not in f)

with sync_playwright() as p:
    br = p.chromium.launch()
    for view, vp in VIEWS.items():
        ctx = br.new_context(viewport=vp, device_scale_factor=1, is_mobile=(view == "mobile"), has_touch=(view == "mobile"))
        pg = ctx.new_page(); hook(pg, view)
        cur["page"] = "register"; register(pg, f"qa5-{view}-{int(time.time())}@example.com")
        shot(pg, view, "01-home", "/")
        shot(pg, view, "x-roads", "/roads", save=False)
        shot(pg, view, "x-map", "/play/path_math_bagrut5_01_analysis?view=map", save=False)
        shot(pg, view, "02-road-math-analysis", "/road/path_math_bagrut5_01_analysis")
        # 0% placement -> band 1 -> lands in math 01 first teaching stage
        play_placement(pg, "path_math_bagrut5_00_placement", 0.0, view, True)
        cur["page"] = "lesson"
        if "path_math_bagrut5_01_analysis" not in pg.url:
            pg.goto(B + "/play/path_math_bagrut5_01_analysis?view=learn"); pg.wait_for_load_state("networkidle")
        txt = card_text(pg)
        log["notes"].append(f"{view} first lesson tile text: {txt[:200]!r} filler={bool(FILLER.search(txt))} overflow={overflow(pg)}")
        shot(pg, view, "03-teaching-stage")
        # advance through learn tiles to first practice
        for _ in range(6):
            if pg.query_selector("#step-card button[name=choice]:not([disabled])"): break
            nxt = pg.query_selector("#step-card form[action$='/ack'] button[type=submit]") or pg.query_selector("#step-card a.continue-step")
            if not nxt: log["notes"].append(f"{view}: no next control on lesson tile"); break
            nxt.click(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
            t2 = card_text(pg)
            log["notes"].append(f"{view} next tile: {t2[:160]!r} filler={bool(FILLER.search(t2))}")
        if pg.query_selector("#step-card button[name=choice]:not([disabled])"):
            pg.click("#step-card button[name=choice] >> nth=1"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(400)
            shot(pg, view, "04-practice-after-answer")
            log["notes"].append(f"{view} practice after answer overflow={overflow(pg)}")
        else:
            log["notes"].append(f"{view}: never reached a practice tile")
        for u in ("/privacy", "/terms", "/settings", "/series/english-bagrut5"):
            st = shot(pg, view, "x" + u.replace("/", "-"), u, save=False); log["notes"].append(f"{view} GET {u} -> {st}")
        ctx.close()
    # sweep: every bagrut5 road, every topic's first tile (peek/read-only is fine), mobile
    ctx = br.new_context(viewport=VIEWS["mobile"], is_mobile=True, has_touch=True); pg = ctx.new_page(); hook(pg, "mobile-sweep")
    cur["page"] = "register"; register(pg, f"qa5-sweep-{int(time.time())}@example.com")
    for pid in ROADS:
        d = json.load(open(f"{CD}/adult/{pid}.json"))
        tops = [t["id"] for t in d.get("topics", [])] or [None]
        for tp in tops:
            cur["page"] = f"sweep {pid} {tp}"
            pg.goto(B + f"/play/{pid}?view=learn" + (f"&topic={tp}" if tp else "")); pg.wait_for_load_state("networkidle")
            txt = card_text(pg); ov = overflow(pg) if txt else None
            log["sweep"].append([pid, tp, len(txt), bool(FILLER.search(txt)), ov, txt[:80]])
    ctx.close(); br.close()
json.dump(log, open(os.environ.get("LOGF", "/workspace/overnight/qa-b5/qa-log.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: len(v) for k, v in log.items()}))
