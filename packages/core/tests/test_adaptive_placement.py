"""Adaptive English placement (#211): engine adaptivity, stop rule, scores, weights, API, variants."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

pytest.importorskip("fastapi")
pytest.importorskip("catsim")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code
from test_english_bagrut_flow import _mini

from myroad_core import placement_cat as cat
from myroad_core.content.loader import content_to_path_version, load_content_paths
from myroad_core.content.schema import validate_content_path
from myroad_core.content.variants import select_variants
from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

PLACE = "path_english_bagrut5_00_placement"
ZERO = "path_english_bagrut5_01_zero"
H = {"X-MyRoad-Request": "1"}
DOMAINS = ("vocabulary", "grammar", "reading", "listening")
DIFFS = (-2.0, -1.0, 0.0, 1.0, 2.0)


def _item(nid, area, diff, **extra):
    n = {
        "id": nid, "type": "practice", "title": nid, "body_he": "בחרו.", "body_content": "I ___ here.",
        "choices": [{"id": "a", "label": "am"}, {"id": "b", "label": "is"}],
        "correct": "a", "feedback_ok": "נכון.", "feedback_try": "עוד ניסיון.",
    }
    if area:
        n["area"] = area
    if diff is not None:
        n["difficulty"] = diff
    n.update(extra)
    return n


def _placement_doc(*, untagged: set[str] = frozenset()) -> dict:
    doc = _mini(PLACE, "מבדק רמה", [])
    nodes = [{"id": "intro", "type": "learn", "title": "פתיחה", "body_he": "מבדק קצר."}]
    for d in DOMAINS:
        for k, b in enumerate(DIFFS):
            nid = f"{d}_{k}"
            if d == "listening":
                nodes.append(_item(nid, None if nid in untagged else d, b, speak_text="I am here."))
                nodes.append(_item(f"{nid}_txt", None, None, body_content="Text: I am here.",
                                   variant_of=nid, variant_when={"audio": False}))
            else:
                nodes.append(_item(nid, None if nid in untagged else d, b))
    nodes.append({"id": "end", "type": "celebrate", "title": "סוף", "body_he": "סיום."})
    doc["nodes"] = nodes
    doc["topics"] = [{"id": "t0", "titles": {"he": "מבדק"}, "emoji": "א", "node_ids": [n["id"] for n in nodes]}]
    return doc


def _items(settings=None) -> list[cat.Item]:
    pv = content_to_path_version(validate_content_path(_placement_doc()))
    doc = pv.model_dump(mode="json", by_alias=True)
    return cat.items_from_doc(select_variants(doc, settings or {"audio": True}))


def _simulate(items, answer) -> list[tuple[cat.Item, bool]]:
    responses: list[tuple[str, bool]] = []
    served = []
    while True:
        nxt = cat.next_item(items, responses)
        if nxt is None:
            return served
        ok = answer(nxt)
        responses.append((nxt.block_id, ok))
        served.append((nxt, ok))


def _assert_edge(items, served, *, hardest):
    """After a correct (miss), the next item is harder (easier) than the last one, unless its
    domain has no harder (easier) item left; then it is the hardest (easiest) left there."""
    used: set[str] = set()
    for k, (it, _) in enumerate(served):
        if k:
            last = served[k - 1][0]
            left = [o.b for o in items if o.domain == it.domain and o.block_id not in used]
            if hardest:
                assert it.b > last.b or (max(left) <= last.b and it.b == max(left)), (k, it, last)
            else:
                assert it.b < last.b or (min(left) >= last.b and it.b == min(left)), (k, it, last)
        used.add(it.block_id)


def _resp(served):
    return [(it.block_id, ok) for it, ok in served]


# --- engine ------------------------------------------------------------------------------


def test_all_correct_harder_each_time_and_top_level():
    items = _items()
    served = _simulate(items, lambda it: True)
    bs = [it.b for it, _ in served]
    # Harder after every first-try correct while a harder item is left in the tested domains.
    assert bs[1] > bs[0]
    _assert_edge(items, served, hardest=True)
    s = cat.summarize(items, _resp(served))
    assert {d["level"] for d in s["domains"]} == {5}
    assert all(d["score"] == 100 for d in s["domains"]) and s["overall"] == 100


def test_all_wrong_easier_and_lowest_level():
    items = _items()
    served = _simulate(items, lambda it: False)
    bs = [it.b for it, _ in served]
    assert bs[1] < bs[0]
    _assert_edge(items, served, hardest=False)
    hard = [it.b for it, _ in _simulate(items, lambda it: True)]
    assert sum(hard) / len(hard) > sum(bs) / len(bs) + 2
    s = cat.summarize(items, _resp(served))
    assert {d["level"] for d in s["domains"]} == {1}
    assert all(d["score"] == 0 for d in s["domains"]) and s["overall"] == 0


def test_next_item_direction_after_one_answer():
    items = _items()
    first = cat.next_item(items, [])
    after_ok = cat.next_item(items, [(first.block_id, True)])
    after_miss = cat.next_item(items, [(first.block_id, False)])
    assert after_ok.b > first.b and after_miss.b < first.b


def test_stops_by_15_and_covers_every_domain_twice():
    items = _items()
    for policy in (lambda it: True, lambda it: False, lambda it: it.order % 2 == 0, lambda it: it.b < 0.5):
        served = _simulate(items, policy)
        assert 2 * len(DOMAINS) <= len(served) <= cat.MAX_ITEMS
        counts = {d: sum(1 for it, _ in served if it.domain == d) for d in DOMAINS}
        assert min(counts.values()) >= 2, counts


def test_mixed_strong_grammar_weak_listening_weights():
    items = _items()
    served = _simulate(items, lambda it: it.domain != "listening")
    s = cat.summarize(items, _resp(served))
    w = s["weights"]
    assert w["listening"] > w["grammar"]
    assert abs(sum(w.values()) - 1) < 1e-9
    by = {d["id"]: d for d in s["domains"]}
    assert by["grammar"]["score"] > by["listening"]["score"]
    assert by["grammar"]["level"] > by["listening"]["level"]


def test_audio_off_serves_text_variant_with_listening_area():
    on = {it.node_id: it for it in _items({"audio": True})}
    off = _items({"audio": False})
    listening = [it for it in off if it.domain == "listening"]
    assert len(listening) == len(DIFFS)
    assert {it.node_id for it in listening} == {f"listening_{k}" for k in range(len(DIFFS))}
    assert all(on[it.node_id].block_id == it.block_id and on[it.node_id].b == it.b for it in listening)


# --- content validation --------------------------------------------------------------------


def test_partial_area_tags_are_a_validation_error():
    with pytest.raises(ValidationError, match="items without area"):
        validate_content_path(_placement_doc(untagged={"grammar_1"}))


def test_bad_area_or_difficulty_rejected():
    doc = _placement_doc()
    doc["nodes"][1]["area"] = "Has Space"
    with pytest.raises(ValidationError):
        validate_content_path(doc)
    doc = _placement_doc()
    doc["nodes"][1]["difficulty"] = 9
    with pytest.raises(ValidationError):
        validate_content_path(doc)


def test_report_real_placement_items_missing_area():
    """Content report: which placement items still lack ``area`` (fallback = topic id)."""
    paths = [p for p in load_content_paths() if cat.is_placement_id(p.id)]
    if not paths:
        pytest.skip("no content")
    for p in paths:
        missing = cat.untagged_placement_items(p.nodes)
        print(f"{p.id}: untagged placement items: {missing}")
        scored = [n for n in p.nodes if n.type in ("practice", "check") and n.choices and not n.variant_of]
        assert not missing or len(missing) == len(scored)


# --- app flow ------------------------------------------------------------------------------


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MYROAD_ANALYTICS", "1")
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in (_placement_doc(), _mini(ZERO, "מאפס", [PLACE])):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "a.db"))
    app = create_learner_app(store=store, seed=False, seed_content=True)
    c = TestClient(app)
    login_with_code(c, {"first_name": "Noa", "last_name": "B", "email": "p211@example.com", "next": "/"})
    yield c, store
    store.close()


def _current(c) -> tuple[dict, dict]:
    sess = c.app.state.play_sessions[c.cookies.get("myroad_play")]
    doc = c.app.state.store.get_version(PLACE, sess["versionId"]).model_dump(mode="json", by_alias=True)
    doc = select_variants(doc, c.app.state.store.get_step_settings(sess["userId"]))
    return sess, doc["blocks"][sess["index"]]


def _play(c, strong) -> list[tuple[dict, bool]]:
    """Play the placement in the app: wrong first (then retry right) where ``strong`` is False."""
    c.post(f"/play/{PLACE}/start", data={"reset": "1"})
    c.post(f"/play/{PLACE}/ack")  # intro
    served = []
    for _ in range(40):
        sess, block = _current(c)
        if sess.get("adaptive_done"):
            break
        kids = block["content"]["kids"]
        ok = strong(kids)
        served.append((kids, ok))
        if not ok:
            c.post(f"/play/{PLACE}/answer", data={"choice": "b"}, follow_redirects=False)
        c.post(f"/play/{PLACE}/answer", data={"choice": "a"}, follow_redirects=False)
    return served


def test_api_shape_after_adaptive_play(env):
    c, store = env
    served = _play(c, lambda k: k.get("area") != "listening")
    assert 2 * len(DOMAINS) <= len(served) <= cat.MAX_ITEMS
    r = c.get("/api/placement/result")
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"band", "recommended_road_id", "gap"} <= set(body)
    assert {d["id"] for d in body["domains"]} == set(DOMAINS)
    for d in body["domains"]:
        assert set(d) == {"id", "level", "score", "items"}
        assert 0 <= d["score"] <= 100 and 1 <= d["level"] <= 5 and d["items"] >= 2
    assert 0 <= body["overall"] <= 100
    assert abs(sum(body["weights"].values()) - 1) < 1e-6
    assert body["weights"]["listening"] > body["weights"]["grammar"]
    # Retries after a miss do not count as correct (first try only, #199).
    listening = next(d for d in body["domains"] if d["id"] == "listening")
    assert listening["score"] == 0


def test_audio_off_listening_text_variant_scored_in_app(env):
    c, store = env
    assert c.post("/api/settings/steps", json={"audio": False}, headers=H).status_code == 200
    served = _play(c, lambda k: True)
    texts = [k for k, _ in served if k.get("area") == "listening"]
    assert texts and all(k["body_content"].startswith("Text:") for k in texts)
    body = c.get("/api/placement/result").json()
    assert next(d for d in body["domains"] if d["id"] == "listening")["items"] >= 2


def test_each_answer_emits_event(env):
    c, store = env
    served = _play(c, lambda k: k.get("area") != "reading")
    evs = [e for e in store.list_analytics_events() if e["type"] == "placement_answer"]
    wrong = sum(1 for _, ok in served if not ok)
    assert len(evs) == len(served) + wrong


def test_post_api_maps_answers_to_domains(env):
    c, _ = env
    answers = [{"questionId": f"{d}_{k}", "correct": d == "grammar"} for d in DOMAINS for k in range(2)]
    body = c.post("/api/placement/result", json={"answers": answers}, headers=H).json()
    w = body["weights"]
    assert w["vocabulary"] > w["grammar"] and abs(sum(w.values()) - 1) < 1e-6


def test_placement_survives_learner_id_change(env):
    """Guest learners (#210) do not exist yet: a session learner's placement moves with
    adopt_learner_data(old, new), which the guest -> registered step will call."""
    c, store = env
    _play(c, lambda k: True)
    old = store.get_learner_by_email("p211@example.com")["userId"]
    before = c.get("/api/placement/result").json()
    store.upsert_learner("user_new_211", "New")
    store.adopt_learner_data(old, "user_new_211")
    assert store.get_placement_detail("user_new_211", PLACE)["domains"] == before["domains"]
    assert store.get_progress("user_new_211", PLACE)["completedAt"]
