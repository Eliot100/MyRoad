"""Mobile pass at 360 and 412 CSS px, Chrome on Android (issue #233, decision 0017).

A fresh touch context per locale (he, ar RTL; en LTR). On each learner screen:
no horizontal scroll, and every stand-alone tap target is at least 44x44 px.
"""
from __future__ import annotations

import pytest

from conftest import login

STEP = "/play/path_a11y_step_player"
PLACEMENT = "/play/path_english_bagrut5_00_placement"
WIDTHS = [(360, 800), (412, 915)]

AUDIT = r"""() => {
  const de = document.documentElement, small = [];
  const sel = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button]';
  for (const el of document.querySelectorAll(sel)) {
    const b = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || b.width === 0) continue;
    if (el.closest('[aria-hidden=true],.visually-hidden,.sr-only')) continue;
    if (el.matches('input[type=checkbox],input[type=radio]') && el.closest('label')) continue;
    if (el.matches('.skip-link') && b.top < -1) continue;
    const p = el.parentElement;
    const inline = el.tagName === 'A' && p && /^(P|LI|SPAN|SMALL|DD)$/.test(p.tagName)
      && p.textContent.trim().length > el.textContent.trim().length + 8;
    if (inline || el.matches('.tv-name a, .legal-links a')) continue;
    if (b.height < 43.5 || b.width < 43.5)
      small.push(el.tagName + '.' + [...el.classList].join('.') + ' "' +
        (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 24) + '" ' +
        Math.round(b.width) + 'x' + Math.round(b.height));
  }
  return {overflow: de.scrollWidth - de.clientWidth, dir: de.dir, small};
}"""


def _check(pg, state: str, want_dir: str) -> None:
    bad = []
    for w, h in WIDTHS:
        pg.set_viewport_size({"width": w, "height": h})
        pg.wait_for_timeout(80)
        r = pg.evaluate(AUDIT)
        assert r["dir"] == want_dir, f"{state} {w}px: dir={r['dir']}"
        if r["overflow"] > 0:
            bad.append(f"[{state} {w}px] horizontal scroll {r['overflow']}px")
        bad += [f"[{state} {w}px] small target {s}" for s in r["small"]]
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("locale,dir_", [("he", "rtl"), ("ar", "rtl"), ("en", "ltr")])
def test_learner_screens_fit_phone(browser_context, server, locale, dir_):
    base, log = server
    ctx = browser_context.browser.new_context(base_url=base, viewport={"width": 360, "height": 800},
                                             has_touch=True, is_mobile=True, device_scale_factor=2)
    ctx.add_cookies([{"name": "myroad_locale", "value": locale, "url": base}])
    pg = ctx.new_page()
    pg.set_default_timeout(10_000)
    try:
        pg.goto("/login")
        _check(pg, "login", dir_)
        login(pg, log, email=f"mobile-{locale}@example.com")
        pg.goto("/")
        _check(pg, "home", dir_)
        pg.goto(PLACEMENT)
        start = pg.locator(f"form[action='{PLACEMENT}/start'] [type=submit]")
        if start.count():
            start.first.click()
            pg.wait_for_load_state()
        pg.goto(PLACEMENT + "?view=learn")
        _check(pg, "placement", dir_)
        pg.goto(STEP)
        start = pg.locator(f"form[action='{STEP}/start'] [type=submit]")
        if start.count():
            start.first.click()
            pg.wait_for_load_state()
        pg.goto(STEP + "?view=map")
        _check(pg, "map", dir_)
        pg.goto(STEP + "?view=learn")
        _check(pg, "step", dir_)
        if pg.locator("button.choice-tile[value=a]").count():
            pg.locator("button.choice-tile[value=a]").click()
            pg.locator("#step-feedback").wait_for()
            _check(pg, "step-feedback", dir_)
        pg.goto("/settings")
        _check(pg, "settings", dir_)
    finally:
        ctx.close()
